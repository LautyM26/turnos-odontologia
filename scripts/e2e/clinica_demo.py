"""E2E real de C-10 (clinica-frontend) con Python Playwright. Sin mocks: UI + API + PostgreSQL.

Requisitos: backend y frontend corriendo, migraciones y ``backend/scripts/seed_demo_clinica.py``
aplicados. Variables (nada se hardcodea acá):

- ``E2E_BASE_URL``  frontend (default http://localhost:5173)
- ``E2E_API_URL``   backend directo, solo para provocar un conflicto 409 (default http://localhost:8000)
- ``E2E_PASSWORD``  el mismo valor de ``SEED_DEMO_PASSWORD`` usado al sembrar
- ``E2E_PACIENTE`` "Apellido, Nombre" del paciente sin odontograma (default "Sintético, Demo Uno")
- ``E2E_OUT``       carpeta de capturas (default openspec/changes/archive/2026-11-17-clinica-frontend/evidencias)

Uso: ``python scripts/e2e/clinica_demo.py``. Sale con código 1 si falla algún paso.
"""

import os
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:5173")
API = os.environ.get("E2E_API_URL", "http://localhost:8000")
PASSWORD = os.environ["E2E_PASSWORD"]
OUT = Path(os.environ.get("E2E_OUT", "openspec/changes/archive/2026-11-17-clinica-frontend/evidencias"))
ODONTOLOGO = "odontologo@clinica-piloto.test"
RECEPCION = "recepcion@clinica-piloto.test"
PACIENTE = os.environ.get("E2E_PACIENTE", "Sintético, Demo Uno")

resultados: list[tuple[str, bool, str]] = []


