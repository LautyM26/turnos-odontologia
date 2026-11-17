# Tasks — whatsapp-bidireccional (C-15)

> Governance ALTO: antes de la tarea 1.1, el usuario aprueba `design.md` (D1–D11).
> TDD en cada grupo: primero el test que falla, después el código. Integración solo con testcontainers `postgres:16-alpine` (regla dura 9). Datos 100 % sintéticos (regla dura 14).
> Antes de crear la migración: `python -m alembic -c backend/alembic.ini heads` tiene que mostrar un único head (hoy `013_reserva_online`).

## 1. Configuración

- [x] 1.1 `Settings` suma las 8 variables de D10. Las secretas son `SecretStr` y el valor vacío se convierte en `None`; `ars_precio_mensaje` es `Decimal`. `httpx` pasa a `dependencies` de `pyproject.toml`. Verificar en `backend/tests/unit/test_settings_whatsapp.py`:
  - arranque sin `WHATSAPP_*`;
  - clave vacía → `None`;
  - secretos enmascarados en `repr`/`model_dump_json`;
  - `ars_precio_mensaje` `"12.50"` → `Decimal("12.50")` exacto;
  - rangos fuera de límite → error.
- [x] 1.2 `backend/.env.example` reemplaza las 4 variables muertas por las de D10 (`WHATSAPP_GATEWAY=fake`, URL local y placeholders). Verificar con `backend/tests/test_env_example.py` actualizado (lista nueva y sin secretos) y que no existe ninguna variable `VITE_` de WhatsApp en `frontend/.env.example`.

## 2. Modelo y migración

- [x] 2.1 Migración `backend/alembic/versions/014_whatsapp.py` (D2, D3, D4, D8) + modelos espejo en `backend/app/domain/whatsapp/models.py` + CHECK espejo de `TurnoTransicion` en `turnos.py`. Verificar con `backend/tests/integration/test_migracion_014.py`:
  - 5 textos base sembrados;
  - CHECKs de `estado`, `direccion`, `intencion`, `motivo_error` y `costo_ars >= 0` → 23514;
  - UNIQUE `(clinica_id, id_externo)` y un recordatorio por turno → 23505;
  - FK compuesta: un turno de otra clínica → 23503;
  - `actor_tipo='paciente_whatsapp'` con usuario → 23514, y sin usuario OK;
  - downgrade a 013 sin filas `paciente_whatsapp` y re-upgrade sin residuos;
  - downgrade con filas `paciente_whatsapp` → falla con mensaje claro;
  - único head.
- [x] 2.2 Aislamiento: consultas scoped de `mensaje_whatsapp` y `whatsapp_sesion` desde B → 0 filas de A. Verificar en `backend/tests/integration/test_whatsapp_aislamiento.py` (regla dura 10).

## 3. Puerto y adapters

- [x] 3.1 `backend/app/infrastructure/whatsapp/puerto.py`, `fake.py` y `factory.py` (D1). Verificar en `backend/tests/unit/test_whatsapp_factory.py`:
  - vacío → `NoConfigurado`;
  - `fake` en `produccion` → `NoConfigurado` + warning;
  - `waha` sin URL → `NoConfigurado`;
  - valor desconocido → `NoConfigurado`;
  - `fake` en `desarrollo` → `FakeMensajeria`;
  - nunca lanza excepciones.
- [x] 3.2 `backend/app/infrastructure/whatsapp/waha.py` sobre `httpx` (D1, endpoints según Context7). Verificar en `backend/tests/unit/test_whatsapp_waha.py` con `httpx.MockTransport`:
  - `sendText` envía `{session, chatId: "5491100000001@c.us", text}` con `X-Api-Key` y devuelve el id;
  - mapeo de los 5 estados de WAHA + desconocido;
  - QR en base64;
  - `iniciar` crea la sesión con webhook, HMAC y los 3 eventos, y reinicia si ya existe;
  - timeout o 5xx → `GatewayNoDisponible`.

## 4. Dominio: textos e interpretación

