# Verify — transiciones-estado-turno (C-05b)

Fecha: 2026-11-16. Resultado: **VERDE, listo para archivar** (no se archivó ni se hizo commit).

## Entorno

- Windows 11, Docker Desktop (Server 29.9.3) sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.12.10 (venv `.venv` en la raíz del repo), pytest 9.2.0, ruff 0.17.5.
- Diseño D1–D6 aprobado por el usuario antes del apply (governance CRÍTICO).

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/ruff check backend
openspec validate transiciones-estado-turno --strict
```

## Resultados

- Baseline previo al change: **530 passed**.
- Con el change: **615 passed, 0 failed, 0 skipped** (7 min 44 s). No hubo regresiones en C-01…C-08 ni en `crear-turno-sin-solapamientos`. El downgrade de las migraciones 004 y 005 ahora pasa también por la 006 y sigue en verde.
- Tests nuevos: **85**.

| Archivo | Tests | Escenarios de la spec que cubre |
|---|---|---|
| unit/test_turno_transiciones.py | 51 (parametrizados) | tabla de transiciones completa (36 pares), "Campo extra en el cuerpo", normalización del motivo, `PermisoDenegado` → 403 |
| integration/test_migracion_006.py | 3 | upgrade/downgrade/re-upgrade; `fn_rechazar_mutacion` se conserva |
| integration/test_turno_transicion_db.py | 7 | "Historial inmutable" (UPDATE/DELETE/TRUNCATE), FK por tenant, CHECKs, aislamiento |
| integration/test_turno_transiciones_api.py | 21 | los 18 escenarios de la spec + repetir estado, turno inexistente y dado de baja |
| integration/test_turno_transiciones_concurrencia.py | 3 | "Dos cancelaciones simultáneas" + test determinista del lock |

- Concurrencia: 3 corridas consecutivas → `2 passed` ×3 (antes del test determinista) y después `3 passed`. Estable.
- `ruff check backend`: All checks passed.
- `openspec validate transiciones-estado-turno --strict`: valid.

## Prueba de mutación (hallazgo durante el apply)

Se quitó temporalmente `.with_for_update()` de `transicionar_turno` para comprobar que los tests detectan la falta del bloqueo (D5):

- **Primera versión:** `test_dos_cancelaciones_simultaneas` (por HTTP, con barrera) **seguía pasando** sin el lock. No discrimina, porque los dos pedidos casi nunca llegan a solaparse dentro de la ventana de la transacción.
- **Corrección:** se agregó `test_transicion_espera_el_lock_y_se_evalua_contra_el_estado_confirmado`. Una sesión retiene el lock de la fila con el turno ya cancelado sin confirmar. La transición concurrente debe quedar esperando (se verifica que el hilo sigue vivo después de 1 s) y, al liberarse el lock, recibir 422.
- **Con la mutación:** `2 failed, 1 passed` (fallan el determinista y `test_confirmar_y_cancelar_a_la_vez...`). Sin la mutación: `3 passed`. El código se restauró desde backup (`grep -c "with_for_update()"` = 1).

## Prueba manual contra la API real (uvicorn + PostgreSQL 16)

- Base temporal `postgres:16-alpine` en el puerto 55432, porque el 5432 lo ocupa un PostgreSQL instalado en Windows.
- `alembic upgrade head` (005 → 006), seeds sintéticos `seed_core` + `seed_catalogo`, `uvicorn app.main:app --app-dir backend`.
- `/docs` (Swagger) respondió 200 y muestra `POST /api/turnos/{turno_id}/transicion` con el enum `confirmado | cancelado | asistido | ausente`.
- Pedidos HTTP reales con el admin sintético:

| # | Pedido | Respuesta |
|---|---|---|
| 1 | `POST /api/turnos` (turno a 30 días) | 201, `estado: "reservado"` |
| 2 | `→ confirmado` | 200, `estado: "confirmado"` |
| 3 | `→ reservado` | 422 (enum: destino no permitido) |
| 4 | `→ ausente` antes de la hora | 422 "No se puede marcar ausente antes del inicio del turno" |
| 5 | Otro turno en el mismo hueco | 409 "Horario no disponible" |
| 6 | `→ cancelado` con motivo | 200, `estado: "cancelado"` |
| 7 | `→ confirmado` sobre cancelado | 422 "Transición no permitida: cancelado → confirmado" |
| 8 | Reservar el hueco liberado | 201 (turno nuevo) |
| 9 | Sin token | 401 |

Historial en la base (`SELECT … FROM turno_transicion`): `reservado → confirmado` y `confirmado → cancelado` con motivo "paciente avisó (demo)", actor 1 y `created_at` del servidor. `UPDATE turno_transicion …` → `ERROR: tabla append-only: UPDATE no permitido sobre turno_transicion`.

Después de la prueba se apagaron el servidor y el contenedor temporal.

## Desvíos respecto de tasks.md

- 4.2: no se modificó `conftest.py`. `turnos_data` ya tenía al odontólogo vinculado a P y a Q sin usuario; los turnos por estado se crean con helpers del módulo.
- Migración 006: agrega `UNIQUE (clinica_id, id)` en `turno` (`uq_turno_clinica_id`), necesario para la FK compuesta por tenant del historial. Es aditivo, con el mismo patrón que la 005 usó en `prestacion`. No estaba explícito en el design (D4 mencionaba la FK compuesta).
