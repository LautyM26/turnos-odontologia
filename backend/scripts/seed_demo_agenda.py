"""Seed de DEMO para la agenda (C-07). Solo datos sintéticos (regla dura 14), marcados ``es_seed``.

Corre sobre ``seed_demo_clinica`` (clínica piloto, usuarios demo, profesional seed) y agrega:

- 2 sillones y 2 profesionales sintéticos con horario de lunes a viernes y habilitaciones;
- 12 pacientes ficticios (DNI 98xxxxxx, sin consentimiento de datos de salud: solo contacto);
- un bloqueo de sillón (mantenimiento) y uno de profesional (capacitación);
- turnos de la semana actual cargados con el motor real (``crear_turno`` y
  ``transicionar_turno``): respetan horario, bloqueos y anti-solapamiento. Los ya pasados quedan
  asistidos o ausentes; algunos futuros, confirmados; hay reservas online y un sobreturno.

Idempotente: si los pacientes demo ya tienen turnos esta semana, no crea más.

Uso (desde la raíz del repo, con las migraciones aplicadas)::

    DATABASE_URL=postgresql+psycopg://... python backend/scripts/seed_demo_agenda.py
"""

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.domain.agenda.horario import reemplazar_horario  # noqa: E402
from app.domain.agenda.models import (  # noqa: E402
    Bloqueo,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.agenda.turnos import (  # noqa: E402
    Turno,
    TurnoNoDisponible,
    crear_turno,
    transicionar_turno,
)
from app.domain.core.models import Clinica, Usuario  # noqa: E402
from app.domain.pacientes.models import Paciente  # noqa: E402
from app.domain.pacientes.normalizacion import nombre_busqueda  # noqa: E402
from app.infrastructure.db import create_engine_for_url, create_session_factory  # noqa: E402
from app.infrastructure.persistence.seed_core import SEED_ADMIN_EMAIL, SEED_CLINICA_CUIT  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_demo_clinica import seed_demo  # noqa: E402

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
SILLONES = (("Sillón 2", "sillon"), ("Box quirúrgico", "box"))
# (nombre, matrícula, especialidad)
PROFESIONALES = (
    ("Dra. Valeria Ríos", "DEMO-0002", "Ortodoncia"),
    ("Dr. Tomás Ibarra", "DEMO-0003", "Cirugía"),
)
PACIENTES = (
    ("Lucía", "Fernández"),
    ("Martín", "Gómez"),
    ("Sofía", "Acosta"),
    ("Joaquín", "Pereyra"),
    ("Camila", "Benítez"),
    ("Bruno", "Ledesma"),
    ("Abril", "Quiroga"),
    ("Franco", "Medina"),
    ("Julieta", "Sosa"),
    ("Tomás", "Vera"),
    ("Milagros", "Ojeda"),
    ("Ignacio", "Ferreyra"),
)
# Agenda tipo por día: (profesional 0..2, sillón 0..2, "HH:MM", prestación 0..2, origen)
PLAN = (
    (0, 0, "09:00", 0, "mostrador"),
    (1, 1, "09:00", 1, "mostrador"),
    (2, 2, "09:30", 2, "mostrador"),
    (0, 0, "09:45", 1, "enlace"),
    (1, 1, "10:00", 0, "whatsapp"),
    (0, 0, "11:00", 0, "mostrador"),
    (2, 2, "11:00", 1, "enlace"),
    (1, 1, "11:30", 2, "mostrador"),
    (0, 0, "14:00", 1, "mostrador"),
    (1, 1, "14:30", 0, "enlace"),
    (2, 2, "15:00", 2, "mostrador"),
    (0, 0, "16:00", 0, "mostrador"),
    (1, 1, "16:30", 1, "mostrador"),
)


def _lunes_local(ahora: datetime) -> datetime:
    local = ahora.astimezone(ZONA)
    return (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _instante(dia: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return dia.replace(hour=h, minute=m).astimezone(UTC)


def _uno(session: Session, modelo, **filtros):  # type: ignore[no-untyped-def]
    stmt = select(modelo)
    for campo, valor in filtros.items():
        stmt = stmt.where(getattr(modelo, campo) == valor)
    return session.scalars(stmt).first()


def seed_demo_agenda(session: Session, ahora: datetime | None = None) -> dict[str, int]:
    seed_demo(session)
    ahora = ahora or datetime.now(UTC)
    clinica = session.scalars(select(Clinica).where(Clinica.cuit == SEED_CLINICA_CUIT)).one()
    cid = clinica.id
    admin = session.scalars(
        select(Usuario).where(func.lower(Usuario.email) == SEED_ADMIN_EMAIL)
    ).one()

    sillones = list(
        session.scalars(
            select(SillonRecurso)
            .where(SillonRecurso.clinica_id == cid, SillonRecurso.es_seed.is_(True))
            .order_by(SillonRecurso.id)
        ).all()
    )
    for nombre, tipo in SILLONES:
        if not any(s.nombre == nombre for s in sillones):
            s = SillonRecurso(clinica_id=cid, nombre=nombre, tipo=tipo, es_seed=True)
            session.add(s)
            session.flush()
            sillones.append(s)

    profesionales = list(
        session.scalars(
            select(Profesional)
            .where(Profesional.clinica_id == cid, Profesional.es_seed.is_(True))
            .order_by(Profesional.id)
        ).all()
    )
    for nombre, matricula, especialidad in PROFESIONALES:
        if not any(p.matricula == matricula for p in profesionales):
            p = Profesional(
                clinica_id=cid,
                nombre=nombre,
                matricula=matricula,
                especialidad=especialidad,
                es_seed=True,
            )
            session.add(p)
            session.flush()
            profesionales.append(p)
    session.commit()

    # Habilitaciones: cada profesional en "su" sillón y en uno compartido.
    habilitaciones = {0: (0, 1), 1: (1, 0), 2: (2, 1)}
    for ip, iss in habilitaciones.items():
        for i_s in iss:
            prof, sillon = profesionales[ip], sillones[i_s]
            if session.get(ProfesionalSillon, (prof.id, sillon.id)) is None:
                session.add(
                    ProfesionalSillon(clinica_id=cid, profesional_id=prof.id, sillon_id=sillon.id)
                )
    session.commit()
    franjas = [
        {"dia_semana": d, "inicio": i * 60, "fin": f * 60}
        for d in range(1, 6)
        for i, f in ((9, 13), (14, 18))
    ]
    for prof in profesionales[1:]:
        reemplazar_horario(session, cid, prof.id, franjas)

    pacientes = []
    for n, (nombre, apellido) in enumerate(PACIENTES, start=1):
        dni = f"98{n:06d}"
        pac = _uno(session, Paciente, clinica_id=cid, dni=dni)
        if pac is None:
            pac = Paciente(
                clinica_id=cid,
                nombre=nombre,
                apellido=apellido,
                dni=dni,
                telefono=f"+54911555{n:05d}",
                nombre_busqueda=nombre_busqueda(apellido, nombre),
                es_seed=True,
            )
            session.add(pac)
            session.flush()
        pacientes.append(pac)
    session.commit()

    lunes = _lunes_local(ahora)
    viernes = lunes + timedelta(days=5)
    prestaciones = list(
        session.scalars(
            select(Prestacion)
            .where(Prestacion.clinica_id == cid, Prestacion.is_active.is_(True))
            .order_by(Prestacion.duracion_min)
        ).all()
    )

    if _uno(session, Bloqueo, clinica_id=cid, motivo="Mantenimiento del equipo") is None:
        miercoles = lunes + timedelta(days=2)
        session.add(
            Bloqueo(
                clinica_id=cid,
                sillon_id=sillones[2].id,
                motivo="Mantenimiento del equipo",
                inicio=_instante(miercoles, "09:00"),
                fin=_instante(miercoles, "11:00"),
            )
        )
        jueves = lunes + timedelta(days=3)
        session.add(
            Bloqueo(
                clinica_id=cid,
                profesional_id=profesionales[1].id,
                motivo="Capacitación",
                inicio=_instante(jueves, "16:00"),
                fin=_instante(jueves, "18:00"),
            )
        )
        session.commit()

    ids_pac = [p.id for p in pacientes]
    ya_hay = session.scalar(
        select(func.count())
        .select_from(Turno)
        .where(
            Turno.clinica_id == cid,
            Turno.paciente_id.in_(ids_pac),
            Turno.inicio >= lunes.astimezone(UTC),
            Turno.inicio < viernes.astimezone(UTC),
        )
    )
    creados = 0
    if not ya_hay:
        antes = lunes.astimezone(UTC) - timedelta(days=1)
        k = 0
        for dia_n in range(5):
            dia = lunes + timedelta(days=dia_n)
            for ip, i_s, hhmm, ipr, origen in PLAN:
                if (dia_n + ip) % 5 == 4 and hhmm >= "14:00":
                    continue  # tardes más livianas para que haya huecos visibles
                datos = {
                    "profesional_id": profesionales[ip].id,
                    "sillon_id": sillones[i_s].id,
                    "paciente_id": ids_pac[k % len(ids_pac)],
                    "prestacion_id": prestaciones[ipr % len(prestaciones)].id,
                    "inicio": _instante(dia, hhmm),
                }
                k += 1
                try:
                    turno = crear_turno(session, cid, datos, antes, origen=origen)
                except TurnoNoDisponible:
                    continue
                creados += 1
                if turno.fin <= ahora:
                    destino = "ausente" if k % 7 == 0 else "asistido"
                    transicionar_turno(session, cid, turno.id, destino, admin.id, None, ahora)
                elif k % 3 == 0:
                    transicionar_turno(session, cid, turno.id, "confirmado", admin.id, None, ahora)
        # un sobreturno el miércoles a media mañana
        miercoles = lunes + timedelta(days=2)
        try:
            crear_turno(
                session,
                cid,
                {
                    "profesional_id": profesionales[0].id,
                    "sillon_id": sillones[0].id,
                    "paciente_id": ids_pac[-1],
                    "prestacion_id": prestaciones[0].id,
                    "inicio": _instante(miercoles, "11:15"),
                    "sobreturno": True,
                    "motivo_sobreturno": "Urgencia: dolor agudo",
                },
                antes,
            )
            creados += 1
        except TurnoNoDisponible:
            pass
    return {
        "sillones": len(sillones),
        "profesionales": len(profesionales),
        "turnos_creados": creados,
    }


def main() -> None:
    engine = create_engine_for_url(os.environ["DATABASE_URL"])
    with create_session_factory(engine)() as session:
        print(seed_demo_agenda(session))


if __name__ == "__main__":
    main()
