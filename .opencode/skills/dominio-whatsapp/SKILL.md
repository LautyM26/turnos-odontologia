---
name: dominio-whatsapp
description: Reglas vigentes de WhatsApp y mensajería (RN-WA + RN-TU-02/03) con trazabilidad a specs y tests. Usar al programar WhatsApp, sesión QR con número dedicado, reconexión o backup de la sesión, recordatorio 24 h, confirmar/cancelar/reprogramar por WhatsApp, webhook o eventos entrantes de WhatsApp, textos base (plantillas internas), costo por mensaje en pesos, bandeja de fallos, fallback email/manual, MensajeriaPort/adapter, oferta de hueco de lista de espera por WhatsApp o chatbot de reprogramación (changes C-15 whatsapp-bidireccional, C-16 lista-espera-relleno, C-17 chatbot-reprogramacion), y antes de /opsx:propose de cualquier change de WhatsApp.
---

# dominio-whatsapp

> Generada con `crear-skill-de-dominio` el 2026-11-17 (matriz actualizada el mismo día al implementar C-15) a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

Cubre el canal WhatsApp de la clínica: recordatorios y respuestas del paciente que **mueven la agenda de verdad** (confirmar, cancelar, reprogramar), con costo visible en pesos. Por DD-10 el canal es una sesión QR con número dedicado, no WhatsApp Business Platform de Meta: el riesgo de caída/bloqueo es asumido y se mitiga con monitoreo, reconexión, backup y fallback.

## 2. Cuándo usarla

- Modelos `MensajeWhatsApp`, `PlantillaWA` (texto base interno); puerto `MensajeriaPort` + adapter QR; `POST /api/webhooks/whatsapp`; sesión (`GET /api/whatsapp/sesion`, reconectar); bandeja de fallos y costos; job de recordatorios.
- Changes del roadmap: C-15 `whatsapp-bidireccional` (pendiente; depende de C-05), C-16 `lista-espera-relleno` (oferta de hueco por WA; reglas RN-AG-06 y RN-TU-04 en `dominio-agenda`), C-17 `chatbot-reprogramacion` (reprogramación conversacional; reglas RN-AG-01/02 en `dominio-agenda`).

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-WA-01 | WhatsApp se envía por sesión QR con número dedicado (no WhatsApp Business Platform de Meta); riesgo de bloqueo/ToS asumido. La sesión se monitorea, se reconecta y se respalda; si cae o el número se bloquea, el turno queda sin confirmar y se escala por email/recordatorio manual. La mensajería va detrás de un puerto/adapter para migrar a WhatsApp Business Platform en F2. | DD-10 (reemplaza DD-02) |
| RN-WA-02 | Costo por mensaje transparente en pesos, como costo interno configurable (`ARS_PRECIO_MENSAJE`). La tarifa oficial ARS queda solo como referencia para F2. | DD-10 |
| RN-WA-03 | Cada mensaje guarda plantilla (texto base interno, sin aprobación de Meta), dirección (entrante/saliente), estado y costo, para exponerlo al consultorio. | DD-10 |
| RN-TU-02 | El recordatorio sale por WhatsApp (sesión QR, texto base interno) con ventana de confirmación; si la sesión cae, el turno queda sin confirmar y se escala por email/recordatorio manual. | DD-10 |
| RN-TU-03 | Confirmar, cancelar y reprogramar por WhatsApp actualiza la agenda (bidireccional real, no aviso de una vía). | DD-10 |

RN-TU-02/03 viven en `dominio-agenda`; se repiten acá porque C-15 las implementa. Relacionadas: RN-AG-06 (oferta de lista de espera, C-16), RN-AG-01/02 (huecos válidos al reprogramar, C-17), RN-CU-01 (solo pacientes con consentimiento de datos).

### Reglas duras de AGENTS.md que aplican

- **4**: schemas Pydantic con `extra='forbid'` (también el payload del webhook que el sistema valida).
- **7**: costo en `NUMERIC` ARS, nunca float; tiempos `TIMESTAMPTZ`.
- **9**: integración PG solo con testcontainers `postgres:16-alpine` + migraciones up/down.
- **10**: `mensaje_whatsapp`, plantillas y lista de espera con `clinica_id` + índice `(clinica_id, …)` + test de aislamiento.
- **12**: credenciales y archivos de sesión QR solo en env/vault del backend; nunca en el browser ni en el repo.
- **14**: teléfonos y nombres de pacientes sintéticos en tests, seeds y ejemplos.
- **17**: WhatsApp por QR con número dedicado (DD-10): documentar sesión QR, reconexión y backup.

### Supuestos abiertos (no son reglas cerradas)

