# Spec Delta — waitlist

## Purpose

Lista de espera con relleno automático (US-004, Flujo 4, RN-AG-06): cuando un turno se cancela, el hueco se ofrece por WhatsApp al primero de la cola que coincide, y el paciente lo toma respondiendo; así se recuperan horas de sillón sin llamar uno por uno.

> Datos de los escenarios 100 % sintéticos: clínicas A y B, profesional P, sillón S1, prestación "Control sintético" (30 min), pacientes "Sintético 1/2/3" con teléfono. "Ahora" = `2031-03-10 12:00` UTC. Oferta vence a los 30 min; anticipación mínima 2 h.

## ADDED Requirements

### Requirement: Alta en la lista de espera

El sistema SHALL permitir a `admin` y `recepcionista` anotar en `POST /api/lista-espera` a un paciente de su clínica para una prestación, con profesional y sillón preferidos opcionales, prioridad (0 a 10, mayor primero) y opcionalmente un turno futuro activo del mismo paciente a adelantar. Referencias inválidas o ajenas SHALL responder `422`; una segunda entrada activa del mismo paciente y prestación, `409`.

#### Scenario: Alta con turno a adelantar (happy path)

- **GIVEN** Sintético 1 tiene un turno el `2031-03-20`
- **WHEN** la recepcionista lo anota para "Control sintético" con ese turno a adelantar
- **THEN** el sistema responde `201` con la entrada `en_cola`.

#### Scenario: Turno a adelantar de otro paciente (error)

- **WHEN** se indica como turno a adelantar un turno de Sintético 2
- **THEN** el sistema responde `422` sin crear la entrada.

#### Scenario: Entrada duplicada

- **GIVEN** Sintético 1 ya está `en_cola` para "Control sintético"
- **WHEN** se lo anota de nuevo para la misma prestación
- **THEN** el sistema responde `409`.

### Requirement: Consulta y edición de la lista

El sistema SHALL listar en `GET /api/lista-espera` las entradas activas (`en_cola` y `ofertado`) de la clínica ordenadas por prioridad descendente y antigüedad, filtrables por prestación; SHALL permitir cambiar prioridad y preferencias en `PATCH /api/lista-espera/{id}`; y `DELETE /api/lista-espera/{id}` SHALL pasar la entrada a `salido` y anular su oferta pendiente. Una entrada de otra clínica SHALL responder `404`.

#### Scenario: Orden de la cola

- **GIVEN** tres entradas con prioridades 0, 5 y 5 (la segunda más antigua)
- **WHEN** se pide la lista
- **THEN** salen primero las de prioridad 5, la más antigua antes, y al final la de prioridad 0.

#### Scenario: Salir de la cola con oferta pendiente

- **GIVEN** la entrada de Sintético 1 tiene una oferta pendiente
- **WHEN** la recepcionista la da de baja
- **THEN** la entrada queda `salido` y la oferta `anulada`.

### Requirement: Detección de huecos liberados

El sistema SHALL considerar hueco liberado a todo turno `cancelado`, activo, no sobreturno, cuyo inicio esté al menos a la anticipación mínima configurada y cuyo horario siga libre (sin otro turno activo superpuesto del profesional o del sillón ni bloqueo). Un hueco con una oferta pendiente SHALL NOT recibir otra oferta simultánea.

#### Scenario: Cancelación a tiempo genera hueco

- **GIVEN** un turno del `2031-03-11 10:00` se cancela
- **WHEN** corre el proceso de la lista de espera
- **THEN** ese horario se trata como hueco liberado.

#### Scenario: Hueco demasiado cercano (borde)

- **GIVEN** un turno que empieza en 90 minutos se cancela
- **WHEN** corre el proceso
- **THEN** no se ofrece.

#### Scenario: Hueco ya ocupado de nuevo

- **GIVEN** la recepción ya dio otro turno en el horario cancelado
- **WHEN** corre el proceso
- **THEN** no se ofrece.

### Requirement: Oferta automática al primero que coincide

