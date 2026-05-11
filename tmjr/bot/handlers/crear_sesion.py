"""Flujo: crear sesión.

Pasos:
  1. Si la persona no es DM, le pedimos biografía y creamos perfil DM.
  2. Elegir origen de la premisa: mis premisas / almacenadas / crear nueva.
       - Mis premisas → picker de las del DM → CONFIRMAR_JUEGO.
       - Almacenadas → picker de las globales → enlaza al DM → CONFIRMAR_JUEGO.
       - Crear nueva → pide nombre + descripción + selección de juego.
  3. CONFIRMAR_JUEGO: hereda el juego de la premisa elegida y ofrece cambiarlo.
  4. Selección/alta de juego (cuando hace falta).
  5. Pedimos fecha (calendario inline).
  6. Pedimos plazas (1-6).
  7. Pedimos lugar (botones predefinidos o texto libre).
  8. Pedimos nota específica de la sesión (/skip).
  9. Reusamos o creamos la premisa, creamos la sesión y publicamos tarjeta.
"""
from __future__ import annotations

from datetime import date, datetime, time

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.keyboards import (
    calendario,
    confirmar_juego_nuevo,
    confirmar_juego_premisa,
    elegir_nombre_sesion,
    juegos_del_dm,
    picker_hora,
    picker_minutos,
    picker_premisas_sesion,
    submenu_elegir_premisa,
)
from tmjr.bot.publicador import limpiar_tarjetas_pasadas, publicar_sesion
from tmjr.bot.states import CrearSesion
from tmjr.db import async_session_maker
from tmjr.services import campanias as campanias_svc
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc
from tmjr.services import sesiones as sesiones_svc

END = ConversationHandler.END


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada del flujo de crear sesión (o campaña).

    Comprueba que la persona esté registrada y sea DM. Si no es DM, pide
    biografía. Si lo es, muestra el menú de elección de premisa.

    Si el callback es `caja_campania_crear` (o tras "Añadir sesión" desde
    una campaña existente, vía `cscamp_*`), set `modo_campania=True` en
    `user_data` para que el último paso cree también la `Campania`.
    """
    query = update.callback_query
    if query is not None:
        await query.answer()
        # Detectar si venimos del flujo de crear campaña.
        if query.data and query.data == "caja_campania_crear":
            context.user_data["modo_campania"] = True
            context.user_data.pop("campania_existente_id", None)
        # "Añadir sesión a campaña existente" se inyecta vía
        # context.user_data["campania_existente_id"] desde el handler de
        # gestión; ahí mismo NO marca modo_campania (la campaña ya existe).

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None:
            await update.effective_message.reply_text(
                "Primero usa /start para registrarte."
            )
            return END
        context.user_data["persona_id"] = persona.id

        if persona.id_master is None:
            await update.effective_message.reply_text(
                "Aún no eres DM. Cuéntame en una frase tu experiencia "
                "como máster (o /skip)."
            )
            return CrearSesion.DM_BIO

    await _ask_elegir_premisa(update)
    return CrearSesion.ELEGIR_PREMISA


async def dm_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la biografía inicial del DM y crea su perfil; pasa a elegir premisa."""
    bio = update.effective_message.text or ""
    if bio.strip().lower() in {"/skip", ""}:
        bio = None

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        await personas_svc.ensure_dm(session, persona, biografia=bio)

    await update.effective_message.reply_text("✅ Perfil de DM creado.")
    await _ask_elegir_premisa(update)
    return CrearSesion.ELEGIR_PREMISA


# ─────────────────────── elegir premisa ───────────────────────────


async def _ask_elegir_premisa(update: Update) -> None:
    """Pregunta de qué origen quiere usar la premisa."""
    await update.effective_message.reply_text(
        "¿De dónde sale la premisa de esta sesión?",
        reply_markup=submenu_elegir_premisa(),
    )


