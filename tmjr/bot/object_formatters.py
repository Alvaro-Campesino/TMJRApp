"""Formatters concretos para los deep-link objects.

Importar este módulo registra los formatters en `object_links`. El handler
de /start usa `format_object(session, kind, id)` para obtener el texto.

Todos los formatters devuelven HTML (parse_mode HTML). El texto de usuario
se escapa con `html.escape` para evitar romper el parser.
"""
from __future__ import annotations

from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.bot.object_links import build_object_link, register_formatter
from tmjr.db.models import Campania, DM, Juego, PJ, Premisa, Sesion
from tmjr.services import campanias as campanias_svc
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc


async def _format_premisa(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de premisa: nombre + juego + descripción + aviso."""
    p = await session.get(Premisa, obj_id)
    if p is None:
        return None
    juego_nombre: str | None = None
    if p.id_juego is not None:
        juego = await session.get(Juego, p.id_juego)
        if juego is not None:
            juego_nombre = juego.nombre
    lines = [f"📜 <b>Premisa:</b> {escape(p.nombre)}"]
    if juego_nombre:
        lines.append(f"🎮 Juego: {escape(juego_nombre)}")
    if p.descripcion:
        lines.append("")
        lines.append(escape(p.descripcion))
    if p.aviso_contenido:
        lines.append("")
        lines.append(f"⚠️ Aviso de contenido: {escape(p.aviso_contenido)}")
    return "\n".join(lines)


async def _format_juego(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de juego: nombre + editorial + biblioteca + ISBN + descripción."""
    j = await session.get(Juego, obj_id)
    if j is None:
        return None
    lines = [f"🎮 <b>Juego:</b> {escape(j.nombre)}"]
    if j.editorial:
        lines.append(f"🏢 Editorial: {escape(j.editorial)}")
    if j.disponible_en_biblioteca:
        lines.append("📚 Disponible en la biblioteca")
    if j.ISBN:
        lines.append(f"💳 ISBN: <code>{escape(j.ISBN)}</code>")
    if j.descripcion:
        lines.append("")
        lines.append(escape(j.descripcion))
    return "\n".join(lines)


async def _format_dm(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de DM: nombre + biografía + sus juegos + sus premisas."""
    dm = await session.get(DM, obj_id)
    if dm is None:
        return None
    persona = await personas_svc.get_persona_by_dm(session, dm.id)
    nombre = persona.nombre if persona else f"DM #{dm.id}"
    juegos = await juegos_svc.list_juegos_for_dm(session, dm.id)
    premisas = await premisas_svc.list_premisas_for_dm(session, dm.id)

    lines = [f"🎲 <b>DM:</b> {escape(nombre)}"]
    if dm.biografia:
        lines.append("")
        lines.append(escape(dm.biografia))
    if juegos:
        lines.append("")
        lines.append("🎮 <b>Juegos:</b>")
        for j in juegos:
            lines.append(f"  • {escape(j.nombre)}")
    if premisas:
        lines.append("")
        lines.append("📜 <b>Premisas:</b>")
        # Cada premisa es un deep-link a su ficha (obj_premisa_<id>);
        # desde allí el usuario tiene el botón de suscripción.
        for p in premisas:
            lines.append(f"  • {build_object_link('premisa', p.id, p.nombre)}")
    return "\n".join(lines)


async def _format_sesion(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de sesión: título, fecha, lugar, plazas, descripción."""
    s = await session.get(Sesion, obj_id)
    if s is None:
        return None
    titulo = s.nombre or f"Sesión #{s.id}"
    lines = [f"🎲 <b>Sesión:</b> {escape(titulo)}"]
    lines.append(f"📅 {s.fecha.isoformat()}")
    if s.lugar:
        lines.append(f"📍 {escape(s.lugar)}")
    lines.append(f"🪑 {s.plazas_totales} plazas")
    if s.descripcion:
        lines.append("")
        lines.append(escape(s.descripcion))
    return "\n".join(lines)


async def _format_campania(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de campaña: nombre (de la premisa) + DM + nº de sesiones + PJs fijos."""
    c = await session.get(Campania, obj_id)
    if c is None:
        return None
    premisa = await session.get(Premisa, c.id_premisa)
    nombre = premisa.nombre if premisa else f"Campaña #{c.id}"
    dm_persona = await personas_svc.get_persona_by_dm(session, c.id_dm)
    dm_nombre = dm_persona.nombre if dm_persona else f"DM #{c.id_dm}"

    pjs_fijos = await campanias_svc.list_pjs_fijos(session, c.id)

    lines = [f"🏰 <b>Campaña:</b> {escape(nombre)}"]
    lines.append(f"🎲 DM: {escape(dm_nombre)}")
    if premisa is not None and premisa.descripcion:
        lines.append("")
        lines.append(escape(premisa.descripcion))
    if pjs_fijos:
        lines.append("")
        lines.append("👥 <b>PJs fijos:</b>")
        for _pj, pj_nombre in pjs_fijos:
            lines.append(f"  • {escape(pj_nombre)}")
    else:
        lines.append("")
        lines.append("<i>Sin PJs fijos todavía.</i>")
    return "\n".join(lines)


async def _format_pj(session: AsyncSession, obj_id: int) -> str | None:
    """Ficha de PJ: nombre (de la persona enlazada) + descripción.

    El nombre del PJ es siempre el de la `Persona` con `id_pj == pj.id`.
    No exponemos otros datos de la persona (juegos/premisas pertenecen
    a su perfil DM, no al PJ) para preservar la privacidad cuando un DM
    abre la ficha de un PJ apuntado a su sesión.
    """
    pj = await session.get(PJ, obj_id)
    if pj is None:
        return None
    persona = await personas_svc.get_persona_by_pj(session, pj.id)
    nombre = persona.nombre if persona is not None else f"PJ #{pj.id}"
    lines = [f"🎭 <b>PJ:</b> {escape(nombre)}"]
    if pj.descripcion:
        lines.append("")
        lines.append(escape(pj.descripcion))
    return "\n".join(lines)


register_formatter("premisa", _format_premisa)
register_formatter("juego", _format_juego)
register_formatter("dm", _format_dm)
register_formatter("sesion", _format_sesion)
register_formatter("campania", _format_campania)
register_formatter("pj", _format_pj)
