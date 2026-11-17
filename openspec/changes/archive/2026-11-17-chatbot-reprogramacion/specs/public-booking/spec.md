# Spec Delta — public-booking

## ADDED Requirements

### Requirement: El token sigue al turno reprogramado

Cuando una reserva online se reprograma por su enlace, el mismo token SHALL identificar al turno nuevo: `GET /api/public/reservas/{token}` SHALL mostrar el horario nuevo y `POST /api/public/reservas/{token}/cancelar` SHALL cancelar el turno nuevo; el turno original SHALL quedar `cancelado` y sin token.

#### Scenario: Comprobante después de reprogramar

- **GIVEN** una reserva online reprogramada de las 10:00 a las 11:00 por su enlace
- **WHEN** el paciente abre el enlace de su reserva
- **THEN** ve el turno de las 11:00 y puede cancelarlo con el mismo token.
