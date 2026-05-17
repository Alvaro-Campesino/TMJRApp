"""Unit tests del servicio de sesiones: crear, apuntar, plazas, errores."""
from __future__ import annotations

from datetime import datetime

import pytest

from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as svc


async def _juego(session, nombre: str = "JuegoTest") -> int:
    j, _ = await juegos_svc.get_or_create_juego(session, nombre=nombre)
    return j.id


async def _persona_dm(session, telegram_id: int, nombre: str = "DM") -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre=nombre
    )
    dm = await personas_svc.ensure_dm(session, persona)
    return dm.id


async def _persona_pj(session, telegram_id: int, nombre: str = "PJ") -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre=nombre
    )
    # En el helper actualizamos también el nombre de la persona, porque
    # ahora el "nombre del PJ" ES `Persona.nombre` (no hay PJ.nombre).
    if persona.nombre != nombre:
        persona.nombre = nombre
        await session.commit()
    pj = await personas_svc.ensure_pj(session, persona)
    return pj.id


async def test_crear_sesion_minima(session):
    id_dm = await _persona_dm(session, 1)
    id_juego = await _juego(session, "JuegoMin")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 1, 4, 18, 0),
    )
    assert s.id is not None
    assert s.id_dm == id_dm
    assert s.id_juego == id_juego
    assert s.descripcion is None
    assert s.plazas_totales == 5
    assert s.plazas_sin_reserva == 1


async def test_crear_sesion_con_overrides(session):
    id_dm = await _persona_dm(session, 2)
    id_juego = await _juego(session, "JuegoOver")
    s = await svc.crear_sesion(
        session,
        id_dm=id_dm,
        id_juego=id_juego,
        fecha=datetime(2030, 1, 11, 18, 0),
        plazas_totales=3,
        plazas_sin_reserva=0,
        descripcion="Aviso: traer dados de 6",
    )
    assert s.plazas_totales == 3
    assert s.plazas_sin_reserva == 0
    assert s.descripcion == "Aviso: traer dados de 6"


async def test_get_sesion_inexistente_devuelve_none(session):
    assert await svc.get_sesion(session, 9999) is None


async def test_apuntar_pj_camino_feliz(session):
    id_dm = await _persona_dm(session, 10)
    id_pj = await _persona_pj(session, 11, "PJ-1")
    id_juego = await _juego(session, "Juego10")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 2, 1, 18, 0),
    )

    sp = await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)
    assert sp.id is not None
    assert sp.id_sesion == s.id
    assert sp.id_pj == id_pj
    assert sp.acompanantes == 0


async def test_apuntar_pj_dos_veces_falla(session):
    id_dm = await _persona_dm(session, 20)
    id_pj = await _persona_pj(session, 21, "PJ-2")
    id_juego = await _juego(session, "Juego20")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 2, 8, 18, 0),
    )

    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)
    with pytest.raises(svc.YaApuntadoError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)


async def test_apuntar_pj_a_sesion_inexistente(session):
    id_pj = await _persona_pj(session, 30, "PJ-3")
    with pytest.raises(ValueError, match="Sesion"):
        await svc.apuntar_pj(session, sesion_id=9999, pj_id=id_pj)


async def test_apuntar_pj_inexistente(session):
    id_dm = await _persona_dm(session, 40)
    id_juego = await _juego(session, "Juego40")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 2, 15, 18, 0),
    )
    with pytest.raises(ValueError, match="PJ"):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=9999)


async def test_sesion_llena_sin_acompanantes(session):
    id_dm = await _persona_dm(session, 50)
    id_juego = await _juego(session, "Juego50")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 3, 1, 18, 0), plazas_totales=2,
    )
    pj1 = await _persona_pj(session, 51, "P1")
    pj2 = await _persona_pj(session, 52, "P2")
    pj3 = await _persona_pj(session, 53, "P3")

    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2)
    with pytest.raises(svc.SesionLlenaError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj3)


