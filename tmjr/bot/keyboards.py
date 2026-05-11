import calendar
from datetime import date

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ─────────────────────── ReplyKeyboard persistente ────────────────────────


CAJA_PERSONA = "👤 Persona"
CAJA_SESION = "🎲 Sesión"
CAJA_PREMISA = "📜 Premisa"
CAJA_CAMPANIA = "🏰 Campaña"
CAJA_JUEGOS = "🎮 Juegos"

CAJAS = (CAJA_PERSONA, CAJA_SESION, CAJA_PREMISA, CAJA_CAMPANIA, CAJA_JUEGOS)


def menu_cajas() -> ReplyKeyboardMarkup:
    """ReplyKeyboard persistente con las 5 cajas de objetos."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(CAJA_PERSONA), KeyboardButton(CAJA_SESION)],
            [KeyboardButton(CAJA_PREMISA), KeyboardButton(CAJA_CAMPANIA)],
            [KeyboardButton(CAJA_JUEGOS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ─────────────────────── Submenú inline por objeto ────────────────────────
# Cada acción es (label, action, disponible).
# El callback que se emite es `caja_<obj>_<action>`.

_SUBMENUS: dict[str, list[tuple[str, str, bool]]] = {
    "sesion":   [("Crear", "crear", True),  ("Listar", "listar", True),  ("Editar", "editar", True)],
    "premisa":  [("Crear", "crear", True),  ("Listar", "listar", True),  ("Editar", "editar", True)],
    "campania": [("Crear", "crear", True),  ("Listar", "listar", True),  ("ℹ️ Info", "info", True)],
    "juegos":   [("Listar", "listar", True), ("Crear", "crear", False), ("Editar", "editar", False)],
}


def submenu_objeto(obj: str) -> InlineKeyboardMarkup:
    """Submenú con Crear / Listar / Editar para el objeto. Marca 🚧 las no disponibles."""
    rows = []
    for label, action, disponible in _SUBMENUS[obj]:
        text = label if disponible else f"{label} 🚧"
        rows.append(
            [InlineKeyboardButton(text, callback_data=f"caja_{obj}_{action}")]
        )
    return InlineKeyboardMarkup(rows)


def submenu_persona(es_dm: bool) -> InlineKeyboardMarkup:
    """Submenú dinámico de la caja Persona, en cuadrícula 2 columnas.

    - Siempre: 'Ver mi perfil' y 'Editar perfil' (cambiar nombre) en la
      primera fila.
    - Si la persona no es DM: segunda fila con 'Crear perfil DM'.
    - Si ya es DM: segunda fila con 'Ver perfil DM' y 'Editar perfil DM'.

    Sigue el patrón de callbacks `caja_persona_<accion>`.
    """
    rows = [
        [
            InlineKeyboardButton("Ver mi perfil", callback_data="caja_persona_ver"),
            InlineKeyboardButton("Editar perfil", callback_data="caja_persona_editar"),
        ],
    ]
    if es_dm:
        rows.append([
            InlineKeyboardButton(
                "Ver perfil DM", callback_data="caja_persona_ver_dm"
            ),
            InlineKeyboardButton(
                "Editar perfil DM", callback_data="caja_persona_editar_dm"
            ),
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                "Crear perfil DM", callback_data="caja_persona_crear_dm"
            ),
        ])
    return InlineKeyboardMarkup(rows)


def vista_perfil_dm() -> InlineKeyboardMarkup:
    """Botones para ver el listado de juegos / premisas del DM."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "📜 Mis premisas", callback_data="caja_persona_ver_dm_premisas"
            )],
            [InlineKeyboardButton(
                "🎮 Mis juegos", callback_data="caja_persona_ver_dm_juegos"
            )],
        ]
    )


def submenu_editar_dm() -> InlineKeyboardMarkup:
    """Submenú de edición del perfil DM: biografía / añadir juego / añadir premisa."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "Editar biografía", callback_data="caja_persona_editar_dm_bio"
            )],
            [InlineKeyboardButton(
                "Añadir juego", callback_data="caja_persona_editar_dm_juego"
            )],
            [InlineKeyboardButton(
                "Añadir premisa", callback_data="caja_persona_editar_dm_premisa"
            )],
        ]
    )


def picker_juegos_para_dm(
    juegos: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """Picker de juegos disponibles para añadir al DM.

    Callbacks: `dm_add_juego_<id>` por entrada, más `dm_picker_done` para cerrar.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"dm_add_juego_{jid}")]
        for jid, nombre in juegos
    ]
    rows.append([InlineKeyboardButton("✅ Hecho", callback_data="dm_picker_done")])
    return InlineKeyboardMarkup(rows)


