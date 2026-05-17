# TMJRApp

**Versión actual: `1.0.0`** (ver fichero `VERSION` en la raíz).

Bot de Telegram + API para gestionar partidas de rol. Las personas usuarias interactúan por Telegram, el bot crea perfiles de **DM** o **PJ** según necesite, y publica una tarjeta por sesión en un canal donde otras personas se apuntan.

**Toda la app corre en un solo proceso**: FastAPI sirve los endpoints HTTP y, en su mismo `lifespan`, monta `python-telegram-bot` v20+ vía webhook. Postgres es la persistencia (Supabase por defecto, portable a cualquier Postgres con `DATABASE_URL`).

> Para el alcance del MVP actual y la hoja de ruta detallada, ver `CONTEXT.md` (gitignorado).
> Para el modelo de datos, ver `schema.dbml` (fuente de verdad).

---

## Tabla de contenidos

1. [Requisitos](#requisitos)
2. [Variables de entorno](#variables-de-entorno)
3. [Arrancar con docker compose](#arrancar-con-docker-compose)
4. [Scripts de operaciones](#scripts-de-operaciones)
5. [Deploy en QNAP Container Station](#deploy-en-qnap-container-station)
6. [Desarrollo local (modo debug)](#desarrollo-local-modo-debug)
7. [Probar el endpoint `/health`](#probar-el-endpoint-health)
8. [Tests](#tests)
9. [Cómo generar un token de Telegram (BotFather)](#cómo-generar-un-token-de-telegram-botfather)
10. [Estructura del repo](#estructura-del-repo)
11. [Endpoints disponibles](#endpoints-disponibles)
12. [Funcionalidades del bot](#funcionalidades-del-bot)
13. [Seguridad: registro por token y comandos admin](#seguridad-registro-por-token-y-comandos-admin)

---

## Requisitos

- Docker 24+ con `docker compose` v2.
- Para correr tests en local (opcional): Python 3.12 + `pip install -r requirements-dev.txt`.

---

## Variables de entorno

Copia `.env.example` a `.env` y rellena lo que necesites:

```bash
cp .env.example .env
```

| Variable | Obligatoria | Uso |
|---|---|---|
| `DATABASE_URL` | sí | Conexión Postgres async (`postgresql+asyncpg://…`). El default del compose apunta al servicio `db` local. |
| `TELEGRAM_TOKEN` | **no** | Si no se define, la app arranca en **modo API-only** (el endpoint `/telegram/webhook` devuelve 503). Útil para tests sin Telegram. |
| `TELEGRAM_WEBHOOK_URL` | no | URL pública por la que Telegram entrega los `Update`s. Si está vacía, el `lifespan` no llama a `setWebhook`. |
| `TELEGRAM_WEBHOOK_SECRET` | no | Secret token con el que Telegram firma cada llamada (`X-Telegram-Bot-Api-Secret-Token`). |
| `TELEGRAM_WEBHOOK_CERT_FILE` | no | Path **dentro del contenedor** al cert público (PEM) que el lifespan sube a Telegram en `setWebhook`. Necesario solo si usas cert self-signed. Default: `/app/certs/nginx.pem`. |
| `TELEGRAM_CHAT_ID` | no | Canal donde el bot publica las tarjetas de sesión. |
| `TELEGRAM_THREAD_ID` | no | ID del topic dentro del canal (canales en modo foro). |
| `ADMIN_TELEGRAM_IDS` | no | CSV de IDs de Telegram autorizados a usar los comandos admin (`/rotar_token`, `/publicar_pin`). Si está vacía, **nadie** puede ejecutarlos. Ej.: `ADMIN_TELEGRAM_IDS=123456789,987654321`. Ver [Seguridad](#seguridad-registro-por-token-y-comandos-admin). |
| `TOKEN_ROTATION_DAYS` | no | Si está definida (>0), APScheduler rota automáticamente el token de invitación cada N días y refresca el pin del canal. Vacía o ausente → sin rotación automática (el admin la dispara con `/rotar_token`). |
| `APP_ENV`, `LOG_LEVEL` | no | Defaults `dev` / `INFO`. |

---

## Construir la imagen

La versión vive en el fichero `VERSION` en la raíz (`1.0.0` ahora mismo). Para construir la imagen con ese tag:

```bash
bash scripts/build.sh
```

Internamente lee `VERSION` y ejecuta:

```bash
docker build --build-arg VERSION=<tag> -t tmjrapp:<tag> -t tmjrapp:latest .
```

La imagen lleva:
- `LABEL org.opencontainers.image.version=<tag>` (inspeccionable con `docker inspect`).
- `ENV TMJR_VERSION=<tag>` disponible dentro del contenedor.
- El propio fichero `VERSION` copiado a `/app/VERSION`.

La app loguea la versión al arrancar y la expone en `GET /health` → `{"status":"ok","version":"1.0.0"}`.

Para que `docker compose up` levante esa misma imagen, define `TMJR_VERSION=1.0.0` en `.env` (compose hace `image: tmjrapp:${TMJR_VERSION}`).

---

## Arrancar con docker compose

```bash
docker compose up --build
```

Levanta dos servicios:

- `db` — Postgres 16 alpine en `5432` con volumen persistente `tmjr_pgdata`.
- `app` — la app TMJRApp en `8000:80`. En el arranque corre `alembic upgrade head` (script `scripts/start.sh`) y luego lanza `uvicorn`.

### Modo público con reverse proxy (`--profile public`)

Para exponer al exterior, levanta también el servicio `proxy`:

```bash
docker compose --profile public up -d --build
```

Añade un tercer servicio:

- `proxy` — `nginx:1.27-alpine` en `${PROXY_PORT:-8443}:443`. Termina **HTTPS con cert self-signed** y solo deja pasar:
  - `POST /telegram/webhook` → `app:80/telegram/webhook` (el bot)
  - `GET  /health` → `app:80/health` (healthcheck público)
  - cualquier otra → `404` (la API interna `/personas`, `/sesiones`, `/docs` queda oculta).

El cert lo generas con `bash scripts/generate-cert.sh` (ver "Scripts de operaciones"). El `nginx/default.conf` espera encontrarlo en `./certs/nginx.pem` y `./certs/nginx.key`.

Cambia el puerto público con `PROXY_PORT=...`, por ejemplo:

```bash
PROXY_PORT=443 docker compose --profile public up -d
```

> ⚠️ Telegram solo acepta webhooks en puertos **443, 80, 88 o 8443**. Cualquier otro = el `setWebhook` falla.

La primera vez tarda más porque construye la imagen y aplica la migración inicial (`migrations/versions/0001_initial_schema.py`), que crea las 16 tablas del modelo.

Para arrancar contra **Supabase** en vez del Postgres local:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:<pass>@db.<proyecto>.supabase.co:5432/postgres \
docker compose up app
```

(Solo el servicio `app`, sin levantar el `db` local.)

Parar todo:

```bash
docker compose down            # mantiene los datos
docker compose down -v         # tira también el volumen de Postgres
```

Ver logs:

```bash
docker compose logs -f app
```

---

## Scripts de operaciones

Carpeta `scripts/`:

| Script | Qué hace |
|---|---|
| `start.sh` | Entrypoint del contenedor `app`: `alembic upgrade head` + `uvicorn`. |
| `run-dev.sh` | Arranca un entorno de **desarrollo local** (Postgres del compose + uvicorn `--reload` + bot en polling). Modos `api` / `bot` / `full`. Ver "Desarrollo local". |
| `generate-cert.sh` | Genera un cert TLS **self-signed** (`certs/nginx.pem` + `certs/nginx.key`) para que nginx termine HTTPS. CN por defecto: `datacerberus.myqnapcloud.com` (sobreescribible con `CERT_CN=...`). |
| `set-webhook.sh` | Registra el webhook en Telegram subiendo el cert público (necesario para self-signed). Subcomandos: `set` (default), `--info`, `--delete`. |
| `build-compose-env.sh` | Genera un `docker-compose-env.yaml` self-contained (con env vars resueltas + paths del NAS) y lo empaqueta en `tmjr-deploy.tar.gz` para subir a QNAP Container Station. |
| `import_old_db.sh` | Importa los datos de un data dir Postgres antiguo (`postgresql_old/`) a la BD actual. Levanta un Postgres temporal con el data dir antiguo, hace `pg_dump --data-only --column-inserts` y aplica el dump al destino tras `TRUNCATE … CASCADE`. Variables: `TARGET_URL` (libpq URL al destino, default `postgresql://tmjr:tmjr@localhost:5432/tmjr`), `TEMP_PORT` (puerto del Postgres temporal, default 5433). El destino debe tener el schema actual aplicado (`alembic upgrade head`). Tolera columnas añadidas al destino (p.ej. `personas.menu_msg_id`, que queda NULL). |

### Generar cert self-signed

```bash
bash scripts/generate-cert.sh
# → certs/nginx.pem  (público — se monta en nginx Y se sube a Telegram)
# → certs/nginx.key  (privado — solo nginx)
```

Verifica con:
```bash
openssl x509 -in certs/nginx.pem -noout -subject -issuer -dates
```

### Registrar el webhook en Telegram

Una vez la app esté accesible en `TELEGRAM_WEBHOOK_URL` (ver "Deploy en QNAP" abajo):

```bash
bash scripts/set-webhook.sh           # registrar
bash scripts/set-webhook.sh --info    # ver estado
bash scripts/set-webhook.sh --delete  # quitar
```

El script lee `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_URL` y `TELEGRAM_WEBHOOK_SECRET` del `.env`, y sube `certs/nginx.pem` con `setWebhook` para que Telegram acepte el cert self-signed. Si `getWebhookInfo` muestra `"has_custom_certificate": true` y `pending_update_count` baja a 0, el pipe está OK.

> El propio `lifespan` de la app **también intenta** subir el cert al arrancar, leyendo `TELEGRAM_WEBHOOK_CERT_FILE` desde dentro del contenedor. Pero el script da control manual y muestra la respuesta de Telegram explícitamente — útil para diagnóstico.

---

## Deploy en QNAP Container Station

La app está pensada para correr en un QNAP NAS con Container Station. La cadena queda:

```
Telegram ──HTTPS:8443──> Router (port forward) ──> QNAP host
                                                    └─> proxy (nginx, TLS aquí, cert self-signed)
                                                          └─HTTP:80──> app (FastAPI + PTB)
                                                                         └──> db (Postgres)
```

### Flujo de deploy

1. **En tu portátil** — genera el cert (una vez) y el bundle:
   ```bash
   bash scripts/generate-cert.sh
   bash scripts/build-compose-env.sh
   # → tmjr-deploy.tar.gz  (yaml + nginx/default.conf + certs/)
   ```

2. **Construye y sube la imagen** al QNAP. Dos opciones:
   - `docker save tmjrapp:latest | ssh user@qnap "sudo docker load"`
   - O empuja a un registry y haz `docker pull` en el QNAP.

3. **En el QNAP por SSH** — crea las rutas persistentes (vacías):
   ```bash
   sudo mkdir -p /share/VMTemplates/TMJR/postgresql
   sudo mkdir -p /share/VMTemplates/TMJR/nginx
   sudo mkdir -p /share/VMTemplates/TMJR/certs
   ```

4. **Sube el tarball** y desempaqueta:
   ```bash
   tar xzf tmjr-deploy.tar.gz
   mv nginx/default.conf  /share/VMTemplates/TMJR/nginx/default.conf
   mv certs/nginx.pem     /share/VMTemplates/TMJR/certs/nginx.pem
   mv certs/nginx.key     /share/VMTemplates/TMJR/certs/nginx.key
   ```

5. **Container Station** → Crear → Aplicación → importar `docker-compose-env.yaml`.
   Alternativamente por SSH:
   ```bash
   sudo docker compose -f docker-compose-env.yaml up -d
   ```

6. **Verifica** que el proxy contesta el `/health` desde la LAN:
   ```bash
   curl -kv https://192.168.1.120:8443/health
   # Debe ver: subject=CN=datacerberus.myqnapcloud.com (self-signed) y 200
   ```

7. **Registra el webhook** desde tu portátil:
   ```bash
   bash scripts/set-webhook.sh
   bash scripts/set-webhook.sh --info   # confirma "has_custom_certificate": true y pending=0
   ```

### Variables del script `build-compose-env.sh`

Si tus rutas en el QNAP son distintas, sobreescribe las defaults:

```bash
QNAP_POSTGRES_PATH=/share/MiVolumen/postgres \
QNAP_NGINX_CONF=/share/MiVolumen/nginx.conf \
QNAP_CERT_PEM=/share/MiVolumen/cert.pem \
QNAP_CERT_KEY=/share/MiVolumen/cert.key \
bash scripts/build-compose-env.sh
```

### Lo que el script automatiza al generar el yaml de QNAP

- Sustituye `${VAR}` del `docker-compose.yml` por sus valores reales del `.env`.
- Quita el bloque `build:` (la imagen ya está en el QNAP, no hay que reconstruir).
- Quita `profiles: ["public"]` (Container Station no maneja profiles bien).
- Cambia paths relativos `./nginx/default.conf` y `./certs/*.pem|key` por las rutas absolutas del NAS.
- Añade `driver_opts` al volumen Postgres para anclarlo a un path del NAS (en vez del volumen named gestionado por Docker, que vive bajo `/var/lib/docker/`).

Resultado: un yaml único, autocontenido, listo para Container Station.

---

## Desarrollo local (modo debug)

Para iterar sobre el código sin reconstruir el contenedor cada vez. Tres modos según qué quieras tocar:

### Setup (una sola vez)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# edita .env con TELEGRAM_TOKEN (recomendable: bot SEPARADO de prod, ver abajo)
```

### Modos de arranque

```bash
bash scripts/run-dev.sh api      # solo API (uvicorn --reload :8000)
bash scripts/run-dev.sh bot      # solo bot (polling, sin webhook)
bash scripts/run-dev.sh full     # ambos a la vez (logs entrelazados)
```

El script:
- Levanta solo el contenedor `db` (Postgres en `:5432`).
- Aplica migraciones con Alembic.
- Override-a `DATABASE_URL` a `localhost` para que la app local lo alcance.
- Hot-reload: cualquier cambio en `tmjr/` reinicia uvicorn automáticamente.

### Bot en polling vs webhook

El modo dev usa **polling** (`getUpdates`), no webhook. Ventajas:

- No necesitas URL pública, ni nginx, ni cert self-signed.
- No tocas el webhook de QNAP (siempre que uses un bot dev distinto).

⚠️ **Importante**: Telegram solo permite **un modo activo** por bot (webhook o polling). Si arrancas `run-dev.sh bot` con el mismo `TELEGRAM_TOKEN` que tu bot de producción, el devbot **borra el webhook** registrado en QNAP — lo verás en el log: *"tenía webhook en X — lo borro para arrancar polling"*. Para evitar esto:

1. Crea un **segundo bot** en BotFather (`/newbot`), p. ej. `@tmjr_dev_bot`.
2. Pon SU token en `.env` para dev local.
3. Mantén el token de prod solo en el QNAP.

### Debug con breakpoints (PyCharm / VSCode)

#### PyCharm

1. **Run → Edit Configurations → Add new → Python**.
2. Para el bot:
   - Module name: `tmjr.devbot`
   - Working directory: raíz del proyecto.
   - Python interpreter: `.venv/bin/python`.
3. Para la API:
   - Module name: `uvicorn`
   - Parameters: `tmjr.main:app --reload --host 0.0.0.0 --port 8000`
   - Mismo intérprete y working dir.
4. Pon breakpoints en `tmjr/bot/handlers/*.py` o cualquier router → Debug ▶️.
5. Necesitas el contenedor `db` levantado aparte: `docker compose up -d db`.

#### VSCode

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Bot polling (dev)",
      "type": "debugpy",
      "request": "launch",
      "module": "tmjr.devbot",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://tmjr:tmjr@localhost:5432/tmjr"
      }
    },
    {
      "name": "API (uvicorn --reload)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["tmjr.main:app", "--reload", "--port", "8000"],
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://tmjr:tmjr@localhost:5432/tmjr"
      }
    }
  ]
}
```

Acuérdate de levantar `db` antes: `docker compose up -d db`.

### Inspeccionar la BD durante el desarrollo

El Postgres del compose está expuesto en `localhost:5432`. Cualquier cliente vale (DBeaver, TablePlus, `psql`):

```bash
psql postgresql://tmjr:tmjr@localhost:5432/tmjr
# o si solo quieres ver una tabla:
psql -h localhost -U tmjr -d tmjr -c "SELECT * FROM personas;"
```

### Limpiar entre iteraciones

```bash
docker compose down -v   # tira el volumen de Postgres → DB virgen
docker compose up -d db  # vuelve a levantarla
bash scripts/run-dev.sh full
# alembic re-aplica migraciones automáticamente
```

---

## Probar el endpoint `/health`

Una vez `docker compose up` haya terminado de arrancar:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

Si tarda, consulta los logs (`docker compose logs app`). El healthcheck del contenedor también golpea `/health` cada 30 s.

---

## Tests

Hay tres suites:

- **Tests unitarios** (`tests/test_*.py` excepto `test_api_smoke.py`) — corren contra SQLite en memoria, sin Docker, sin Telegram. Es lo que se ejecuta por defecto con `pytest`.
- **Tests e2e** (`tests/e2e/`) — opt-in. Spawnan un Postgres ephemero con `testcontainers`, montan la app con todo su `lifespan` (PTB inicializado de verdad), mockean la API HTTP de Telegram con `respx` y ejercitan los flujos del bot enviando `Update`s simulados a `/telegram/webhook`.
- **Smoke test de integración** (`tests/test_api_smoke.py`) — llama a la app levantada con `docker compose up`. Está excluido del runner por defecto y se ejecuta apuntando explícitamente a su path.

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

> No hace falta `TELEGRAM_TOKEN`: los tests unitarios usan SQLite en memoria y un cliente httpx ASGI que no dispara el lifespan; el smoke test apunta a la app que arranca en modo API-only si el token está vacío.

### Tests unitarios + coverage

```bash
pytest --cov
```

Salida actual: **109 tests** en verde.

Qué se cubre:

| Capa | Test file | Qué valida |
|---|---|---|
| Servicios | `test_services_personas.py` | Idempotencia de `get_or_create_persona`, `ensure_dm`, `ensure_pj`. Persona puede ser DM y PJ a la vez. |
| Servicios | `test_services_sesiones.py` | `crear_sesion`, `apuntar_pj`, `plazas_ocupadas`. Errores `YaApuntadoError`, `SesionLlenaError`, sesión/PJ inexistente. Acompañantes cuentan contra plazas. `add_invitado` / `remove_ultimo_invitado` sobre el contador `sesion_pj.acompanantes`. Renderizado de la tarjeta expande invitados en slots. |
| Servicios | `test_services_tokens.py` | `crear_token` (revoca activos previos), `revocar_activos`, `token_activo`, `validar` (caducados, revocados, inexistentes). |
| API | `test_api_personas.py` | Health, upsert idempotente, 404 en persona inexistente, 422 en validación Pydantic. |
| API | `test_api_sesiones.py` | Crear sesión, validación `plazas_totales ∈ [1,6]`, apuntar 201, 409 al apuntar dos veces, 409 al apuntar a sesión llena, 404 con PJ inexistente. |
| Bot | `test_bot_keyboards.py` | Callbacks de los teclados inline (`crear_sesion`, `apuntar_{id}`, `{prefix}_ok/_no`). |
| Bot | `test_bot_publicador.py` | `publicar_sesion` falla limpio sin `TELEGRAM_CHAT_ID` y, configurado, llama a `bot.send_message` con los kwargs correctos (mock del `Bot`). |

Lo que queda fuera de coverage por diseño (`pyproject.toml [tool.coverage.run] omit`):

- `tmjr/main.py` — bootstrapping del proceso, mejor cubrirlo por integración.
- Bot handlers de conversación (`crear_sesion.py`, `unirse.py`, `start.py`, `bot/app.py`) — son flujos PTB que necesitarían mocks elaborados de `Update`/`Context`; mejor cubiertos por una futura suite e2e.

### Tests e2e (con Docker daemon disponible)

Necesitan acceso a `/var/run/docker.sock` para que `testcontainers` pueda levantar Postgres. **No** necesitan que `docker compose up` esté ya corriendo — la suite spawnea su propia DB ephemera.

```bash
pytest tests/e2e -v
```

Qué cubre:

| Test | Flujo |
|---|---|
| `test_start_crea_persona_en_db` | `/start` inserta una fila en `personas`. |
| `test_start_responde_con_saludo` | El bot responde con un saludo personalizado tras el `/start`. |
| `test_start_idempotente` | Dos `/start` del mismo `telegram_id` no duplican filas. |
| `test_crear_sesion_full_flow_crea_dm_y_publica` | Persona sin DM → bot pide bio → fecha → plazas → crea `dm`, `sesion`, y publica tarjeta en el canal (verificado vía `respx` viendo `sendMessage` al `chat_id` del canal). |
| `test_crear_sesion_fecha_invalida_repregunta` | Fecha mal formateada no avanza el flujo y el bot pide repetir. |
| `test_unirse_full_flow_crea_pj_y_apunta` | Persona sin PJ pulsa `apuntar_{id}` desde el canal → bot pide nombre/desc en DM → crea `pj` y `sesion_pj`. |

Coverage combinada (unit + e2e): **88%**. Para regenerarla:

```bash
coverage erase
pytest --cov --cov-append              # unit
pytest tests/e2e --cov --cov-append    # e2e
coverage report
```

### Smoke test de integración (con Docker compose levantado)

Diferencia con e2e: el smoke test no spawnea contenedores; asume que `docker compose up` ya está corriendo y le pega por HTTP. Útil para validar el deploy real de extremo a extremo.

```bash
docker compose up -d --build
pytest tests/test_api_smoke.py -v
```

Si el contenedor está en otro host/puerto, exporta `TMJR_BASE_URL`:

```bash
TMJR_BASE_URL=http://otra-maquina:8000 pytest tests/test_api_smoke.py
```

---

## Cómo generar un token de Telegram (BotFather)

Una vez quieras **probar el bot de verdad** (no solo la API), necesitas un token. Lo da [@BotFather](https://t.me/BotFather), el bot oficial de Telegram para registrar bots:

1. Abre Telegram (móvil o web) e inicia conversación con **@BotFather**.
2. Envía `/newbot`.
3. BotFather te pide:
   - **Nombre del bot** — el que verán los usuarios (cualquier string razonable).
   - **Username** — tiene que terminar en `bot`, p. ej. `tmjr_dev_bot`. Si está pillado, te pedirá otro.
4. Te devuelve un mensaje con el token, que tiene la pinta:
   ```
   1234567890:AAH1abcDEFghIJKlmNOPQrsTUVwxyz1234567
   ```
5. Pégalo en `.env`:
   ```env
   TELEGRAM_TOKEN=1234567890:AAH1abcDEFghIJKlmNOPQrsTUVwxyz1234567
   ```
6. (Opcional, recomendable) Endurece el bot con BotFather:
   - `/setprivacy` → **Disabled** si quieres que el bot vea todos los mensajes del canal (no solo los que le mencionan).
   - `/setjoingroups` → **Disabled** si solo lo vas a usar en chats privados.

### Cómo obtener `TELEGRAM_WEBHOOK_URL`

No es algo que se "genere" — es la URL pública por la que **Telegram entregará los `Update`s** a tu app. Tiene que cumplir tres requisitos:

- **HTTPS** (Telegram rechaza HTTP plano).
- **Puerto 443, 80, 88 o 8443** (los únicos que Telegram permite).
- **Termina en `/telegram/webhook`** (la ruta que expone esta app).

Tres maneras típicas de conseguirla, ordenadas de menos a más curro:

#### Opción 1 — `ngrok` (desarrollo local, 1 minuto)

[ngrok](https://ngrok.com/) abre un túnel HTTPS desde un dominio público hasta tu `localhost`. Gratis para dev.

```bash
# 1. Instala ngrok y autentica (una sola vez)
#    https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken <tu-token>

# 2. Levanta la app local
docker compose up -d

# 3. Abre el túnel apuntando al puerto 8000 del compose
ngrok http 8000
```

Verás algo como:

```
Forwarding   https://abcd-1234-efgh.ngrok-free.app -> http://localhost:8000
```

Esa URL es la base pública. Tu webhook completo sería:

```env
TELEGRAM_WEBHOOK_URL=https://abcd-1234-efgh.ngrok-free.app/telegram/webhook
```

⚠️ Cada vez que reinicies ngrok (en plan gratuito) la URL cambia y tienes que actualizar `.env` y reiniciar la app.

#### Opción 2 — Cloudflare Tunnel (dev o prod, gratis y URL estable)

[`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) te da una URL `*.trycloudflare.com` efímera o, si tienes un dominio en Cloudflare, una URL fija.

```bash
# URL efímera (no requiere cuenta):
cloudflared tunnel --url http://localhost:8000
# → https://random-words-1234.trycloudflare.com
```

Para URL fija con tu dominio: sigue la guía de "Named tunnels" de Cloudflare; te queda algo como `https://bot.tudominio.com/telegram/webhook`.

#### Opción 3 — VPS con dominio propio (producción)

Despliega el contenedor en un VPS (DigitalOcean, Hetzner, Fly.io…) detrás de un reverse proxy con HTTPS. Las dos rutas más simples:

- **Caddy** (HTTPS automático con Let's Encrypt en una línea):
  ```
  bot.tudominio.com {
      reverse_proxy localhost:8000
  }
  ```
- **Nginx + certbot** — más manual, mismo resultado.
- **Fly.io / Railway** — te dan HTTPS y dominio gratis sin tocar nginx.

Resultado: `TELEGRAM_WEBHOOK_URL=https://bot.tudominio.com/telegram/webhook`.

#### Opción 4 — QNAP NAS con cert self-signed

Este repo trae el setup completo. Ver sección [Deploy en QNAP Container Station](#deploy-en-qnap-container-station). Resumen del flujo:

- nginx (en compose) termina HTTPS con cert self-signed (`scripts/generate-cert.sh`).
- Telegram acepta el self-signed porque le subimos el cert público al hacer `setWebhook` (`scripts/set-webhook.sh`).
- URL queda: `https://<tu-host>.myqnapcloud.com:8443/telegram/webhook`.

#### Genera el secret y rellena `.env`

El secret valida que las requests entrantes vienen de Telegram (verificadas por la cabecera `X-Telegram-Bot-Api-Secret-Token`). Cualquier string aleatorio sirve:

```bash
openssl rand -hex 32
```

```env
TELEGRAM_WEBHOOK_URL=https://<tu-url-publica>/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=<el-secret-generado>
```

Al arrancar la app con esas variables, el `lifespan` intenta hacer `setWebhook` automáticamente. Si usas cert self-signed, también puedes (y a veces debes) registrarlo manualmente con `bash scripts/set-webhook.sh` para tener control y ver la respuesta de Telegram.

#### Verificar que Telegram tiene el webhook bien

```bash
bash scripts/set-webhook.sh --info
# o, equivalente directo:
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo"
```

Esperado:
- `"url": "https://<tu-url>/telegram/webhook"`
- `"has_custom_certificate": true` (si usas self-signed)
- `"pending_update_count": 0`
- `"last_error_message"` ausente.

Si hay errores (cert inválido, 4xx/5xx, secret mal), aparecerán en `last_error_message` con la fecha del último intento. Para borrar el webhook:

```bash
bash scripts/set-webhook.sh --delete
```

### Para el canal donde se publican las sesiones

1. Crea un canal o grupo en Telegram.
2. Añade tu bot como administrador con permisos de "Enviar mensajes".
3. Obtén el `chat_id`:
   - Manda un mensaje al canal.
   - `curl https://api.telegram.org/bot<TELEGRAM_TOKEN>/getUpdates` → busca `chat.id`.
   - Si es un canal de modo foro, también `message_thread_id` del topic donde quieras publicar.
4. Pon en `.env`:
   ```env
   TELEGRAM_CHAT_ID=-100xxxxxxxxxx
   TELEGRAM_THREAD_ID=123          # opcional
   ```

---

## Estructura del repo

```
TMJRApp/
├── tmjr/                       # Paquete único: API + bot
│   ├── main.py                 # FastAPI + lifespan que arranca PTB, aplica migraciones y monta scheduler
│   ├── devbot.py               # Entrypoint dev (polling, sin webhook)
│   ├── config.py               # Settings con pydantic-settings (admin_telegram_ids, token_rotation_days, …)
│   ├── scheduler.py            # APScheduler — job opcional de rotación de token cada N días
│   ├── api/                    # Routers FastAPI (personas, sesiones, juegos, premisas)
│   ├── bot/
│   │   ├── app.py              # build_application() + post_initialize (cachea bot username)
│   │   ├── keyboards.py        # 5 cajas + tarjeta + pickers + submenús dinámicos
│   │   ├── states.py           # IntEnum por ConversationHandler
│   │   ├── publicador.py       # publicar_sesion (HTML), limpiar_tarjetas_pasadas (>24h)
│   │   ├── object_links.py     # Utility deep-links genéricos (registry + URLs)
│   │   ├── object_formatters.py# Formatters HTML para premisa/juego/dm/sesion/campania
│   │   └── handlers/
│   │       ├── start.py            # /start (acepta payloads invitacion_/obj_/apuntar_)
│   │       ├── admin_tokens.py     # /rotar_token y /publicar_pin (admin-only)
│   │       ├── suscripciones.py    # Toggle suscripción + Mis suscripciones + Suscriptores DM
│   │       ├── help.py
│   │       ├── cajas.py            # Dispatcher del ReplyKeyboard
│   │       ├── mi_perfil.py        # Ver y editar perfil persona
│   │       ├── perfil_dm.py        # Crear/Ver/Editar perfil DM + pickers juegos/premisas
│   │       ├── crear_sesion.py     # Crear sesión / crear campaña (modo_campania flag)
│   │       ├── editar_sesion.py    # Editar / borrar sesión (+ notificación a apuntados)
│   │       ├── crear_premisa.py    # Crear premisa
│   │       ├── editar_premisa.py   # Editar premisa
│   │       ├── listar_sesiones.py  # Listar sesiones abiertas (>= hoy)
│   │       ├── listar_premisas.py  # Catálogo de premisas con deep-links
│   │       ├── listar_juegos.py    # Catálogo de juegos con deep-links
│   │       ├── unirse.py           # Apuntarse + auto-fijo si es 1ª de campaña
│   │       ├── desapuntarse.py     # Borrarse de una sesión
│   │       ├── gestionar_campania.py # Listar campañas DM + añadir sesión + gestionar PJs
│   │       ├── info_campania.py    # Botón Info de la caja Campaña
│   │       └── proximamente.py     # Stub para callbacks aún no implementados
│   ├── db/
│   │   ├── models.py           # ORM (~14 tablas)
│   │   └── session.py          # engine/sessionmaker LAZY + reset_db_state() para tests
│   └── services/               # Lógica de dominio
│       ├── personas.py         # Persona/PJ/DM, get_persona_by_dm
│       ├── sesiones.py         # CRUD, apuntar, desapuntar, listar, borrar, update, invitados (acompanantes)
│       ├── premisas.py         # CRUD, link a DM, listar
│       ├── juegos.py           # Catálogo + DM↔juegos
│       ├── campanias.py        # CRUD, PJs fijos, materializar, next_numero
│       ├── tokens.py           # Tokens de invitación rotativos (crear, validar, revocar)
│       ├── app_config.py       # Key/value store en BD (pin_message_id, …)
│       └── suscripciones.py    # Suscripciones Persona↔Premisa + lógica de notificación
├── migrations/versions/        # Alembic (0001 inicial, 0002 sesion campos, 0003 lugar,
│                               #          0004 juegos editorial/biblio/ISBN, 0005 fecha→datetime,
│                               #          0006 pj.id_anfitrion para invitados,
│                               #          0007 drop pj.id_anfitrion,
│                               #          0008 token_invitacion + app_config + personas.registrado_via_token_id)
├── nginx/default.conf          # Config del reverse proxy (TLS termination)
├── certs/                      # nginx.pem + nginx.key (gitignored)
├── scripts/
│   ├── start.sh                # entrypoint del contenedor app
│   ├── run-dev.sh              # arranque dev (api / bot / full)
│   ├── generate-cert.sh        # genera cert self-signed
│   ├── set-webhook.sh          # registra webhook en Telegram con el cert
│   └── build-compose-env.sh    # genera bundle de deploy para QNAP
├── tests/                      # ver sección "Tests"
├── Dockerfile                  # multi-stage builder + runtime
├── docker-compose.yml          # app + db + (profile public) proxy
├── alembic.ini
├── pyproject.toml              # config pytest + coverage
├── schema.dbml                 # fuente de verdad del modelo
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── tmjr-deploy.tar.gz          # bundle generado para QNAP (gitignored)
```

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck del contenedor. |
| `POST` | `/personas` | Upsert idempotente por `telegram_id`. |
| `GET` | `/personas/by-telegram/{telegram_id}` | Lee persona por su ID de Telegram. |
| `POST` | `/personas/{id}/dm` | Crea perfil DM si la persona no lo tiene. |
| `POST` | `/personas/{id}/pj` | Crea perfil PJ si la persona no lo tiene. |
| `POST` | `/sesiones` | Crea sesión (requiere `id_dm`). |
| `GET` | `/sesiones/{id}` | Lee una sesión. |
| `POST` | `/sesiones/{id}/apuntar` | Apunta un PJ a la sesión. |
| `POST` | `/telegram/webhook` | Webhook PTB (valida `X-Telegram-Bot-Api-Secret-Token`). |

Documentación interactiva en `http://localhost:8000/docs` (Swagger UI generado por FastAPI).

---

## Funcionalidades del bot

El bot **solo responde en chats privados** con el usuario. En grupos y canales se ignora cualquier `/comando`. Lo único que el bot publica en el canal de sesiones (`TELEGRAM_CHAT_ID`) son las tarjetas de las sesiones creadas.

### Comandos directos

| Comando | Descripción |
|---|---|
| `/start` | Muestra el menú de cajas si la persona ya está registrada. **Para registrarse por primera vez** requiere payload `invitacion_<token>` (deep-link del pin del canal). Sin payload válido y sin registro previo, el bot pide pulsar el botón del mensaje fijado. También acepta payloads `obj_<kind>_<id>` (ficha de un objeto) y `apuntar_<id>` (intento de apuntarse desde el canal — si no estás registrado, redirige al pin). |
| `/help` | Cómo funciona el bot. |
| `/crear_sesion` | Inicia el flujo de creación de sesión. |
| `/listar_sesiones` | Sesiones abiertas (hoy o futuras) con tarjeta y botón Apuntarse. |
| `/listar_juegos` | Catálogo global de juegos (cada nombre es un deep-link a su ficha). |
| `/crear_premisa` | Inicia el flujo de creación de premisa. |
| `/listar_premisas` | Catálogo global de premisas (links a la ficha y al juego). |
| `/mi_perfil` | Ficha resumen del usuario. |
| `/cancelar` | Aborta cualquier flujo en curso. |

#### Comandos admin (ocultos del menú nativo)

Los comandos `/rotar_token` y `/publicar_pin` están **registrados como handlers** pero **no aparecen en el menú nativo de Telegram** (no se incluyen en `BOT_COMMANDS`). Razón: solo deben usarlos los admins listados en `ADMIN_TELEGRAM_IDS`; cualquier otro usuario recibe `"No autorizado."`. Mostrarlos en el menú global confundiría al resto del grupo. Se invocan tecleándolos a mano en el DM con el bot. Ver [Seguridad](#seguridad-registro-por-token-y-comandos-admin) para el detalle.

#### Visibilidad del menú: el "/" hamburguesa queda vacío

El menú de comandos nativo (lo que sale al pulsar "/" o el botón hamburguesa del cliente) se publica **vacío** en cualquier scope:

- `BotCommandScopeAllPrivateChats` — el listado por defecto en el DM con el bot. **`BOT_COMMANDS` está vacío** intencionadamente; en su lugar, el bot **fija un mensaje en el DM** con botones inline `❓ Ayuda` y `🏠 Inicio` (ver siguiente sección).
- `BotCommandScopeAllGroupChats` — grupos y supergrupos (incl. foros con hilos).
- `BotCommandScopeAllChatAdministrators` — vista de admin en cualquier grupo.
- `BotCommandScopeDefault` — fallback para clientes que no soporten scopes específicos.

El bot **sigue procesando** comandos que se tecleen a mano (`/start`, `/help`, `/cancelar`, `/rotar_token`, `/publicar_pin`), pero ninguno aparece sugerido. La lógica está en `post_initialize` (`tmjr/bot/app.py`); se ejecuta cada vez que el bot arranca, sobrescribiendo cualquier configuración previa de scopes en Telegram (que es persistente por API).

#### Mensaje fijado del menú principal (DM)

Tras cada `/start` exitoso (registro nuevo o login), el bot **fija un mensaje en el DM con la persona** con dos botones inline:

- `❓ Ayuda` → llama al mismo handler que `/help` (callback `menu_help`).
- `🏠 Inicio` → llama al mismo handler que `/start` (callback `menu_start`).

Antes de fijar el nuevo, intenta despinear y borrar el anterior (cuyo `message_id` se guarda en `personas.menu_msg_id`). Best-effort: cualquier fallo de Telegram en el `unpin`/`delete`/`send`/`pin` se loguea como warning y la operación principal sigue. Helper: `tmjr/bot/menu_dm.py:fijar_menu_principal()`.

Razón: con el menú nativo vacío, el usuario necesita una forma visible de acceder a la ayuda y reiniciar el menú de cajas sin recordar comandos. El mensaje fijado siempre está accesible en la cabecera del chat.

### Cajas del menú principal

| Caja | Acciones disponibles |
|---|---|
| 👤 Persona | Ver mi perfil · Editar perfil (cambiar nombre) · Crear/Ver/Editar perfil DM (biografía, añadir juegos, añadir premisas) |
| 🎲 Sesión | **Crear** (solo DM) · **Mis sesiones** (solo DM — sus sesiones futuras con tarjeta + ✏️ Editar) · **Sesiones publicadas** (todas las sesiones abiertas con botones Apuntarse/±1, vista equivalente a `/listar_sesiones`) |
| 📜 Premisa | Crear · Listar · Editar (solo el DM dueño) |
| 🏰 Campaña | Crear · Listar (gestionar PJs fijos, añadir sesión) · Info |
| 🎮 Juegos | Listar |

### Flujo "Crear sesión"

```
DM_BIO (si no eres DM aún)
  → ELEGIR_PREMISA (Mis premisas / Almacenadas / Crear nueva)
    → si reusas: hereda el juego (CONFIRMAR_JUEGO con opción Cambiar)
    → si nueva: PREMISA_NOMBRE → DESC → JUEGO (catálogo del DM o añadir)
  → SESION_NOMBRE_PICK (heredar nombre de premisa o poner otro)
  → FECHA (calendario inline) → HORA (12-23) → MINUTOS (00/15/30/45)
  → PLAZAS (1-10)
  → PLAZAS_MINIMAS (0..plazas, /skip para 0 = sin mínimo)
  → LUGAR (Biblioteca · Online · texto libre)
  → SESION_DESC (/skip o nota)
  → publica tarjeta + notifica al DM si quien crea no es el propio DM
```

### Plazas mínimas y notificación de umbral

Cada sesión tiene un `plazas_minimas` (default 0, máx = `plazas_totales`). Si > 0, la tarjeta muestra "🪑 X plazas (mínimo Y)" y el DM recibe DM cada vez que la **ocupación cruza el umbral**:

- ✅ **Hacia arriba** (`<min → ≥min`): "Tu sesión X ha alcanzado el mínimo de jugadores (Y/Y)." Disparado por `apuntar` o `+1`.
- ⚠️ **Hacia abajo** (`≥min → <min`): "Tu sesión X ha bajado del mínimo de jugadores (Z/Y)." Disparado por `borrarme` o `-1`.

Si `plazas_minimas == 0` no se notifica nunca (el umbral está siempre alcanzado). Best-effort (logged warning si el DM no contesta). Helper en `tmjr/bot/notificaciones.py` + `services.sesiones.cruce_minimo`.

### Tarjeta publicada en el canal

```
Sesión: <título>
🎲 DM: <link al DM>
🎮 Juego: <link al juego>
Premisa: <link a la premisa> (si difiere del título)
Descripción: <override de la sesión>
<descripción de la premisa>

📅 2026-05-15 18:00
📍 <lugar>
🪑 <plazas>
Jugadores apuntados:
1. <PJ>
…

[🙋 Apuntarse] [🚪 Borrarme]
[➕1]          [➖1]
```

Los nombres de DM, Juego y Premisa son **deep-links** a `t.me/<bot>?start=obj_<kind>_<id>`. Al pulsar, Telegram abre el chat privado con el bot y le manda `/start` con el payload, y el bot devuelve la ficha del objeto.

### Notificaciones

Cuando alguien se apunta, el DM recibe un mensaje privado con el nombre del PJ y un deep-link a la sesión. Si el DM nunca habló con el bot (chat not found), se loguea como warning y la inscripción sigue adelante.

### Suscripciones a premisas

En el listado de premisas (`📜 Premisa → Listar` o `/listar_premisas`) cada premisa lleva un botón inline `🔔 Suscribirse` / `🔕 Suscrito ✓` que actúa como **toggle**. La suscripción es a nivel de Persona (no de PJ).

El mismo botón aparece **al abrir la ficha de una premisa por deep-link** (`obj_premisa_<id>`), lo que permite suscribirse navegando desde otros sitios: por ejemplo, desde la ficha de un DM (`obj_dm_<id>`), cada premisa que aparece en su lista es un enlace clickable a su ficha individual — al pulsar, llegas a una vista con todos los campos de la premisa (nombre, juego, descripción, aviso) y el botón de suscripción debajo.

- **Notificación al suscriptor**: cuando se publica una sesión **one-shot** (sin campaña) con esa premisa, o la **primera sesión** de una campaña con esa premisa, los suscritos reciben DM con un deep-link `apuntar_<id>` a la sesión. Las sesiones 2..N de una misma campaña ya no notifican. Sesiones sin premisa nunca notifican. El propio DM se filtra para no auto-notificarse.
- **Notificación al DM**: al crearse la suscripción, todos los DMs que han "usado" esa premisa reciben un DM `"X se ha suscrito a tu premisa Y"`. "Usada" = la premisa está en `dm_premisas` (catálogo del DM) **o** el DM ha publicado al menos una sesión con esa premisa.
- **Borrarse**: `👤 Persona → 🔔 Mis suscripciones` lista las premisas suscritas; cada una con un botón `🚪 Borrarme — <nombre>`.
- **Lado DM**: `👤 Persona → Ver perfil DM → 👥 Suscriptores` muestra las premisas usadas por el DM con conteo de suscriptores (sin exponer identidades).

Todas las notificaciones son **best-effort**: si el destinatario nunca habló con el bot (chat not found) o Telegram falla, se loguea como warning y la operación sigue adelante.

### Invitados sin Telegram (+1 / -1)

Para acompañantes que no tienen cuenta de Telegram, la tarjeta tiene dos botones bajo Apuntarse/Borrarme:

- **➕1**: incrementa el contador `sesion_pj.acompanantes` del PJ del usuario. Requiere que el anfitrión esté ya apuntado a la sesión.
- **➖1**: decrementa el contador. Si está a 0, no hace nada.

Los invitados **no son PJs reales** — son un contador numérico por anfitrión. Al renderizar la tarjeta se expanden inline ocupando un slot cada uno como `"Invitado-<nombre PJ>"` truncado a 20 caracteres, en la posición numérica correspondiente. Cuentan contra `plazas_totales` de la sesión.

### Limpieza automática del canal

Al publicar una sesión nueva, el bot borra del canal cualquier tarjeta cuya `fecha` ya esté en el pasado por más de 24 horas. Best-effort: si Telegram falla al borrar (mensaje ya no existe, etc.), se loguea y se limpian los identificadores en BD igualmente para no reintentar.

Listar sesiones (`/listar_sesiones`) ya filtra solo las futuras (>= hoy 00:00).

### Mis sesiones (vista del DM): nombres de PJ clickables

En `🎲 Sesión → Mis sesiones` cada tarjeta de sesión se renderiza igual que en el canal **excepto** los nombres de los jugadores apuntados: cada PJ real es un deep-link `obj_pj_<id>` que abre su ficha (nombre + descripción si tiene). Los acompañantes sin Telegram (slots `Invitado-X`) no son clickables — no son PJs reales.

En la tarjeta publicada en el canal y en `🎲 Sesión → Sesiones publicadas` los nombres se siguen mostrando como texto plano, por privacidad. La función responsable es `render_tarjeta_sesion_dm_html` (`tmjr/bot/publicador.py`); el resto sigue usando `render_tarjeta_sesion_html`.

### Detección de duplicados al crear juegos / premisas

Para evitar entradas como "Vampire la Mascarada" y "Vampyre la Mascarada" conviviendo en el catálogo, antes de aceptar un nombre nuevo el bot compara contra el catálogo en dos capas:

1. **Normalización** (`tmjr/services/text_match.py:normalizar`): pasa a minúsculas, quita tildes, colapsa espacios y elimina puntuación (excepto `&`). Equipara "D&D 5e" / "D&D  5E" / " d&d 5e ".
2. **Similitud difusa** (`rapidfuzz.fuzz.token_sort_ratio`): para typos y variaciones. Umbral por defecto **80** (configurable como `text_match.SIMILARITY_THRESHOLD`). Devuelve hasta 5 candidatos ordenados por score desc.

Cuando hay candidatos por encima del umbral, el bot muestra un teclado inline con cada candidato (nombre + `%` de similitud) más un botón `➕ Crear igualmente`. Si el usuario pulsa un existente, se reutiliza (y se enlaza al perfil DM si procede). Si pulsa "Crear igualmente", el flujo continúa y se inserta.

Puntos de entrada cableados:
- `crear_premisa.py`: nombre de premisa (estado `CONFIRMAR_DUP_PREMISA`) y nombre de juego nuevo (estado `CONFIRMAR_DUP_JUEGO`).
- `crear_sesion.py`: rama "Crear premisa nueva" (estado `CONFIRMAR_DUP_PREMISA`) y subflujo "Añadir juego nuevo al catálogo" (estado `CONFIRMAR_DUP_JUEGO`).

Servicios públicos: `juegos_svc.buscar_juegos_similares(session, nombre)` y `premisas_svc.buscar_premisas_similares(session, nombre)`. Tests del scorer en `tests/test_services_text_match.py`.

### El nombre del PJ es el de la Persona

La tabla `PJ` **no tiene columna `nombre`**: el nombre que se muestra del PJ es siempre el de la `Persona` enlazada (`Persona.id_pj`). Esto evita la posibilidad de quedar desincronizado y simplifica la edición — basta con cambiar tu nombre en `👤 Persona → Editar perfil` y se refleja automáticamente en todas las tarjetas, listas y notificaciones.

Consecuencias prácticas:
- En el flujo "Apuntarse a sesión", la primera vez que la persona crea un PJ **no se le pregunta el nombre**. Solo se le pide una descripción libre del personaje + **límites de contenido** que necesita (o `/skip`).
- La ficha del PJ (`obj_pj_<id>`) muestra solo nombre + descripción del PJ. **Nunca** se exponen los juegos / premisas de la persona — eso pertenece a su perfil DM y solo se ve desde `obj_dm_<id>`.
- Cuando el DM recibe la notificación "X se ha apuntado a tu sesión", el nombre `X` es un deep-link al `obj_pj_<id>` correspondiente, así puede consultar la descripción y los límites del jugador con un toque.

### Edición por el DM

Las cajas Sesión y Premisa tienen ahora "Editar". Solo el DM dueño puede editar:

- **Sesión** (solo futuras): nombre, descripción, lugar, fecha y hora, plazas (1-10), plazas mínimas (0..plazas). Las plazas no pueden bajar por debajo de los apuntados, y el mínimo nunca puede ser mayor que el total. Tras guardar, si la tarjeta está publicada en el canal se actualiza automáticamente. Además, opción 🗑 **Borrar sesión** con confirmación: borra la sesión y su tarjeta del canal y notifica por DM a todos los apuntados.
- **Premisa**: nombre, descripción, aviso de contenido, juego asociado (con opción de añadir uno nuevo al catálogo).

### Campañas

Una **campaña** agrupa varias sesiones bajo una misma premisa con un grupo fijo de PJs.

- **Crear**: 🏰 Campaña → Crear. Eliges (o creas) la premisa y a continuación configuras la **primera sesión** (mismo flujo de crear sesión). La sesión se publica como tarjeta en el canal con la línea `🏰 Campaña: <link>`.
- **PJs fijos**: quienes pulsan 🙋 Apuntarse en la **primera sesión** quedan automáticamente como fijos. Para añadir o eliminar manualmente: 🏰 Campaña → Listar → elige campaña → 👥 Gestionar PJs.
- **Nuevas sesiones**: 🏰 Campaña → Listar → elige campaña → ➕ Añadir sesión → usa `/crear_sesion`. La sesión queda asociada a la campaña con número autoincrementado. Los PJs fijos quedan **pre-apuntados** y reciben un DM con deep-link a la sesión. Si alguno no puede acudir, pulsa 🚪 Borrarme en la tarjeta — solo se borra de esa sesión, sigue siendo fijo.
- **Eliminar PJ**: lo quita de los fijos y de las sesiones **futuras** (las pasadas se conservan como histórico).
- **Info**: 🏰 Campaña → Info muestra una explicación rápida del funcionamiento.

---

## Seguridad: registro por token y comandos admin

El bot publica tarjetas en `TELEGRAM_CHAT_ID` (un canal/grupo). Para evitar que **cualquiera** que escriba al bot por privado pueda registrarse y empezar a apuntarse a sesiones, el alta de personas está gobernada por un **token de invitación rotativo** publicado en un mensaje fijado dentro del canal.

### Flujo de registro de una persona nueva

1. El admin publica (una vez, con `/publicar_pin`) un mensaje fijado en el canal con un botón "🔑 Unirme al bot".
2. Ese botón es un deep-link `https://t.me/<bot>?start=invitacion_<token>` al token activo.
3. Un miembro del canal lo pulsa → Telegram abre chat privado con el bot y envía `/start invitacion_<token>`.
4. El bot valida el token (que esté activo y no caducado) y registra a la persona, persistiendo el `id` del token en `personas.registrado_via_token_id` (auditoría).
5. A partir de aquí la persona ya puede usar todas las funciones normales (apuntarse a sesiones, crear DM, etc.).

Si alguien escribe `/start` al bot **sin token** y no está registrado, el bot le contesta indicando que pulse el botón del mensaje fijado del canal. Los botones "🙋 Apuntarse" y "➕1/➖1" de las tarjetas también redirigen al pin si quien los pulsa no está aún registrado.

### Rotación del token

Hay dos formas de rotar el token (revoca el activo y emite uno nuevo):

- **Manual**: el admin envía `/rotar_token` por privado. El bot intenta editar el `reply_markup` del pin existente para que su botón apunte al token nuevo (no se vuelve a fijar nada).
- **Automática**: si `TOKEN_ROTATION_DAYS` está definida, APScheduler ejecuta `_job_rotar_token` cada N días al arrancar el lifespan. El job hace exactamente lo mismo que `/rotar_token`. Sin la variable, el scheduler no se arranca.

Rotar **no invalida a los usuarios ya registrados** — solo invalida deep-links con tokens antiguos. Es decir, el token solo se usa para alta inicial.

### Comandos admin (whitelist `ADMIN_TELEGRAM_IDS`)

| Comando | Qué hace |
|---|---|
| `/publicar_pin` | Crea un token si no hay activo, envía un mensaje al canal con el botón `🔑 Unirme al bot` (deep-link al token activo) y lo fija. Guarda el `message_id` en la tabla `app_config` (clave `pin_message_id`) para futuras ediciones. Si ya existe un pin previo, lo despina antes (best-effort). |
| `/rotar_token` | Genera un nuevo token (revoca el anterior), responde al admin con el nuevo deep-link y, si existe un `pin_message_id` guardado, edita el botón de ese pin para que apunte al token nuevo. |

**Whitelist**: ambos comandos comprueban que `update.effective_user.id ∈ ADMIN_TELEGRAM_IDS` (CSV en `.env`). Si no, responden `"No autorizado."` y cortan. Con la lista vacía nadie puede ejecutarlos — recuerda añadir tu ID antes del primer deploy.

**Ocultos del menú nativo**: estos dos comandos **no aparecen** en la lista de `BOT_COMMANDS` registrada vía `set_my_commands`, por lo que no salen sugeridos al resto del grupo cuando escriben "/" en el chat con el bot. Para usarlos, el admin los teclea a mano en el DM. Si en algún momento quieres cambiar esto y mostrarlos solo a admins concretos, Telegram admite `BotCommandScopeChat` por usuario — pero hoy no está cableado.

### Configuración mínima para activar el sistema

En `.env`:

```env
TELEGRAM_CHAT_ID=-100xxxxxxxxxx       # ya lo tenías
ADMIN_TELEGRAM_IDS=123456789          # tu Telegram ID (el de BotFather con /id, o /start a @userinfobot)
TOKEN_ROTATION_DAYS=30                # opcional — rotación cada 30 días; omite para rotación solo manual
```

Primera vez tras desplegar (bootstrap del propio admin):

1. Habla con el bot por privado y manda `/publicar_pin`. `/publicar_pin` **solo comprueba la whitelist de admins**, no exige que ya estés registrado, así que funciona aunque sea la primera invocación absoluta. Si no había token activo, lo crea sobre la marcha y fija el mensaje en el canal con el botón de invitación.
2. Pulsa tú mismo el botón **🔑 Unirme al bot** del pin (o teclea `/start invitacion_<token>` con el token que el bot te devolvió en el paso anterior). Ahora estás registrado.
3. Comparte el canal con quien quieras invitar; pulsan el botón → se registran.

> Si pierdes el botón del pin (por ejemplo, despinaste el mensaje a mano), vuelve a lanzar `/publicar_pin` — borra el pin anterior y publica uno nuevo.