- **SU-04**: recordatorio 24 h antes y timeout de la oferta de lista de espera. Sin validar con el piloto: configuración, nunca constantes.
- **PA-05 / SU-07**: quién opera y paga el número dedicado y la infraestructura de sesión; criterio de migración a WhatsApp Business Platform en F2.
- Librería/cliente concreto de sesión QR (no definido en la KB): el adapter real es intercambiable; en tests usar un adapter falso. Consultar su doc con Context7 sin enviar secretos ni datos de pacientes.
- Interpretación de respuestas libres ("SI", "sí", "1", "cancelo"…): no está fijada en la KB; decidirla y justificarla en el `design.md` del change.

## 4. Cómo aplicarlas

- Confirmar/cancelar desde WhatsApp **reutiliza** `transicionar_turno(...)` y `puede_transicionar` de `backend/app/domain/agenda/turnos.py` (C-05b); no duplicar la tabla de estados. `origen='whatsapp'` y `'lista_espera'` ya existen en `ORIGENES_TURNO`.
- Reprogramar (C-17) y ofertar huecos (C-16) usan `buscar_huecos` de `backend/app/domain/agenda/huecos.py` y `crear_turno`: mismas reglas de duración, bloqueos, horario y 409.
- Código de C-15:
  - puerto `Mensajeria` + `FakeMensajeria` + `WahaMensajeria` + factory en `backend/app/infrastructure/whatsapp/`;
  - dominio en `backend/app/domain/whatsapp/` (`interpretar`, `renderizar`, `despachar`, `procesar_mensaje_entrante`, `procesar_ack`, `procesar_estado_sesion`);
  - router `backend/app/api/whatsapp.py`;
  - job `backend/app/jobs/recordatorios.py`;
  - migración `backend/alembic/versions/014_whatsapp.py`;
  - runbook `docs/whatsapp-sesion.md`.
