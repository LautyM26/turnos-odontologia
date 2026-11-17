"""E2E manual de C-15 contra la API real por HTTP (gateway fake). Datos sintéticos."""

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

API = "http://127.0.0.1:8010"
PASS = os.environ["SEED_DEMO_PASSWORD"]
ADMIN_PASS = os.environ["SEED_ADMIN_PASSWORD"]
HMAC_KEY = os.environ["WHATSAPP_WEBHOOK_HMAC_KEY"]


def paso(titulo: str, r: httpx.Response | None = None, extra: object = None) -> None:
    print(f"\n### {titulo}")
    if r is not None:
        print(f"{r.request.method} {r.request.url.path}{'?' + r.request.url.query.decode() if r.request.url.query else ''} -> {r.status_code}")
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:900])
        except Exception:
            print(r.text[:300])
    if extra is not None:
        print(extra)


engine = create_engine(os.environ["DATABASE_URL"])
with Session(engine) as s:
    prof = s.scalars(select(Profesional)).first()
    sillon = s.scalars(select(SillonRecurso)).first()
    prest = s.scalars(select(Prestacion).where(Prestacion.is_active.is_(True))).first()
    pac = s.scalars(select(Paciente).where(Paciente.telefono.is_not(None))).first()
    if not s.scalars(select(ProfesionalSillon).where(
            ProfesionalSillon.profesional_id == prof.id, ProfesionalSillon.sillon_id == sillon.id)).first():
        s.add(ProfesionalSillon(clinica_id=prof.clinica_id, profesional_id=prof.id, sillon_id=sillon.id))
    if not s.scalars(select(FranjaHoraria).where(FranjaHoraria.profesional_id == prof.id)).first():
        s.add_all(FranjaHoraria(clinica_id=prof.clinica_id, profesional_id=prof.id, dia_semana=d,
                                inicio_min=0, fin_min=1440) for d in range(1, 8))
    s.commit()
    ids = dict(prof=prof.id, sillon=sillon.id, prest=prest.id, pac=pac.id, tel=pac.telefono,
               clinica=prof.clinica_id)
print("datos sintéticos:", ids)

c = httpx.Client(base_url=API, timeout=30)


def login(email: str, pw: str) -> dict[str, str]:
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


recep = login("recepcion@clinica-piloto.test", PASS)
admin = login("admin@clinica-piloto.test", ADMIN_PASS)

inicio = (datetime.now(UTC) + timedelta(hours=20)).replace(minute=0, second=0, microsecond=0)
r = c.post("/api/turnos", headers=recep, json={
    "profesional_id": ids["prof"], "sillon_id": ids["sillon"], "paciente_id": ids["pac"],
    "prestacion_id": ids["prest"], "inicio": inicio.isoformat()})
paso("1. Recepción crea un turno para dentro de ~20 h", r)
turno_id = r.json()["id"]

job = subprocess.run([sys.executable, "-m", "app.jobs.recordatorios"], cwd=os.path.join(ROOT, "backend"),
                     capture_output=True, text=True, env=os.environ)
paso("2. Corre el job de recordatorios (cron)", extra=job.stdout.strip() + job.stderr.strip()[-300:])
job2 = subprocess.run([sys.executable, "-m", "app.jobs.recordatorios"], cwd=os.path.join(ROOT, "backend"),
                      capture_output=True, text=True, env=os.environ)
paso("2b. Segunda corrida: no reenvía", extra=job2.stdout.strip())

paso("3. Mensajes del turno", c.get(f"/api/whatsapp/mensajes?turno_id={turno_id}", headers=recep))

evento = {"event": "message", "session": f"clinica-{ids['clinica']}", "engine": "WEBJS",
          "payload": {"id": "true_e2e_SI_1", "from": ids["tel"].lstrip("+") + "@c.us",
                      "fromMe": False, "body": "Sí, confirmo"}}
cuerpo = json.dumps(evento).encode()
firma = hmac.new(HMAC_KEY.encode(), cuerpo, hashlib.sha512).hexdigest()
r = c.post("/api/webhooks/whatsapp", content=cuerpo,
           headers={"X-Webhook-Hmac": firma, "Content-Type": "application/json"})
paso("4. El gateway entrega la respuesta 'Sí, confirmo' firmada (sin JWT)", r)
r = c.post("/api/webhooks/whatsapp", content=cuerpo,
           headers={"X-Webhook-Hmac": firma, "Content-Type": "application/json"})
paso("4b. Mismo evento repetido", r)
r = c.post("/api/webhooks/whatsapp", content=cuerpo,
           headers={"X-Webhook-Hmac": "0" * 128, "Content-Type": "application/json"})
paso("4c. Firma inválida", r)

paso("5. Turno después de la respuesta", c.get(f"/api/turnos/{turno_id}", headers=recep))
with Session(engine) as s:
    hist = s.execute(text("SELECT desde, hacia, actor_tipo, actor_usuario_id FROM turno_transicion "
                          "WHERE turno_id=:t"), {"t": turno_id}).all()
paso("5b. Historial de transiciones", extra=hist)

evento2 = {"event": "message", "session": f"clinica-{ids['clinica']}",
           "payload": {"id": "true_e2e_hola", "from": ids["tel"].lstrip("+") + "@c.us",
                       "fromMe": False, "body": "hola, ¿a qué hora era?"}}
cuerpo2 = json.dumps(evento2).encode()
r = c.post("/api/webhooks/whatsapp", content=cuerpo2, headers={
    "X-Webhook-Hmac": hmac.new(HMAC_KEY.encode(), cuerpo2, hashlib.sha512).hexdigest()})
paso("6. Texto libre del paciente", r)
r = c.get("/api/whatsapp/fallos", headers=recep)
paso("6b. Bandeja de fallos (recepción)", r)
fallo = r.json()[0]["id"]
paso("6c. Recepción resuelve el fallo", c.post(f"/api/whatsapp/fallos/{fallo}/resolver", headers=recep))

hoy = datetime.now(UTC).date()
paso("7. Costos del día (admin)", c.get(f"/api/whatsapp/costos?desde={hoy}&hasta={hoy + timedelta(days=1)}",
                                         headers=admin))
paso("8. Sesión (admin)", c.get("/api/whatsapp/sesion", headers=admin))
paso("8b. Reconectar como recepción", c.post("/api/whatsapp/sesion/reconectar", headers=recep))
r = c.post("/api/whatsapp/sesion/reconectar", headers=admin)
paso("8c. Reconectar como admin (fake -> escanear_qr)", r)
