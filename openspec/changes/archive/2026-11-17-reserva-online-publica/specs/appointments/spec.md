# Spec Delta — appointments

## ADDED Requirements

### Requirement: Transiciones del paciente por enlace

El historial de transiciones SHALL registrar el tipo de actor de cada transición: `usuario` (con `actor_usuario_id` obligatorio) o `paciente_enlace` (sin usuario). Un turno reservado por enlace SHALL quedar con `origen = "enlace"`; uno creado en el mostrador, con `origen = "mostrador"`. La base SHALL rechazar una transición de tipo `usuario` sin `actor_usuario_id` y una de tipo `paciente_enlace` con usuario.

#### Scenario: Cancelación por enlace en el historial

- **WHEN** el paciente cancela su turno con el token
- **THEN** el historial guarda `desde = "reservado"`, `hacia = "cancelado"`, `actor_tipo = "paciente_enlace"` y `actor_usuario_id` nulo.

#### Scenario: Coherencia del actor

- **WHEN** se intenta insertar una transición `actor_tipo = "usuario"` sin `actor_usuario_id`
- **THEN** la base la rechaza (`23514`).
