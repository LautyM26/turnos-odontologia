"""Evidencia visual de C-20 (rediseño): claro/oscuro × desktop/móvil sobre la base de demo.

Requisitos: backend + frontend corriendo y seeds de demo aplicados. Solo datos sintéticos.
Variables: ``E2E_BASE_URL`` (default http://localhost:5173), ``E2E_API_URL`` (default
http://localhost:8000), ``E2E_PASSWORD`` (= ``SEED_DEMO_PASSWORD``), ``E2E_OUT`` (default
openspec/changes/archive/2026-11-17-rediseno-visual/evidencias). Crea una reserva pública sintética para el enlace.

Uso: ``python scripts/e2e/rediseno_evidencias.py``. Sale con código 1 si falla algún paso.
"""

import json
import os
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")
API = os.environ.get("E2E_API_URL", "http://localhost:8000")
PASSWORD = os.environ["E2E_PASSWORD"]
OUT = Path(os.environ.get("E2E_OUT", "openspec/changes/archive/2026-11-17-rediseno-visual/evidencias"))
SLUG = "clinica-piloto"


def api(metodo: str, ruta: str, cuerpo: dict | None = None) -> object:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    pedido = urllib.request.Request(
        API + ruta,
        data=datos,
        method=metodo,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido) as r:
        return json.loads(r.read())


def reserva_sintetica() -> str:
    cat = api("GET", f"/api/public/clinicas/{SLUG}")
    prestacion, profesional = (
        cat["prestaciones"][0]["id"],
        cat["profesionales"][0]["id"],
    )
    desde = datetime.now(UTC) + timedelta(days=2)
    q = f"profesional_id={profesional}&prestacion_id={prestacion}&desde={desde.isoformat()}&hasta={(desde + timedelta(days=7)).isoformat()}"
    huecos = api("GET", f"/api/public/clinicas/{SLUG}/huecos?{q.replace('+', '%2B')}")
    creada = api(
        "POST",
        f"/api/public/clinicas/{SLUG}/reservas",
        {
            "profesional_id": profesional,
            "prestacion_id": prestacion,
            "inicio": huecos[-1]["inicio"],
            "dni": "39000999",
            "nombre": "Demo",
            "apellido": "Reprograma",
            "email": "reprograma@ejemplo.test",
            "acepta_privacidad": True,
        },
    )
    return creada["token"]


def capturar(page: Page, nombre: str, completa: bool = True) -> None:
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{nombre}.png"), full_page=completa)


def recorrido(page: Page, sufijo: str, token: str, movil: bool) -> None:
    page.goto(BASE + "/")
    expect(
        page.get_by_role("heading", level=1, name="Turnos Odontología")
    ).to_be_visible()
    # Recorre la landing para que el reveal marque cada bloque como visible.
    for y in range(0, 6000, 500):
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(80)
    page.evaluate("window.scrollTo(0, 0)")
    capturar(page, f"landing-{sufijo}")
    page.goto(BASE + "/login")
    capturar(page, f"login-{sufijo}", completa=False)
    page.goto(f"{BASE}/reserva/{token}")
    expect(page.get_by_role("link", name="Reprogramar")).to_be_visible()
    capturar(page, f"comprobante-{sufijo}")
    page.get_by_role("link", name="Reprogramar").click()
    expect(page.get_by_role("heading", name="Reprogramar turno")).to_be_visible()
    capturar(page, f"reprogramar-{sufijo}")
    page.goto(f"{BASE}/reservar/{SLUG}")
    page.get_by_label("Prestación").select_option(index=1)
    page.get_by_label("Profesional").select_option(index=1)
    expect(page.get_by_role("heading", name="Horarios disponibles")).to_be_visible()
    capturar(page, f"reserva-{sufijo}")
    page.goto(BASE + "/privacidad")
    capturar(page, f"privacidad-{sufijo}", completa=False)
    page.goto(BASE + "/login")
    page.get_by_label("Email").fill("odontologo@clinica-piloto.test")
    page.get_by_label("Contraseña").fill(PASSWORD)
    page.get_by_role("button", name="Ingresar").click()
    page.wait_for_url("**/pacientes")
    capturar(page, f"pacientes-{sufijo}", completa=False)
    page.goto(BASE + "/agenda")
    expect(page.get_by_role("button", name="Actualizar agenda")).to_be_visible()
    capturar(page, f"agenda-{sufijo}", completa=False)
    if not movil:
        page.goto(BASE + "/pacientes/7/odontograma")
        capturar(page, f"odontograma-{sufijo}")
        page.goto(BASE + "/pacientes/7/evoluciones")
        capturar(page, f"evoluciones-{sufijo}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token = reserva_sintetica()
    fallas = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for tema in ("light", "dark"):
            for movil in (False, True):
                vista = (
                    {"width": 390, "height": 844}
                    if movil
                    else {"width": 1440, "height": 900}
                )
                ctx = navegador.new_context(
                    viewport=vista,
                    is_mobile=movil,
                    locale="es-AR",
                    timezone_id="America/Argentina/Buenos_Aires",
                    color_scheme=tema,
                )
                sufijo = f"{'claro' if tema == 'light' else 'oscuro'}-{'movil' if movil else 'desktop'}"
                try:
                    recorrido(ctx.new_page(), sufijo, token, movil)
                    print(f"[OK] {sufijo}")
                except Exception as e:  # noqa: BLE001 (reporta y sigue con la próxima combinación)
                    fallas += 1
                    print(f"[FALLA] {sufijo}: {e}")
                ctx.close()
        navegador.close()
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
