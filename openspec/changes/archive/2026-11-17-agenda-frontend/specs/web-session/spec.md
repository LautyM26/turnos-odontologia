# Spec Delta — web-session

## ADDED Requirements

### Requirement: Navegación lateral del layout autenticado

El layout autenticado SHALL ofrecer una navegación lateral con "Agenda" y "Pacientes", con el ítem activo marcado (`aria-current="page"`), colapsable en pantallas chicas, y SHALL conservar en la barra superior la identidad, los roles y "Cerrar sesión". Tras el ingreso, el destino por defecto SHALL seguir siendo `/pacientes`, salvo que se pida otra ruta.

#### Scenario: Ir a la agenda desde el menú

- **WHEN** un usuario autenticado elige "Agenda" en la navegación
- **THEN** se abre `/agenda` y el ítem queda marcado como actual.

#### Scenario: Navegación en móvil

- **WHEN** el ancho es de 390 px
- **THEN** la navegación se abre con un botón accesible ("Abrir menú") y se cierra con Escape.
