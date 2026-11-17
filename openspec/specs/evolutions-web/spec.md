# evolutions-web Specification

## Purpose
Gobierna la timeline de evoluciones clínicas en el navegador: registrar cada atención con su autor y la hora del servidor, mostrar la historia completa sin posibilidad de editarla ni borrarla, y corregir solo agregando una evolución nueva enlazada (Ley 26.529).

## Requirements

### Requirement: Timeline de evoluciones

La pestaña Evoluciones SHALL mostrar las evoluciones de la más reciente a la más antigua, cada una con fecha y hora (zona horaria de Argentina), profesional autor, pieza FDI si la tiene y texto completo, y SHALL ofrecer "Cargar anteriores" mientras exista `next_cursor`, pidiendo `GET /evoluciones?after_id=`.

#### Scenario: Timeline ordenada (happy path)

- **GIVEN** las evoluciones E1, E2 y E3 registradas en ese orden
- **WHEN** el usuario abre la pestaña
- **THEN** ve E3, E2 y E1 en ese orden, cada una con su profesional y su fecha.

#### Scenario: Más de una página (borde)

- **GIVEN** una historia con `next_cursor`
- **WHEN** el usuario elige "Cargar anteriores"
- **THEN** las evoluciones siguientes se agregan al final sin repetir ninguna.

#### Scenario: Sin evoluciones (borde)

- **WHEN** el paciente no tiene evoluciones
- **THEN** la pestaña muestra "Todavía no hay evoluciones registradas".

### Requirement: Historia sin edición ni borrado

La UI SHALL no ofrecer, para ninguna evolución, acciones de editar, borrar ni reordenar, y SHALL no enviar nunca `PUT`, `PATCH` ni `DELETE` a evoluciones. La única acción sobre una evolución existente SHALL ser "Corregir".

#### Scenario: Sin botones de edición (error de negocio)

- **WHEN** un odontólogo ve una evolución propia
- **THEN** no hay ningún control "Editar" ni "Eliminar"; solo "Corregir".

#### Scenario: Cliente sin métodos de edición (borde)

- **WHEN** se audita el código de evoluciones del frontend
- **THEN** no existe ninguna llamada con método `PUT`, `PATCH` ni `DELETE` a `/evoluciones`.

### Requirement: Alta de evolución

El odontólogo SHALL poder registrar una evolución con texto obligatorio (1 a 10 000 caracteres, con contador) y una pieza FDI opcional elegida de una lista válida; el cuerpo SHALL llevar solo `texto` y `pieza_fdi`, nunca autor ni fecha. Con `201`, la evolución SHALL aparecer primera en la timeline y el formulario SHALL vaciarse.

#### Scenario: Registrar una evolución (happy path)

- **WHEN** el odontólogo escribe "Control sintético, sin hallazgos", elige la pieza 16 y guarda
- **THEN** el frontend envía `{"texto": "...", "pieza_fdi": 16}` y la evolución aparece primera con su autor y la hora que devolvió el servidor.

#### Scenario: Texto vacío (error de negocio)

- **WHEN** el texto está vacío o solo tiene espacios
- **THEN** el frontend indica "Escribí la evolución" y no envía la request.

#### Scenario: Odontólogo sin profesional vinculado (borde)

- **WHEN** el servidor responde `422` por falta de autor profesional
- **THEN** el frontend muestra el motivo devuelto y conserva el texto escrito.

#### Scenario: Doble envío (borde)

- **WHEN** el odontólogo hace doble clic en "Guardar evolución"
- **THEN** el frontend envía una sola request.

### Requirement: Corrección como evolución nueva

"Corregir" SHALL abrir un formulario con el texto original como punto de partida y un motivo obligatorio (1 a 500 caracteres), y SHALL enviar `POST /evoluciones` con `texto`, `pieza_fdi`, `corrige_a_id` y `motivo_correccion`. Con `201`, la corrección SHALL aparecer primera y la original SHALL seguir visible, sin cambios en su texto.

#### Scenario: El autor corrige su evolución (happy path)

- **GIVEN** la evolución E1 del odontólogo O
- **WHEN** O corrige E1 con el texto "Texto corregido sintético" y el motivo "Pieza mal indicada"
- **THEN** aparece una evolución nueva E2 que muestra "Corrige a la evolución del <fecha de E1>" y su motivo, E1 sigue en la timeline con su texto original y la timeline tiene una entrada más que antes.

#### Scenario: Corrección sin motivo (error de negocio)

- **WHEN** el motivo está vacío
- **THEN** el frontend indica "Indicá el motivo de la corrección" y no envía la request.

#### Scenario: La evolución ya fue corregida (borde)

- **WHEN** el servidor responde `409` porque otra corrección llegó antes
- **THEN** el frontend muestra que esa evolución ya fue corregida, recarga la timeline y ofrece corregir la versión vigente.

### Requirement: Quién puede corregir

El frontend SHALL mostrar "Corregir" solo en evoluciones cuyo autor es el usuario actual, que todavía no fueron corregidas, y solo a usuarios con rol odontólogo. Otro profesional SHALL ver la evolución en modo lectura y SHALL poder registrar una evolución nueva. Un `403` del servidor SHALL mostrarse con su motivo.

#### Scenario: Evolución de otro profesional (borde)

- **GIVEN** la evolución E1 del odontólogo O
- **WHEN** la ve el odontólogo P
- **THEN** E1 no tiene "Corregir".

#### Scenario: Evolución ya corregida (borde)

- **GIVEN** E1 corregida por E2
- **WHEN** el autor ve la timeline
- **THEN** E1 no tiene "Corregir" y E2 sí.

### Requirement: Cadena de correcciones visible

Una evolución corregida SHALL mostrarse atenuada con la etiqueta "Corregida" y un enlace a la evolución que la corrige; una corrección SHALL mostrar a qué evolución corrige, con enlace, y su motivo. Los enlaces SHALL llevar el foco a la evolución destino dentro de la timeline.

#### Scenario: Navegar de la original a la corrección (happy path)

- **GIVEN** E1 corregida por E3
- **WHEN** el usuario elige "Ver corrección" en E1
- **THEN** la timeline se desplaza a E3 y E3 recibe el foco.
