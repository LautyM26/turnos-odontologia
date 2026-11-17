# Verify — whatsapp-bidireccional (C-15)

Fecha: 2026-11-17. Resultado: **VERDE** (suite completa, ruff, mutaciones y E2E por HTTP).

## Entorno

- Windows 11, Docker Desktop 29.9.2 sobre WSL2.
- PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.13.5 en `.venv`: en esta PC no hay 3.12. `requires-python >= 3.12`.
- pytest 9.2.0, ruff 0.17.5, SQLAlchemy 2.1.9, FastAPI 0.163.2.
- El diseño D1–D11 lo aprobó el usuario el 2026-11-17 ("hacé todo lo necesario"; governance ALTO).
- Base: `main` en `983ec12`, rama `feat/whatsapp-c15`.

## Comandos (desde la raíz del repo)

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m ruff check backend
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-whatsapp RN-WA
openspec validate whatsapp-bidireccional --strict
```

## Resultados

- Backend, suite completa: **1477 passed, 0 failed, 0 skipped** (19 min 46 s) (antes del change: 1348).
- `ruff check backend`: limpio.
- `verificar.py dominio-whatsapp RN-WA`: `RESULTADO: OK`. Las 3 copias de la skill son idénticas.
- `openspec validate --strict`: válido.
- Tests nuevos: **129** (126 en archivos nuevos y 3 en archivos existentes).

| Archivo | Tests | Cubre |
|---|---|---|
| unit/test_settings_whatsapp.py | 12 | arranque sin variables; claves vacías → `None`; secretos enmascarados en `repr`/`str`/JSON; precio `Decimal` exacto; rangos |
| unit/test_whatsapp_factory.py | 7 | vacío, `fake` bloqueado en producción, `waha` sin URL, valor desconocido → `NoConfigurado` (nunca lanza); comportamiento del fake |
| unit/test_whatsapp_waha.py | 14 | contrato `sendText` (`chatId`, `X-Api-Key`, id string u objeto); mapeo de 6 estados; QR; crear sesión con webhook HMAC y 3 eventos; sesión existente → PUT + restart; 5xx/timeout → `GatewayNoDisponible`; 4xx → `SesionNoActiva` (`httpx.MockTransport`, sin red) |
| unit/test_whatsapp_interpretar.py | 23 | tabla de respuestas (1/sí/confirmo, 2/no/cancelo, 3/reprogramar, texto libre, vacío, emoji, "12", "sino"); chatId → E.164; grupos y `@lid` → `None` |
| integration/test_migracion_014.py | 20 | tablas, índices y textos sembrados; `NUMERIC(12,2)`; 9 CHECKs → 23514; entrante con costo; UNIQUE de `id_externo` y de recordatorio → 23505; FK compuesta → 23503; nombre de sesión; actor `paciente_whatsapp`; downgrade bloqueado con historial; downgrade/re-upgrade en base limpia; único head |
| integration/test_whatsapp_aislamiento.py | 1 | consultas scoped de otra clínica → 0 filas |
| integration/test_whatsapp_textos.py | 2 | hora local de la clínica (10:00 UTC → 07:00), profesional y opciones 1/2/3; una variable faltante → `TextoIncompleto` |
| integration/test_recordatorios.py | 9 | un escenario por test: un solo envío con costo `12.50`, fuera de ventana, no reservados, ritmo (3 s entre envíos), sesión caída → bandeja sin tocar el turno, reintento sobre la misma fila, tope de intentos, sin teléfono, sin gateway que se reintenta al configurarlo |
| integration/test_recordatorios_concurrencia.py | 1 | dos corridas simultáneas → un solo envío |
| integration/test_whatsapp_entrante.py | 11 | "Sí!" confirma (historial `paciente_whatsapp` sin usuario y respuesta `confirmacion`); "2" cancela y libera el hueco; reprogramar; texto libre; confirmar un cancelado; número sin recordatorio; mismo teléfono en otra clínica; turno ya empezado; acuses monótonos; acuse de error; sesión caída + WARNING |
| integration/test_whatsapp_idempotencia.py | 2 | el mismo evento en serie y en paralelo → 1 entrante, 1 transición, 1 respuesta |
| integration/test_whatsapp_webhook_api.py | 11 | firma válida sin JWT; firma inválida, otra clave o sin firma → 401 sin efectos; sin secreto → 503; sesión ajena, evento desconocido, `fromMe` y grupo → 200 ignorado; payload sin `id`/`from` y JSON inválido → 422; acuse y estado de sesión por webhook |
| integration/test_whatsapp_sesion_api.py | 7 | QR al admin; recepción ve el estado; odontólogo → 403; sin token → 401; sin gateway → 501 y health 200; gateway caído → último estado con `en_vivo: false` y reconectar → 503; reconectar solo admin, con URL del webhook y HMAC; una sesión por clínica |
| integration/test_whatsapp_bandeja_api.py | 6 | bandeja (fallos y pedidos), resolver, resolver dos veces o un enviado → 404; aislamiento B/A; odontólogo → 403; costos de mayo `37.50` con desglose; rango inválido → 422; mensajes de un turno y turno ajeno → 404 |
| integration/test_exportacion_api.py | +1 (+2 CSV) | `mensajes_whatsapp.csv` solo de la clínica, con conteo en el manifest; `mensajes_whatsapp` y `whatsapp_sesiones` en el chequeo de conteos por entidad |
| test_env_example.py | +2 | `.env.example` con el bloque del gateway y sin las 4 variables muertas; ninguna variable `VITE_` de WhatsApp |

### Hallazgos durante el apply

- **Bug real atrapado por un test de la migración:** el CHECK `telefono IS NOT NULL OR motivo_error = 'sin_telefono'` daba NULL (y pasaba) cuando `motivo_error` era NULL. Se cambió a `IS NOT DISTINCT FROM` en la migración y en el modelo.
- **`extra='forbid'` atrapó una fuga:** el servicio de la bandeja devolvía todas las columnas (`clinica_id`, `resuelto_por`, `updated_at`…) y el schema de salida lo rechazó. Ahora la salida se arma solo con los campos declarados.
- **Hora local sin `tzdata`:** en Windows, `zoneinfo` no trae la base de zonas horarias. La fecha y hora del texto se calculan en PostgreSQL con `timezone(clinica.zona_horaria, inicio)`, que además es la misma fuente que usa C-05d.
- **Compose:** `${VAR:?}` en el servicio `waha` rompía `docker compose config` aun sin el perfil, porque compose interpola todos los servicios. Se usa un default vacío, documentado; el puerto queda atado a `127.0.0.1`.
- **Tarea 7.2:** el caso "campo extra en el cuerpo → 422" no aplica, porque ningún endpoint autenticado de WhatsApp recibe cuerpo. Todos los schemas son `extra='forbid'`, y el 422 por payload mal formado se prueba en el webhook.
- **Docker Desktop** se auto-actualizó al arrancar y el motor tardó unos minutos en responder. No fue un problema del proyecto.

## Pruebas de mutación

Corridas sobre una copia del backend, para no tocar el árbol mientras corría la suite.

| Mutación | Tests que fallan | Resultado |
|---|---|---|
| Claim del recordatorio roto (sin `NOT EXISTS` y el perdedor del `ON CONFLICT` también envía) | `test_recordatorio_enviado_una_sola_vez`, `test_reintento_exitoso_reutiliza_la_fila`, `test_tope_de_intentos`, `test_sin_gateway_queda_no_configurado_y_se_reintenta_al_configurar`, `test_dos_corridas_simultaneas_un_solo_envio` | detectada |
| Comparación HMAC desactivada | `test_firma_invalida_401_sin_efectos` | detectada |
| Deduplicación por `id_externo` desactivada | `test_mismo_evento_dos_veces_seguidas`, `test_mismo_evento_dos_veces_en_paralelo` | detectada |

## Prueba manual end-to-end (API real por HTTP)

Montaje:
- PostgreSQL 16 en Docker, migrado a la 014, con `seed_demo_clinica.py`;
- `uvicorn` en `:8010` con `WHATSAPP_GATEWAY=fake`, `ENTORNO=desarrollo`, `ARS_PRECIO_MENSAJE=12.50` y un secreto HMAC sintético;
- script `evidencias/e2e_c15.py`, con la salida completa en `evidencias/e2e-api-http.txt`.

Pasos:

1. Recepción crea un turno para dentro de ~20 h → `201 reservado`.
2. El job (`python -m app.jobs.recordatorios`) envía 1 recordatorio. La segunda corrida envía 0.
3. `GET /api/whatsapp/mensajes?turno_id=1` → recordatorio `enviado`, `costo_ars "12.50"`, con el texto "…el 18/11 a las 14:00 con Profesional Ejemplo (seed). Respondé 1 para confirmar, 2 para cancelar o 3 para reprogramar."
4. Evento del gateway "Sí, confirmo", firmado, sin JWT → `{"resultado": "confirmado"}`.
   - El mismo evento otra vez → `duplicado`.
   - Firma inválida → `401`.
5. El turno queda `confirmado`, con historial `('reservado', 'confirmado', 'paciente_whatsapp', None)`.
6. "hola, ¿a qué hora era?" → `bandeja`. Recepción lo ve en `/api/whatsapp/fallos` (con nombre del paciente e inicio del turno) y lo resuelve → `200`.
7. Costos del día (admin) → total `"25.00"`: recordatorio 12.50 + confirmación 12.50; 2 entrantes a 0.00.
8. Sesión:
   - `GET /api/whatsapp/sesion` → `activa`;
   - reconectar como recepción → `403`;
   - reconectar como admin → `escanear_qr` con QR.

No se probó con un teléfono ni con un WAHA real: no hay número dedicado de prueba. El adapter `waha` está cubierto por contrato con `httpx.MockTransport`, y los endpoints usados se verificaron contra la doc vigente de WAHA (Context7). El primer vínculo real se hace siguiendo `docs/whatsapp-sesion.md` §3.
