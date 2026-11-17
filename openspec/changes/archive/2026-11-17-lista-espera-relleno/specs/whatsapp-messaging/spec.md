# Spec Delta — whatsapp-messaging

## MODIFIED Requirements

### Requirement: Interpretación de la respuesta del paciente

El sistema SHALL registrar cada mensaje entrante con costo 0, asociarlo al último saliente vigente a ese número en esa clínica (recordatorio con turno futuro u oferta de lista de espera con hueco futuro) e interpretar su primera palabra ignorando mayúsculas, tildes y signos: `1`/`si`/`confirmo`/`confirmar` → confirmar; `2`/`no`/`cancelo`/`cancelar` → cancelar; `3`/`reprogramar`/`cambiar` → reprogramar; otra → no interpretable. Ante una oferta, confirmar SHALL aceptarla y cancelar, rechazarla.

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

### Requirement: Textos base internos sembrados

El sistema SHALL disponer de siete textos base en español rioplatense (`recordatorio_24h`, `confirmacion`, `cancelacion`, `reprogramacion`, `oferta_hueco`, `oferta_aceptada`, `oferta_no_disponible`), propios de la plataforma y sin aprobación de Meta (DD-10), cuyas variables se completan en el servidor.

#### Scenario: Textos disponibles tras migrar

- **WHEN** se aplican las migraciones sobre una base vacía
- **THEN** existen exactamente esos siete textos base y el downgrade de cada migración elimina los suyos sin residuos.
