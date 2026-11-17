# Spec Delta — data-export

## MODIFIED Requirements

### Requirement: Exportación completa en ZIP de CSV

El sistema SHALL responder a `GET /api/admin/exportacion?formato=csv` con un archivo ZIP descargable que contenga un CSV por entidad existente del tenant (pacientes, fichas, adjuntos, odontogramas, evoluciones, consentimientos, firmas, turnos, historial de turnos, catálogo, usuarios, auditoría clínica, mensajes de WhatsApp, sesión de WhatsApp, lista de espera, ofertas de lista de espera y conversaciones de reprogramación), los archivos de los adjuntos y un `manifest.json`.

#### Scenario: Exportación de una clínica con datos

- **WHEN** un admin pide la exportación de una clínica con pacientes, ficha, odontograma, evoluciones, turnos y un consentimiento firmado
- **THEN** recibe `200` con `Content-Type: application/zip`, `Content-Disposition: attachment` y un ZIP con un CSV por entidad cuyas filas coinciden en cantidad con las de la base para esa clínica, más los archivos de adjuntos y el `manifest.json`.

#### Scenario: Clínica sin datos clínicos (borde)

- **WHEN** un admin exporta una clínica sin pacientes
- **THEN** recibe un ZIP válido donde cada CSV tiene solo la fila de encabezados y el manifest declara 0 filas para esas entidades.

#### Scenario: Formato PDF no soportado

- **WHEN** se pide `formato=pdf` o un formato desconocido
- **THEN** el sistema responde `422` indicando que el formato soportado es `csv` y no registra una exportación.

#### Scenario: Mensajes de WhatsApp incluidos y aislados

- **GIVEN** la clínica A tiene 2 mensajes de WhatsApp y la clínica B tiene 1
- **WHEN** el admin de A exporta
- **THEN** `mensajes_whatsapp.csv` tiene exactamente 2 filas de datos, ninguna de B, y el manifest declara 2 para `mensajes_whatsapp`.

#### Scenario: Lista de espera incluida y aislada

- **GIVEN** la clínica A tiene 2 entradas de lista de espera y la clínica B tiene 1
- **WHEN** el admin de A exporta
- **THEN** `lista_espera.csv` tiene exactamente 2 filas de datos, ninguna de B, y el manifest declara 2 para `lista_espera`.

#### Scenario: Conversaciones de reprogramación incluidas y aisladas

- **GIVEN** la clínica A tiene 1 conversación de reprogramación y la clínica B tiene 1
- **WHEN** el admin de A exporta
- **THEN** `conversaciones_whatsapp.csv` tiene exactamente 1 fila de datos, de A.
