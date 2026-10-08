# Spec Delta — clinic-catalog

## Purpose

Define el catálogo operativo de cada clínica — profesionales, sillones/recursos, prestaciones con duración propia y su habilitación cruzada — que el motor de turnos y la agenda consumen, aislado por tenant y administrado solo desde servidor.

## ADDED Requirements

### Requirement: Catálogo aislado por clínica

El sistema SHALL asociar cada profesional, sillón/recurso, prestación y habilitación a exactamente una clínica tomada del tenant del JWT (nunca del cuerpo del request) y SHALL devolver `404` ante cualquier lectura o escritura de un registro de otra clínica.

#### Scenario: Listado no incluye registros de otra clínica

- **WHEN** el admin de la clínica A lista profesionales y la clínica B tiene profesionales activos
- **THEN** la respuesta contiene solo profesionales de A (0 filas de B).

#### Scenario: Acceso por id ajeno

- **WHEN** el admin de A pide `GET /api/admin/prestaciones/{id}` con el id de una prestación de B
- **THEN** el sistema responde `404` sin revelar que existe.

#### Scenario: clinica_id en el cuerpo es rechazado

- **WHEN** un `POST /api/admin/sillones` incluye el campo `clinica_id`
- **THEN** el sistema responde `422` (campo no declarado).

### Requirement: Administración del catálogo solo por admin

El sistema SHALL permitir crear, leer, modificar y dar de baja profesionales, sillones/recursos, prestaciones y bloqueos bajo `/api/admin/*` únicamente al rol `admin`, respondiendo `401` sin token y `403` a cualquier otro rol.

#### Scenario: Admin crea una prestación

- **WHEN** un admin hace `POST /api/admin/prestaciones` con nombre, duración y precio válidos
- **THEN** el sistema responde `201` con la prestación creada y activa.

#### Scenario: Recepcionista intenta administrar

- **WHEN** un usuario con rol `recepcionista` hace `POST /api/admin/profesionales`
- **THEN** el sistema responde `403` y no persiste nada.

#### Scenario: Sin token

- **WHEN** se llama a `GET /api/admin/sillones` sin JWT
- **THEN** el sistema responde `401`.

### Requirement: Lectura del catálogo para el staff

El sistema SHALL exponer en `/api/catalogo/{profesionales,sillones,prestaciones}` la lista de registros activos del tenant a los roles `admin`, `recepcionista` y `odontologo`, y SHALL responder `403` a cualquier otro rol.

#### Scenario: Recepcionista lista prestaciones

- **WHEN** una recepcionista pide `GET /api/catalogo/prestaciones`
- **THEN** recibe solo las prestaciones activas de su clínica con su duración.

#### Scenario: Rol paciente-enlace rechazado

- **WHEN** un JWT con solo rol `paciente-enlace` pide `GET /api/catalogo/profesionales`
- **THEN** el sistema responde `403`.

### Requirement: Baja lógica del catálogo

El sistema SHALL dar de baja profesionales, sillones/recursos y prestaciones solo de forma lógica (inactivo + fecha de baja), SHALL excluirlos de los listados por defecto y SHALL permitir al admin verlos con un filtro explícito de inactivos.

#### Scenario: DELETE no borra físicamente

- **WHEN** un admin hace `DELETE /api/admin/sillones/{id}`
- **THEN** el sistema responde `204`, el sillón deja de aparecer en listados por defecto y la fila persiste inactiva con fecha de baja.

#### Scenario: Admin ve inactivos a pedido

- **WHEN** el admin lista sillones con el filtro de inactivos activado
- **THEN** el sillón dado de baja aparece marcado como inactivo.

### Requirement: Listados paginados por cursor

El sistema SHALL paginar los listados admin por cursor estable (orden por id ascendente, `limit` por defecto 50 y máximo 200) y SHALL devolver el cursor de la página siguiente o nulo al final; un `limit` fuera de rango SHALL responder `422`.

#### Scenario: Recorrido completo sin repetidos

- **WHEN** el admin recorre 120 prestaciones con `limit=50` siguiendo el cursor
- **THEN** obtiene 3 páginas (50, 50, 20) sin duplicados y la última trae cursor nulo.

#### Scenario: Limit excesivo

- **WHEN** el admin pide `limit=500`
- **THEN** el sistema responde `422`.

### Requirement: Profesional con matrícula única por clínica

El sistema SHALL exigir nombre y matrícula no vacíos para cada profesional, SHALL rechazar con `409` una matrícula repetida entre profesionales activos de la misma clínica y SHALL registrar los flags `agenda_activa` (por defecto verdadero) y `tercerizado` (por defecto falso).

#### Scenario: Matrícula repetida en la misma clínica

- **WHEN** el admin de A crea un profesional con una matrícula que ya usa otro profesional activo de A
- **THEN** el sistema responde `409`.

#### Scenario: Misma matrícula en otra clínica

- **WHEN** el admin de B crea un profesional con la misma matrícula que uno de A
- **THEN** el sistema lo crea sin conflicto.

### Requirement: Vínculo usuario–profesional para agenda propia

