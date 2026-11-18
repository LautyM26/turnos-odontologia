# Spec Delta — visual-theme

## Purpose

Sistema visual común a todas las pantallas (`design-system/turnos-odontologia/MASTER.md`): tokens, tipografía, componentes, modo claro y oscuro, motion según el contexto y accesibilidad base.

## ADDED Requirements

### Requirement: Modo claro y oscuro

La interfaz SHALL seguir por defecto la preferencia de color del sistema operativo y SHALL ofrecer un control accesible para elegir "Claro", "Oscuro" o "Sistema", disponible en la barra del layout autenticado y en las páginas públicas. La elección SHALL recordarse en el navegador sin datos personales, y SHALL aplicarse antes del primer pintado para evitar el parpadeo.

#### Scenario: Preferencia del sistema (happy path)

- **GIVEN** el sistema operativo en modo oscuro y sin elección guardada
- **WHEN** se abre cualquier pantalla
- **THEN** se ve en modo oscuro.

#### Scenario: Elegir modo manualmente

- **WHEN** el usuario elige "Claro" en el control de tema
- **THEN** la interfaz pasa a modo claro y se mantiene así al recargar.

#### Scenario: Contraste en ambos modos

- **WHEN** se revisa cualquier texto o control en modo claro u oscuro
- **THEN** el contraste del texto es al menos 4,5:1 y el de los bordes de controles al menos 3:1.

### Requirement: Convención clínica del odontograma intacta

El rediseño SHALL conservar la lógica del odontograma, la numeración FDI y la convención de colores (rojo = a realizar, azul = existente) en ambos modos, y SHALL NOT cambiar el comportamiento ni los permisos de ninguna pantalla clínica.

#### Scenario: Colores clínicos en modo oscuro

- **WHEN** se ve el odontograma en modo oscuro
- **THEN** los hallazgos a realizar siguen en rojo y los existentes en azul, con contraste suficiente sobre el fondo.

### Requirement: Motion según el contexto

Las páginas públicas SHALL usar entradas escalonadas y reveal al hacer scroll, y las pantallas de la app SHALL limitarse a transiciones de estado breves. Toda animación SHALL respetar `prefers-reduced-motion` (estado final inmediato) y SHALL animar solo `transform` y `opacity`.

#### Scenario: Movimiento reducido

- **GIVEN** el sistema con `prefers-reduced-motion: reduce`
- **WHEN** se abre la landing
- **THEN** todo el contenido aparece directamente, sin animaciones de entrada.

### Requirement: Pantallas con el sistema de diseño

Login, pacientes, ficha, odontograma, evoluciones, adjuntos, reserva, comprobantes, legales y 404 SHALL usar los componentes y tokens del sistema de diseño: encabezado de página consistente, controles con label visible, errores junto al campo, estados de carga, vacío y error, e íconos de una sola familia. Los textos, roles y nombres accesibles de los que dependen los flujos SHALL mantenerse.

#### Scenario: Login rediseñado

- **WHEN** se abre `/login`
- **THEN** se ve el formulario con el sistema de diseño, con los campos "Email" y "Contraseña" y el botón "Ingresar".

#### Scenario: Página no encontrada

- **WHEN** se abre una ruta inexistente con sesión
- **THEN** se ve "Página no encontrada" con un acceso para volver.
