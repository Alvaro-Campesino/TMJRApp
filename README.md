# TMJRApp

App para un bot de Telegram que gestiona la oferta e inscripción a partidas de rol.

El proyecto se compone de dos servicios que se ejecutan juntos en un mismo contenedor:

- **API** (FastAPI + Uvicorn) — expone los endpoints CRUD contra una base de datos Supabase.
- **Bot** (python-telegram-bot / pyTelegramBotAPI) — interactúa con las usuarias por Telegram y consume la API.

---

## Tabla de contenidos

1. [Requisitos y variables de entorno](#requisitos-y-variables-de-entorno)
2. [Docker](#docker)
   - [Dockerfile](#dockerfile)
   - [docker-compose.yml](#docker-composeyml)
3. [Estructura de carpetas y ficheros](#estructura-de-carpetas-y-ficheros)
4. [Descripción por módulo](#descripción-por-módulo)
   - [app/](#app)
   - [bot/](#bot)
   - [scripts/](#scripts)
   - [docs/](#docs)

---

## Requisitos y variables de entorno

- Python 3.12
- Dependencias en `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `python-telegram-bot`  
  *(el código usa además `supabase`, `python-dotenv` y `pyTelegramBotAPI` — conviene añadirlas a `requirements.txt`).*

Variables de entorno esperadas (cargadas con `python-dotenv` desde `.env` en local, o inyectadas por Docker Compose):

| Variable | Uso |
|----------|-----|
| `SUPABASE_SUPAFAST_URL` | URL del proyecto Supabase que usa la API. |
| `SUPABASE_SUPAFAST_KEY` | Clave de servicio/anon de Supabase. |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram. |

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY . /app
COPY . /bot

RUN pip install -r requirements.txt --no-cache-dir

EXPOSE 80

CMD ["sh scripts/deploy-api.sh & sh scripts/deploy-bot.sh"]
```

Qué hace cada línea:

- `FROM python:3.12-slim` — imagen base ligera con Python 3.12.
- `WORKDIR /app` — directorio de trabajo dentro del contenedor.
- `COPY . /app` y `COPY . /bot` — copia el proyecto dos veces, una para la API y otra para el bot (ambos comparten el mismo código).
- `RUN pip install -r requirements.txt --no-cache-dir` — instala las dependencias Python sin cachear wheels.
- `EXPOSE 80` — declara el puerto 80 (el que usa la API).
- `CMD ["sh scripts/deploy-api.sh & sh scripts/deploy-bot.sh"]` — arranca API y bot en paralelo.  
  > ⚠️ Tal como está escrito, el `CMD` en forma *exec* no interpreta `&`; para que funcione hay que usar la forma *shell* (`CMD sh -c "scripts/deploy-api.sh & scripts/deploy-bot.sh"`) o separarlos en dos servicios.

### docker-compose.yml

Define dos servicios que comparten la misma imagen construida desde el `Dockerfile`:

- **api**
  - Publica `8000:80` (la API queda accesible en `http://localhost:8000`).
  - Monta el código del proyecto en `/api`.
  - Recibe `SUPABASE_SUPAFAST_URL` y `SUPABASE_SUPAFAST_KEY`.
- **bot**
  - Monta el código en `/bot`.
  - Recibe `TELEGRAM_BOT_TOKEN`.
  - Declara `depends_on: api` para arrancar después.

Arranque típico:

```bash
docker compose up --build
```

---

## Estructura de carpetas y ficheros

```
TMJRApp/
├── Dockerfile              # Imagen Python 3.12-slim con API + bot
├── docker-compose.yml      # Servicios api y bot
├── requirements.txt        # Dependencias Python
├── pyvenv.cfg              # Config de virtualenv (local)
├── .gitignore
├── README.md
│
├── app/                    # API FastAPI
│   ├── main.py             # Punto de entrada, registra routers
│   ├── dependencies.py     # (vacío) reservado para dependencias FastAPI
│   ├── logger.txt          # Notas / salida de logger
│   ├── comandos cmd        # Notas de arranque en Windows
│   ├── crud/
│   │   ├── __init__.py
│   │   └── usuarias.py     # (vacío) reservado para capa CRUD
│   ├── models/             # Modelos Pydantic
│   │   ├── __init__.py
│   │   ├── aventura.py
│   │   ├── espera.py
│   │   ├── participa.py
│   │   ├── premisa.py
│   │   ├── rol.py
│   │   ├── sesion.py
│   │   └── usuaria.py
│   ├── routers/            # Endpoints FastAPI
│   │   ├── __init__.py
│   │   ├── base.py         # Cliente Supabase y helpers compartidos
│   │   ├── aventuras.py
│   │   ├── esperas.py
│   │   ├── participaciones.py
│   │   ├── premisas.py
│   │   ├── roles.py
│   │   ├── sesiones.py
│   │   └── usuarias.py
│   └── schemas/
│       └── __init__.py     # (vacío) reservado para esquemas
│
├── bot/                    # Bot de Telegram
│   ├── telegrambot.py      # Versión con python-telegram-bot (conversación + inline keyboard)
│   └── telegrambot2.py     # Versión con pyTelegramBotAPI (consume la API)
│
├── scripts/
│   ├── deploy-api.sh       # Arranca uvicorn en :80
│   └── deploy-bot.sh       # Arranca el bot de Telegram
│
└── docs/
    └── comandos cmd        # Notas de arranque en Windows
```

---

## Descripción por módulo

### `app/`

#### `app/main.py`

Punto de entrada de la API. Crea la instancia `FastAPI`, configura el logger de Uvicorn y registra los routers de cada entidad (`usuarias`, `premisas`, `aventuras`, `roles`, `sesiones`, `participaciones`, `esperas`). Si se ejecuta como script, lanza `uvicorn.run`.

> Nota: la guarda `if __name__ == 'main':` tiene una errata — debería ser `'__main__'`.

#### `app/models/`

Modelos Pydantic. Cada entidad tiene una clase principal y una variante `...Update` con todos los campos opcionales para PATCH/updates parciales.

| Fichero | Clases / funciones |
|---------|--------------------|
| `aventura.py` | `Aventura`, `AventuraUpdate` — partida concreta con plazas y estado de inscripción. |
| `espera.py` | `Espera`, `EsperaUpdate` — entrada en lista de espera de una aventura. |
| `participa.py` | `Participa`, `ParticipaUpdate` — relación usuaria-aventura-rol. |
| `premisa.py` | `Premisa`, `PremisaUpdate` — plantilla/idea de partida (título, sistema, descripción, aviso de contenido, master). |
| `rol.py` | `Rol`, `RolUpdate` — catálogo de roles. |
| `sesion.py` | `Sesion`, `SesionUpdate` — sesión concreta dentro de una aventura (número + fecha). |
| `usuaria.py` | `FiltroContenido`, `Usuaria`, `UsuariaUpdate`, y la función `random_user_gender(has_article, is_capital, is_plural)` que devuelve una forma gramatical aleatoria entre femenino, masculino y neutro (`usuaria` / `usuario` / `usuarie`) para los mensajes de respuesta. |

#### `app/routers/`

Endpoints FastAPI. Todos siguen el mismo patrón CRUD sobre Supabase.

**`routers/base.py`** — utilidades compartidas:

- Carga `.env`, crea el cliente `supabase: Client` con `SUPABASE_SUPAFAST_URL` / `SUPABASE_SUPAFAST_KEY`.
- `is_empty(model)` — `True` si la respuesta de Supabase es `None` o `data == []`.
- `get(id, table_name)` — lee una fila por `id`, devuelve `None` si no existe.
- `not_found()` — lanza `HTTPException(404)`.
- `check_exists(id, table_name)` — combina `get` + `not_found`.

**Routers de entidades** (`aventuras.py`, `esperas.py`, `participaciones.py`, `premisas.py`, `roles.py`, `sesiones.py`) siguen todos el mismo esquema:

| Método / ruta | Función | Qué hace |
|---------------|---------|----------|
| `GET /{entidad}` | `leer_...(limit=10, offset=0)` | Lista paginada. |
| `POST /{entidad}/create` | `crear_...(obj)` | Inserta (excluye `id`). |
| `POST /{entidad}/update/{id}` | `editar_...(id, obj)` | Update parcial (`exclude_unset`). |
| `DELETE /{entidad}/delete/{id}` | `borrar_...(id)` | Borra por `id`. |
| `GET /{entidad}/{id}` | `leer_...(id)` | Devuelve la instancia hidratada como modelo. |

> En varios routers, `check_exists` se llama con un solo argumento — falta pasar `table_name`, es un bug conocido.

**`routers/usuarias.py`** — añade sobre el patrón anterior:

- `leer_usuarias` y `leer_usuaria` devuelven solo `id, filtro_contenido, peticion`.
- `crear_usuaria` captura el error `23505` (UNIQUE violation) para informar de `telegram_id` duplicado.
- `GET /usuaria/tgid/{tg}` — `leer_usuaria_by_tgid(tg)` busca por `telegram_id` de Telegram.
- Los mensajes de respuesta (actualizado / borrado) usan `random_user_gender()` para variar el género gramatical.

#### `app/crud/`, `app/schemas/`, `app/dependencies.py`

Ficheros esqueleto vacíos, reservados para:

- Extraer la lógica de acceso a datos a `crud/` (hoy vive en cada router).
- Separar esquemas de entrada/salida en `schemas/`.
- Declarar dependencias FastAPI (`Depends`) comunes en `dependencies.py`.

---

### `bot/`

Hay dos implementaciones del bot, cada una con una librería distinta:

**`bot/telegrambot.py`** (python-telegram-bot, async):

- Carga `TELEGRAM_BOT_TOKEN`.
- Define los estados `MENU, OPTION1, OPTION2` para un `ConversationHandler`.
- `start(update, context)` — muestra un menú con `InlineKeyboardMarkup` de dos opciones.
- `button(update, context)` — gestiona el `callback_query` de los botones inline.
- `cancel(update, context)` — termina la conversación.
- `main()` — construye la `Application`, registra el `ConversationHandler` y lanza `run_polling`.

**`bot/telegrambot2.py`** (pyTelegramBotAPI, síncrono):

- `send_welcome(message)` — handler de `/ini`: mensaje de bienvenida.
- `partidas(message)` — handler de `/partidas`: llama a `routers.sesiones.get_partidas()` y lista las partidas disponibles.
- Arranca con `bot.infinity_polling()`.

---

### `scripts/`

- **`deploy-api.sh`** — `uvicorn main:app --host 0.0.0.0 --port 80 --log-level trace`.
- **`deploy-bot.sh`** — `py bot/telegrambot.py` *(en Linux habría que cambiar `py` por `python`)*.

Ambos los invoca el `CMD` del Dockerfile.

---

### `docs/`

- **`comandos cmd`** — notas de arranque manual en un entorno Windows (activar venv, entrar en `app/`, `uvicorn main:app --reload`). Útil como chuleta local; no forma parte del runtime.
