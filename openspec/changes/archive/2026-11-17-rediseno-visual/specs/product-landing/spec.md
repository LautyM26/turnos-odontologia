# Spec Delta — product-landing

## Purpose

Página pública de presentación del producto en `/`: qué resuelve, sus diferenciales y los dos accesos principales (ingresar como staff, reservar como paciente).

## ADDED Requirements

### Requirement: Presentación del producto

La página `/` SHALL mostrar, sin sesión, un hero con el nombre del producto, una propuesta de valor de hasta 20 palabras, una captura real de la agenda (datos sintéticos) y dos acciones: "Ingresar" (`/login`) y "Reservar turno" (reserva pública de la clínica de demo). Debajo SHALL presentar los diferenciales del producto y un pie con enlaces a `/privacidad` y `/cumplimiento`.

#### Scenario: Visitante abre la home (happy path)

- **WHEN** un visitante sin sesión abre `/`
- **THEN** ve el hero con "Ingresar" y "Reservar turno", la captura de la agenda con texto alternativo descriptivo y los diferenciales.

#### Scenario: Ir a ingresar

- **WHEN** elige "Ingresar"
- **THEN** navega a `/login`.

#### Scenario: Ir a reservar

- **WHEN** elige "Reservar turno"
- **THEN** navega a `/reservar/clinica-piloto`.

### Requirement: Landing sin llamadas a la API ni datos personales

La landing SHALL renderizarse sin pedidos a la API. Sus capturas SHALL contener solo datos sintéticos (regla dura 14).

#### Scenario: Sin pedidos

- **WHEN** se abre `/`
- **THEN** no se hace ningún pedido a `/api/*`.