async def test_acompanantes_cuentan_para_plazas(session):
    id_dm = await _persona_dm(session, 60)
    id_juego = await _juego(session, "Juego60")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 3, 8, 18, 0), plazas_totales=3,
    )
    pj1 = await _persona_pj(session, 61, "Q1")
    pj2 = await _persona_pj(session, 62, "Q2")

    # 1 PJ con 1 acompañante = 2 plazas
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1, acompanantes=1)
    # 1 PJ extra ya hace 3 → cabe
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2, acompanantes=0)

    pj3 = await _persona_pj(session, 63, "Q3")
    with pytest.raises(svc.SesionLlenaError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj3)


async def test_list_sesiones_for_dm_filtra_por_dm_y_futuras(session):
    id_dm_a = await _persona_dm(session, 200)
    id_dm_b = await _persona_dm(session, 201, "DM-B")
    id_juego = await _juego(session, "JuegoDMlist")

    # 1 sesión futura del DM-A, 1 pasada del DM-A, 1 del DM-B
    await svc.crear_sesion(
        session, id_dm=id_dm_a, id_juego=id_juego,
        fecha=datetime(2030, 6, 1, 18, 0),
    )
    await svc.crear_sesion(
        session, id_dm=id_dm_a, id_juego=id_juego,
        fecha=datetime(2020, 1, 1, 18, 0),     # pasada
    )
    await svc.crear_sesion(
        session, id_dm=id_dm_b, id_juego=id_juego,
        fecha=datetime(2030, 6, 2, 18, 0),
    )

    futuras = await svc.list_sesiones_for_dm(session, id_dm_a, only_future=True)
    assert len(futuras) == 1
    assert futuras[0].fecha == datetime(2030, 6, 1, 18, 0)

    todas = await svc.list_sesiones_for_dm(session, id_dm_a, only_future=False)
    assert len(todas) == 2


async def test_update_sesion_aplica_y_valida_plazas(session):
    id_dm = await _persona_dm(session, 210)
    id_juego = await _juego(session, "JuegoUpd")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 7, 1, 18, 0), plazas_totales=4,
    )

    # Cambios simples
    s2 = await svc.update_sesion(
        session, s, nombre="Nuevo nombre", lugar="Online"
    )
    assert s2.nombre == "Nuevo nombre"
    assert s2.lugar == "Online"

    # Apuntar 2 PJs y luego intentar bajar plazas a 1 → falla
    pj1 = await _persona_pj(session, 211, "PA1")
    pj2 = await _persona_pj(session, 212, "PA2")
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2)

    with pytest.raises(ValueError, match="ocupadas"):
        await svc.update_sesion(session, s, plazas_totales=1)

    # Subir plazas sí
    s3 = await svc.update_sesion(session, s, plazas_totales=6)
    assert s3.plazas_totales == 6


async def test_invitados_add_remove_y_borrar_sesion_limpia(session):
    """add_invitado / remove_ultimo_invitado sobre acompanantes y borrar sesión."""
    from sqlalchemy import select
    from tmjr.db.models import Sesion, SesionPJ

    id_dm = await _persona_dm(session, 400)
    id_juego = await _juego(session, "JuegoInv")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 9, 15, 18, 0), plazas_totales=4,
    )
    anfitrion = await _persona_pj(session, 401, "Anfitrion")

    # Apuntar al anfitrión.
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=anfitrion)

    # +1 dos veces: acompanantes pasa a 2.
    sp1 = await svc.add_invitado(
        session, sesion_id=s.id, anfitrion_pj_id=anfitrion,
    )
    assert sp1.acompanantes == 1
    sp2 = await svc.add_invitado(
        session, sesion_id=s.id, anfitrion_pj_id=anfitrion,
    )
    assert sp2.acompanantes == 2

    # 4ª plaza: aún cabe; 5ª: explota con SesionLlenaError (1 + 3 = 4 plazas).
    await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=anfitrion)
    with pytest.raises(svc.SesionLlenaError):
        await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=anfitrion)

    # remove_ultimo_invitado: decrementa acompanantes.
    assert await svc.remove_ultimo_invitado(
        session, sesion_id=s.id, anfitrion_pj_id=anfitrion
    ) is True
    sp = (
        await session.execute(
            select(SesionPJ)
            .where(SesionPJ.id_sesion == s.id)
            .where(SesionPJ.id_pj == anfitrion)
        )
    ).scalar_one()
    assert sp.acompanantes == 2

    # Borrar sesión: limpia la fila de sesion_pj.
    await svc.borrar_sesion(session, s)
    assert await session.get(Sesion, s.id) is None
    sp_rows = (
        await session.execute(
            select(SesionPJ).where(SesionPJ.id_sesion == s.id)
        )
    ).scalars().all()
    assert sp_rows == []


