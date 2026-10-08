"""bloqueos_solapados: contrato para C-05 (rango semiabierto, alcance, tenant)."""

from datetime import UTC, datetime

import pytest

from app.domain.agenda.bloqueos import bloqueos_solapados
from app.domain.agenda.models import Bloqueo, Profesional, SillonRecurso


def _t(h: int, m: int = 0) -> datetime:
    return datetime(2032, 3, 1, h, m, tzinfo=UTC)


@pytest.fixture(scope="module")
def escenario(session_factory, auth_data):  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    with session_factory() as session:
        p1 = Profesional(clinica_id=a, nombre="P1", matricula="SOL-P1")
        p2 = Profesional(clinica_id=a, nombre="P2", matricula="SOL-P2")
        s1 = SillonRecurso(clinica_id=a, nombre="Sol S1", tipo="sillon")
        s2 = SillonRecurso(clinica_id=a, nombre="Sol S2", tipo="sillon")
        pb = Profesional(clinica_id=b, nombre="PB", matricula="SOL-PB")
        session.add_all([p1, p2, s1, s2, pb])
        session.flush()

        def bloqueo(clinica, ini, fin, **kw):  # type: ignore[no-untyped-def]
            fila = Bloqueo(clinica_id=clinica, inicio=ini, fin=fin, motivo="m", **kw)
            session.add(fila)
            session.flush()
            return fila.id

        ids = {
            "prof": bloqueo(a, _t(10), _t(11), profesional_id=p1.id),
            "sillon": bloqueo(a, _t(14), _t(15), sillon_id=s1.id),
            "clinica": bloqueo(a, _t(18), _t(19)),
            "contiguo": bloqueo(a, _t(12), _t(13), profesional_id=p1.id),
            "inactivo": bloqueo(a, _t(20), _t(21), profesional_id=p1.id),
            "otra_clinica": bloqueo(b, _t(10), _t(11)),
            "otra_clinica_prof": bloqueo(b, _t(10), _t(11), profesional_id=pb.id),
        }
        session.get(Bloqueo, ids["inactivo"]).is_active = False
        session.commit()
        return {"a": a, "b": b, "p1": p1.id, "p2": p2.id, "s1": s1.id, "s2": s2.id, "ids": ids}


def _consulta(session_factory, esc, ini, fin, p=None, s=None):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return {b.id for b in bloqueos_solapados(session, esc["a"], ini, fin, p, s)}


def test_devuelve_bloqueo_del_profesional_que_se_superpone(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    ids = _consulta(session_factory, escenario, _t(10, 30), _t(11, 30), p=escenario["p1"])
    assert escenario["ids"]["prof"] in ids
    otro = _consulta(session_factory, escenario, _t(10, 30), _t(11, 30), p=escenario["p2"])
    assert escenario["ids"]["prof"] not in otro


def test_bloqueo_de_sillon_solo_afecta_a_ese_sillon(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    propio = _consulta(session_factory, escenario, _t(14, 10), _t(14, 40), s=escenario["s1"])
    assert escenario["ids"]["sillon"] in propio
    ajeno = _consulta(
        session_factory, escenario, _t(14, 10), _t(14, 40), p=escenario["p1"], s=escenario["s2"]
    )
    assert escenario["ids"]["sillon"] not in ajeno


def test_bloqueo_de_clinica_afecta_a_cualquier_par(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    pares = ((escenario["p1"], escenario["s1"]), (escenario["p2"], escenario["s2"]), (None, None))
    for p, s in pares:
        ids = _consulta(session_factory, escenario, _t(18, 30), _t(19, 30), p=p, s=s)
        assert escenario["ids"]["clinica"] in ids


def test_rango_contiguo_no_se_superpone(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    # El bloqueo es [12, 13); un turno [13, 13:30) no lo toca, uno [12:59, 13:30) si.
    toca = _consulta(session_factory, escenario, _t(13), _t(13, 30), p=escenario["p1"])
    assert escenario["ids"]["contiguo"] not in toca
    cruza = _consulta(session_factory, escenario, _t(12, 59), _t(13, 30), p=escenario["p1"])
    assert escenario["ids"]["contiguo"] in cruza
    antes = _consulta(session_factory, escenario, _t(11, 30), _t(12), p=escenario["p1"])
    assert escenario["ids"]["contiguo"] not in antes


def test_ignora_inactivos_y_otras_clinicas(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    inactivo = _consulta(session_factory, escenario, _t(20), _t(21), p=escenario["p1"])
    assert escenario["ids"]["inactivo"] not in inactivo
    otra = _consulta(session_factory, escenario, _t(10), _t(11), p=escenario["p1"])
    assert escenario["ids"]["otra_clinica"] not in otra
    assert escenario["ids"]["otra_clinica_prof"] not in otra


def test_sin_superposicion_devuelve_vacio(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    assert _consulta(session_factory, escenario, _t(3), _t(4), p=escenario["p1"]) == set()


def test_inicio_naive_o_rango_invalido_levanta_value_error(session_factory, escenario) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(ValueError):
            naive = datetime(2032, 3, 1, 10)
            bloqueos_solapados(session, escenario["a"], naive, _t(11), None, None)
        with pytest.raises(ValueError):
            bloqueos_solapados(session, escenario["a"], _t(11), _t(10), None, None)
