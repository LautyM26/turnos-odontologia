# web-session Specification

## Purpose
Gobierna la sesión del staff de la clínica en el navegador: ingreso con email y contraseña, token de acceso solo en memoria, renovación silenciosa con la cookie HttpOnly, rutas protegidas y cierre de sesión, de modo que toda pantalla autenticada (clínica, y luego agenda) comparta un único mecanismo.

## Requirements

### Requirement: Ingreso del staff

El frontend SHALL ofrecer una pantalla `/login` con email y contraseña que llame a `POST /api/auth/login`; con éxito SHALL guardar el access token solo en memoria, cargar la identidad con `GET /api/auth/me` y navegar a la ruta pedida originalmente o, si no había, a `/pacientes`.

#### Scenario: Login correcto (happy path)

- **GIVEN** un usuario odontólogo sintético con credenciales válidas
- **WHEN** completa email y contraseña y envía el formulario
- **THEN** el frontend navega a `/pacientes` y muestra su email y su rol en la barra superior.

#### Scenario: Vuelve a la ruta pedida (borde)

- **GIVEN** un usuario sin sesión que abrió `/pacientes/7/odontograma`
- **WHEN** fue redirigido a `/login` e ingresa correctamente
- **THEN** el frontend lo lleva a `/pacientes/7/odontograma`.

#### Scenario: Credenciales inválidas (error de negocio)

- **WHEN** el backend responde `401` al login
- **THEN** el frontend muestra "Email o contraseña incorrectos" asociado al formulario, conserva el email escrito, limpia la contraseña y no navega.

#### Scenario: Demasiados intentos (borde)

- **WHEN** el backend responde `429` al login
- **THEN** el frontend muestra un mensaje que pide esperar un minuto antes de reintentar y no navega.

### Requirement: Token de acceso solo en memoria

El frontend SHALL mantener el access token únicamente en memoria del proceso y SHALL no escribirlo nunca en `localStorage`, `sessionStorage`, cookies legibles por JavaScript ni en la URL; el refresh token SHALL quedar solo en la cookie HttpOnly que gestiona el navegador.

#### Scenario: Ningún token en almacenamiento del navegador

- **WHEN** se audita el código fuente del frontend
- **THEN** no hay accesos a `localStorage` ni `sessionStorage`, y el access token solo se guarda en una variable en memoria.

#### Scenario: Recarga de la página (borde)

- **GIVEN** un usuario con sesión iniciada y cookie de refresh vigente
- **WHEN** recarga la página en `/pacientes/7`
- **THEN** el frontend recupera la sesión con `POST /api/auth/refresh` sin pedir credenciales y vuelve a mostrar `/pacientes/7`.

### Requirement: Rutas protegidas

El frontend SHALL exigir sesión para todas las rutas del staff (`/pacientes` y sus subrutas) y SHALL dejar públicas `/login`, `/`, `/reservar/:token`, `/cumplimiento` y `/comprobantes/:id`. Sin sesión ni refresh válido, una ruta protegida SHALL redirigir a `/login` recordando la ruta pedida.

#### Scenario: Ruta protegida sin sesión (error de negocio)

- **GIVEN** un navegador sin access en memoria y sin cookie de refresh válida
- **WHEN** se abre `/pacientes`
- **THEN** el frontend redirige a `/login` y no muestra datos de pacientes.

#### Scenario: Ruta pública sin sesión

- **WHEN** se abre `/cumplimiento` sin sesión
- **THEN** la página se muestra sin pasar por `/login`.

#### Scenario: Usuario ya logueado abre /login (borde)

- **GIVEN** un usuario con sesión vigente
- **WHEN** abre `/login`
- **THEN** el frontend lo lleva a `/pacientes`.

### Requirement: Renovación silenciosa y reintento único

Ante un `401` de un endpoint protegido, el frontend SHALL renovar el access con `POST /api/auth/refresh` y reintentar la request una sola vez. Las renovaciones concurrentes SHALL compartir una única llamada a `/api/auth/refresh`, porque el backend invalida un refresh ya rotado.

#### Scenario: Access vencido durante el uso (happy path)

- **GIVEN** un access vencido y una cookie de refresh vigente
- **WHEN** el frontend pide `/api/pacientes` y recibe `401`
- **THEN** llama una vez a `/api/auth/refresh`, reintenta `/api/pacientes` con el access nuevo y muestra el resultado sin intervención del usuario.

#### Scenario: Varias requests vencen a la vez (borde)

- **WHEN** tres requests paralelas reciben `401` al mismo tiempo
- **THEN** el frontend hace exactamente una llamada a `/api/auth/refresh` y reintenta las tres con el access nuevo.

#### Scenario: Refresh rechazado (error de negocio)

- **WHEN** `/api/auth/refresh` responde `401`
- **THEN** el frontend descarta la sesión en memoria, redirige a `/login` con el aviso "Tu sesión expiró, volvé a ingresar" y no reintenta en bucle.

### Requirement: Cierre de sesión

El frontend SHALL ofrecer "Cerrar sesión" en la barra superior, que llame a `POST /api/auth/logout`, descarte el access en memoria y la identidad cargada, y lleve a `/login`, incluso si el backend no responde.

#### Scenario: Logout (happy path)

- **WHEN** el usuario elige "Cerrar sesión"
- **THEN** el frontend llama a `/api/auth/logout`, navega a `/login` y una vuelta atrás del navegador a `/pacientes` vuelve a pedir login.

#### Scenario: Logout con el backend caído (borde)

- **WHEN** `/api/auth/logout` falla por red
- **THEN** el frontend igual descarta la sesión local y muestra `/login`.

### Requirement: Identidad y roles visibles

El frontend SHALL mostrar en el layout autenticado el email y los roles legibles del usuario (Administrador, Odontólogo, Recepcionista) tomados de `GET /api/auth/me`, y SHALL usar esos roles solo para mostrar u ocultar acciones; la autorización real SHALL seguir siendo la respuesta del backend.

#### Scenario: Recepcionista logueado

- **WHEN** ingresa un usuario con rol recepcionista
- **THEN** la barra superior muestra su email y "Recepcionista".

#### Scenario: Usuario con varios roles (borde)

- **WHEN** ingresa un usuario con roles admin y odontólogo
- **THEN** la barra superior muestra ambos roles.

### Requirement: Navegación lateral del layout autenticado

El layout autenticado SHALL ofrecer una navegación lateral con "Agenda" y "Pacientes", con el ítem activo marcado (`aria-current="page"`), colapsable en pantallas chicas, y SHALL conservar en la barra superior la identidad, los roles y "Cerrar sesión". Tras el ingreso, el destino por defecto SHALL seguir siendo `/pacientes`, salvo que se pida otra ruta.

#### Scenario: Ir a la agenda desde el menú

- **WHEN** un usuario autenticado elige "Agenda" en la navegación
- **THEN** se abre `/agenda` y el ítem queda marcado como actual.

#### Scenario: Navegación en móvil

- **WHEN** el ancho es de 390 px
- **THEN** la navegación se abre con un botón accesible ("Abrir menú") y se cierra con Escape.