async def test_add_invitado_falla_si_anfitrion_no_apuntado(session):
    """Si el anfitrión no está apuntado a la sesión, +1 lanza AnfitrionNoApuntadoError."""
    id_dm = await _persona_dm(session, 405)
    id_juego = await _juego(session, "JuegoInvAnf")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 9, 18, 18, 0),
    )
    pj = await _persona_pj(session, 406, "NoApuntado")
    with pytest.raises(svc.AnfitrionNoApuntadoError):
        await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=pj)


async def test_crear_sesion_con_plazas_minimas_valida_rango(session):
    """`plazas_minimas` debe estar en [0, plazas_totales]."""
    id_dm = await _persona_dm(session, 700)
    id_juego = await _juego(session, "Jmin")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 8, 1, 18, 0),
        plazas_totales=5, plazas_minimas=3,
    )
    assert s.plazas_minimas == 3

    import pytest
    with pytest.raises(ValueError):
        await svc.crear_sesion(
            session, id_dm=id_dm, id_juego=id_juego,
            fecha=datetime(2030, 8, 2, 18, 0),
            plazas_totales=4, plazas_minimas=5,
        )


def test_cruce_minimo_arriba_abajo_y_none():
    """Helper de detección de cruce del umbral mínimo."""
    # Sin mínimo → siempre None
    assert svc.cruce_minimo(0, 5, 0) is None
    # Subir cruzando: antes < min, después >= min
    assert svc.cruce_minimo(1, 3, 3) == "arriba"
    assert svc.cruce_minimo(0, 4, 3) == "arriba"
    # Bajar cruzando: antes >= min, después < min
    assert svc.cruce_minimo(3, 2, 3) == "abajo"
    assert svc.cruce_minimo(5, 0, 3) == "abajo"
    # Sin cruce: ambos por encima o ambos por debajo
    assert svc.cruce_minimo(4, 5, 3) is None
    assert svc.cruce_minimo(0, 1, 3) is None
    # Quedarse exactamente en el mínimo no es cruce si ya estaba allí
    assert svc.cruce_minimo(3, 3, 3) is None


async def test_update_sesion_plazas_minimas_no_supera_total(session):
    """No se puede subir el mínimo por encima del total existente."""
    id_dm = await _persona_dm(session, 701)
    id_juego = await _juego(session, "Jmin2")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 8, 3, 18, 0),
        plazas_totales=4, plazas_minimas=0,
    )
    import pytest
    with pytest.raises(ValueError):
        await svc.update_sesion(session, s, plazas_minimas=5)