Por cada hueco liberado, el sistema SHALL elegir la entrada `en_cola` de mayor prioridad (y más antigua) con la misma prestación, cuyo profesional y sillón preferidos (si los tiene) coincidan con el hueco, con teléfono, a la que nunca se le ofreció ese hueco y, si tiene turno a adelantar, cuyo turno empiece después del hueco. SHALL crear una oferta `pendiente` que vence a los minutos configurados, pasar la entrada a `ofertado` y enviarle el texto base `oferta_hueco`.

#### Scenario: Cancelación dispara oferta al primero (happy path)

- **GIVEN** Sintético 2 (prioridad 5) y Sintético 3 (prioridad 0) esperan "Control sintético" y se cancela un turno de esa prestación
- **WHEN** corre el proceso
- **THEN** Sintético 2 recibe por WhatsApp la oferta con fecha, hora y profesional, y su entrada queda `ofertado`.

#### Scenario: Otra prestación no coincide

- **GIVEN** solo hay entradas para otra prestación
- **WHEN** se libera un hueco de "Control sintético"
- **THEN** no se envía ninguna oferta.

#### Scenario: Turno a adelantar anterior al hueco

- **GIVEN** la entrada de Sintético 2 quiere adelantar un turno que es anterior al hueco liberado
- **WHEN** corre el proceso
- **THEN** a Sintético 2 no se le ofrece ese hueco.

### Requirement: Vencimiento y rotación de la oferta

Una oferta `pendiente` cuyo vencimiento pasó SHALL quedar `expirada` y su entrada SHALL volver a `en_cola`; en la misma corrida el hueco SHALL ofrecerse a la siguiente entrada elegible. Si nadie más es elegible, el hueco SHALL quedar libre en la agenda.

#### Scenario: Expirar pasa al siguiente

- **GIVEN** a Sintético 2 se le ofreció el hueco hace 31 minutos sin respuesta
- **WHEN** corre el proceso
- **THEN** su oferta queda `expirada`, su entrada `en_cola`, y Sintético 3 recibe la oferta del mismo hueco.

#### Scenario: Nadie más disponible

- **GIVEN** todas las entradas elegibles ya rechazaron o dejaron vencer ese hueco
- **WHEN** corre el proceso
- **THEN** no se envían más ofertas para ese hueco y el horario sigue libre.

### Requirement: Fallo del canal no consume la cola

Si la oferta no puede enviarse (canal no configurado, sesión caída o gateway no disponible), el sistema SHALL anular esa oferta, devolver la entrada a `en_cola`, dejar el fallo en la bandeja de WhatsApp y no seguir ofertando en esa corrida.

#### Scenario: Sesión caída

- **GIVEN** la sesión de WhatsApp de A está caída y hay un hueco liberado
- **WHEN** corre el proceso
- **THEN** la oferta queda `anulada`, la entrada sigue `en_cola` y el envío fallido aparece en `GET /api/whatsapp/fallos`.

### Requirement: Aceptar la oferta reasigna el hueco

Ante "1"/"sí" a una oferta `pendiente` y vigente, el sistema SHALL crear un turno en el horario del hueco para el paciente de la entrada, con el mismo profesional, sillón y prestación, origen `lista_espera` y las mismas validaciones que cualquier alta; SHALL marcar la oferta `aceptada` con el turno creado y la entrada `aceptado`, y SHALL responder al paciente con el texto base `oferta_aceptada`.

#### Scenario: Aceptar reasigna (happy path)

- **GIVEN** Sintético 2 tiene la oferta pendiente del hueco del `2031-03-11 10:00`
- **WHEN** responde "1"
- **THEN** existe un turno `reservado` de Sintético 2 a esa hora con origen `lista_espera`, la oferta está `aceptada` y recibe `oferta_aceptada`.

#### Scenario: Aceptar adelanta y libera el turno viejo

- **GIVEN** la entrada de Sintético 1 tenía como turno a adelantar el del `2031-03-20`
- **WHEN** acepta la oferta del `2031-03-11`
- **THEN** se crea el turno del 11, el del 20 pasa a `cancelado` con actor `paciente_whatsapp`, y en la corrida siguiente el horario del 20 se ofrece a la cola.

### Requirement: Aceptación sin hueco disponible

Si la oferta ya no está `pendiente` (vencida, rechazada o anulada) o el horario fue ocupado entre la oferta y la respuesta, el sistema SHALL NOT crear turno, SHALL anular la oferta si seguía pendiente, SHALL devolver la entrada a `en_cola` y SHALL responder con el texto base `oferta_no_disponible`.