def picker_premisas_para_dm(
    premisas: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """Picker de premisas disponibles para añadir al DM.

    Callbacks: `dm_add_premisa_<id>` por entrada, más `dm_picker_done` para cerrar.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"dm_add_premisa_{pid}")]
        for pid, nombre in premisas
    ]
    rows.append([InlineKeyboardButton("✅ Hecho", callback_data="dm_picker_done")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────── Inline keyboards específicos ─────────────────────


def tarjeta_sesion(sesion_id: int) -> InlineKeyboardMarkup:
    """Botones de la tarjeta publicada en el canal.

    Fila 1: 🙋 Apuntarse · 🚪 Borrarme (mí mismo).
    Fila 2: ➕1 · ➖1     (invitados sin Telegram, ligados al anfitrión).
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🙋 Apuntarse", callback_data=f"apuntar_{sesion_id}"
                ),
                InlineKeyboardButton(
                    "🚪 Borrarme", callback_data=f"desapuntar_{sesion_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕1", callback_data=f"mas1_{sesion_id}"
                ),
                InlineKeyboardButton(
                    "➖1", callback_data=f"menos1_{sesion_id}"
                ),
            ],
        ]
    )


def confirmar_cancelar(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"{prefix}_ok"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"{prefix}_no"),
            ]
        ]
    )


def juegos_del_dm(juegos: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Teclado con los juegos del DM + opción 'Añadir nuevo'.

    `juegos`: lista de tuples (id, nombre).
    Callbacks: `juego_<id>` para los existentes, `juego_nuevo` para añadir.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"juego_{jid}")]
        for jid, nombre in juegos
    ]
    rows.append([InlineKeyboardButton("➕ Añadir nuevo", callback_data="juego_nuevo")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────── Calendario inline ────────────────────────
# Callbacks emitidos:
#   cal_nav_YYYY-MM     → navegar a otro mes (edita el reply_markup)
#   cal_pick_YYYY-MM-DD → fecha elegida
#   cal_noop            → celdas vacías o deshabilitadas


_MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
_DIAS_ES = ["L", "M", "X", "J", "V", "S", "D"]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def calendario(
    year: int,
    month: int,
    *,
    min_date: date | None = None,
) -> InlineKeyboardMarkup:
    """Calendario inline para elegir una fecha del mes (year, month).

    `min_date` deshabilita días previos y la flecha de mes anterior cuando ya
    no quedan días seleccionables ahí.
    """
    rows: list[list[InlineKeyboardButton]] = []

    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, +1)
    last_day_prev = calendar.monthrange(prev_y, prev_m)[1]
    can_go_back = min_date is None or date(prev_y, prev_m, last_day_prev) >= min_date
    rows.append([
        InlineKeyboardButton(
            "‹" if can_go_back else " ",
            callback_data=(
                f"cal_nav_{prev_y:04d}-{prev_m:02d}" if can_go_back else "cal_noop"
            ),
        ),
        InlineKeyboardButton(
            f"{_MESES_ES[month - 1]} {year}", callback_data="cal_noop"
        ),
        InlineKeyboardButton(
            "›", callback_data=f"cal_nav_{next_y:04d}-{next_m:02d}"
        ),
    ])

    rows.append([InlineKeyboardButton(d, callback_data="cal_noop") for d in _DIAS_ES])

    for week in calendar.monthcalendar(year, month):  # firstweekday=0 (lunes)
        fila: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                fila.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
                continue
            d = date(year, month, day)
            if min_date is not None and d < min_date:
                fila.append(InlineKeyboardButton("·", callback_data="cal_noop"))
            else:
                fila.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=f"cal_pick_{year:04d}-{month:02d}-{day:02d}",
                    )
                )
        rows.append(fila)

    return InlineKeyboardMarkup(rows)


def picker_campanias_dm(
    campanias: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """Picker de campañas del DM. Callbacks: `cmppick_<id>`."""
    rows = [
        [InlineKeyboardButton(label, callback_data=f"cmppick_{cid}")]
        for cid, label in campanias
    ]
    return InlineKeyboardMarkup(rows)


def submenu_gestionar_campania() -> InlineKeyboardMarkup:
    """Submenú al elegir una campaña: añadir sesión / gestionar PJs / info."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "➕ Añadir sesión", callback_data="cmpacc_addsesion"
            )],
            [InlineKeyboardButton(
                "👥 Gestionar PJs", callback_data="cmpacc_pjs"
            )],
            [InlineKeyboardButton(
                "ℹ️ Ver info", callback_data="cmpacc_info"
            )],
        ]
    )


def submenu_gestionar_pjs() -> InlineKeyboardMarkup:
    """Submenú gestión de PJs: añadir / eliminar."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "➕ Añadir PJ", callback_data="cmppj_add"
            )],
            [InlineKeyboardButton(
                "➖ Eliminar PJ", callback_data="cmppj_rm"
            )],
        ]
    )