async def test_nombre_pjs_en_sesion_expande_acompanantes(session):
    """Cada acompañante ocupa un slot detrás de su anfitrión; truncado a 20 chars."""
    id_dm = await _persona_dm(session, 420)
    id_juego = await _juego(session, "JuegoNombres")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 9, 17, 18, 0), plazas_totales=6,
    )

    pj_normal = await _persona_pj(session, 421, "Marta")
    anfitrion_corto = await _persona_pj(session, 422, "Alvaro")
    anfitrion_largo = await _persona_pj(
        session, 423, "NombreLarguisimoQueSeTrunca"
    )

    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj_normal)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=anfitrion_corto)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=anfitrion_largo)
    # Alvaro trae 2 invitados (caben en su slot).
    await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=anfitrion_corto)
    await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=anfitrion_corto)
    # El anfitrión de nombre largo trae 1: se trunca a 20 chars en el slot.
    await svc.add_invitado(session, sesion_id=s.id, anfitrion_pj_id=anfitrion_largo)

    nombres = await svc.nombre_pjs_en_sesion(session, s.id)
    assert nombres == [
        "Marta",
        "Alvaro",
        "Invitado-Alvaro",
        "Invitado-Alvaro",
        "NombreLarguisimoQueSeTrunca",  # el nombre del anfitrión NO se trunca
        "Invitado-NombreLargu",  # invitado truncado a 20 chars totales
    ]
    assert len(nombres[5]) == 20

    # `slots_pjs_en_sesion` devuelve lo mismo pero con el pj_id por slot:
    # PJ apuntado → su id; acompañante → None.
    slots = await svc.slots_pjs_en_sesion(session, s.id)
    assert [n for n, _ in slots] == nombres
    pj_ids = [pid for _, pid in slots]
    assert pj_ids[0] == pj_normal
    assert pj_ids[1] == anfitrion_corto
    assert pj_ids[2] is None and pj_ids[3] is None  # acompañantes
    assert pj_ids[4] == anfitrion_largo
    assert pj_ids[5] is None


async def test_remove_ultimo_invitado_sin_invitados_devuelve_false(session):
    id_dm = await _persona_dm(session, 410)
    id_juego = await _juego(session, "JuegoInv2")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 9, 16, 18, 0),
    )
    pj = await _persona_pj(session, 411, "SinInvi")
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj)
    assert await svc.remove_ultimo_invitado(
        session, sesion_id=s.id, anfitrion_pj_id=pj
    ) is False


async def test_borrar_sesion_y_apuntados_telegram(session):
    """Verifica apuntados_telegram + borrar_sesion (cascada a sesion_pj)."""
    from sqlalchemy import select
    from tmjr.db.models import Sesion, SesionPJ

    id_dm = await _persona_dm(session, 300)
    id_juego = await _juego(session, "JuegoBorrar")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 8, 1, 18, 0),
    )

    # Apuntar 2 PJs (conocemos sus telegram_id porque _persona_pj los crea).
    pj1 = await _persona_pj(session, 301, "PB1")
    pj2 = await _persona_pj(session, 302, "PB2")
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2)

    # apuntados_telegram devuelve los telegram_ids con el nombre del PJ.
    telegrams = await svc.apuntados_telegram(session, s.id)
    assert sorted(telegrams) == sorted([(301, "PB1"), (302, "PB2")])

    # borrar_sesion elimina la fila + las dependencias.
    await svc.borrar_sesion(session, s)
    assert await session.get(Sesion, s.id) is None
    rows = (
        await session.execute(select(SesionPJ).where(SesionPJ.id_sesion == s.id))
    ).all()
    assert rows == []


async def test_plazas_ocupadas_calculo(session):
    id_dm = await _persona_dm(session, 70)
    id_juego = await _juego(session, "Juego70")
    s = await svc.crear_sesion(
        session, id_dm=id_dm, id_juego=id_juego,
        fecha=datetime(2030, 3, 15, 18, 0), plazas_totales=6,
    )
    pj1 = await _persona_pj(session, 71, "R1")
    pj2 = await _persona_pj(session, 72, "R2")

    assert await svc.plazas_ocupadas(session, s.id) == 0
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1, acompanantes=2)
    assert await svc.plazas_ocupadas(session, s.id) == 3  # 1 + 2
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2, acompanantes=0)
    assert await svc.plazas_ocupadas(session, s.id) == 4
