# Tasks — lista-espera-relleno (C-16)

> Governance MEDIO: el usuario aprueba `design.md` (D1–D10) antes de la tarea 1.1.
> TDD en cada grupo. Integración solo con testcontainers `postgres:16-alpine` (regla dura 9). Datos sintéticos (regla dura 14).
> Antes de la migración: `python -m alembic -c backend/alembic.ini heads` tiene que mostrar un único head (hoy `014_whatsapp`).

## 1. Configuración

- [x] 1.1 `Settings` suma `lista_espera_oferta_min` (30, 5–240) y `lista_espera_anticipacion_min` (120, 0–1440); actualizar `.env.example` (D10). Verificar:
  - `backend/tests/unit/test_settings_lista_espera.py`: defaults y valores fuera de rango → error;
  - `backend/tests/test_env_example.py`, con las dos variables agregadas.

## 2. Modelo y migración

- [x] 2.1 Migración `015_lista_espera` + modelos en `backend/app/domain/lista_espera/models.py`: tablas, UNIQUE parciales, índice y CHECK ampliado de `plantilla_wa` con 2 textos nuevos (D2). Verificar con `backend/tests/integration/test_migracion_015.py`:
  - 7 textos base;
  - CHECKs de estado y prioridad → 23514;
  - entrada activa duplicada → 23505;
  - dos ofertas pendientes por hueco o por entrada → 23505;
  - el mismo hueco dos veces a la misma entrada → 23505;
  - FK compuesta ajena → 23503;
  - downgrade a 014 y re-upgrade en base limpia;
  - único head.
- [x] 2.2 `horario_libre(...)` público en `turnos.py` (D9). Verificar en `backend/tests/integration/test_horario_libre.py`: libre, turno superpuesto, bloqueo y fuera de horario. Además, `test_turnos_api.py` sigue verde.

## 3. Render y asociación de respuestas (C-15)

- [x] 3.1 Dividir `renderizar` en `variables_horario` + `renderizar_texto` (D4) sin cambiar su comportamiento. Verificar con `test_whatsapp_textos.py` y `test_recordatorios.py` en verde, más un test de `oferta_hueco` renderizado con el paciente de la entrada.
- [x] 3.2 `_contexto_vigente` (recordatorio u oferta, gana el más reciente) y delegación a `responder_oferta` (D5). Verificar con la suite de C-15 de entrantes e idempotencia en verde, más el escenario "Respuesta a una oferta y no al recordatorio".

## 4. Servicios de la lista de espera

- [x] 4.1 Alta, listado, edición y baja con validaciones (D2, D8). Verificar en `backend/tests/integration/test_lista_espera_servicio.py`:
  - alta con turno a adelantar;
  - turno de otro paciente → 422;
  - duplicada → 409;
  - orden por prioridad y antigüedad;
  - baja con oferta pendiente → `salido` + oferta `anulada`.
- [x] 4.2 Oferta: elección del candidato y envío (D3, D4). Verificar en `backend/tests/integration/test_lista_espera_oferta.py`:
  - la cancelación dispara una oferta al primero (prioridad);
  - otra prestación no coincide;
  - el preferido no coincide;
  - candidato sin teléfono se saltea;
  - turno a adelantar anterior al hueco;
  - hueco < 2 h no se ofrece;
  - hueco ocupado de nuevo no se ofrece;
  - el texto nombra al paciente de la entrada y no al que canceló;
  - hueco de A no va a la cola de B.
- [x] 4.3 Aceptar y rechazar (D6). Verificar en `backend/tests/integration/test_lista_espera_respuestas.py`:
  - aceptar crea el turno `lista_espera` + `oferta_aceptada`;
  - aceptar con turno a adelantar cancela el viejo con actor `paciente_whatsapp`, y la corrida siguiente lo ofrece;
  - hueco tomado en el medio → anulada + `oferta_no_disponible`;
  - oferta vencida → `oferta_no_disponible`;
  - rechazar → `rechazada` + `en_cola`, sin respuesta.
- [x] 4.4 Concurrencia: dos mensajes distintos "1" y "si" en paralelo para la misma oferta → 1 turno y 1 respuesta. Verificar en `backend/tests/integration/test_lista_espera_concurrencia.py`.

## 5. Job

- [x] 5.1 `backend/app/jobs/lista_espera.py` (`procesar_lista_espera` + `main`, D1). Verificar en `backend/tests/integration/test_job_lista_espera.py`:
  - vencer pasa al siguiente en la misma corrida;
  - nadie más disponible → sin ofertas;
  - sesión caída → oferta anulada, entrada `en_cola`, fallo en `/api/whatsapp/fallos` y la corrida se corta;
  - la corrida repetida no duplica ofertas.

## 6. API

- [x] 6.1 Router `backend/app/api/lista_espera.py` + `include_router` (D7, D8). Verificar en `backend/tests/integration/test_lista_espera_api.py`, un test por escenario de API de `waitlist`:
  - CRUD, oferta manual 201/409/422, bandeja, métricas 3/1/2 y rango 422;
  - odontólogo → 403, sin token → 401, ids de otra clínica → 404.

## 7. Exportación y operación

- [x] 7.1 `ENTIDADES_EXPORTABLES` suma `lista_espera` y `ofertas_lista_espera` (D10). Verificar con el escenario nuevo en `test_exportacion_api.py`.
- [x] 7.2 `docs/whatsapp-sesion.md` §4: cron de la lista cada 5 min. Skill `dominio-agenda`: fila RN-AG-06 de la matriz; skill `dominio-whatsapp`: la asociación de ofertas. Verificar con `verificar.py dominio-agenda RN-AG RN-TU` y `verificar.py dominio-whatsapp RN-WA` en `RESULTADO: OK`, y las copias idénticas.

## 8. Verificación integral

- [x] 8.1 Suite completa `python -m pytest backend/tests -q` en verde + `ruff check backend` limpio.
- [x] 8.2 Mutación: romper el claim de aceptación (`AND estado='pendiente'`) y el `NOT EXISTS` de la rotación; confirmar que falla al menos un test en cada caso; restaurar.
- [x] 8.3 E2E por HTTP con el gateway fake: cancelar un turno → correr el job → la oferta llega → "1" firmado → turno nuevo; el turno a adelantar se cancela y se ofrece en cascada. Dejarlo en `verify.md` + `evidencias/`.

## Workflow follow-up

- `/opsx:archive lista-espera-relleno`, marcar C-16 en `CHANGES.md` y anotar la migración 015 en `docs/CONTINUAR.md`.
- Avisar a Matheo del helper `horario_libre` en `turnos.py`.
- Commit solo cuando el usuario lo pida (regla dura 3).
