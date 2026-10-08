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

El sistema SHALL resolver el tenant desde el header `X-Clinica-Id`, SHALL rechazar con `4xx` todo request scoped que llegue sin tenant o con tenant inexistente, y SHALL nunca defaultear a un tenant implícito.

#### Scenario: Request sin tenant header

- **WHEN** un endpoint scoped recibe un request sin `X-Clinica-Id`
- **THEN** el sistema responde `422` (tenant requerido) sin tocar la base.

#### Scenario: Tenant inexistente

- **WHEN** el header trae un `clinica_id` que no existe
- **THEN** el sistema responde `404` y no ejecuta la operación.

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
