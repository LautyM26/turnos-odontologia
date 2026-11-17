# Proposal — lista-espera-relleno (C-16)

## Why

US-004 y Flujo 4 (RN-AG-06): cada turno cancelado es una hora de sillón perdida. Hoy la recepción tiene que llamar uno por uno para llenar ese hueco. C-05 ya garantiza que un hueco es reservable y C-15 ya manda y recibe WhatsApp con bandeja y costos. Falta conectar las dos cosas: cuando se libera un hueco, ofrecérselo automáticamente al primero de la lista, y que el paciente lo tome respondiendo "1".

## What Changes

- **Lista de espera** (`lista_espera`), una entrada por paciente y prestación activa:
  - prestación, profesional y sillón preferidos (opcionales);
  - prioridad;
  - estado `en_cola | ofertado | aceptado | salido`;
  - **turno a adelantar** (opcional): un turno futuro del mismo paciente. Solo se le ofrecen huecos anteriores a ese turno.
- **Ofertas** (`oferta_lista_espera`): un registro por cada hueco ofrecido a una entrada. Guarda el hueco (turno cancelado de origen, inicio y fin, profesional, sillón, prestación), el estado `pendiente | aceptada | rechazada | expirada | anulada`, el vencimiento, el mensaje de WhatsApp y el turno creado.
- **Relleno automático**: job `python -m app.jobs.lista_espera` (cron cada 5 min). En cada corrida:
  1. Vence las ofertas pasadas de `LISTA_ESPERA_OFERTA_MIN` (30 por defecto). La entrada vuelve a la cola.
  2. Busca los **huecos liberados**: turnos `cancelado`, que no son sobreturno, que empiezan dentro de `LISTA_ESPERA_ANTICIPACION_MIN` o más (120 por defecto), sin oferta pendiente y con el horario todavía libre.
  3. A cada hueco le elige la mejor entrada `en_cola` de la **misma prestación** (y del profesional o sillón preferido, si la entrada lo indica), con teléfono y que todavía no recibió ese hueco. El orden es prioridad y después antigüedad.
  4. Le envía el texto base `oferta_hueco` por WhatsApp, reutilizando `despachar` de C-15.
  5. Nadie disponible → el hueco queda libre. Gateway caído → la oferta se anula y la corrida se corta, para no quemar a toda la cola.
- **Respuesta del paciente** (extiende C-15): el mensaje entrante se asocia al último mensaje vigente a ese número, sea un recordatorio o una oferta.
  - **"1"/"sí" a una oferta pendiente**: se crea el turno (`origen = lista_espera`) con `crear_turno` (mismas reglas, 409 incluido). Si la entrada tenía turno a adelantar, ese turno se cancela con actor `paciente_whatsapp`. Su hueco queda liberado y la corrida siguiente lo ofrece. El paciente recibe el texto `oferta_aceptada`.
  - **"2"/"no"**: oferta rechazada, sin respuesta automática. La entrada vuelve a la cola para huecos futuros.
  - **Oferta vencida o ya tomada, o hueco ocupado entre la oferta y la respuesta**: texto `oferta_no_disponible`, sin crear nada.
  - **Doble aceptación** (eventos distintos o simultáneos): una sola reasignación efectiva.
- **API** (admin y recepción; odontólogo `403`):
  - CRUD `/api/lista-espera`. `DELETE` = sale de la cola y anula su oferta pendiente.
  - `POST /api/lista-espera/{id}/ofertar`: oferta manual de un hueco puntual.
  - `GET /api/lista-espera/bandeja`: ofertas recientes por estado.
  - `GET /api/lista-espera/metricas?desde&hasta`: huecos liberados, recuperados y perdidos (métrica de ocupación de `01`).
- **Textos base**: se suman `oferta_aceptada` y `oferta_no_disponible` (7 en total).
- **Configuración**: `LISTA_ESPERA_OFERTA_MIN=30` y `LISTA_ESPERA_ANTICIPACION_MIN=120`.
- **Exportación**: suma `lista_espera.csv` y `ofertas_lista_espera.csv`.
- Migración `015_lista_espera` (`down_revision = "014_whatsapp"`).

### Decisiones tomadas con el usuario (2026-11-17)

1. Una entrada puede indicar el turno a adelantar. Al aceptar, ese turno se cancela solo y su hueco vuelve a ofrecerse en cascada. Sin turno vinculado, la entrada es para quien todavía no tiene turno.
2. La oferta vence a los 30 min y solo se ofrecen huecos que empiezan dentro de 2 h o más. Ambos valores son configurables (SU-04).
3. Match por misma prestación, más profesional y sillón preferidos si la entrada los indica.

### Supuestos (registrados, de bajo impacto)

- **Solo los cancelados liberan huecos.** Un turno `ausente` se marca desde su inicio, cuando el hueco ya pasó. La reprogramación de C-17 libera el hueco cancelando, así que queda cubierta.
- **Hueco = turno cancelado.** "Reasignar" (Flujo 4) se implementa creando un turno nuevo en ese horario. El cancelado es terminal y su historial es inmutable.
- **Seña:** no aplica todavía (C-12). La política "transfiere/exige seña" queda para C-12.
- **Rechazar o dejar vencer la oferta no saca de la cola.** La entrada puede recibir huecos futuros; recepción la saca si hace falta.
- **Métrica "hora perdida"** = hueco liberado (cancelado, sin sobreturno) en el rango sin ninguna oferta aceptada. Si recepción lo llenó a mano también cuenta como perdido para la lista: mide lo que recupera la lista, no la ocupación total.

## Non-goals

- Pantallas de lista de espera y bandeja (C-07/C-14).
- Seña y cobro (C-12).
- Chatbot de reprogramación (C-17).
- Ofrecer huecos de otra prestación u otra duración.
- Detectar huecos al instante: el cron de 5 min se suma a una ventana de oferta de 30.

## Capabilities

### New Capabilities

- `waitlist`:
  - cola de espera con prioridad y turno a adelantar;
  - detección de huecos liberados;
  - oferta automática con vencimiento y rotación;
  - aceptación y rechazo con reasignación efectiva única;
  - oferta manual, bandeja y métricas;
  - RBAC y aislamiento por clínica.

### Modified Capabilities

- `whatsapp-messaging`: la respuesta se asocia también a la última oferta de lista de espera, y los textos base pasan a ser siete.
- `platform-config`: configuración de la ventana de oferta y de la anticipación mínima.
- `data-export`: la exportación incluye la lista de espera y sus ofertas.

## Impact

- **Código nuevo**:
  - `backend/app/domain/lista_espera/` (modelos, servicios, schemas);
  - `backend/app/api/lista_espera.py`;
  - `backend/app/jobs/lista_espera.py`;
  - `backend/alembic/versions/015_lista_espera.py`.
- **Código modificado**:
  - `domain/whatsapp/servicios.py`: asociación de la respuesta y render con variables explícitas;
  - `domain/agenda/turnos.py`: un helper público `horario_libre(...)` que envuelve el pre-chequeo existente. **Avisar a Matheo**;
  - `settings.py`, `.env.example`, `exportador.py`, `main.py`;
  - `docs/whatsapp-sesion.md`: el cron de la lista.
- **DB**:
  - tablas `lista_espera` y `oferta_lista_espera`, con índices `(clinica_id, prestacion_id, estado, prioridad)` y UNIQUE parciales (una oferta pendiente por hueco y por entrada; el mismo hueco nunca dos veces a la misma entrada; una entrada activa por paciente y prestación);
  - CHECK de `plantilla_wa.clave` ampliado.
- **Dependencias nuevas**: ninguna.
- **Governance**: MEDIO.
