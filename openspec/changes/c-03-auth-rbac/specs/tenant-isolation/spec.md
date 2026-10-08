# Spec Delta — tenant-isolation

## MODIFIED Requirements

### Requirement: Resolución de tenant por request

El sistema SHALL tomar el `tenant_id` del claim JWT como tenant autoritativo, SHALL mantener `X-Clinica-Id` como afirmación del cliente sujeta a cross-check (mismatch → `403`), SHALL rechazar con `401` todo request scoped sin JWT válido (salvo ruta pública declarada), SHALL rechazar con `4xx` el tenant inexistente y SHALL nunca defaultear a un tenant implícito.

#### Scenario: Request sin token

- **WHEN** un endpoint scoped recibe un request sin JWT válido y no es ruta pública
- **THEN** el sistema responde `401` sin tocar la base.

#### Scenario: Mismatch JWT vs header

- **WHEN** el JWT trae `tenant_id=A` pero el header `X-Clinica-Id` trae B
- **THEN** el sistema responde `403` y no ejecuta la operación.

#### Scenario: JWT de otro tenant no ve filas ajenas

- **WHEN** se consulta con un JWT del tenant A
- **THEN** el resultado contiene solo filas de A y cero filas de B (aunque el header afirme B).

#### Scenario: Request sin tenant header

- **WHEN** un endpoint scoped recibe un JWT válido sin header `X-Clinica-Id`
- **THEN** el sistema usa el `tenant_id` del JWT y ejecuta la operación (el header es afirmación opcional; sin JWT válido rige "Request sin token" → `401`).

#### Scenario: Tenant inexistente

- **WHEN** el JWT o el header refieren un `clinica_id` que no existe
- **THEN** el sistema responde `404` y no ejecuta la operación.

#### Scenario: Ruta pública sin token

- **WHEN** una ruta pública declarada (reserva, webhooks, comprobantes, cumplimiento) recibe un request sin JWT
- **THEN** el sistema la sirve sin exigir tenant autenticado.