async def elegir_premisa_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Despacha la elección del menú inicial de premisa.

    - csprem_nueva → flujo clásico (PREMISA_NOMBRE).
    - csprem_mis → picker con las premisas del DM.
    - csprem_almacenadas → picker con las premisas globales que aún no tiene.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "csprem_nueva":
        await query.edit_message_text("Vamos a crear una premisa nueva.")
        await _ask_nombre(update)
        return CrearSesion.PREMISA_NOMBRE

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        if data == "csprem_mis":
            premisas = await premisas_svc.list_premisas_for_dm(
                session, persona.id_master
            )
            vacio_msg = (
                "Aún no tienes premisas. Elige otra opción del menú."
            )
            siguiente = CrearSesion.PICK_PREMISA_PROPIA
        else:  # csprem_almacenadas
            premisas = await premisas_svc.list_premisas_not_in_dm(
                session, persona.id_master
            )
            vacio_msg = (
                "No hay premisas almacenadas disponibles. Elige otra opción."
            )
            siguiente = CrearSesion.PICK_PREMISA_GLOBAL

    if not premisas:
        await query.edit_message_text(vacio_msg)
        await _ask_elegir_premisa(update)
        return CrearSesion.ELEGIR_PREMISA

    await query.edit_message_text(
        "Elige una premisa:",
        reply_markup=picker_premisas_sesion(
            [(p.id, p.nombre) for p in premisas]
        ),
    )
    return siguiente


