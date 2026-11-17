# Spec Delta — whatsapp-messaging

## MODIFIED Requirements

### Requirement: Interpretación de la respuesta del paciente

El sistema SHALL registrar cada entrante con costo 0. Si hay una conversación de reprogramación sin cerrar con ese número, SHALL tratarlo dentro de ella; si no, SHALL asociarlo al último saliente vigente (recordatorio con turno futuro u oferta con hueco futuro) e interpretar su primera palabra ignorando mayúsculas, tildes y signos: `1`/`si`/`confirmo`/`confirmar` → confirmar; `2`/`no`/`cancelo`/`cancelar` → cancelar; `3`/`reprogramar`/`cambiar` → reprogramar; otra → no interpretable.

#### Scenario: Variantes de confirmación

- **WHEN** llegan por separado "1", "SI", "Sí, confirmo" y "confirmar"
- **THEN** todas se interpretan como confirmar.

#### Scenario: Mensaje vacío o emoji (borde)

- **WHEN** llega un mensaje vacío o solo "👍"
- **THEN** se interpreta como no interpretable.

#### Scenario: Respuesta a una oferta y no al recordatorio

- **GIVEN** al paciente se le envió un recordatorio y después una oferta de lista de espera
- **WHEN** responde "1"
- **THEN** la respuesta acepta la oferta y el turno del recordatorio no cambia.

#### Scenario: Número dentro de la conversación

- **GIVEN** el paciente tiene una conversación de reprogramación eligiendo
- **WHEN** responde "2"
- **THEN** se toma como la opción 2 y no como cancelación del turno.

### Requirement: La respuesta del paciente actualiza la agenda

Confirmar y cancelar SHALL aplicar la transición de estado del turno asociado con actor `paciente_whatsapp`, en la misma transacción que registra el mensaje entrante, y luego SHALL responder al paciente con el texto base correspondiente (RN-TU-03). Reprogramar SHALL abrir la conversación de reprogramación cuando haya opciones; sin opciones SHALL dejar el pedido en la bandeja sin cambiar el turno.

#### Scenario: Respuesta "SI" confirma el turno (happy path)

- **GIVEN** a T se le envió el recordatorio
- **WHEN** llega del teléfono del paciente el mensaje "Sí!"
- **THEN** T pasa a `confirmado`, el historial registra `reservado → confirmado` con actor `paciente_whatsapp` y sin usuario, y el paciente recibe el texto base `confirmacion`.

#### Scenario: Respuesta "2" cancela y libera el hueco

- **GIVEN** a T se le envió el recordatorio
- **WHEN** llega el mensaje "2"
- **THEN** T pasa a `cancelado`, su horario queda libre para otro turno y el paciente recibe el texto base `cancelacion`.

#### Scenario: Pedido de reprogramación

- **WHEN** llega el mensaje "reprogramar"
- **THEN** T no cambia y el paciente recibe las opciones de reprogramación, o, si no hay huecos, el mensaje queda en la bandeja y recibe el texto base `reprogramacion`.

### Requirement: Textos base internos sembrados

El sistema SHALL disponer de doce textos base en español rioplatense (`recordatorio_24h`, `confirmacion`, `cancelacion`, `reprogramacion`, `oferta_hueco`, `oferta_aceptada`, `oferta_no_disponible`, `reprogramacion_opciones`, `reprogramacion_confirmar`, `reprogramacion_hecha`, `reprogramacion_sin_cambios`, `reprogramacion_vencida`), propios de la plataforma y sin aprobación de Meta (DD-10), cuyas variables se completan en el servidor.

#### Scenario: Textos disponibles tras migrar

- **WHEN** se aplican las migraciones sobre una base vacía
- **THEN** existen exactamente esos doce textos base y el downgrade de cada migración elimina los suyos sin residuos.
