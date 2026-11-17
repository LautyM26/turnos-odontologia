# Spec Delta — public-booking-web

## Purpose

Pantallas públicas de la reserva online: elegir y reservar un hueco sin cuenta, y ver o cancelar la reserva con el enlace privado.

## ADDED Requirements

### Requirement: Página de reserva por clínica

La página `/reservar/{slug}` SHALL permitir, sin sesión:

1. elegir prestación y profesional;
2. ver los huecos de la semana agrupados por día, con navegación a la semana siguiente o anterior (nunca antes de hoy);
3. elegir un hueco;
4. cargar DNI, nombre, apellido y email o teléfono, y aceptar la política de privacidad con un enlace a `/privacidad`;
5. confirmar.

El fin del turno SHALL mostrarse tal como lo devuelve el servidor.

#### Scenario: Reserva completa (happy path)

- **WHEN** el visitante elige prestación, profesional y hueco, completa sus datos, acepta la política y confirma
- **THEN** la página navega a `/reserva/{token}` con el comprobante.

#### Scenario: Hueco tomado mientras completaba (borde)

- **WHEN** la API responde `409` al confirmar
- **THEN** la página avisa que el horario ya no está disponible, recarga los huecos y conserva los datos cargados para elegir otro.

#### Scenario: Datos inválidos

- **WHEN** la API responde `422`
- **THEN** la página muestra el error junto al formulario sin perder lo cargado.

#### Scenario: Enlace de clínica inexistente

- **WHEN** el slug no existe (`404`)
- **THEN** la página muestra "Enlace no encontrado".

### Requirement: Comprobante y cancelación

La página `/reserva/{token}` SHALL mostrar la clínica, el profesional, la prestación, la fecha y la hora en hora local, y el estado. SHALL ofrecer "Cancelar turno" con confirmación solo si el turno se puede cancelar. Tras cancelar, SHALL mostrar el estado `cancelado`.

#### Scenario: Cancelar desde el comprobante

- **WHEN** el paciente confirma la cancelación
- **THEN** la página muestra "Turno cancelado" y oculta el botón.

#### Scenario: Token inválido

- **WHEN** el token no existe (`404`)
- **THEN** la página muestra "Reserva no encontrada".

### Requirement: Accesibilidad y seguridad del frontend público

Las páginas públicas SHALL ser navegables con teclado, con etiquetas en cada campo, mensajes de error asociados al campo y anuncios de estado (`aria-live`) al reservar o cancelar. SHALL NOT guardar el token ni los datos del paciente en `localStorage`; el token vive solo en la URL del comprobante.

#### Scenario: Error anunciado

- **WHEN** falla la reserva
- **THEN** el mensaje se anuncia en una región `aria-live` y el foco vuelve al formulario.