def paso(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append((nombre, ok, detalle))
    print(f"[{'OK' if ok else 'FALLA'}] {nombre} {detalle}")


def foto(page: Page, nombre: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{nombre}.png"), full_page=True)


def login(page: Page, email: str) -> None:
    page.goto(f"{BASE}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Contraseña").fill(PASSWORD)
    page.get_by_role("button", name="Ingresar").click()
    expect(page.get_by_role("heading", name="Pacientes")).to_be_visible()


def abrir_paciente(page: Page, apellido_nombre: str) -> None:
    page.get_by_role("link", name=apellido_nombre).click()
    expect(page.get_by_role("navigation", name="Secciones del paciente")).to_be_visible()


def correr(page: Page, errores: list[str]) -> None:
    # --- 1. login odontólogo y listado ---------------------------------------------------
    page.goto(f"{BASE}/login")
    foto(page, "01-login")
    login(page, ODONTOLOGO)
    expect(page.get_by_text(ODONTOLOGO)).to_be_visible()
    expect(page.get_by_text("Odontólogo", exact=True)).to_be_visible()
    foto(page, "02-pacientes")
    paso("login odontólogo + listado de pacientes", True)

    # --- 2. paciente → ficha ---------------------------------------------------------------
    abrir_paciente(page, PACIENTE)
    expect(page.get_by_text("Consentimiento de datos: otorgado")).to_be_visible()
    foto(page, "03-ficha")
    paso("detalle del paciente con consentimiento otorgado", True)

    # --- 3. odontograma: marcar 16 O caries a realizar y guardar ---------------------------
    page.get_by_role("link", name="Odontograma").click()
    expect(page.get_by_text("Sin odontograma registrado todavía")).to_be_visible()
    paso("odontograma versión 0 permanente (32 piezas)", page.get_by_role("button", name="Pieza", exact=False).count() >= 32)
    page.locator('#pieza-16 [data-cara="O"]').click()
    panel = page.get_by_role("dialog", name="Pieza 16")
    expect(panel).to_be_visible()
    expect(panel.get_by_label("Cara O")).to_be_focused()
    panel.get_by_label("Cara O").select_option("caries")
    panel.get_by_label("Registro de la cara O").select_option("a_realizar")
    foto(page, "04-panel-pieza-16")
    panel.get_by_role("button", name="Listo").click()
    expect(page.get_by_role("button", name="Pieza 16: caries a realizar en O")).to_be_visible()
    expect(page.get_by_text("Cambios sin guardar")).to_be_visible()
    page.get_by_role("button", name="Guardar odontograma").click()
    expect(page.get_by_text("Versión 1 · guardada por")).to_be_visible()
    foto(page, "05-odontograma-guardado")
    paso("odontograma: marcar 16 O caries a realizar y guardar versión 1", True)

    # --- 4. conflicto 409: otro profesional guarda y mi borrador queda viejo ---------------
    page.locator('#pieza-26 [data-cara="V"]').click()
    panel = page.get_by_role("dialog", name="Pieza 26")
    panel.get_by_label("Cara V").select_option("obturacion")
    panel.get_by_role("button", name="Listo").click()
    pid = page.url.split("/pacientes/")[1].split("/")[0]
    api = page.context.request
    tok = api.post(
        f"{API}/api/auth/login", data={"email": ODONTOLOGO, "password": PASSWORD}
    ).json()["access_token"]
    resp = api.post(
        f"{API}/api/pacientes/{pid}/odontograma",
        headers={"Authorization": f"Bearer {tok}"},
        data={
            "version_esperada": 1,
            "denticion": "permanente",
            "piezas": {"36": {"caras": {"M": {"codigo": "caries", "registro": "existente"}}}},
        },
    )
    assert resp.status == 201, resp.text()
    page.get_by_role("button", name="Guardar odontograma").click()
    alerta = page.get_by_role("alert")
    expect(alerta).to_contain_text("Hay una versión más nueva del odontograma")
    expect(page.get_by_role("button", name="Pieza 26: obturación existente en V")).to_be_visible()
    foto(page, "06-conflicto-409")
    page.get_by_role("button", name="Recargar versión vigente").click()
    page.get_by_role("button", name="Descartar y recargar").click()
    expect(page.get_by_text("Versión 2 · guardada por")).to_be_visible()
    expect(page.get_by_role("button", name="Pieza 36: caries existente en M")).to_be_visible()
    paso("conflicto 409: aviso, borrador conservado, recarga de la versión vigente", True)

    # --- 5. evoluciones: alta + corrección ---------------------------------------------------
    page.get_by_role("link", name="Evoluciones").click()
    page.get_by_label("Texto de la evolución").fill("Control sintético de demostración")
    page.get_by_label("Pieza FDI (opcional)").select_option("16")
    page.get_by_role("button", name="Guardar evolución").click()
    expect(page.get_by_role("article").first).to_contain_text("Control sintético de demostración")
    foto(page, "07-evolucion-creada")
    antes = page.get_by_role("article").count()
    page.get_by_role("button", name="Corregir").first.click()
    form = page.get_by_role("form", name="Corregir evolución")
    form.get_by_label("Texto de la evolución").fill("Control sintético corregido")
    form.get_by_label("Motivo de la corrección").fill("Texto ajustado en la demo")
    form.get_by_role("button", name="Guardar corrección").click()
    expect(page.get_by_role("article")).to_have_count(antes + 1)
    original = page.get_by_role("article").nth(1)
    expect(original).to_contain_text("Control sintético de demostración")
    expect(original).to_contain_text("Corregida")
    expect(page.get_by_role("article").first).to_contain_text("Corrige a la evolución del")
    foto(page, "08-evolucion-corregida")
    paso("evolución nueva y corrección (la original queda Corregida, una entrada más)", True)

    # --- 6. adjuntos: inválido y válido ------------------------------------------------------
    page.get_by_role("link", name="Adjuntos").click()
    with tempfile.TemporaryDirectory() as tmp:
        malo = Path(tmp) / "informe.docx"
        malo.write_bytes(b"no soy un pdf")
        page.get_by_label("Archivo").set_input_files(str(malo))
        page.get_by_role("button", name="Subir adjunto").click()
        expect(page.get_by_role("alert")).to_contain_text("Solo se aceptan fotos JPG/PNG o PDF")
        foto(page, "09-adjunto-invalido")
        bueno = Path(tmp) / "estudio.pdf"
        bueno.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
        page.get_by_label("Archivo").set_input_files(str(bueno))
        page.get_by_role("button", name="Subir adjunto").click()
        expect(page.get_by_text("Adjunto subido")).to_be_visible()
    foto(page, "10-adjunto-subido")
    paso("adjunto inválido rechazado en el cliente y PDF válido subido", True)

    # --- 7. layout móvil sin scroll horizontal de página -------------------------------------
    page.set_viewport_size({"width": 360, "height": 800})
    page.get_by_role("link", name="Odontograma").click()
    expect(page.get_by_role("button", name="Guardar odontograma")).to_be_visible()
    ancho = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    foto(page, "11-odontograma-360px")
    paso("360 px: sin scroll horizontal de la página", ancho[0] <= ancho[1], f"scrollWidth={ancho[0]} clientWidth={ancho[1]}")
    page.set_viewport_size({"width": 1280, "height": 900})

    # --- 8. logout ----------------------------------------------------------------------------
    page.get_by_role("button", name="Cerrar sesión").click()
    expect(page.get_by_role("heading", name="Ingresar")).to_be_visible()
    page.go_back()
    expect(page.get_by_role("heading", name="Ingresar")).to_be_visible()
    paso("logout y 'atrás' vuelve a pedir login", True)

    # --- 9. recepcionista ---------------------------------------------------------------------
    login(page, RECEPCION)
    expect(page.get_by_text("Recepcionista", exact=True)).to_be_visible()
    abrir_paciente(page, PACIENTE)
    page.get_by_role("link", name="Odontograma").click()
    expect(page.get_by_text("Sin acceso clínico: tu rol no permite ver la historia clínica")).to_be_visible()
    assert page.locator("svg[viewBox='0 0 40 40']").count() == 0
    expect(page.get_by_role("heading", name=PACIENTE)).to_be_visible()
    foto(page, "12-recepcion-sin-acceso-clinico")
    page.get_by_role("link", name="Ficha").click()
    expect(page.get_by_label("Teléfono")).to_be_visible()
    paso("recepcionista: Sin acceso clínico en odontograma, datos administrativos visibles", True)

    # --- 10. consola ----------------------------------------------------------------------------
    # 401/403/409 son respuestas deliberadas de los flujos (refresh sin sesión, recepción, conflicto)
    esperados = ("status of 401", "status of 403", "status of 409")
    inesperados = [e for e in errores if not any(x in e for x in esperados)]
    paso("consola del navegador sin errores inesperados", not inesperados, "; ".join(inesperados)[:300])
    print(f"(errores de consola esperados 401/403/409: {len(errores) - len(inesperados)})")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errores: list[str] = []
        page.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
        try:
            correr(page, errores)
        except Exception as exc:  # noqa: BLE001
            foto(page, "99-fallo")
            paso("flujo E2E", False, repr(exc)[:400])
        finally:
            browser.close()
    return 0 if all(ok for _, ok, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
