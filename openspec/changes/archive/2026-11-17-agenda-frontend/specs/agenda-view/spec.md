# Spec Delta — agenda-view

## Purpose

Lectura de la agenda para el staff: los turnos y los bloqueos de una ventana de tiempo, con lo mínimo para pintarlos (nombres de paciente y prestación, estado, origen y sobreturno), respetando el rol y la clínica.

## ADDED Requirements

### Requirement: Listado de turnos de una ventana

El sistema SHALL responder en `GET /api/agenda/turnos` con `desde` y `hasta` (con zona, `hasta > desde`, ≤ 7 días; si no, `422`) los turnos no dados de baja de la clínica que se superponen con la ventana, ordenados por inicio, con paciente ("Apellido, Nombre"), prestación, estado, origen y marca de sobreturno. Los filtros `profesional_id` y `sillon_id` SHALL acotar el resultado.

#### Scenario: Día de la recepción (happy path)

- **GIVEN** la clínica A tiene el 2033-09-05 un turno de P en S1 a las 10:00 (`confirmado`) y un sobreturno de Q en S2 a las 10:15
- **WHEN** la recepcionista pide `GET /api/agenda/turnos?desde=2033-09-05T03:00Z&hasta=2033-09-06T03:00Z`
- **THEN** el sistema responde `200` con los dos turnos ordenados, con los nombres de paciente y prestación, y el segundo con `es_sobreturno = true`.

#### Scenario: Filtro por profesional

- **WHEN** se agrega `profesional_id = P`
- **THEN** solo vuelven los turnos de P.

#### Scenario: Cancelados incluidos para mostrarlos atenuados

- **GIVEN** un turno `cancelado` en la ventana
- **WHEN** se pide la agenda
- **THEN** el turno vuelve con `estado = "cancelado"`; los dados de baja lógica no vuelven.

#### Scenario: Ventana mayor a 7 días (error de negocio)

- **WHEN** se pide una ventana de 8 días o con `hasta <= desde`
- **THEN** el sistema responde `422`.

### Requirement: Bloqueos visibles para el staff

El sistema SHALL responder en `GET /api/agenda/bloqueos` con `desde` y `hasta` (mismas reglas de ventana) los bloqueos activos que se superponen con la ventana: los de toda la clínica, los de profesional (filtrables con `profesional_id`) y los de sillón. Cada bloqueo SHALL incluir id, alcance (clínica, profesional o sillón con su id), inicio, fin y motivo.

#### Scenario: Feriado de clínica y almuerzo del profesional

- **GIVEN** un bloqueo de clínica que cubre el día y uno de P de 13:00 a 14:00
- **WHEN** la recepcionista pide los bloqueos del día
- **THEN** el sistema responde `200` con ambos y su alcance.

### Requirement: Agenda por rol y por clínica

Admin y recepcionista SHALL poder leer la agenda de toda su clínica. El odontólogo SHALL leer solo la agenda del profesional vinculado a su usuario: SHALL enviar `profesional_id` y, si es otro, recibir `403`. Sin autenticación SHALL responder `401`. Ninguna consulta SHALL devolver turnos ni bloqueos de otra clínica.

#### Scenario: Odontólogo ve su agenda

- **WHEN** el odontólogo vinculado a P pide la agenda con `profesional_id = P`
- **THEN** el sistema responde `200` solo con turnos de P.

#### Scenario: Odontólogo pide otra agenda

- **WHEN** el odontólogo vinculado a P pide `profesional_id = Q`
- **THEN** el sistema responde `403`.

#### Scenario: Aislamiento entre clínicas

- **GIVEN** la clínica B tiene turnos y bloqueos en la misma ventana
- **WHEN** la recepcionista de A pide la agenda
- **THEN** no vuelve ninguna fila de B.