El sistema SHALL permitir vincular un profesional a lo sumo a un usuario activo de la misma clínica (y un usuario a lo sumo a un profesional activo) y SHALL usar ese vínculo para autorizar la agenda propia del odontólogo; sin vínculo el odontólogo SHALL recibir `403` sobre cualquier agenda.

#### Scenario: Odontólogo vinculado accede a su agenda

- **WHEN** un usuario `odontologo` vinculado al profesional P pide un recurso de agenda de P
- **THEN** el sistema lo autoriza.

#### Scenario: Odontólogo vinculado pide agenda ajena

- **WHEN** ese mismo usuario pide un recurso de agenda del profesional Q
- **THEN** el sistema responde `403`.

#### Scenario: Vínculo con usuario de otra clínica

- **WHEN** el admin de A intenta vincular un profesional a un usuario de B
- **THEN** el sistema responde `422` y no guarda el vínculo.

#### Scenario: Usuario ya vinculado

- **WHEN** el admin intenta vincular un segundo profesional activo al mismo usuario
- **THEN** el sistema responde `409`.

### Requirement: Sillón o recurso tipado

El sistema SHALL exigir para cada sillón/recurso un nombre único entre los activos de la clínica y un tipo dentro de `sillon`, `box` o `equipo`, rechazando cualquier otro tipo con `422` y un nombre duplicado con `409`.

#### Scenario: Tipo inválido

- **WHEN** el admin crea un recurso con tipo `quirofano`
- **THEN** el sistema responde `422`.

#### Scenario: Nombre duplicado

- **WHEN** el admin crea un segundo sillón activo llamado igual que uno existente de su clínica
- **THEN** el sistema responde `409`.

### Requirement: Prestación con duración propia

El sistema SHALL guardar para cada prestación una duración en minutos editable (entero entre 5 y 480) que define la duración del turno en lugar de un slot fijo (RN-AG-02), y SHALL rechazar con `422` duraciones fuera de rango o no enteras.

#### Scenario: Duraciones distintas por prestación

- **WHEN** existen "Consulta" de 30 min y "Obturación" de 60 min
- **THEN** el fin calculado para un inicio a las 10:00 es 10:30 y 11:00 respectivamente.

#### Scenario: Duración editada

- **WHEN** el admin cambia la duración de "Consulta" de 30 a 40 minutos
- **THEN** los cálculos posteriores de fin usan 40 minutos.

#### Scenario: Duración inválida

- **WHEN** el admin envía `duracion_min = 0` o `duracion_min = 600`
- **THEN** el sistema responde `422`.

### Requirement: Fin de turno calculado solo en servidor

El sistema SHALL calcular el fin de un turno como inicio más la duración de la prestación exclusivamente en el servidor, SHALL rechazar inicios sin zona horaria y SHALL ignorar cualquier fin o duración enviados por el cliente.

#### Scenario: Inicio sin zona horaria

- **WHEN** se pide calcular el fin para un inicio `2026-10-08T10:00:00` sin offset
- **THEN** el sistema lo rechaza como inválido (`422` en API).

#### Scenario: Cruce de medianoche

- **WHEN** una prestación de 60 min inicia a las 23:30-03:00
- **THEN** el fin es 00:30-03:00 del día siguiente.

### Requirement: Precio de referencia en ARS exacto

El sistema SHALL almacenar el precio de referencia de cada prestación como monto decimal exacto en ARS con 2 decimales, no negativo, SHALL rechazar con `422` montos negativos o con más de 2 decimales y SHALL serializarlo sin pérdida de precisión.

#### Scenario: Monto con centavos

- **WHEN** el admin guarda precio `15000.50`
- **THEN** la lectura devuelve exactamente `15000.50`.

#### Scenario: Monto negativo

- **WHEN** el admin envía precio `-1`
- **THEN** el sistema responde `422`.

### Requirement: Habilitación profesional–sillón

El sistema SHALL permitir al admin reemplazar el conjunto de sillones/recursos habilitados para un profesional, SHALL rechazar con `422` sillones inexistentes, inactivos o de otra clínica sin aplicar cambios parciales y SHALL exponer la habilitación en el detalle del profesional.

#### Scenario: Reemplazo del set

- **WHEN** el admin hace `PUT /api/admin/profesionales/{id}/sillones` con `[S1, S2]` y antes estaba habilitado `[S3]`
- **THEN** el detalle del profesional muestra exactamente `[S1, S2]`.

#### Scenario: Sillón de otra clínica

- **WHEN** el set incluye un sillón de otra clínica
- **THEN** el sistema responde `422` y la habilitación previa queda intacta.

### Requirement: Seed sintético de catálogo

El sistema SHALL proveer un seed idempotente que cree en la clínica piloto 1 sillón, 1 profesional y 3 prestaciones con duraciones de ejemplo, todos marcados como seed, sin datos reales, y SHALL permitir eliminarlos sin afectar registros no-seed.

#### Scenario: Re-ejecución sin duplicados

- **WHEN** el seed de catálogo se ejecuta dos veces
- **THEN** existen exactamente 1 sillón, 1 profesional y 3 prestaciones seed en la clínica piloto.

#### Scenario: Borrado del seed

- **WHEN** se ejecuta la limpieza de seed y la clínica tiene además una prestación cargada por el admin
- **THEN** desaparecen solo los registros marcados como seed y la prestación del admin persiste.