def picker_pjs(
    pjs: list[tuple[int, str]], *, prefix: str
) -> InlineKeyboardMarkup:
    """Picker genérico de PJs con prefijo configurable.

    Callbacks: `<prefix>_<pj_id>`.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"{prefix}_{pid}")]
        for pid, nombre in pjs
    ]
    return InlineKeyboardMarkup(rows)


def picker_sesiones_dm(
    sesiones: list[tuple[int, str, str]],
) -> InlineKeyboardMarkup:
    """Picker de sesiones del DM para editar.

    `sesiones`: lista de (id, label_visible, fecha_str). Callbacks:
    `edsespick_<id>`.
    """
    rows = [
        [InlineKeyboardButton(
            f"{label} — {fecha}", callback_data=f"edsespick_{sid}"
        )]
        for sid, label, fecha in sesiones
    ]
    return InlineKeyboardMarkup(rows)


def submenu_editar_sesion() -> InlineKeyboardMarkup:
    """Submenú con los campos editables de una sesión + opción de borrar."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Nombre", callback_data="edsescampo_nombre")],
            [InlineKeyboardButton("Descripción", callback_data="edsescampo_desc")],
            [InlineKeyboardButton("Lugar", callback_data="edsescampo_lugar")],
            [InlineKeyboardButton("Fecha y hora", callback_data="edsescampo_fecha")],
            [InlineKeyboardButton("Plazas", callback_data="edsescampo_plazas")],
            [InlineKeyboardButton("🗑 Borrar sesión", callback_data="edsescampo_borrar")],
        ]
    )


def confirmar_borrar_sesion() -> InlineKeyboardMarkup:
    """Confirmación previa al borrado: callbacks `edborrar_si` / `edborrar_no`."""
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Sí, borrar", callback_data="edborrar_si"),
            InlineKeyboardButton("❌ Cancelar", callback_data="edborrar_no"),
        ]]
    )


def picker_premisas_dm_editar(
    premisas: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """Picker de premisas del DM para editar. Callbacks: `edprempick_<id>`."""
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"edprempick_{pid}")]
        for pid, nombre in premisas
    ]
    return InlineKeyboardMarkup(rows)


def submenu_editar_premisa() -> InlineKeyboardMarkup:
    """Submenú con los campos editables de una premisa."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Nombre", callback_data="edpremcampo_nombre")],
            [InlineKeyboardButton("Descripción", callback_data="edpremcampo_desc")],
            [InlineKeyboardButton("Aviso de contenido", callback_data="edpremcampo_aviso")],
            [InlineKeyboardButton("Juego asociado", callback_data="edpremcampo_juego")],
        ]
    )


def picker_hora() -> InlineKeyboardMarkup:
    """Picker de hora (12 a 23) en cuadrícula 4x3.

    Callbacks: `cshora_<HH>` (HH con dos dígitos).
    """
    horas = list(range(12, 24))
    rows = []
    for i in range(0, len(horas), 4):
        rows.append([
            InlineKeyboardButton(f"{h:02d}", callback_data=f"cshora_{h:02d}")
            for h in horas[i:i + 4]
        ])
    return InlineKeyboardMarkup(rows)


def picker_minutos() -> InlineKeyboardMarkup:
    """Picker de minutos: 00, 15, 30, 45 en una sola fila.

    Callbacks: `csmin_<MM>`.
    """
    minutos = ["00", "15", "30", "45"]
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f":{m}", callback_data=f"csmin_{m}") for m in minutos]]
    )


def confirmar_juego_nuevo(nombre: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ Crear '{nombre}'", callback_data="nuevo_juego_ok"
                ),
                InlineKeyboardButton("❌ Cancelar", callback_data="nuevo_juego_no"),
            ]
        ]
    )


# ─────────────────── Selección de premisa al crear sesión ─────────────────


def submenu_elegir_premisa() -> InlineKeyboardMarkup:
    """Submenú inicial al crear sesión: 3 opciones de origen de la premisa.

    Callbacks: `csprem_mis`, `csprem_almacenadas`, `csprem_nueva`.
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                "📜 Mis premisas", callback_data="csprem_mis"
            )],
            [InlineKeyboardButton(
                "🗂 Premisas almacenadas", callback_data="csprem_almacenadas"
            )],
            [InlineKeyboardButton(
                "➕ Crear premisa nueva", callback_data="csprem_nueva"
            )],
        ]
    )


def picker_premisas_sesion(
    premisas: list[tuple[int, str]],
) -> InlineKeyboardMarkup:
    """Picker de premisas para reutilizar al crear sesión.

    Callbacks: `csprempick_<id>` por premisa.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"csprempick_{pid}")]
        for pid, nombre in premisas
    ]
    return InlineKeyboardMarkup(rows)


def elegir_nombre_sesion(premisa_nombre: str) -> InlineKeyboardMarkup:
    """Pregunta si la sesión hereda el nombre de la premisa o usa otro.

    Callbacks: `csnombre_misma`, `csnombre_otro`.
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"📌 Usar nombre de premisa: '{premisa_nombre}'",
                callback_data="csnombre_misma",
            )],
            [InlineKeyboardButton(
                "✏️ Poner otro nombre", callback_data="csnombre_otro"
            )],
        ]
    )


def confirmar_juego_premisa(juego_nombre: str) -> InlineKeyboardMarkup:
    """Tras heredar el juego de la premisa, ofrece continuar o cambiarlo.

    Callbacks: `csjuego_continuar`, `csjuego_cambiar`.
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                f"✅ Continuar con {juego_nombre}",
                callback_data="csjuego_continuar",
            )],
            [InlineKeyboardButton(
                "🔄 Cambiar juego", callback_data="csjuego_cambiar"
            )],
        ]
    )