async def pick_premisa_propia(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """El DM elige una de SUS premisas; la cargamos y mostramos su juego."""
    return await _aceptar_premisa_existente(update, context, enlazar=False)


async def pick_premisa_global(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """El DM elige una premisa almacenada (no suya); la enlazamos al DM."""
    return await _aceptar_premisa_existente(update, context, enlazar=True)


async def _aceptar_premisa_existente(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    enlazar: bool,
) -> int:
    """Carga la premisa elegida, opcionalmente la enlaza al DM y propone el juego.

    Guarda en `user_data`:
      - `premisa_existente_id`: id de la premisa a reusar.
      - `premisa_nombre`: nombre (lo necesitan los siguientes pasos para mostrar).
      - `juego_id`: el juego heredado de la premisa (puede ser None).
    """
    query = update.callback_query
    await query.answer()
    premisa_id = int(query.data.removeprefix("csprempick_"))

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        premisa = await premisas_svc.get_premisa(session, premisa_id)
        if premisa is None:
            await query.edit_message_text("Esa premisa ya no existe.")
            return END

        if enlazar:
            await premisas_svc.link_premisa_to_dm(
                session, id_dm=persona.id_master, id_premisa=premisa.id
            )

        juego = None
        if premisa.id_juego is not None:
            from tmjr.db.models import Juego
            juego = await session.get(Juego, premisa.id_juego)

    context.user_data["premisa_existente_id"] = premisa.id
    context.user_data["premisa_nombre"] = premisa.nombre
    context.user_data["juego_id"] = premisa.id_juego

    await query.edit_message_text(
        f"📜 Premisa: *{premisa.nombre}*", parse_mode="Markdown"
    )

    if juego is not None:
        await update.effective_message.reply_text(
            f"🎮 Juego heredado de la premisa: *{juego.nombre}*",
            parse_mode="Markdown",
            reply_markup=confirmar_juego_premisa(juego.nombre),
        )
        return CrearSesion.CONFIRMAR_JUEGO

    # La premisa no tenía juego asociado: pedimos uno con el flujo normal.
    await update.effective_message.reply_text(
        "Esta premisa no tiene un juego asociado. Vamos a elegir uno."
    )
    return await _ask_juego(update, context)


async def confirmar_juego_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Resuelve la confirmación del juego heredado: continuar o cambiar."""
    query = update.callback_query
    await query.answer()

    if query.data == "csjuego_continuar":
        await query.edit_message_reply_markup(reply_markup=None)
        await _ask_nombre_sesion(
            update.effective_message, context.user_data["premisa_nombre"]
        )
        return CrearSesion.SESION_NOMBRE_PICK

    # csjuego_cambiar
    await query.edit_message_reply_markup(reply_markup=None)
    return await _ask_juego(update, context)


# ─────────────────────────── premisa ──────────────────────────────


async def _ask_nombre(update: Update) -> None:
    await update.effective_message.reply_text(
        "¿Cómo se llama la partida? (título corto, ≤100 caracteres)"
    )


async def premisa_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un título para la premisa no vacío de hasta 100 caracteres."
        )
        return CrearSesion.PREMISA_NOMBRE
    context.user_data["premisa_nombre"] = nombre

    await update.effective_message.reply_text(
        "Descripción breve de la Premisa que estás creando (≤400 caracteres) o /skip si no quieres añadir."
    )
    return CrearSesion.PREMISA_DESC


async def premisa_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    desc = None if raw.strip().lower() in {"/skip", ""} else raw.strip()
    if desc and len(desc) > 400:
        await update.effective_message.reply_text(
            "Demasiado largo (máx. 400). Resúmelo o usa /skip."
        )
        return CrearSesion.PREMISA_DESC
    context.user_data["premisa_desc"] = desc

    return await _ask_juego(update, context)


# ─────────────────────────── juego ────────────────────────────────


async def _ask_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)

    if juegos:
        kb = juegos_del_dm([(j.id, j.nombre) for j in juegos])
        await update.effective_message.reply_text(
            "¿Para qué sistema de rol? Elige uno o añade nuevo:",
            reply_markup=kb,
        )
    else:
        kb = juegos_del_dm([])
        await update.effective_message.reply_text(
            "Aún no tienes juegos en tu lista. Añade el primero:",
            reply_markup=kb,
        )
    return CrearSesion.PREMISA_JUEGO


async def premisa_juego_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "juego_nuevo":
        await query.edit_message_text(
            "Escribe el nombre del juego (p. ej. D&D 5e, Vampiro, Blades in the Dark)."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    # data == "juego_<id>"
    juego_id = int(data.split("_", 1)[1])
    context.user_data["juego_id"] = juego_id

    async with async_session_maker() as session:
        from tmjr.db.models import Juego
        juego = await session.get(Juego, juego_id)
        nombre = juego.nombre if juego else "?"

    await query.edit_message_text(f"Juego: *{nombre}*", parse_mode="Markdown")
    await _ask_nombre_sesion(
        update.effective_message, context.user_data["premisa_nombre"]
    )
    return CrearSesion.SESION_NOMBRE_PICK


# ─────────────────── nuevo juego (subflujo) ───────────────────────


async def nuevo_juego_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    context.user_data["nuevo_juego_nombre"] = nombre
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        existing = await juegos_svc.find_juego_by_name(session, nombre)
        if existing is not None:
            # Ya está en el catálogo global → enlaza al DM (idempotente) y sigue.
            persona = await personas_svc.get_persona(session, persona_id)
            await juegos_svc.add_juego_to_dm(
                session, id_dm=persona.id_master, id_juego=existing.id
            )
            context.user_data["juego_id"] = existing.id
            await update.effective_message.reply_text(
                f"✅ '{existing.nombre}' ya estaba en el catálogo, lo añado a tu lista."
            )
            await _ask_nombre_sesion(
                update.effective_message, context.user_data["premisa_nombre"]
            )
            return CrearSesion.SESION_NOMBRE_PICK

    # No existe → confirmar antes de crear.
    await update.effective_message.reply_text(
        f"'{nombre}' no está en el catálogo global. "
        "¿Lo creo y lo añado a tu lista?",
        reply_markup=confirmar_juego_nuevo(nombre),
    )
    return CrearSesion.CONFIRMAR_NUEVO_JUEGO


async def confirmar_nuevo_juego(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "nuevo_juego_no":
        await query.edit_message_text(
            "Cancelado. Vuelve a escribir el nombre o usa /cancelar."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    # nuevo_juego_ok
    nombre = context.user_data["nuevo_juego_nombre"]
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        juego = await juegos_svc.create_juego(session, nombre=nombre)
        persona = await personas_svc.get_persona(session, persona_id)
        await juegos_svc.add_juego_to_dm(
            session, id_dm=persona.id_master, id_juego=juego.id
        )
    context.user_data["juego_id"] = juego.id

    await query.edit_message_text(f"✅ Creado '{juego.nombre}' en el catálogo.")
    await _ask_nombre_sesion(
        update.effective_message, context.user_data["premisa_nombre"]
    )
    return CrearSesion.SESION_NOMBRE_PICK


# ─────────────────────────── nombre de la sesión ──────────────────


async def _ask_nombre_sesion(message, premisa_nombre: str) -> None:
    """Pregunta si la sesión hereda el nombre de la premisa o usa otro."""
    await message.reply_text(
        "¿Cómo quieres llamar a esta sesión?",
        reply_markup=elegir_nombre_sesion(premisa_nombre),
    )


async def sesion_nombre_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Despacha la elección del nombre de la sesión.

    - csnombre_misma → reusa el nombre de la premisa y pasa a la fecha.
    - csnombre_otro  → pide texto al usuario.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "csnombre_misma":
        context.user_data["sesion_nombre"] = context.user_data["premisa_nombre"]
        await query.edit_message_text(
            f"📌 Nombre de sesión: *{context.user_data['sesion_nombre']}*",
            parse_mode="Markdown",
        )
        await _ask_fecha(update.effective_message)
        return CrearSesion.FECHA

    # csnombre_otro
    await query.edit_message_text(
        "Escribe el nombre que quieras para esta sesión (≤100 caracteres)."
    )
    return CrearSesion.SESION_NOMBRE_OTRO


async def sesion_nombre_otro(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Recibe el nombre alternativo de la sesión y pasa a la fecha."""
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return CrearSesion.SESION_NOMBRE_OTRO

    context.user_data["sesion_nombre"] = nombre
    await _ask_fecha(update.effective_message)
    return CrearSesion.FECHA


# ─────────────────────────── fecha + plazas ───────────────────────


async def _ask_fecha(message) -> None:
    """Envía el calendario inline abierto al mes actual.

    `message` es un `telegram.Message` sobre el que hacer reply_text (el bot
    siempre llega aquí desde un callback o un mensaje, así que
    `update.effective_message` cubre los dos casos).
    """
    today = date.today()
    await message.reply_text(
        "Elige la fecha de la sesión:",
        reply_markup=calendario(today.year, today.month, min_date=today),
    )


async def fecha_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    raw = query.data.removeprefix("cal_nav_")  # "YYYY-MM"
    year, month = (int(x) for x in raw.split("-"))
    await query.edit_message_reply_markup(
        reply_markup=calendario(year, month, min_date=date.today())
    )
    return CrearSesion.FECHA


async def fecha_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recoge la fecha y pasa al picker de hora."""
    query = update.callback_query
    raw = query.data.removeprefix("cal_pick_")  # "YYYY-MM-DD"
    f = date.fromisoformat(raw)
    if f < date.today():
        # Defensa en profundidad: el calendario no muestra estos botones, pero
        # si el callback llega igual no creamos una sesión en el pasado.
        await query.answer(
            "Esa fecha ya pasó. Elige otro día.", show_alert=True
        )
        return CrearSesion.FECHA

    await query.answer()
    # Guardamos solo el día; la hora se concatena en minutos_pick.
    context.user_data["fecha_dia"] = f

    await query.edit_message_text(
        f"📅 Fecha: *{f.isoformat()}*", parse_mode="Markdown"
    )
    await query.message.reply_text(
        "¿A qué hora empieza?",
        reply_markup=picker_hora(),
    )
    return CrearSesion.HORA


async def fecha_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
    return CrearSesion.FECHA


async def hora_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la hora elegida y pasa al picker de minutos."""
    query = update.callback_query
    await query.answer()
    hora = int(query.data.removeprefix("cshora_"))
    context.user_data["hora"] = hora

    await query.edit_message_text(
        f"🕐 Hora: *{hora:02d}:??*", parse_mode="Markdown"
    )
    await query.message.reply_text(
        "¿Y los minutos?",
        reply_markup=picker_minutos(),
    )
    return CrearSesion.MINUTOS


async def minutos_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Combina día + hora + minutos en un datetime y pasa a PLAZAS."""
    query = update.callback_query
    await query.answer()
    minutos = int(query.data.removeprefix("csmin_"))
    hora = context.user_data["hora"]
    dia = context.user_data["fecha_dia"]
    fecha_dt = datetime.combine(dia, time(hour=hora, minute=minutos))
    context.user_data["fecha"] = fecha_dt

    await query.edit_message_text(
        f"📅 Fecha y hora: *{fecha_dt.strftime('%Y-%m-%d %H:%M')}*",
        parse_mode="Markdown",
    )
    await query.message.reply_text("¿Cuántas plazas? (1-6)")
    return CrearSesion.PLAZAS


async def plazas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida el número de plazas y pasa a preguntar por el lugar."""
    raw = (update.effective_message.text or "").strip()
    try:
        n = int(raw)
        assert 1 <= n <= 6
    except (ValueError, AssertionError):
        await update.effective_message.reply_text(
            "Tiene que ser un número entre 1 y 6."
        )
        return CrearSesion.PLAZAS
    context.user_data["plazas"] = n

    await _ask_lugar(update.effective_message)
    return CrearSesion.LUGAR_RESPUESTA


# ─────────────────────────── lugar ────────────────────────────────


_LUGAR_OTRO = "✏️ Escribe otro..."


async def _ask_lugar(message) -> None:
    """Envía el ReplyKeyboard con los lugares predefinidos + opción libre."""
    keyboard = [
        [
            KeyboardButton("🏢 Biblioteca Rafael Azcona"),
            KeyboardButton("📱 Online"),
            KeyboardButton(_LUGAR_OTRO),
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=True
    )
    await message.reply_text(
        "📍 ¿Dónde será la partida?\n"
        "(Pulsa un botón o escribe la ubicación)",
        reply_markup=reply_markup,
    )


async def lugar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el lugar.

    Si el usuario pulsa 'Escribe otro...' pedimos texto libre y volvemos a
    esperar en el mismo estado. En cuanto recibimos un valor válido lo
    guardamos en `user_data["lugar"]` y pasamos a la nota de la sesión.
    """
    lugar_text = (update.effective_message.text or "").strip()

    if lugar_text == _LUGAR_OTRO:
        await update.effective_message.reply_text(
            "Escribe la dirección o lugar:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CrearSesion.LUGAR_RESPUESTA

    context.user_data["lugar"] = lugar_text
    await update.effective_message.reply_text(
        f"📍 Lugar: {lugar_text}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.effective_message.reply_text(
        "¿Quieres añadir una nota específica para *esta* sesión? "
        "(≤400 caracteres, o /skip para usar solo la descripción de la premisa)",
        parse_mode="Markdown",
    )
    return CrearSesion.SESION_DESC


async def sesion_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    if raw.strip().lower() in {"/skip", ""}:
        sesion_desc_text = None
    else:
        if len(raw) > 400:
            await update.effective_message.reply_text(
                "Demasiado largo (máx. 400). Resúmelo o usa /skip."
            )
            return CrearSesion.SESION_DESC
        sesion_desc_text = raw.strip()

    persona_id = context.user_data["persona_id"]
    juego_id = context.user_data.get("juego_id")
    premisa_nombre = context.user_data["premisa_nombre"]
    sesion_nombre = context.user_data.get("sesion_nombre", premisa_nombre)
    premisa_desc_text = context.user_data.get("premisa_desc")
    premisa_existente_id = context.user_data.get("premisa_existente_id")
    lugar = context.user_data.get("lugar")
    n = context.user_data["plazas"]
    modo_campania = context.user_data.get("modo_campania", False)
    campania_existente_id = context.user_data.get("campania_existente_id")

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        if premisa_existente_id is not None:
            # Reusamos una premisa existente (mis premisas / almacenadas).
            premisa = await premisas_svc.get_premisa(session, premisa_existente_id)
        else:
            premisa = await premisas_svc.crear_premisa(
                session,
                nombre=premisa_nombre,
                id_juego=juego_id,
                descripcion=premisa_desc_text,
            )
            # Enlazamos la nueva premisa al DM para que aparezca en 'Mis premisas'.
            await premisas_svc.link_premisa_to_dm(
                session, id_dm=persona.id_master, id_premisa=premisa.id
            )

        # ¿Crear campaña primero (modo crear campaña)?
        id_campania = campania_existente_id
        numero = None
        if modo_campania and id_campania is None:
            campania = await campanias_svc.crear_campania(
                session,
                id_dm=persona.id_master,
                id_premisa=premisa.id,
            )
            id_campania = campania.id
            numero = 1
        elif id_campania is not None:
            numero = await campanias_svc.next_numero(session, id_campania)

        sesion = await sesiones_svc.crear_sesion(
            session,
            id_dm=persona.id_master,
            id_juego=juego_id,
            fecha=context.user_data["fecha"],
            plazas_totales=n,
            nombre=sesion_nombre,
            descripcion=sesion_desc_text,
            lugar=lugar,
            id_premisa=premisa.id,
            id_campania=id_campania,
            numero=numero,
        )

        # Si es una sesión NO-primera de campaña (numero > 1), materializar
        # los PJs fijos en sesion_pj para que se publique con todos ya apuntados.
        if id_campania is not None and (numero or 0) > 1:
            await campanias_svc.materializar_pjs_a_sesion(session, sesion)
        jugadores = []
        try:
            chat_id, thread_id, message_id = await publicar_sesion(
                context.bot, sesion, premisa=premisa, jugadores=jugadores
            )
        except (RuntimeError, TelegramError) as e:
            await update.effective_message.reply_text(
                f"Sesión creada (#{sesion.id}) pero no se pudo publicar: {e}"
            )
            return END

        await sesiones_svc.marcar_publicada(
            session, sesion,
            telegram_chat_id=chat_id,
            telegram_thread_id=thread_id,
            telegram_message_id=message_id,
        )

    if id_campania is not None:
        if numero == 1 and modo_campania:
            await update.effective_message.reply_text(
                f"✅ Campaña creada (#{id_campania}). Sesión #{sesion.id} "
                f"'{sesion_nombre}' publicada en el canal."
            )
        else:
            await update.effective_message.reply_text(
                f"✅ Sesión #{sesion.id} '{sesion_nombre}' (campaña #{id_campania}, "
                f"sesión nº {numero}) publicada. PJs fijos pre-apuntados."
            )
    else:
        await update.effective_message.reply_text(
            f"✅ Sesión #{sesion.id} '{sesion_nombre}' creada y publicada en el canal."
        )

    # Notificar a PJs fijos si es sesión nueva de campaña (no la primera).
    if id_campania is not None and (numero or 0) > 1:
        await _notificar_pjs_fijos_nueva_sesion(
            context.bot, id_campania, sesion, sesion_nombre
        )

    # Limpieza: tarjetas pasadas >24h y user_data del flujo.
    await limpiar_tarjetas_pasadas(context.bot)
    context.user_data.pop("modo_campania", None)
    context.user_data.pop("campania_existente_id", None)
    return END


async def _notificar_pjs_fijos_nueva_sesion(
    bot, id_campania: int, sesion, sesion_nombre: str
) -> None:
    """DM a cada PJ fijo de la campaña avisando de la nueva sesión publicada.

    Best-effort: captura `TelegramError` y loguea sin romper el flujo.
    """
    import logging
    from html import escape
    from telegram.error import TelegramError
    from tmjr.bot.object_links import build_object_link
    from tmjr.db import async_session_maker

    logger = logging.getLogger(__name__)

    async with async_session_maker() as s:
        avisos = await campanias_svc.list_telegram_de_pjs_fijos(s, id_campania)
    if not avisos:
        return
    fecha_str = sesion.fecha.strftime("%Y-%m-%d %H:%M")
    enlace = build_object_link("sesion", sesion.id, sesion_nombre)
    for telegram_id, pj_nombre in avisos:
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"🏰 Hola <b>{escape(pj_nombre)}</b>, hay una nueva sesión "
                    f"de tu campaña: {enlace}\n📅 {fecha_str}\n\n"
                    f"Estás pre-apuntado/a. Si no puedes acudir, pulsa "
                    f"<b>🚪 Borrarme</b> en la tarjeta del canal."
                ),
                parse_mode="HTML",
            )
        except TelegramError as e:
            logger.warning(
                "No pude notificar al PJ fijo (telegram_id=%s): %s",
                telegram_id, e,
            )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _entry,
                pattern=r"^(crear_sesion|caja_sesion_crear|caja_campania_crear)$",
            ),
            CommandHandler("crear_sesion", _entry, filters=filters.ChatType.PRIVATE),
        ],
        states={
            CrearSesion.DM_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dm_bio),
                CommandHandler("skip", dm_bio),
            ],
            CrearSesion.ELEGIR_PREMISA: [
                CallbackQueryHandler(elegir_premisa_pick, pattern=r"^csprem_"),
            ],
            CrearSesion.PICK_PREMISA_PROPIA: [
                CallbackQueryHandler(pick_premisa_propia, pattern=r"^csprempick_\d+$"),
            ],
            CrearSesion.PICK_PREMISA_GLOBAL: [
                CallbackQueryHandler(pick_premisa_global, pattern=r"^csprempick_\d+$"),
            ],
            CrearSesion.CONFIRMAR_JUEGO: [
                CallbackQueryHandler(
                    confirmar_juego_pick, pattern=r"^csjuego_(continuar|cambiar)$"
                ),
            ],
            CrearSesion.PREMISA_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_nombre),
            ],
            CrearSesion.PREMISA_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_desc),
                CommandHandler("skip", premisa_desc),
            ],
            CrearSesion.PREMISA_JUEGO: [
                CallbackQueryHandler(premisa_juego_pick, pattern=r"^juego_"),
            ],
            CrearSesion.NUEVO_JUEGO_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_juego_nombre),
            ],
            CrearSesion.CONFIRMAR_NUEVO_JUEGO: [
                CallbackQueryHandler(
                    confirmar_nuevo_juego, pattern=r"^nuevo_juego_(ok|no)$"
                ),
            ],
            CrearSesion.SESION_NOMBRE_PICK: [
                CallbackQueryHandler(
                    sesion_nombre_pick, pattern=r"^csnombre_(misma|otro)$"
                ),
            ],
            CrearSesion.SESION_NOMBRE_OTRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sesion_nombre_otro),
            ],
            CrearSesion.FECHA: [
                CallbackQueryHandler(fecha_nav, pattern=r"^cal_nav_\d{4}-\d{2}$"),
                CallbackQueryHandler(
                    fecha_pick, pattern=r"^cal_pick_\d{4}-\d{2}-\d{2}$"
                ),
                CallbackQueryHandler(fecha_noop, pattern=r"^cal_noop$"),
            ],
            CrearSesion.HORA: [
                CallbackQueryHandler(hora_pick, pattern=r"^cshora_\d{2}$"),
            ],
            CrearSesion.MINUTOS: [
                CallbackQueryHandler(minutos_pick, pattern=r"^csmin_\d{2}$"),
            ],
            CrearSesion.PLAZAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, plazas),
            ],
            CrearSesion.LUGAR_RESPUESTA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lugar_respuesta),
            ],
            CrearSesion.SESION_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sesion_desc),
                CommandHandler("skip", sesion_desc),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="crear_sesion",
        persistent=False,
    )