- [x] 4.1 `backend/app/domain/whatsapp/servicios.py`: `interpretar(texto)` y `telefono_de_chat_id(chat_id)` (D6, D7). Verificar en `backend/tests/unit/test_whatsapp_interpretar.py` con una tabla:
  - "Sí!", "SI, confirmo", "1", "confirmar" → confirmar;
  - "2", "NO", "cancelo" → cancelar;
  - "3", "Reprogramar" → reprogramar;
  - "hola", "", "👍" → desconocida;
  - `…@c.us` → E.164; `@g.us`/`@lid` → `None`.
- [x] 4.2 Render de textos base con zona horaria de la clínica (D4). Verificar en `backend/tests/integration/test_whatsapp_textos.py`:
  - el recordatorio de T (10:00 UTC, clínica `America/Argentina/Buenos_Aires`) dice `07:00`, el profesional y las opciones 1/2/3;
  - una variable faltante → error, nunca texto con `{...}`.

## 5. Recordatorios (job)

- [x] 5.1 `backend/app/jobs/recordatorios.py` (`enviar_recordatorios` + `main()` estilo `purga_blacklist`, D5). Verificar en `backend/tests/integration/test_recordatorios.py`, un test por escenario de "Recordatorio previo al turno", "Ritmo de envío limitado" y "Fallo de envío va a la bandeja sin tocar el turno":
  - dos corridas → un solo envío con `costo_ars = Decimal("12.50")`;
  - fuera de ventana, cancelado o confirmado → nada;
  - intervalos registrados ≥ 3 s con un límite de 20/min, y sin espera antes del primero;
  - sesión caída → `error` + bandeja + turno `reservado`;
  - reintento → la misma fila con `intentos = 2`;
  - tope de intentos → no se reintenta más;
  - sin teléfono → `sin_telefono` sin reintento;
  - `NoConfigurado` → `no_configurado`.
- [x] 5.2 Concurrencia del claim: dos `enviar_recordatorios` simultáneos sobre el mismo turno → un solo envío al `FakeMensajeria`. Verificar en `backend/tests/integration/test_recordatorios_concurrencia.py`.

## 6. Webhook y respuestas del paciente

- [x] 6.1 `procesar_mensaje_entrante`, `procesar_ack` y `procesar_estado_sesion` (D2, D7). Verificar en `backend/tests/integration/test_whatsapp_entrante.py`, un test por escenario de "La respuesta del paciente actualiza la agenda", "Respuestas que no mueven la agenda van a la bandeja", "Estado de entrega" y "Una sesión por clínica":
  - "Sí!" → `confirmado` + historial `paciente_whatsapp` sin usuario + respuesta `confirmacion`;
  - "2" → `cancelado` + el hueco admite un turno nuevo;
  - "reprogramar" → bandeja + respuesta, turno igual;
  - texto libre → bandeja sin respuesta;
  - confirmar un cancelado → bandeja sin transición;
  - número sin recordatorio → bandeja sin turno;
  - mismo teléfono en A y B → no toca B;
  - acuses monótonos;
  - `WORKING → FAILED` → `caida` + log `WARNING`.
- [x] 6.2 Idempotencia: el mismo evento dos veces seguidas y dos veces en paralelo → 1 mensaje entrante, 1 transición y 1 respuesta. Verificar en `backend/tests/integration/test_whatsapp_idempotencia.py`.
- [x] 6.3 Router del webhook en `backend/app/api/whatsapp.py` (D6) + `include_router`. Verificar en `backend/tests/integration/test_whatsapp_webhook_api.py`:
  - firma válida → 200 y efectos;
  - firma inválida o ausente → 401 sin efectos;
  - sin secreto → 503;
  - evento desconocido o sesión ajena → 200 sin filas;
  - `fromMe: true` → ignorado;
  - payload sin `id` o `from` → 422;
  - ruta sin JWT.

## 7. API autenticada

