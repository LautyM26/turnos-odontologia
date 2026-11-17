# Tasks — chatbot-reprogramacion (C-17)

> Governance MEDIO: el usuario aprueba `design.md` (D1–D6) antes de la tarea 1.1.
> TDD en cada grupo. Integración solo con testcontainers `postgres:16-alpine`. Datos sintéticos.
> Antes de la migración, `alembic heads` tiene que mostrar un único head (hoy `015_lista_espera`).

## 1. Configuración y migración

- [x] 1.1 `Settings` suma `chatbot_timeout_min` (30, 5–240) y `reprogramacion_anticipacion_min` (120, 0–1440); actualizar `.env.example` (D6). Verificar con `backend/tests/unit/test_settings_reprogramacion.py` (defaults y valores fuera de rango) y con `test_env_example.py`.
- [x] 1.2 Migración `016_reprogramacion` + modelo `ConversacionWA` en `backend/app/domain/reprogramacion/models.py` (D1). Verificar con `backend/tests/integration/test_migracion_016.py`:
  - 12 textos base;
  - CHECKs de estado y resultado → 23514;
  - dos conversaciones abiertas por número → 23505, y una cerrada convive con una abierta;
  - turno de otra clínica → 23503;
  - downgrade a 015 y re-upgrade;
  - único head.

## 2. Servicio de reprogramación

- [x] 2.1 `opciones(...)` y `reprogramar(...)` en `backend/app/domain/reprogramacion/servicios.py` (D2, D3). Verificar en `backend/tests/integration/test_reprogramacion_servicio.py`:
  - tres primeros huecos del mismo profesional;
  - turno cancelado o empezado → sin opciones;
  - anticipación mínima;
  - reprogramar crea el turno nuevo y cancela el viejo con actor y motivo;
  - `inicio` que no es opción → 422;
  - horario ocupado → 409 con alternativas;
  - el token pasa al turno nuevo.

## 3. Chatbot por WhatsApp

- [x] 3.1 `chatbot.iniciar` / `chatbot.responder` + la rama de conversación en `procesar_mensaje_entrante` (D4). Verificar en `backend/tests/integration/test_chatbot_reprogramacion.py`, un test por escenario de la spec:
  - "3" abre el chatbot;
  - sin huecos → bandeja + `reprogramacion`;
  - "2" + "si" reprograma y responde `reprogramacion_hecha`;
  - "no" → sin cambios;
  - "7" → bandeja;
  - hueco tomado en el medio → alternativas;
  - conversación vencida + "2" no cancela;
  - un número dentro de la conversación es una opción.

  Además, la suite de C-15 y C-16 (entrantes, idempotencia, respuestas de la lista) sigue en verde.
- [x] 3.2 Concurrencia: "si" y "SI" simultáneos con la conversación confirmando → 1 turno nuevo y 1 cancelación. Verificar en `backend/tests/integration/test_chatbot_concurrencia.py`.

## 4. Enlace público

- [x] 4.1 `GET /api/public/reservas/{token}/opciones` y `POST …/reprogramar` en `api/publico.py` (D5). Verificar en `backend/tests/integration/test_reprogramacion_publica_api.py`:
  - opciones 200 sin sillones;
  - token inválido → 404;
  - reprogramar → 200 y el comprobante muestra el horario nuevo; cancelar con el mismo token cancela el nuevo;
  - `inicio` inválido → 422;
  - ocupado → 409 con alternativas;
  - campo extra → 422;
  - sin JWT.

## 5. Exportación y documentación

- [x] 5.1 `ENTIDADES_EXPORTABLES` suma `conversaciones_whatsapp` (D6). Verificar con el escenario nuevo de `test_exportacion_api.py`.
- [x] 5.2 Skills `dominio-agenda` (RN-TU-03 cubierta) y `dominio-whatsapp` (el chatbot en la asociación de respuestas). Verificar después de archivar: `verificar.py` en `RESULTADO: OK` para ambas y las copias idénticas.

## 6. Verificación integral

- [x] 6.1 Suite completa en verde + `ruff check backend` limpio.
- [x] 6.2 Mutación: romper el claim `confirmando → ejecutando` y la prioridad de la conversación sobre el recordatorio; confirmar que falla al menos un test en cada caso; restaurar.
- [x] 6.3 E2E por HTTP con el gateway fake:
  1. recordatorio → "3" → opciones → "2" → "si" → turno nuevo y viejo cancelado;
  2. reprogramar por enlace con token.

  Dejarlo en `verify.md` + `evidencias/`.

## Workflow follow-up

- `/opsx:archive chatbot-reprogramacion`, marcar C-17 en `CHANGES.md` y anotar la migración 016 en `docs/CONTINUAR.md`.
- Commit solo cuando el usuario lo pida.
