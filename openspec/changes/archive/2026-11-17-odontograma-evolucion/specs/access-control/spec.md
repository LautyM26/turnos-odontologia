# Spec Delta — access-control

## MODIFIED Requirements

### Requirement: Lectura clínica solo admin y odontólogo

El sistema SHALL permitir leer ficha, historial de ficha, listado y contenido de adjuntos, odontograma (vigente e historial), evoluciones e historia consolidada solo a admin y odontólogo; el recepcionista SHALL recibir `403` en todo endpoint clínico del paciente.

#### Scenario: Recepcionista lee ficha

- **WHEN** un recepcionista pide `GET /api/pacientes/{id}/ficha` o un adjunto
- **THEN** el sistema responde `403` y no audita una lectura clínica.

#### Scenario: Admin lee ficha

- **WHEN** un admin pide la ficha de un paciente de su clínica
- **THEN** el sistema la retorna y audita la lectura.

#### Scenario: Recepcionista en odontograma, evoluciones o historia

- **WHEN** un recepcionista pide el odontograma, las evoluciones o la historia de un paciente de su clínica
- **THEN** el sistema responde `403` y no audita una lectura clínica.

#### Scenario: Paciente-enlace en endpoints clínicos (borde)

- **WHEN** un JWT con solo rol `paciente-enlace` pide `/api/pacientes/{id}/historia`
- **THEN** el sistema responde `403`.

### Requirement: Escritura clínica solo odontólogo

El sistema SHALL permitir crear versiones de ficha, subir adjuntos, guardar versiones de odontograma y registrar o corregir evoluciones solo a usuarios con rol odontólogo; admin sin rol odontólogo y recepcionista SHALL recibir `403`.

#### Scenario: Admin sin rol odontólogo edita ficha

- **WHEN** un usuario solo admin hace PUT de ficha
- **THEN** el sistema responde `403` y no crea versión.

#### Scenario: Dueño con roles admin y odontólogo

- **WHEN** un usuario con roles admin y odontólogo hace PUT de ficha de un paciente con consentimiento
- **THEN** el sistema crea la versión.

#### Scenario: Recepcionista registra una evolución

- **WHEN** un recepcionista envía `POST /api/pacientes/{id}/evoluciones` o `POST /api/pacientes/{id}/odontograma`
- **THEN** el sistema responde `403` y no crea nada.

#### Scenario: Admin sin rol odontólogo guarda odontograma (borde)

- **WHEN** un usuario solo admin guarda un odontograma o registra una evolución
- **THEN** el sistema responde `403` y no crea nada.

### Requirement: Vínculo odontólogo–paciente

El sistema SHALL decidir el acceso clínico de un odontólogo a un paciente, incluidos odontograma, evoluciones e historia, mediante una regla de vínculo reemplazable que falla cerrado (`403`) ante error. Hasta que se inyecte una regla basada en turnos, la regla interina SHALL otorgar vínculo con todo paciente de su propia clínica, con cada lectura clínica auditada.

#### Scenario: Regla interina dentro de la clínica

- **WHEN** un odontólogo pide la ficha de un paciente de su clínica antes de existir turnos
- **THEN** el sistema la retorna y registra el evento de lectura.

#### Scenario: Regla de vínculo niega acceso

- **WHEN** la regla de vínculo configurada indica que el odontólogo no está vinculado al paciente
- **THEN** el sistema responde `403` en ficha, adjuntos, odontograma, evoluciones e historia de ese paciente.

#### Scenario: Paciente de otra clínica

- **WHEN** un odontólogo pide la ficha de un paciente de otra clínica
- **THEN** el sistema responde `404` sin evaluar el vínculo.
