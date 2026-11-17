"""E2E de C-16 contra la API real por HTTP (gateway fake). Datos sintéticos del seed demo."""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "backend"))
from app.domain.agenda.models import (  # noqa: E402
    FranjaHoraria, Prestacion, Profesional, ProfesionalSillon, SillonRecurso,
)
from app.domain.pacientes.models import Paciente  # noqa: E402

API = "http://127.0.0.1:8011"
HMAC_KEY = os.environ["WHATSAPP_WEBHOOK_HMAC_KEY"]


def paso(titulo, r=None, extra=None):  # type: ignore[no-untyped-def]
    print(f"\n### {titulo}")
    if r is not None:
        q = r.request.url.query.decode()
        print(f"{r.request.method} {r.request.url.path}{'?' + q if q else ''} -> {r.status_code}")
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:700])
        except Exception:
            print(r.text[:200])
    if extra is not None:
        print(extra)


engine = create_engine(os.environ["DATABASE_URL"])
with Session(engine) as s:
    prof = s.scalars(select(Profesional)).first()
    sillon = s.scalars(select(SillonRecurso)).first()
    prest = s.scalars(select(Prestacion).where(Prestacion.is_active.is_(True))).first()
    pacs = s.scalars(select(Paciente).where(Paciente.telefono.is_not(None)).order_by(Paciente.id)).all()[:3]
    if not s.scalars(select(ProfesionalSillon).where(ProfesionalSillon.profesional_id == prof.id)).first():
        s.add(ProfesionalSillon(clinica_id=prof.clinica_id, profesional_id=prof.id, sillon_id=sillon.id))
    if not s.scalars(select(FranjaHoraria).where(FranjaHoraria.profesional_id == prof.id)).first():
        s.add_all(FranjaHoraria(clinica_id=prof.clinica_id, profesional_id=prof.id, dia_semana=d,
                                inicio_min=0, fin_min=1440) for d in range(1, 8))
    s.commit()
    A, B, C = [(p.id, p.telefono, p.nombre) for p in pacs]
    clinica = prof.clinica_id
    PROF, SILLON, PREST = prof.id, sillon.id, prest.id

c = httpx.Client(base_url=API, timeout=30)
recep = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
    "email": "recepcion@clinica-piloto.test", "password": os.environ["SEED_DEMO_PASSWORD"]}).json()["access_token"]}
base = (datetime.now(UTC) + timedelta(hours=20)).replace(minute=0, second=0, microsecond=0)


def turno(paciente_id, inicio):  # type: ignore[no-untyped-def]
    return c.post("/api/turnos", headers=recep, json={
        "profesional_id": PROF, "sillon_id": SILLON, "paciente_id": paciente_id,
        "prestacion_id": PREST, "inicio": inicio.isoformat()})


def job():  # type: ignore[no-untyped-def]
    r = subprocess.run([sys.executable, "-m", "app.jobs.lista_espera"], cwd=os.path.join(ROOT, "backend"),
                       capture_output=True, text=True, env=os.environ)
    return (r.stdout + r.stderr[-300:]).strip()


def whatsapp(tel, texto, ident):  # type: ignore[no-untyped-def]
    cuerpo = json.dumps({"event": "message", "session": f"clinica-{clinica}", "payload": {
        "id": ident, "from": tel.lstrip("+") + "@c.us", "fromMe": False, "body": texto}}).encode()
    return c.post("/api/webhooks/whatsapp", content=cuerpo, headers={
        "X-Webhook-Hmac": hmac.new(HMAC_KEY.encode(), cuerpo, hashlib.sha512).hexdigest()})


print("pacientes sintéticos:", {"A": A[2], "B": B[2], "C": C[2]})
t_a = turno(A[0], base)
paso("1. Turno de A para dentro de ~20 h (será el hueco)", t_a)
t_viejo = turno(B[0], base + timedelta(days=5))
paso("2. Turno de B en 5 días (lo quiere adelantar)", t_viejo)
r = c.post("/api/lista-espera", headers=recep, json={"paciente_id": B[0], "prestacion_id": PREST,
           "prioridad": 5, "turno_a_adelantar_id": t_viejo.json()["id"]})
paso("3. B a la lista de espera (prioridad 5, adelantar)", r)
r = c.post("/api/lista-espera", headers=recep, json={"paciente_id": C[0], "prestacion_id": PREST})
paso("4. C a la lista de espera (prioridad 0)", r)
r = c.post(f"/api/turnos/{t_a.json()['id']}/transicion", headers=recep, json={"estado": "cancelado"})
paso("5. A cancela su turno en el mostrador", r)
paso("6. Corre el job de la lista de espera", extra=job())
paso("7. Bandeja de ofertas", c.get("/api/lista-espera/bandeja", headers=recep))
paso("8. B responde '1' por WhatsApp (evento firmado)", whatsapp(B[1], "1", "true_e2e16_B1"))
paso("8b. B repite 'si' (otro mensaje)", whatsapp(B[1], "si", "true_e2e16_B2"))
paso("9. Turno viejo de B", c.get(f"/api/turnos/{t_viejo.json()['id']}", headers=recep))
with Session(engine) as s:
    nuevos = s.execute(text("SELECT id, paciente_id, inicio, origen, estado FROM turno "
                            "WHERE origen='lista_espera'")).all()
paso("9b. Turnos creados por la lista", extra=nuevos)
paso("10. Corre el job otra vez (cascada: hueco del turno viejo de B)", extra=job())
paso("11. Bandeja", c.get("/api/lista-espera/bandeja", headers=recep))
paso("12. C responde 'no'", whatsapp(C[1], "no", "true_e2e16_C1"))
hoy = datetime.now(UTC).date()
paso("13. Métricas", c.get(f"/api/lista-espera/metricas?desde={hoy}&hasta={hoy + timedelta(days=7)}",
                            headers=recep))
with Session(engine) as s:
    msgs = s.execute(text("SELECT telefono, direccion, plantilla, estado, costo_ars FROM mensaje_whatsapp "
                          "ORDER BY id")).all()
paso("14. Mensajes de WhatsApp registrados", extra="\n".join(map(str, msgs)))
