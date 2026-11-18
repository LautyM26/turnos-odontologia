"""Capturas reales de la app para la landing (C-20 tarea 2.1). Solo datos sintéticos (regla dura 14).

Requisitos: backend y frontend corriendo, ``seed_demo_clinica.py`` y ``seed_demo_agenda.py`` aplicados.
Variables: ``E2E_BASE_URL`` (default http://localhost:5173) y ``E2E_PASSWORD`` (= ``SEED_DEMO_PASSWORD``).
Salida: ``frontend/public/landing/`` (agenda.png, semana.png, reserva-movil.png), tema claro.

Uso: ``python scripts/e2e/capturas_landing.py``.
"""

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")
PASSWORD = os.environ["E2E_PASSWORD"]
OUT = Path("frontend/public/landing")
LIMITE = 250 * 1024


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        comun = {
            "locale": "es-AR",
            "timezone_id": "America/Argentina/Buenos_Aires",
            "color_scheme": "light",
        }

        escritorio = navegador.new_context(
            viewport={"width": 1440, "height": 900}, **comun
        )
        page = escritorio.new_page()
        page.goto(f"{BASE}/login")
        page.get_by_label("Email").fill("recepcion@clinica-piloto.test")
        page.get_by_label("Contraseña").fill(PASSWORD)
        page.get_by_role("button", name="Ingresar").click()
        page.wait_for_url("**/pacientes")
        page.goto(f"{BASE}/agenda")
        expect(page.get_by_role("button", name="Actualizar agenda")).to_be_visible()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "agenda.png"))
        page.get_by_role("button", name="Semana", exact=True).click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "semana.png"))

        movil = navegador.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            is_mobile=True,
            **comun,
        )
        page = movil.new_page()
        page.goto(f"{BASE}/reservar/clinica-piloto")
        prestacion = page.get_by_label("Prestación")
        prestacion.select_option(index=1)
        page.get_by_label("Profesional").select_option(index=1)
        page.get_by_role(
            "heading", name="Horarios disponibles"
        ).scroll_into_view_if_needed()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "reserva-movil.png"))
        navegador.close()

    for archivo in sorted(OUT.glob("*.png")):
        tamano = archivo.stat().st_size
        print(
            f"{archivo.name}: {tamano // 1024} KB{'  (supera 250 KB)' if tamano > LIMITE else ''}"
        )


if __name__ == "__main__":
    main()
