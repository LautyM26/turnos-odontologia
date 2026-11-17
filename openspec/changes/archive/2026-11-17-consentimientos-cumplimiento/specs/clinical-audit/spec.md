# Spec Delta — clinical-audit

## ADDED Requirements

### Requirement: Consentimientos auditados en la auditoría clínica

El sistema SHALL registrar en la auditoría clínica, en la misma transacción, un evento `crear` al generar un consentimiento y un evento `firmar` al firmarlo (entidad `consentimiento`), y un evento `leer` por cada listado o detalle consultado, con diff limitado a ids y versión de texto, sin el texto ni los datos del firmante.

#### Scenario: Generación y firma auditadas

- **WHEN** un odontólogo genera el consentimiento C1 y luego lo firma
- **THEN** existen un evento `crear` y un evento `firmar` sobre la entidad `consentimiento` con id C1, su usuario como actor y la fecha del servidor.

#### Scenario: Lectura auditada

- **WHEN** un admin consulta el detalle de un consentimiento
- **THEN** existe un evento `leer` sobre la entidad `consentimiento` con ese id.

#### Scenario: Firma incompleta sin evento (borde)

- **WHEN** una firma termina en `422`, `409` o `403`
- **THEN** no existe evento `firmar` para esa request y el diff de los eventos existentes no contiene `firmante_nombre`, `firmante_dni` ni el texto.
