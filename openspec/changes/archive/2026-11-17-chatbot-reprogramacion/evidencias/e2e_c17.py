"""E2E de C-17 contra la API real por HTTP (gateway fake). Datos sintéticos del seed demo."""

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

API = "http://127.0.0.1:8012"
HMAC_KEY = os.environ["WHATSAPP_WEBHOOK_HMAC_KEY"]


def paso(titulo, r=None, extra=None):  # type: ignore[no-untyped-def]
    print(f"\n### {titulo}")
    if r is not None:
        print(f"{r.request.method} {r.request.url.path} -> {r.status_code}")
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:600])
        except Exception:
            print(r.text[:200])
    if extra is not None:
        print(extra)


engine = create_engine(os.environ["DATABASE_URL"])
with Session(engine) as s:
    prof = s.scalars(select(Profesional)).first()
    sillon = s.scalars(select(SillonRecurso)).first()
    prest = s.scalars(select(Prestacion).where(Prestacion.is_active.is_(True))).first()
    pac = s.scalars(select(Paciente).where(Paciente.telefono.is_not(None)).order_by(Paciente.id)).first()
    if not s.scalars(select(ProfesionalSillon).where(ProfesionalSillon.profesional_id == prof.id)).first():
        s.add(ProfesionalSillon(clinica_id=prof.clinica_id, profesional_id=prof.id, sillon_id=sillon.id))
    if not s.scalars(select(FranjaHoraria).where(FranjaHoraria.profesional_id == prof.id)).first():
        s.add_all(FranjaHoraria(clinica_id=prof.clinica_id, profesional_id=prof.id, dia_semana=d,
                                inicio_min=0, fin_min=1440) for d in range(1, 8))
    s.commit()
    PROF, SILLON, PREST, CLINICA = prof.id, sillon.id, prest.id, prof.clinica_id
    PAC, TEL = pac.id, pac.telefono

c = httpx.Client(base_url=API, timeout=30)
recep = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
    "email": "recepcion@clinica-piloto.test", "password": os.environ["SEED_DEMO_PASSWORD"]}).json()["access_token"]}


def whatsapp(texto, ident):  # type: ignore[no-untyped-def]
    cuerpo = json.dumps({"event": "message", "session": f"clinica-{CLINICA}", "payload": {
        "id": ident, "from": TEL.lstrip("+") + "@c.us", "fromMe": False, "body": texto}}).encode()
    return c.post("/api/webhooks/whatsapp", content=cuerpo, headers={
        "X-Webhook-Hmac": hmac.new(HMAC_KEY.encode(), cuerpo, hashlib.sha512).hexdigest()})


def ultimo_texto():  # type: ignore[no-untyped-def]
    with Session(engine) as s:
        return s.scalar(text("SELECT texto FROM mensaje_whatsapp WHERE direccion='saliente' "
                             "ORDER BY id DESC LIMIT 1"))


inicio = (datetime.now(UTC) + timedelta(hours=20)).replace(minute=0, second=0, microsecond=0)
t = c.post("/api/turnos", headers=recep, json={"profesional_id": PROF, "sillon_id": SILLON,
           "paciente_id": PAC, "prestacion_id": PREST, "inicio": inicio.isoformat()})
paso("1. Recepción crea el turno de Demo Uno (~20 h)", t)
r = subprocess.run([sys.executable, "-m", "app.jobs.recordatorios"], cwd=os.path.join(ROOT, "backend"),
                   capture_output=True, text=True, env=os.environ)
paso("2. Job de recordatorios", extra=r.stdout.strip())
paso("3. El paciente responde '3' (reprogramar)", whatsapp("3", "true_e2e17_1"))
paso("3b. Opciones que recibió", extra=ultimo_texto())
paso("4. Elige '2'", whatsapp("2", "true_e2e17_2"))
paso("4b. Pedido de confirmación", extra=ultimo_texto())
paso("5. Confirma 'si'", whatsapp("si", "true_e2e17_3"))
paso("5b. Respuesta", extra=ultimo_texto())
paso("6. Turno original", c.get(f"/api/turnos/{t.json()['id']}", headers=recep))
with Session(engine) as s:
    filas = s.execute(text("SELECT id, inicio, origen, estado FROM turno ORDER BY id")).all()
    conv = s.execute(text("SELECT estado, resultado, turno_id, turno_nuevo_id FROM conversacion_wa")).all()
    tr = s.execute(text("SELECT turno_id, desde, hacia, actor_tipo, motivo FROM turno_transicion")).all()
paso("6b. Turnos / conversación / historial", extra=f"{filas}\n{conv}\n{tr}")

# --- Enlace web (token de C-06) ---
dia = (datetime.now(UTC) + timedelta(days=3)).replace(hour=13, minute=0, second=0, microsecond=0)
res = c.post("/api/public/clinicas/clinica-piloto/reservas", json={
    "profesional_id": PROF, "prestacion_id": PREST, "inicio": dia.isoformat(), "dni": "93456789",
    "nombre": "Enlace", "apellido": "Sintetico", "telefono": "+5491100000077",
    "acepta_privacidad": True})
paso("7. Reserva online (C-06)", res)
token = res.json()["token"]
ops = c.get(f"/api/public/reservas/{token}/opciones")
paso("8. Opciones por enlace", ops)
paso("9. Reprogramar a la 1ª opción por enlace",
     c.post(f"/api/public/reservas/{token}/reprogramar", json={"inicio": ops.json()[0]["inicio"]}))
paso("10. El mismo token muestra el turno nuevo", c.get(f"/api/public/reservas/{token}"))
