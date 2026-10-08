"""Aislamiento multi-tenant del catálogo (C-04, regla dura 10) en PG16 real."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.agenda.models import (
    Bloqueo,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.infrastructure.persistence.repository import BaseRepository


@pytest.fixture(scope="module")
def catalogo_ab(session_factory, auth_data):  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    ids: dict[str, dict[str, int]] = {"a": {}, "b": {}}
    with session_factory() as session:
        for key, cid in (("a", a), ("b", b)):
            sillon = SillonRecurso(clinica_id=cid, nombre=f"S-iso-{key}", tipo="sillon")
            prof = Profesional(clinica_id=cid, nombre="P", matricula=f"ISO-{key}")
            prest = Prestacion(
                clinica_id=cid, nombre="Pr", duracion_min=30, precio_referencia=Decimal("10.50")
            )
            session.add_all([sillon, prof, prest])
            session.flush()
            session.add(
                ProfesionalSillon(profesional_id=prof.id, sillon_id=sillon.id, clinica_id=cid)
            )
            bloq = Bloqueo(
                clinica_id=cid,
                inicio=datetime(2030, 1, 1, 10, tzinfo=UTC),
                fin=datetime(2030, 1, 1, 11, tzinfo=UTC),
                motivo="iso",
            )
            session.add(bloq)
            session.flush()
            ids[key] = {
                "sillon": sillon.id, "profesional": prof.id,
                "prestacion": prest.id, "bloqueo": bloq.id,
            }  # fmt: skip
        session.commit()
    return {"a": a, "b": b, "ids": ids}


MODELOS = [
    (SillonRecurso, "sillon"),
    (Profesional, "profesional"),
    (Prestacion, "prestacion"),
    (Bloqueo, "bloqueo"),
]


@pytest.mark.parametrize(("modelo", "clave"), MODELOS)
def test_lista_solo_filas_del_tenant(session_factory, catalogo_ab, modelo, clave) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        filas = BaseRepository(session, modelo, catalogo_ab["a"]).list(include_inactive=True)
        assert filas
        assert {f.clinica_id for f in filas} == {catalogo_ab["a"]}
        assert catalogo_ab["ids"]["b"][clave] not in {f.id for f in filas}


@pytest.mark.parametrize(("modelo", "clave"), MODELOS)
def test_get_por_id_ajeno_devuelve_none_y_propio_devuelve_fila(  # type: ignore[no-untyped-def]
    session_factory, catalogo_ab, modelo, clave
) -> None:
    with session_factory() as session:
        repo = BaseRepository(session, modelo, catalogo_ab["a"])
        assert repo.get(catalogo_ab["ids"]["b"][clave], include_inactive=True) is None
        assert repo.get(catalogo_ab["ids"]["a"][clave]) is not None


def test_habilitacion_aislada_por_tenant(session_factory, catalogo_ab) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        filas = BaseRepository(session, ProfesionalSillon, catalogo_ab["a"]).list()
        assert {f.clinica_id for f in filas} == {catalogo_ab["a"]}
        assert {f.sillon_id for f in filas} == {catalogo_ab["ids"]["a"]["sillon"]}


def test_modelos_mapean_numeric_decimal_y_rango_generado(session_factory, catalogo_ab) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        prest = session.get(Prestacion, catalogo_ab["ids"]["a"]["prestacion"])
        assert prest.precio_referencia == Decimal("10.50")
        assert isinstance(prest.precio_referencia, Decimal)
        bloq = session.get(Bloqueo, catalogo_ab["ids"]["a"]["bloqueo"])
        assert bloq.rango is not None


def test_paginacion_keyset_120_prestaciones_en_50_50_20(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    # Clinica propia para contar exacto sin depender de otras filas del modulo.
    from app.domain.core.models import Clinica

    with session_factory() as session:
        clinica = Clinica(nombre="Clinica Paginacion Sintetica", cuit="30711111118", es_seed=True)
        session.add(clinica)
        session.flush()
        for n in range(120):
            session.add(
                Prestacion(
                    clinica_id=clinica.id,
                    nombre=f"Pr {n}",
                    duracion_min=30,
                    precio_referencia=Decimal("1.00"),
                )
            )
        session.commit()
        repo = BaseRepository(session, Prestacion, clinica.id)
        paginas, cursor, vistos = [], None, []
        while True:
            items, cursor = repo.page(cursor, 50)
            paginas.append(len(items))
            vistos += [i.id for i in items]
            if cursor is None:
                break
        assert paginas == [50, 50, 20]
        assert len(set(vistos)) == 120
        assert vistos == sorted(vistos)