- **Enviar un mensaje** (C-16 oferta de hueco, C-17 chatbot): crear `MensajeWhatsApp` saliente `pendiente` con el texto de `renderizar(...)` y llamar a `despachar(...)`. Ya registra costo, estado y bandeja. No llamar al adapter directo.
- **Respuestas entrantes**: hoy `procesar_mensaje_entrante` asocia la respuesta al último **recordatorio** vigente del número. C-16/C-17 tienen que extender esa asociación (por ejemplo, a la última `oferta_hueco`) sin romper la idempotencia por `id_externo`.
- El webhook es público (`backend/app/api/deps.py`) y se autentica con HMAC-SHA512 (`WHATSAPP_WEBHOOK_HMAC_KEY`, header `X-Webhook-Hmac`). Sin secreto → 503; firma mala → 401.
- Variables: `WHATSAPP_GATEWAY` (vacío/`fake`/`waha`), `WHATSAPP_GATEWAY_URL`, `WHATSAPP_GATEWAY_API_KEY`, `WHATSAPP_WEBHOOK_HMAC_KEY`, `WHATSAPP_RECORDATORIO_HORAS`, `WHATSAPP_MAX_INTENTOS`, `WHATSAPP_ENVIOS_POR_MINUTO`, `ARS_PRECIO_MENSAJE` (`Decimal`). Sin gateway la API arranca igual (sesión → 501).
- Fallo de envío (sesión caída, número bloqueado, sin teléfono) → `error` + motivo + bandeja (`requiere_atencion`); el turno no cambia de estado.
- Migraciones: 014 = C-15. La siguiente usa el número libre y `down_revision` = head del momento; `alembic heads` con un único head.

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-WA-01 | `openspec/specs/whatsapp-messaging/spec.md` · "Una sesión de WhatsApp por clínica", "Consulta del estado de la sesión", "Reconexión de la sesión solo por admin", "Canal no configurado no impide operar", "Fallo de envío va a la bandeja sin tocar el turno", "Bandeja de fallos con resolución manual"; `openspec/specs/platform-config/spec.md` · "Configuración del gateway de WhatsApp" | `backend/tests/integration/test_whatsapp_sesion_api.py` · `test_admin_ve_qr_cuando_hay_que_escanear`, `test_reconectar_solo_admin_y_configura_webhook`, `test_sin_gateway_501_y_health_200`, `test_gateway_caido_devuelve_ultimo_estado_conocido`; `backend/tests/integration/test_recordatorios.py` · `test_sesion_caida_va_a_la_bandeja_sin_tocar_el_turno`; `backend/tests/integration/test_whatsapp_bandeja_api.py` · `test_bandeja_lista_fallos_y_resolver`; `backend/tests/unit/test_whatsapp_factory.py` · `test_fake_bloqueado_en_produccion` | cubierta (el backup de la sesión es operación manual, documentada en el runbook `docs/whatsapp-sesion.md`) |
| RN-WA-02 | `openspec/specs/whatsapp-messaging/spec.md` · "Registro de mensajes con costo en pesos", "Resumen de costos por período" | `backend/tests/integration/test_recordatorios.py` · `test_recordatorio_enviado_una_sola_vez`; `backend/tests/integration/test_whatsapp_bandeja_api.py` · `test_costos_del_mes_en_ars`; `backend/tests/unit/test_settings_whatsapp.py` · `test_precio_decimal_exacto` | cubierta |
| RN-WA-03 | `openspec/specs/whatsapp-messaging/spec.md` · "Registro de mensajes con costo en pesos", "Estado de entrega de los mensajes salientes", "Textos base internos sembrados" | `backend/tests/integration/test_whatsapp_bandeja_api.py` · `test_mensajes_de_un_turno`; `backend/tests/integration/test_whatsapp_entrante.py` · `test_acuses_monotonos`; `backend/tests/integration/test_migracion_014.py` · `test_upgrade_crea_tablas_y_siembra_textos` | cubierta |
| RN-TU-02 | `openspec/specs/whatsapp-messaging/spec.md` · "Recordatorio previo al turno", "Ritmo de envío limitado", "Fallo de envío va a la bandeja sin tocar el turno" | `backend/tests/integration/test_recordatorios.py` · `test_recordatorio_enviado_una_sola_vez`, `test_turno_fuera_de_ventana_no_recibe`, `test_ritmo_de_envio_limitado`, `test_reintento_exitoso_reutiliza_la_fila`; `backend/tests/integration/test_recordatorios_concurrencia.py` · `test_dos_corridas_simultaneas_un_solo_envio` | cubierta |
| RN-TU-03 | `openspec/specs/whatsapp-messaging/spec.md` · "Interpretación de la respuesta del paciente", "La respuesta del paciente actualiza la agenda", "Evento duplicado no repite efectos", "Webhook de eventos autenticado"; `openspec/specs/appointments/spec.md` · "Transiciones del paciente por enlace" (actor `paciente_whatsapp`) | `backend/tests/integration/test_whatsapp_entrante.py` · `test_si_confirma_el_turno`, `test_dos_cancela_y_libera_el_hueco`, `test_reprogramar_va_a_la_bandeja_con_respuesta`; `backend/tests/integration/test_whatsapp_idempotencia.py` · `test_mismo_evento_dos_veces_en_paralelo`; `backend/tests/integration/test_whatsapp_webhook_api.py` · `test_firma_valida_confirma_sin_jwt`, `test_firma_invalida_401_sin_efectos` | parcial: confirmar y cancelar están cubiertos; reprogramar solo deja el pedido en la bandeja (el chatbot es C-17) |

Resumen: 5 reglas (3 RN-WA + 2 RN-TU) · 4 cubiertas · 1 parcial · 0 pendientes. Trazabilidad por significado: ningún test cita el código RN.

### Conflictos detectados

- `knowledge-base/04_modelo_de_datos.md` §Seed decía "Plantillas WhatsApp aprobadas" y `knowledge-base/06_funcionalidades.md` US-005 decía "Plantillas aprobadas" (y el título de la Épica 2 "WhatsApp oficial"): contradicen DD-10. **Corregido en la KB el 2026-11-17** (textos base internos).
- `knowledge-base/01_vision_y_objetivos.md` (objetivo de recepcionista), `knowledge-base/README.md` y el plan de validación de SU-07 en `knowledge-base/09_decisiones_y_supuestos.md` hablaban de WhatsApp oficial/BSP/plantillas. **Corregido en la KB el 2026-11-17.** Las menciones de "WhatsApp oficial" en el análisis de mercado (`01` §Propósito, `02` §Justificación) describen a la competencia, no son reglas: se dejan.
- Variables de entorno: `knowledge-base/08_arquitectura_propuesta.md` y la ficha C-15 de `CHANGES.md` nombraban `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID` y `WHATSAPP_WEBHOOK_VERIFY`, y el repo tenía otras 4 variables que ningún código leía. **Resuelto en C-15 (D10):** las variables del gateway reemplazan a ambas listas y `08` quedó actualizado el 2026-11-17.

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Ninguna implementación contradice DD-10 (QR con número dedicado, detrás de `MensajeriaPort`).
- [ ] Evento entrante duplicado no duplica la transición; costo en `NUMERIC` ARS; sesión caída → bandeja de fallos + fallback.
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14).
