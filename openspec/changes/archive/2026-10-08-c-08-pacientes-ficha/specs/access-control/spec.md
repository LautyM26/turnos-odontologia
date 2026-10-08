# Spec Delta — access-control

## ADDED Requirements

### Requirement: Acceso a datos administrativos del paciente por rol

El sistema SHALL permitir crear, leer, buscar y editar datos administrativos, de contacto, obra social y consentimiento de pacientes a los roles admin, recepcionista y odontólogo de la clínica, y SHALL responder `403` a cualquier otro rol (incluido paciente-enlace).

#### Scenario: Recepcionista gestiona contacto

- **WHEN** un recepcionista crea o edita el teléfono de un paciente
- **THEN** el sistema lo permite.

#### Scenario: Rol paciente-enlace en API privada

- **WHEN** un JWT con solo rol `paciente-enlace` llama a `/api/pacientes`
- **THEN** el sistema responde `403`.

### Requirement: Lectura clínica solo admin y odontólogo

El sistema SHALL permitir leer ficha, historial de ficha, listado y contenido de adjuntos solo a admin y odontólogo; el recepcionista SHALL recibir `403` en todo endpoint clínico del paciente.

#### Scenario: Recepcionista lee ficha

- **WHEN** un recepcionista pide `GET /api/pacientes/{id}/ficha` o un adjunto
- **THEN** el sistema responde `403` y no audita una lectura clínica.

#### Scenario: Admin lee ficha

- **WHEN** un admin pide la ficha de un paciente de su clínica
- **THEN** el sistema la retorna y audita la lectura.

### Requirement: Escritura clínica solo odontólogo

El sistema SHALL permitir crear versiones de ficha y subir adjuntos solo a usuarios con rol odontólogo; admin sin rol odontólogo y recepcionista SHALL recibir `403`.

#### Scenario: Admin sin rol odontólogo edita ficha

- **WHEN** un usuario solo admin hace PUT de ficha
- **THEN** el sistema responde `403` y no crea versión.

#### Scenario: Dueño con roles admin y odontólogo

- **WHEN** un usuario con roles admin y odontólogo hace PUT de ficha de un paciente con consentimiento
- **THEN** el sistema crea la versión.

### Requirement: Vínculo odontólogo–paciente

El sistema SHALL decidir el acceso clínico de un odontólogo a un paciente mediante una regla de vínculo reemplazable que falla cerrado (`403`) ante error. Hasta que existan turnos, la regla interina SHALL otorgar vínculo con todo paciente de su propia clínica, con cada lectura clínica auditada.

#### Scenario: Regla interina dentro de la clínica

- **WHEN** un odontólogo pide la ficha de un paciente de su clínica antes de existir turnos
- **THEN** el sistema la retorna y registra el evento de lectura.

#### Scenario: Regla de vínculo niega acceso

- **WHEN** la regla de vínculo configurada indica que el odontólogo no está vinculado al paciente
- **THEN** el sistema responde `403` en ficha y adjuntos de ese paciente.

#### Scenario: Paciente de otra clínica

- **WHEN** un odontólogo pide la ficha de un paciente de otra clínica
- **THEN** el sistema responde `404` sin evaluar el vínculo.
