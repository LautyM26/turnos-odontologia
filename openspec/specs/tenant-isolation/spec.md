# tenant-isolation Specification

## Purpose

Garantiza que cada clínica (tenant) solo ve y modifica sus propios datos: toda lectura/escritura tenant-scoped está filtrada por `clinica_id` y ningún error de query expone filas de otro tenant.

## Requirements

### Requirement: Todo dato tenant-scoped exige clinica_id

El sistema SHALL exigir `clinica_id` NOT NULL en cada tabla tenant-scoped y SHALL filtrar por tenant toda lectura/escritura de esas tablas, de modo que una query con tenant A nunca retorne filas del tenant B.

#### Scenario: Query cruzada retorna cero filas

- **WHEN** existen usuarios en clínica A y clínica B y se consulta con tenant A
- **THEN** el resultado contiene solo filas de A y cero filas de B.

#### Scenario: Escritura sin tenant es rechazada

- **WHEN** se intenta persistir un registro tenant-scoped sin `clinica_id`
- **THEN** el sistema lo rechaza con error de validación/integridad (nunca lo guarda huérfano).

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

### Requirement: Soft-delete por defecto

El sistema SHALL implementar borrado lógico (`is_active=false` + `deleted_at`) y SHALL excluir filas inactivas de las lecturas por defecto; el borrado físico queda prohibido en dominio.

#### Scenario: Registro eliminado no aparece en listados

- **WHEN** se elimina lógicamente un usuario activo
- **THEN** los listados scoped dejan de incluirlo pero la fila persiste con `deleted_at` informado.

### Requirement: Índices por tenant en cada tabla scoped

Cada tabla tenant-scoped SHALL tener índice compuesto `(clinica_id, ...)` e índice parcial `WHERE is_active` en los listados calientes, verificable en la migración 001.

#### Scenario: Plan de query usa índice de tenant

- **WHEN** se explaina una query filtrada por `clinica_id` e `is_active`
- **THEN** el plan usa el índice compuesto/parcial (index scan, no seq scan en tablas con volumen).
