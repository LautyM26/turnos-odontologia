"""Dos admins se quitan el rol mutuamente a la vez: uno 200, otro 409 (C-18 4.3).

Se invoca el servicio con dos sesiones (la ventana de la carrera entre autenticar y mutar no
es controlable por HTTP). La garantía la da ``SELECT ... FOR UPDATE`` sobre las filas de los
admins activos. PG16 real.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from app.api.deps import AuthContext
from app.domain.core.models import Clinica
from app.domain.usuarios.errores import UltimoAdmin
from app.domain.usuarios.schemas import RolesIn
from app.domain.usuarios.servicios import reemplazar_roles
from tests.integration.conftest import crear_usuario


def test_dos_admins_que_se_quitan_el_rol_dejan_al_menos_uno(  # type: ignore[no-untyped-def]
    session_factory, auth_data, password_hash
) -> None:
    with session_factory() as s:
        clinica = Clinica(nombre="Clinica Concurrencia Sintetica", cuit="30712345678", es_seed=True)
        s.add(clinica)
        s.commit()
        cid = clinica.id
    u1 = crear_usuario(session_factory, password_hash, cid, "conc-1@test.test", ["admin"])
    u2 = crear_usuario(session_factory, password_hash, cid, "conc-2@test.test", ["admin"])

    barrera = threading.Barrier(2)

    def _una(args):  # type: ignore[no-untyped-def]
        actor, objetivo = args
        auth = AuthContext(sub=actor, tenant_id=cid, roles=("admin",), email="x", jti="j")
        with session_factory() as session:
            barrera.wait(timeout=30)
            try:
                reemplazar_roles(session, auth, objetivo, RolesIn(roles=["recepcionista"]), None)
            except UltimoAdmin:
                return 409
            return 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(_una, [(u1, u2), (u2, u1)]))
    assert Counter(respuestas) == {200: 1, 409: 1}
    with session_factory() as s:
        admins = s.scalar(
            text(
                "SELECT count(*) FROM usuario_rol ur JOIN rol r ON r.id = ur.rol_id "
                "WHERE ur.clinica_id=:c AND r.clave='admin' AND ur.is_active"
            ),
            {"c": cid},
        )
    assert admins == 1
