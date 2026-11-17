# Spec Delta — clinical-record

## ADDED Requirements

### Requirement: Historia clínica consolidada

El sistema SHALL exponer `GET /api/pacientes/{id}/historia` con, en una sola respuesta, la ficha vigente, el odontograma vigente y la primera página de evoluciones (las 50 más recientes, en orden de registro descendente, con `next_cursor` para seguir en `/evoluciones`). Cada parte vacía SHALL devolverse como `version = 0` o como lista vacía, sin error.

#### Scenario: Historia completa (happy path)

- **GIVEN** un paciente con ficha en versión 2, odontograma en versión 1 y 3 evoluciones
- **WHEN** un odontólogo pide la historia
- **THEN** el sistema responde `200` con la ficha versión 2, el odontograma versión 1 y las 3 evoluciones de la más reciente a la más antigua.

#### Scenario: Paciente sin datos clínicos (borde)

- **WHEN** se pide la historia de un paciente sin ficha, sin odontograma y sin evoluciones
- **THEN** el sistema responde `200` con ficha `version = 0`, odontograma `version = 0` y evoluciones vacías.

#### Scenario: Historia de un paciente de otra clínica (error de negocio)

- **WHEN** un admin de la clínica A pide la historia de un paciente de la clínica B
- **THEN** el sistema responde `404`.

#### Scenario: Más de una página de evoluciones (borde)

- **GIVEN** un paciente con 51 evoluciones
- **WHEN** se pide la historia
- **THEN** la respuesta trae las 50 más recientes y un `next_cursor` que en `/evoluciones` devuelve la restante.
