# Verify — horario-atencion (C-05d)

Fecha: 2026-11-17. Resultado: **VERDE, revisado y archivado** el 2026-11-17.

## Entorno

- Windows 11, Docker Desktop sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.12.10 (venv `.venv` en la raíz del repo), pytest 9.2.0, ruff 0.17.5.
- Diseño D1–D6 aprobado por el usuario el 2026-11-17, antes del apply (governance CRÍTICO).
- Base: `main` en `0eb05f5` (C-05c archivado).

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/ruff check backend
openspec validate horario-atencion --strict
```

## Resultados

- Suite completa: **1284 passed, 0 failed, 0 skipped** (16 min 9 s). Antes del change: 1232.
- `ruff check backend`: limpio.
- `openspec validate --strict`: válido.
- Tests nuevos: **52**. Además, `test_seed_catalogo.py` suma asserts de horario.
- Después de la suite se corrigió un test (ver Mutación) y se formatearon los archivos nuevos; los 52 tests del change se volvieron a correr en verde.

| Archivo | Tests | Escenarios de la spec que cubre |
|---|---|---|
| unit/test_horario_schemas.py | 16 | `HH:MM` ↔ minutos, `24:00`, contiguas válidas, inválidas (formato, rango, día, superpuestas, contenida), >70 franjas, campo extra, salida `HH:MM` |
| integration/test_migracion_012.py | 11 | tabla, constraints, índice, default de `zona_horaria`; CHECKs 23514; FK compuesta 23503; **aislamiento** (repositorio de A ve 0 franjas de B); downgrade a 011 + re-upgrade; único head |
| integration/test_horario_api.py | 13 | "Horario partido de lunes a viernes", "Franjas superpuestas en el mismo día" (horario previo intacto), "Franja inválida", "Día completo", "Reemplazo total", lista vacía, "Recepción no edita horarios" 403, "Profesional de otra clínica" 404, inexistente 404, "Recepcionista consulta el horario" + odontólogo 200, sin token 401 |
| integration/test_horario_concurrencia.py | 1 | D3: un PUT concurrente espera el lock del profesional y queda un solo set, nunca la unión |
| integration/test_horario_turnos.py | 11 | "Turno dentro del horario", "Turno que termina fuera del horario", "Profesional sin horario" (alta y huecos), "Sobreturno fuera del horario", franjas contiguas (alta y huecos), cruce de medianoche local, "Horario partido recorta los huecos", "Franja local convertida a UTC", **propiedad**: todo hueco con horario partido acepta `crear_turno` |

Compatibilidad (D6): con el horario `00:00–24:00` en `turnos_data`, los tests de C-05/C-05b/C-05c (`test_turnos_api`, `test_turnos_concurrencia`, `test_sobreturnos_api`, `test_huecos_servicio`, `test_huecos_api`) pasaron sin otros cambios: 60 passed.

## Pruebas de mutación

- **Lock del reemplazo:** sin `with_for_update()` en `_profesional_activo`, `test_horario_concurrencia.py` **falla**: el segundo PUT no espera y quedan los dos sets mezclados.
- **A, huecos sin horario:** sin `* horario.m` en `libre_prof`, fallan **4** tests: horario partido, sin horario, UTC y la propiedad.
- **B, alta sin horario:** con el chequeo `dentro_de_horario` anulado en `crear_turno`, la primera corrida falló **1** test y reveló un falso positivo. `test_turno_que_termina_fuera_del_horario_409_sin_fila` daba 409 por **solapamiento** con el turno del test anterior, no por horario. Se le dio un lunes propio, y la mutación ahora hace fallar **2** tests: fuera de horario y sin horario.

En los tres casos se restauró el código y se volvió a correr en verde.

## EXPLAIN ANALYZE (ventana de 7 días, horario partido lunes a viernes 09–13 y 14–18)

Base de desarrollo (`postgres:16-alpine`, seed sintético), paso 15, prestación de 30 min:

- **150 huecos**: 30 por día × 5 días hábiles, lo esperado.
- La CTE `horario` se materializa una vez (`loops=1`, 1,3 ms). `libre_prof` y `libre_sillon` también corren una vez.
- Planning 14 ms, **Execution 5,4 ms**. En C-05c, sin horario, eran 3,8 ms.

## Prueba manual (uvicorn + API real, base de desarrollo en la 012)

Script con `urllib` contra `http://localhost:8000`, admin seed, paciente sintético (`paciente.horario@ejemplo.test`), fecha dentro de 2 días (00:00 local = 03:00Z):

```
1) horario seed: 200 {"zona": "America/Argentina/Buenos_Aires", "n": 10, "primera": {"dia_semana": 1, "inicio": "09:00", "fin": "13:00"}}
2) PUT superpuesto: 422 "Value error, franjas superpuestas el día 1"
3) PUT 09-13 todos los días: 200 {"n": 7}
4) huecos del día (UTC): 200 ["12:00", "12:15", "12:30", "...", "15:15", "15:30"]
5) turno 12:30 local (dentro): 201 {"estado": "reservado"}
6) turno 12:45 local (termina 13:15): 409 {"detail": "Horario no disponible"}
7) sobreturno 13:15 local: 201 {"es_sobreturno": true}
8) restaura horario seed: 200 {"n": 10}
```

09:00 local = 12:00Z, y el último hueco (15:30Z = 12:30 local) termina justo a las 13:00 local.

## Trazabilidad

- KB `04_modelo_de_datos.md`: entidad FranjaHoraria y `Clinica.zona_horaria`.
- README: tests del change y aviso "cargar horario antes de dar turnos".
- `docs/CONTINUAR.md`: migración 012 tomada; la próxima es la 013. `AGENTS.md`/`CLAUDE.md` no se tocaron.
- `dominio-agenda`: horario en las secciones 2 y 4, y fila de requisito sin RN (decisión del usuario) con sus tests. Las copias están sincronizadas. `verificar.py dominio-agenda RN-AG RN-TU`: **OK** después del archive (la spec `business-hours` nació en el sync).

## Archivo

- Revisado por el usuario el 2026-11-17 y archivado con `openspec archive` como `2026-11-17-horario-atencion`: `business-hours` creada (4 requirements), `schedule-availability` +1 y 1 modificado, `appointments` +1. `openspec validate --specs`: 27/27.