#### Scenario: Hueco tomado en el medio (error de negocio)

- **GIVEN** Sintético 2 tiene la oferta pendiente y la recepción da ese horario a otro paciente
- **WHEN** Sintético 2 responde "1"
- **THEN** no se crea turno, la oferta queda `anulada` y recibe `oferta_no_disponible`.

#### Scenario: Aceptar una oferta vencida

- **GIVEN** la oferta de Sintético 2 ya está `expirada`
- **WHEN** responde "sí"
- **THEN** no se crea turno y recibe `oferta_no_disponible`.

### Requirement: Una sola reasignación por oferta

Ante aceptaciones repetidas de la misma oferta, por el mismo evento o por mensajes distintos, incluso simultáneas, el sistema SHALL crear un único turno y enviar una única respuesta `oferta_aceptada`; las repeticiones posteriores a una oferta ya `aceptada` SHALL NOT tener efectos.

#### Scenario: Doble aceptar → 1 efectivo (borde)

- **WHEN** llegan a la vez dos mensajes distintos "1" y "si" de Sintético 2 para la misma oferta
- **THEN** existe un solo turno nuevo y una sola respuesta `oferta_aceptada`.

### Requirement: Rechazar la oferta

Ante "2"/"no" a una oferta `pendiente`, el sistema SHALL marcarla `rechazada`, devolver la entrada a `en_cola` sin enviar respuesta automática; en la corrida siguiente el hueco SHALL ofrecerse a la siguiente entrada elegible.

#### Scenario: Rechazo rota la oferta

- **WHEN** Sintético 2 responde "no" a su oferta
- **THEN** la oferta queda `rechazada`, su entrada `en_cola`, y la próxima corrida ofrece el hueco a Sintético 3.

### Requirement: Oferta manual de un hueco

El sistema SHALL permitir a `admin` y `recepcionista` ofrecer en `POST /api/lista-espera/{id}/ofertar` un hueco liberado puntual (el turno cancelado de origen) a una entrada `en_cola`, salteando la prioridad pero no las reglas de coincidencia, anticipación y disponibilidad (`422` si no se cumplen) ni la oferta pendiente del hueco (`409`).

#### Scenario: Recepción elige a quién ofrecer

- **GIVEN** un hueco liberado sin oferta pendiente
- **WHEN** la recepcionista lo ofrece a la entrada de Sintético 3
- **THEN** el sistema responde `201` con la oferta `pendiente` y Sintético 3 recibe el WhatsApp.

#### Scenario: Hueco con oferta en curso

- **GIVEN** el hueco ya tiene una oferta pendiente a Sintético 2
- **WHEN** la recepcionista lo ofrece a Sintético 3
- **THEN** el sistema responde `409`.

### Requirement: Bandeja y métricas de recupero

El sistema SHALL responder en `GET /api/lista-espera/bandeja` a `admin` y `recepcionista` con las ofertas recientes de su clínica (paciente, hueco, estado, vencimiento, turno creado), y en `GET /api/lista-espera/metricas?desde&hasta` con la cantidad de huecos liberados en el rango, recuperados (con oferta aceptada) y perdidos (sin oferta aceptada); un rango invertido o mayor a 366 días SHALL responder `422`.

#### Scenario: Métrica de la semana

- **GIVEN** en la semana se cancelaron 3 turnos y uno se recuperó por la lista
- **WHEN** el admin pide las métricas de esa semana
- **THEN** responde liberados 3, recuperados 1, perdidos 2.

### Requirement: Lista de espera aislada y restringida por rol

Entradas y ofertas SHALL estar aisladas por clínica (0 filas de otra clínica; ids ajenos → `404`) y los endpoints de la lista SHALL responder `403` al `odontologo` y `401` sin token. Un hueco de una clínica SHALL ofrecerse solo a entradas de esa clínica.

#### Scenario: Hueco de A no se ofrece a la cola de B

- **GIVEN** B tiene entradas para una prestación propia y se cancela un turno de A
- **WHEN** corre el proceso
- **THEN** ninguna entrada de B recibe oferta.

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo pide `GET /api/lista-espera`
- **THEN** el sistema responde `403`.
