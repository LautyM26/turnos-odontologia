# Verify — lista-espera-relleno (C-16)

Fecha: 2026-11-17. Resultado: **VERDE** (suite completa, ruff, mutaciones y E2E por HTTP).

## Entorno

- Windows 11, Docker Desktop 29.9.2 sobre WSL2; PostgreSQL `postgres:16-alpine` vía testcontainers.
- Python 3.13.5 (`.venv`), pytest 9.2.0, ruff 0.17.5.
- El usuario aprobó el diseño D1–D10 el 2026-11-17 (governance MEDIO).
- Base: rama `feat/lista-espera-c16`, sobre `943a732` (C-15).

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff check backend
openspec validate lista-espera-relleno --strict
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-agenda RN-AG RN-TU
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-whatsapp RN-WA
```

## Resultados

- Backend, suite completa: **1529 en verde**. La corrida completa dio 1527 passed y 2 failed (18 min 25 s). Los 2 fallos eran de `test_migracion_014.py`, que esperaba exactamente 5 textos base (desde la 015 son 7). Se ajustaron a "al menos los 5 de la 014" y el archivo se volvió a correr: 20 passed (antes del change: 1477).
- `ruff check backend`: limpio.
- `openspec validate --strict`: válido.
- Tests nuevos: **52** (51 en archivos nuevos + 1 en `test_exportacion_api.py`). La suite de C-15 (entrantes, idempotencia, textos, recordatorios) sigue en verde después del refactor del render y de la asociación.

| Archivo | Tests | Cubre |
|---|---|---|
| unit/test_settings_lista_espera.py | 5 | defaults 30/120; valores fuera de rango |
| integration/test_migracion_015.py | 11 | tablas, índices y 7 textos base; defaults; CHECKs (23514); entrada activa duplicada (23505, la inactiva convive); referencias ajenas (23503); pendiente por hueco y por entrada; el mismo hueco a la misma entrada (23505); la rotación a otra entrada sí se permite; CHECK de `turno_creado` solo si la oferta está aceptada; downgrade y re-upgrade en base limpia; único head |
| integration/test_horario_libre.py | 4 | horario libre; ocupado por un turno; un cancelado no ocupa; bloqueo; fuera de horario |
| integration/test_lista_espera_servicio.py | 7 | alta con turno a adelantar; turno de otro paciente, pasado o cancelado → 422; referencias ajenas → 422; duplicada → 409; orden prioridad/antigüedad; baja con oferta pendiente |
| integration/test_lista_espera_oferta.py | 9 | la cancelación dispara la oferta al primero, con el texto con su nombre y opciones; nunca nombra a quien canceló; otra prestación; preferencias de profesional y sillón; sin teléfono se saltea; turno a adelantar anterior al hueco; hueco a menos de 2 h; hueco ocupado de nuevo; un hueco de A no va a la cola de B |
| integration/test_lista_espera_respuestas.py | 6 | aceptar reasigna (turno `lista_espera` + `oferta_aceptada`); aceptar adelanta, cancela el viejo con actor `paciente_whatsapp` y se ofrece en cascada; hueco tomado en el medio → anulada + `oferta_no_disponible`; oferta vencida; rechazar rota sin respuesta automática; la respuesta a una oferta no toca el recordatorio |
| integration/test_lista_espera_concurrencia.py | 1 | "1" y "si" en paralelo → 1 turno y 1 `oferta_aceptada` (estable en 3 corridas) |
| integration/test_job_lista_espera.py | 4 | vencer y pasar al siguiente en la misma corrida; nadie más disponible; sesión caída → oferta anulada, entrada en cola, fallo en la bandeja y corrida cortada; corrida repetida sin duplicar |
| integration/test_lista_espera_api.py | 4 | CRUD (201/409/422/extra → 422/204/404); oferta manual 201/409/422; bandeja y métricas 3/1/2, rango → 422; RBAC (403/401) y aislamiento (404) |
| integration/test_exportacion_api.py | +1 (+2 CSV) | `lista_espera.csv` aislado por clínica, con conteo en el manifest; las dos tablas entran en el chequeo de conteos por entidad |

### Hallazgos durante el apply

- **Test de C-15 demasiado estricto:** `test_migracion_014.py` comparaba los textos base con `==`. Una migración posterior que suma textos es válida, así que pasó a `>=`.

- **El render de C-15 tomaba el paciente del turno.** Para la oferta habría nombrado a quien canceló. Se dividió en `variables_horario` + `renderizar_texto`, y un test garantiza que el texto de la oferta nunca nombra al que canceló.
- **El mismo horario cancelado dos veces** (cancelar, volver a reservar, cancelar otra vez) generaba dos huecos para el mismo horario. El "en curso" se evalúa por `(clínica, profesional, inicio)` y no por turno, y los repetidos se descartan dentro de la corrida.
- **El claim va antes de crear el turno**: `crear_turno` hace commit adentro y soltaría un lock de fila. Lo confirma la mutación de abajo.
- **Ajustes de las skills:** se corrigió la matriz de `dominio-agenda`, donde RN-TU-02/03 figuraban pendientes aunque C-15 ya las cubre. `verificar.py dominio-agenda` falla antes de archivar solo porque `openspec/specs/waitlist/spec.md` se crea al archivar; después del archivo da OK.

## Pruebas de mutación

Corridas sobre una copia del backend, en paralelo a la suite.

| Mutación | Tests que fallan | Resultado |
|---|---|---|
| Claim de aceptación sin `estado='pendiente'` | `test_dos_aceptaciones_distintas_en_paralelo` | detectada |
| Rotación sin `NOT EXISTS` del hueco ya ofrecido | `test_expirar_pasa_al_siguiente_en_la_misma_corrida`, `test_rechazar` | detectada |

## Prueba manual end-to-end (API real por HTTP)

Montaje:

- PostgreSQL 16 en Docker, migrado a la 015, con el seed demo;
- `uvicorn` en `:8011` con `WHATSAPP_GATEWAY=fake`;
- script `evidencias/e2e_c16.py`, con la salida completa en `evidencias/e2e-api-http.txt`.

Pasos:

1. Turno de A en unas 20 h y turno de B en 5 días.
2. B entra a la lista con prioridad 5 y "adelantar"; C, con prioridad 0.
3. A cancela en el mostrador. El job ofrece el hueco a B: `1 ofertas`, bandeja `pendiente`.
4. B responde "1" con un evento firmado:
   - resultado `oferta_aceptada`;
   - se crea el turno de B con origen `lista_espera`;
   - el turno viejo de B queda `cancelado`.
5. B repite "si" → `sin_efecto`.
6. El job vuelve a correr y la **cascada** ofrece a C el hueco del turno viejo de B. C responde "no" → `oferta_rechazada`.
7. Métricas de la semana: liberados 2, recuperados 1, perdidos 1.
8. Mensajes registrados:
   - `oferta_hueco` y `oferta_aceptada` a B, a 12.50 cada una;
   - `oferta_hueco` a C, a 12.50;
   - las respuestas entrantes, a 0.00.
