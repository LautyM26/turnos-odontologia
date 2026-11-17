# Spec Delta — clinical-evolutions

## Purpose

Gobierna las evoluciones clínicas del paciente: el registro de cada atención con autor profesional y fecha/hora del servidor, que nunca se edita ni se borra y que solo se corrige agregando una evolución nueva enlazada (Ley 26.529).

## ADDED Requirements

### Requirement: Alta de evolución con autor profesional y hora del servidor

El sistema SHALL crear una evolución con `POST /api/pacientes/{id}/evoluciones` y responder `201`. El autor SHALL ser el usuario autenticado y su profesional vinculado, y la fecha/hora SHALL asignarla el servidor (TIMESTAMPTZ). El cuerpo SHALL admitir solo `texto` (1 a 10 000 caracteres, sin contar espacios en los bordes), `pieza_fdi` opcional y los campos de corrección (RN-CL-01).

#### Scenario: Odontólogo registra una evolución (happy path)

- **GIVEN** un paciente con consentimiento y un odontólogo vinculado a un profesional activo
- **WHEN** el odontólogo envía `{"texto": "Control sintético", "pieza_fdi": 16}`
- **THEN** el sistema responde `201` con el texto, la pieza, su usuario como autor, el profesional vinculado y la fecha/hora del servidor.

#### Scenario: Texto vacío (error de negocio)

- **WHEN** el odontólogo envía `texto` vacío o con solo espacios
- **THEN** el sistema responde `422` y no crea la evolución.

#### Scenario: Pieza FDI inexistente (borde)

- **WHEN** el odontólogo envía `pieza_fdi = 19`
- **THEN** el sistema responde `422` y no crea la evolución.

### Requirement: Evolución sin autor rechazada

El sistema SHALL rechazar con `422`, sin persistir nada, toda evolución cuyo autor profesional no pueda determinarse: un usuario odontólogo sin profesional activo vinculado, o un cuerpo que intente declarar el autor, el profesional o la fecha/hora. La base de datos SHALL rechazar una evolución sin autor o sin profesional (RN-CL-01, regla dura 15).

#### Scenario: Odontólogo sin profesional vinculado (error de negocio)

- **GIVEN** un usuario con rol odontólogo sin profesional activo vinculado
- **WHEN** envía una evolución válida
- **THEN** el sistema responde `422` indicando que falta el autor profesional, y no se crea la evolución.

#### Scenario: Autor declarado en el cuerpo

- **WHEN** el cuerpo incluye `autor_usuario_id`, `profesional_id` o `fecha_hora`
- **THEN** el sistema responde `422` y no crea la evolución.

#### Scenario: INSERT directo sin autor (borde)

- **WHEN** se inserta una evolución con `autor_usuario_id` o `profesional_id` nulos usando la conexión de la aplicación
- **THEN** la base de datos rechaza la sentencia.

### Requirement: Evoluciones sin edición ni borrado

El sistema SHALL no exponer `PUT`, `PATCH` ni `DELETE` sobre evoluciones (`405`), y la base de datos SHALL rechazar `UPDATE`, `DELETE` y `TRUNCATE` directos sobre ellas, incluso con la conexión de la aplicación (RN-CL-02).

#### Scenario: PUT sobre una evolución (error de negocio)

- **WHEN** se envía `PUT` o `PATCH` a `/api/pacientes/{id}/evoluciones/{evolucion_id}`
- **THEN** el sistema responde `405` y la evolución no cambia.

#### Scenario: DELETE sobre una evolución

- **WHEN** se envía `DELETE` a `/api/pacientes/{id}/evoluciones/{evolucion_id}`
- **THEN** el sistema responde `405` y la evolución sigue existiendo.

#### Scenario: UPDATE o DELETE directo rechazado (borde)

- **WHEN** se ejecuta `UPDATE`, `DELETE` o `TRUNCATE` sobre la tabla de evoluciones
- **THEN** la base de datos rechaza la sentencia y las filas quedan intactas.

### Requirement: Corrección como evolución nueva enlazada

El sistema SHALL corregir una evolución creando una fila nueva con `corrige_a_id` (la evolución corregida) y un `motivo_correccion` obligatorio (1 a 500 caracteres), con su propio autor y fecha/hora. La original SHALL quedar intacta y SHALL informar qué evolución la corrige.

#### Scenario: Autor corrige su evolución (happy path)

- **GIVEN** una evolución E1 del odontólogo O
- **WHEN** O envía `{"texto": "Texto corregido sintético", "corrige_a_id": E1, "motivo_correccion": "Pieza mal indicada"}`
- **THEN** el sistema responde `201` con una evolución E2 que tiene `corrige_a_id = E1`, E1 conserva su texto original y figura con `corregida_por_id = E2`.

#### Scenario: Corrección sin motivo (error de negocio)