- [x] 7.1 `GET /api/whatsapp/sesion` y `POST /api/whatsapp/sesion/reconectar` (D9). Verificar en `backend/tests/integration/test_whatsapp_sesion_api.py`:
  - admin con `escanear_qr` → 200 + QR;
  - `activa` → sin QR;
  - recepción ve el estado y reconectar le da 403;
  - odontólogo → 403; sin token → 401;
  - `NoConfigurado` → 501 y `/api/health` 200;
  - gateway caído → último estado con `en_vivo: false`;
  - reconectar pasa la URL del webhook y la clave HMAC al fake.
- [x] 7.2 `GET /api/whatsapp/fallos`, `POST /api/whatsapp/fallos/{id}/resolver`, `GET /api/whatsapp/costos` y `GET /api/whatsapp/mensajes` (D9). Verificar en `backend/tests/integration/test_whatsapp_bandeja_api.py`:
  - la bandeja lista salientes en error y entrantes pendientes;
  - resolver → 200 y desaparece; resolver dos veces → 404; id de otra clínica → 404;
  - costos: marzo `"37.50"` con desglose y rango invertido o > 366 días → 422;
  - mensajes de un turno ajeno → 404;
  - B no ve nada de A;
  - ~~campo extra en el cuerpo → 422~~: ningún endpoint autenticado de WhatsApp recibe cuerpo; todos los schemas usan `extra='forbid'` (el webhook prueba el 422 con payload mal formado);
  - odontólogo → 403.

## 8. Exportación, operación y documentación

- [x] 8.1 `exportador.ENTIDADES_EXPORTABLES` suma `mensajes_whatsapp` y `whatsapp_sesiones` (D11). Verificar con el escenario nuevo de `data-export` en `backend/tests/integration/test_exportacion_api.py`: 2 filas de A, 0 de B, conteo del manifest.
- [x] 8.2 Servicio `waha` en `docker-compose.yml` (perfil `whatsapp`, tag fijo, volumen de sesión) y runbook `docs/whatsapp-sesion.md`, que cubre:
  - riesgo de bloqueo/ToS (DD-10);
  - número dedicado;
  - escaneo y reconexión;
  - backup y restauración cifrada del volumen;
  - cron cada 15 min;
  - rollback con `WHATSAPP_GATEWAY=`;
  - migración F2.

  Verificar que `docker compose config` y `docker compose --profile whatsapp config` validan, y que los comandos del runbook coinciden con los nombres reales.
- [x] 8.3 KB y skill:
  - `knowledge-base/08_arquitectura_propuesta.md` reemplaza `WHATSAPP_API_TOKEN/PHONE_ID/WEBHOOK_VERIFY` por las variables de D10;
  - `knowledge-base/04_modelo_de_datos.md` §MensajeWhatsApp refleja las columnas reales;
  - la matriz de `dominio-whatsapp` se actualiza.

  Verificar con `python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-whatsapp RN-WA` → `RESULTADO: OK` y `diff -r` vacío entre las 3 copias de la skill.

## 9. Verificación integral

- [x] 9.1 Suite completa `python -m pytest backend/tests -q` en verde + `ruff check backend` limpio.
- [x] 9.2 Prueba de mutación (consejo de C-05b): romper a propósito el claim del recordatorio, la comparación HMAC y la deduplicación por `id_externo`, y confirmar que en cada caso falla al menos un test. Volver todo atrás.
- [x] 9.3 Prueba manual en Swagger con `WHATSAPP_GATEWAY=fake`: firmar a mano un evento "SI", ver el turno confirmado, la bandeja y los costos. Si hay teléfono de prueba, hacer un e2e con WAHA real. Dejarlo en `verify.md`.

## Workflow follow-up

- `/opsx:archive whatsapp-bidireccional`, marcar `[x]` C-15 en `CHANGES.md` y anotar la migración 014 en `docs/CONTINUAR.md` §5.
- Commit en la rama `feat/whatsapp-c15` solo cuando el usuario lo pida (conventional commits, sin co-autoría IA, regla dura 3).
- Después: C-16 `lista-espera-relleno` y C-17 `chatbot-reprogramacion` sobre este puerto.
