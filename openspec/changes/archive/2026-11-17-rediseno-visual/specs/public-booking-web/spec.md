# Spec Delta — public-booking-web

## ADDED Requirements

### Requirement: Reprogramar desde el comprobante

El comprobante `/reserva/{token}` SHALL ofrecer "Reprogramar", que lleva a `/reprogramar/{token}`, mientras el turno se pueda cancelar (reservado o confirmado y antes de su inicio), y SHALL ocultarlo en otro caso.

#### Scenario: Turno futuro

- **WHEN** el paciente abre el comprobante de un turno reservado para mañana
- **THEN** ve "Reprogramar" junto a "Cancelar turno".

#### Scenario: Turno cancelado

- **WHEN** el turno está cancelado
- **THEN** no se ofrece "Reprogramar".