- **WHEN** se envía `corrige_a_id` sin `motivo_correccion`, o `motivo_correccion` sin `corrige_a_id`
- **THEN** el sistema responde `422` y no crea la evolución.

#### Scenario: Corregir una evolución ya corregida (borde)

- **GIVEN** E1 ya corregida por E2
- **WHEN** se envía una corrección con `corrige_a_id = E1`
- **THEN** el sistema responde `409` indicando que debe corregirse la versión vigente (E2), y no crea la evolución.

#### Scenario: Correcciones simultáneas de la misma evolución (borde)

- **WHEN** dos correcciones de E1 llegan en paralelo
- **THEN** exactamente una responde `201` y la otra `409`.

### Requirement: Solo el autor corrige su evolución

El sistema SHALL permitir corregir una evolución solo al usuario que la escribió; otro odontólogo SHALL recibir `403` y registrar, si corresponde, una evolución nueva sin `corrige_a_id`. La evolución a corregir SHALL pertenecer al mismo paciente y a la misma clínica; si no, el sistema SHALL responder `422`.

#### Scenario: Otro odontólogo intenta corregir (error de negocio)

- **GIVEN** una evolución E1 del odontólogo O
- **WHEN** el odontólogo P envía una corrección de E1
- **THEN** el sistema responde `403` y no crea la evolución.

#### Scenario: Corregir una evolución de otro paciente (borde)

- **WHEN** se envía una corrección cuyo `corrige_a_id` pertenece a otro paciente, o a un paciente de otra clínica
- **THEN** el sistema responde `422` y no crea la evolución.

### Requirement: Consulta ordenada de evoluciones

El sistema SHALL exponer `GET /api/pacientes/{id}/evoluciones` con las evoluciones del paciente en orden de registro descendente (la más reciente primero), paginadas por cursor (`limit` 1 a 200, por defecto 50; `after_id`), y `GET /api/pacientes/{id}/evoluciones/{evolucion_id}` con una sola. Cada evolución SHALL incluir autor, profesional, fecha/hora, pieza, `corrige_a_id` y `corregida_por_id`.

#### Scenario: Evoluciones ordenadas (happy path)

- **GIVEN** las evoluciones E1, E2 y E3 registradas en ese orden, con E3 corrigiendo a E1
- **WHEN** un odontólogo pide las evoluciones
- **THEN** el sistema devuelve E3, E2 y E1 en ese orden, y E1 con `corregida_por_id = E3`.

#### Scenario: Paginación sin repetidos (borde)

- **GIVEN** 3 evoluciones
- **WHEN** se piden con `limit = 2` y luego con el `next_cursor` devuelto
- **THEN** la primera página trae las 2 más recientes, la segunda la restante, y ninguna se repite.

#### Scenario: Evolución de otro paciente por id (error de negocio)

- **WHEN** se pide `GET /api/pacientes/{A}/evoluciones/{id}` con una evolución del paciente B
- **THEN** el sistema responde `404`.

### Requirement: Gate de consentimiento para evoluciones

El sistema SHALL rechazar con `403` el alta de evoluciones, incluidas las correcciones, de un paciente con `consentimiento_datos = false`, sin persistir nada. La lectura de evoluciones existentes SHALL seguir disponible tras una revocación.

#### Scenario: Evolución sin consentimiento (error de negocio)

- **WHEN** un odontólogo registra una evolución de un paciente sin consentimiento
- **THEN** el sistema responde `403` y no crea la evolución.

#### Scenario: Lectura tras revocación (borde)

- **GIVEN** un paciente con evoluciones al que luego se le revocó el consentimiento
- **WHEN** un odontólogo pide sus evoluciones
- **THEN** el sistema las devuelve.

### Requirement: Aislamiento de evoluciones por clínica

El sistema SHALL acotar las evoluciones a la clínica del JWT: un paciente de otra clínica SHALL responder `404`, y una consulta de evoluciones con otro `clinica_id` SHALL devolver 0 filas. La base de datos SHALL impedir que una evolución referencie un paciente, autor o profesional de otra clínica.

#### Scenario: Evoluciones de un paciente de otra clínica (error de negocio)

- **WHEN** un odontólogo de la clínica A pide o registra evoluciones de un paciente de la clínica B
- **THEN** el sistema responde `404` y no crea ni audita nada.

#### Scenario: Consulta cruzada a nivel repositorio (borde)

- **GIVEN** evoluciones en la clínica B
- **WHEN** se consultan con el `clinica_id` de la clínica A
- **THEN** el resultado tiene 0 filas.

#### Scenario: Profesional de otra clínica a nivel base (borde)

- **WHEN** se inserta una evolución con un `profesional_id` de otra clínica
- **THEN** la base de datos rechaza la sentencia por clave foránea.
