# Verify — reserva-online-publica (C-06)

Fecha: 2026-11-17. Resultado: **VERDE, revisado y archivado** el 2026-11-17.

## Entorno

- Windows 11, Docker Desktop sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.12.10 (`.venv`), pytest 9.2.0, ruff 0.17.5.
- Frontend: Node, Vite 8, React 19, TypeScript estricto, vitest 4, biome 2.
- Playwright (Python) para la prueba en navegador real; ya documentado en el README para el E2E de C-10.
- Diseño D1–D6 aprobado por el usuario el 2026-11-17 (governance ALTO). Base: `main` en `f12f5fc`.

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/ruff check backend
cd frontend && npm run build && npx vitest run
openspec validate reserva-online-publica --strict
```

## Resultados

- Backend, suite completa: **1348 passed, 0 failed, 0 skipped** (13 min 40 s; antes del change: 1284). Corrida hecha después del arreglo de la exportación.
- `ruff check backend`: limpio.
- Frontend:
  - `npm run build` (tsc estricto + vite): OK.
  - `npx vitest run`: **215 passed** (16 archivos).
  - `tsc --noEmit`: limpio.
  - `npm run lint` (biome) **ya estaba en rojo antes de este change**, con 62 errores en `main`: todos de formato por finales de línea CRLF de la copia de trabajo en Windows. Git guarda LF (`core.autocrlf`). Los archivos nuevos de C-06 pasan biome sin errores. Los 4 archivos existentes que se tocaron (`router.tsx`, `styles.css`, `client.ts`, `app-shell.test.tsx`) solo marcan CRLF, y sus versiones LF (lo que entra al repo) pasan biome limpias (`biome check --stdin-file-path`).
- Tests nuevos: **64 en backend** y **14 en frontend**.

| Archivo | Tests | Cubre |
|---|---|---|
| unit/test_reserva_schemas.py | 14 | normalización (DNI, email, teléfono E.164, inicio UTC); privacidad false, null o ausente; sin contacto; `sobreturno`/`clinica_id` extra → error |
| integration/test_migracion_013.py | 15 | columnas, UNIQUE/CHECK del slug (23514/23505), default válido, slug del seed, UNIQUE parcial del token, coherencia del actor (23514), filas previas `usuario`, downgrade/re-upgrade, único head |
| integration/test_turno_transicion_db.py | +1 | transición `paciente_enlace` sin usuario |
| integration/test_reserva_publica_servicio.py | 14 | paciente nuevo sin usuario y auditado como `sistema`; DNI existente sin tocar la ficha; paciente de baja 422; tope por DNI y liberación al cancelar; segundo sillón; ocupado 409; catálogo solo con profesionales con horario; slug 404; fuera de horario 409 y sin horario 422; pasado 422; ver/cancelar con token e historial; cancelar tarde, dos veces o con token inválido |
| integration/test_reserva_publica_concurrencia.py | 2 | 5 reservas simultáneas del mismo hueco con un sillón dan 1 ganadora y 4 `409`; el mismo DNI nuevo en paralelo genera un solo paciente |
| integration/test_reserva_publica_api.py | 18 | un test por escenario de `public-booking`, más funcionamiento sin JWT (ignora la sesión de staff), aislamiento por slug y ráfaga → 429 con `Retry-After` |
| frontend tests/reserva-api.test.ts | 6 | URLs, cuerpo, `desde` ISO; **nunca** `Authorization` ni `X-Clinica-Id` con sesión de staff abierta; 404/409/422/429 → `ApiError` |
| frontend tests/reserva.test.tsx | 8 | flujo completo → comprobante; 409 recarga huecos y conserva los datos; 422 asociado al campo (`aria-invalid` + descripción); slug 404; agrupación por día en la zona de la clínica; sin `localStorage`; cancelar con diálogo; token 404 |

### Hallazgos durante el apply

- **Bug real encontrado por un test del equipo:** `test_exportacion_api.py::test_ningun_csv_tiene_columnas_de_secretos` (C-18) falló porque la exportación vuelca todas las columnas de `turno` y ahora incluía `token_publico_hash`. Se agregó la columna a `COLUMNAS_EXCLUIDAS` del exportador, que es el punto de extensión previsto. La exportación vuelve a pasar sus 17 tests.
- **Ajuste a D1:** `clinica.slug` tiene en la base un default al azar con formato válido (`c-` + 12 hex), en lugar de completarse solo en la migración. Así, cualquier alta de clínica (seeds, tests, futuros changes) tiene slug sin cambios. `seed_core` fija `clinica-piloto`.
- **Supuesto confirmado en los tests:** un profesional no puede tener dos turnos simultáneos aunque haya otro sillón libre (exclusion constraint por profesional). Dos tests de API asumían lo contrario y se corrigieron; el código ya era correcto.
- **Rate limit:** un cuerpo inválido da 422 en la validación de FastAPI **antes** del limiter, así que no consume cupo. El límite cuenta pedidos que llegan al endpoint (por ejemplo, un slug inexistente sí cuenta).

## Pruebas de mutación

- **Sin tope por DNI** (umbral a 10⁶): fallan `test_tope_de_dos_reservas_por_dni_y_cancelada_libera` y `test_tercera_reserva_mismo_dni_409`.
- **Sin el filtro "profesional con horario"** del catálogo y la reserva: fallan `test_catalogo_solo_lista_profesionales_con_horario`, `test_fuera_de_horario_409_y_sin_horario_422` y `test_profesional_sin_horario_no_se_ofrece`.

En ambos casos se restauró el código y se volvió a correr en verde.

## Prueba manual (uvicorn + Vite + navegador real)

Base de desarrollo migrada a la 013 y `seed_core` (slug `clinica-piloto`). Llamadas a través del proxy de Vite (`:5173/api`), como el navegador:

```
0) página /reservar/clinica-piloto (vite): 200 html
1) catálogo vía proxy: 200 {"clinica": "Clinica Piloto Sintetica", "prest": 3, "profs": ["Profesional Ejemplo (seed)"]}
2) huecos 7 días: 200 {"n": 148, "campos": ["fin", "inicio"]}
3) sin privacidad: 422
4) reserva: 201 {"estado": "reservado", "cancelable": true, "token_len": 43}
5) mismo hueco otro DNI: 409 {"detail": "Horario no disponible"}
6) ver con token: 200 (sin datos del paciente)
7) staff ve el turno (GET /api/turnos/{id}): 200 {"origen": "enlace", "estado": "reservado", "sillon_id": 1}
8) cancelar con token: 200 {"estado": "cancelado", "cancelable": false}
9) hueco liberado: vuelve a aparecer
10) historial: reservado->cancelado paciente_enlace null
```

**Navegador (Playwright, Chromium)**, a 1280 px y 390 px: elegir prestación y profesional, elegir un horario, completar datos, aceptar privacidad, confirmar, comprobante, cancelar con diálogo, "Turno cancelado". Además, `/reservar/no-existe` → "Enlace no encontrado". Capturas en `evidencias/`.

La revisión visual de las capturas encontró y corrigió dos problemas:

- `capitalize` ponía en mayúscula cada palabra ("17 De Noviembre"); se cambió a `first-letter:uppercase`.
- En móvil el formulario quedaba lejos del horario elegido; se agregó un scroll al formulario que respeta `prefers-reduced-motion`, y el día dentro del resumen del turno.

## Diseño visual

Se siguió D6: el sistema visual sobrio de C-10 (tokens neutros, `system-ui`, `Aviso`, `DialogoConfirmacion`).

- Se aplicó el checklist de accesibilidad: labels, `aria-invalid`/`aria-describedby`, `aria-live`, `aria-pressed` en los horarios, foco visible y `<dialog>` nativo.
- Motion mínimo: transición de color en los horarios y una entrada de 150 ms del formulario, anulada por `prefers-reduced-motion`.
- No se usó la cadena de animación fuerte del CLAUDE.md global porque D6, aprobado, prioriza la identidad clínica existente.

## Trazabilidad

- KB `04`: `Clinica.slug`, reserva por enlace en Turno (`origen`, `token_publico_hash`) y `actor_tipo` del historial.
- README: tests del change y enlace de la reserva. `docs/CONTINUAR.md`: migración 013 tomada, próxima 014, y el punto de extensión de la seña para C-12.
- `dominio-agenda`: RN-AG-05 **cubierta** (6 cubiertas · 1 parcial · 3 pendientes) y sección 4 con la reserva pública. `verificar.py dominio-agenda RN-AG RN-TU`: **OK** después del archive.
- `dominio-caja`: RN-CA-01/02 siguen pendientes, con el punto de extensión anotado. `verificar.py` → OK.

## Archivo

- Revisado por el usuario el 2026-11-17 y archivado como `2026-11-17-reserva-online-publica`: `public-booking` (9 requirements) y `public-booking-web` (3) creadas, `appointments` +1. `openspec validate --specs`: 29/29.
