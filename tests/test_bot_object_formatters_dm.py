"""Tests del formatter `_format_dm`: premisas como deep-links."""
from __future__ import annotations

import re

from tmjr.bot import object_formatters, object_links
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc


async def test_format_dm_envuelve_premisas_en_deep_links(session):
    """Las premisas listadas en la ficha del DM son <a href=…obj_premisa_X>."""
    prev = object_links.get_bot_username()
    object_links.set_bot_username("test_bot")
    try:
        persona, _ = await personas_svc.get_or_create_persona(
            session, telegram_id=42, nombre="Maestra"
        )
        dm = await personas_svc.ensure_dm(session, persona, biografia="hola")

        j, _ = await juegos_svc.get_or_create_juego(session, nombre="D&D 5e")
        p1 = await premisas_svc.crear_premisa(
            session, nombre="La maldición de Strahd", id_juego=j.id
        )
        p2 = await premisas_svc.crear_premisa(
            session, nombre="Tomb of Annihilation", id_juego=j.id
        )
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=dm.id, id_premisa=p1.id
        )
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=dm.id, id_premisa=p2.id
        )

        info = await object_formatters._format_dm(session, dm.id)
        assert info is not None
        # Cada premisa debe aparecer envuelta en <a href="…obj_premisa_<id>">…</a>.
        for p in (p1, p2):
            assert (
                re.search(
                    rf'<a href="https://t\.me/test_bot\?start=obj_premisa_{p.id}">',
                    info,
                )
                is not None
            ), f"Falta deep-link de premisa {p.id} en: {info!r}"
            assert f">{p.nombre}</a>" in info
    finally:
        object_links.set_bot_username(prev)


async def test_format_dm_no_expone_id_de_premisa(session):
    """La ficha del DM no debe mostrar el id numérico de cada premisa."""
    object_links.set_bot_username(None)  # sin link, solo texto plano
    try:
        persona, _ = await personas_svc.get_or_create_persona(
            session, telegram_id=43, nombre="Otra"
        )
        dm = await personas_svc.ensure_dm(session, persona)
        j, _ = await juegos_svc.get_or_create_juego(session, nombre="J-id")
        p = await premisas_svc.crear_premisa(
            session, nombre="Mi premisa", id_juego=j.id
        )
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=dm.id, id_premisa=p.id
        )

        info = await object_formatters._format_dm(session, dm.id)
        assert info is not None
        # No debería aparecer el `id` (entero) suelto en el texto.
        assert f"#{p.id}" not in info
        assert f" {p.id} " not in info
    finally:
        object_links.set_bot_username(None)
