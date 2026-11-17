# Spec Delta — prescriptions

## Purpose

Permite al odontólogo emitir recetas y órdenes de estudio electrónicas únicamente a través de un partner registrado en ReNaPDiS, vinculadas a su evolución clínica, y consultarlas desde la historia del paciente (RN-CU-03, DD-06, regla dura 17).

## ADDED Requirements

### Requirement: Emisión vía partner registrado

El sistema SHALL emitir una receta (`tipo = receta`, con 1 a 10 medicamentos por nombre genérico, presentación, cantidad e indicaciones) o una orden de estudio (`tipo = orden_estudio`, con 1 a 10 estudios) únicamente a través del partner configurado, y SHALL guardar el partner, el id externo, el enlace al PDF del partner, el autor y la fecha/hora del servidor.

#### Scenario: Receta emitida con partner simulado

- **WHEN** un odontólogo hace `POST /api/pacientes/{id}/recetas` con `tipo = receta`, una evolución propia del paciente, un diagnóstico y un medicamento, con el partner simulado configurado
- **THEN** el sistema responde `201` con `partner = "fake"`, un `id_externo` que empieza con `FAKE-`, `simulada = true`, el enlace al PDF, `evolucion_id` y la fecha del servidor.

#### Scenario: Orden de estudio emitida

- **WHEN** el odontólogo emite `tipo = orden_estudio` con un estudio (p. ej. radiografía panorámica)
- **THEN** el sistema responde `201` con `tipo = orden_estudio` y su id externo.

#### Scenario: Ítems fuera de rango (borde)

- **WHEN** la receta no trae medicamentos, trae más de 10, o una orden de estudio trae medicamentos
- **THEN** el sistema responde `422` y no llama al partner.

#### Scenario: Datos de servidor en el cuerpo (borde)

- **WHEN** el cuerpo trae `id_externo`, `partner`, `pdf_url`, `simulada`, `autor_usuario_id` o `fecha`
- **THEN** el sistema responde `422` por campo no declarado.

### Requirement: Datos del paciente y del profesional desde el servidor

El sistema SHALL enviar al partner los datos del paciente (nombre, apellido, DNI, obra social, plan y afiliado) y del profesional (nombre y matrícula) leídos de la base, nunca del cuerpo de la request, y SHALL exigir que el usuario tenga un profesional activo vinculado.

#### Scenario: Datos tomados de la base

- **WHEN** se emite una receta
- **THEN** el partner recibe el DNI y la obra social registrados del paciente y la matrícula del profesional vinculado al usuario.

#### Scenario: Odontólogo sin profesional vinculado

- **WHEN** emite un odontólogo sin profesional activo vinculado
- **THEN** el sistema responde `422` y no llama al partner.

#### Scenario: Paciente sin obra social (borde)

- **WHEN** el paciente no tiene obra social cargada
- **THEN** la receta se emite como particular (obra social vacía) y responde `201`.

### Requirement: Vínculo con una evolución propia

Cada receta SHALL quedar vinculada a una evolución existente del mismo paciente y de la misma clínica escrita por el odontólogo que emite.

#### Scenario: Evolución de otro paciente

- **WHEN** `evolucion_id` pertenece a otro paciente o no existe
- **THEN** el sistema responde `422` y no llama al partner.

#### Scenario: Evolución de otro odontólogo

- **WHEN** `evolucion_id` es del paciente pero la escribió otro odontólogo
- **THEN** el sistema responde `422` indicando que la receta debe vincularse a una evolución propia.

#### Scenario: Evolución corregida (borde)

- **WHEN** `evolucion_id` es una evolución propia que ya fue corregida
- **THEN** la receta se emite y queda vinculada a esa evolución (la cadena de corrección sigue visible en la historia).

### Requirement: Partner no configurado

Si no hay partner configurado, o el configurado no puede usarse en el entorno actual, la emisión SHALL responder `501` con un mensaje que indique qué configurar, sin llamar a ningún servicio y sin afectar al resto de la API; las consultas de recetas SHALL seguir respondiendo.

#### Scenario: Sin partner

- **WHEN** un odontólogo emite una receta y `RECETAS_PARTNER` no está definido
- **THEN** el sistema responde `501` con un mensaje que menciona `RECETAS_PARTNER` y no guarda nada.

#### Scenario: Consultas sin partner

- **WHEN** no hay partner configurado y un admin pide `GET /api/pacientes/{id}/recetas`
- **THEN** el sistema responde `200` con las recetas existentes (o lista vacía).

#### Scenario: Partner simulado en producción (borde)

- **WHEN** `RECETAS_PARTNER = fake` y `ENTORNO = produccion`
- **THEN** la emisión responde `501` indicando que el partner simulado está deshabilitado en producción.

### Requirement: Errores del partner

El sistema SHALL responder `502` con `reintentable = true` cuando el partner no responde, excede el tiempo de espera o falla internamente, y `422` con el motivo informado cuando el partner rechaza los datos; en ambos casos SHALL NOT guardar la receta.

#### Scenario: Partner caído

- **WHEN** el partner falla por timeout o error interno
- **THEN** el sistema responde `502` con `reintentable = true` y no existe receta ni evento de emisión.

#### Scenario: Partner rechaza los datos

- **WHEN** el partner rechaza la prescripción (p. ej. matrícula no habilitada)
- **THEN** el sistema responde `422` con el motivo del partner, sin credenciales ni datos internos en el mensaje.

#### Scenario: Mensaje del partner con secreto (borde)

- **WHEN** el error del partner incluye la credencial configurada en su texto
- **THEN** la respuesta y los logs muestran el mensaje con la credencial enmascarada.

### Requirement: Emisión idempotente

El sistema SHALL exigir una `clave_idempotencia` (UUID) por emisión; un reintento con la misma clave para el mismo paciente SHALL devolver la receta ya emitida sin volver a llamar al partner.

#### Scenario: Doble clic

- **WHEN** el odontólogo envía dos veces la misma emisión con la misma `clave_idempotencia`
- **THEN** la segunda respuesta es `200` con la misma receta, el partner recibió una sola emisión y existe una sola fila.

#### Scenario: Misma clave con otro contenido

- **WHEN** se reutiliza una `clave_idempotencia` con otro tipo, evolución o ítems
- **THEN** el sistema responde `409` y no emite.

#### Scenario: Emisiones concurrentes con la misma clave (borde)

- **WHEN** dos emisiones con la misma clave llegan a la vez
- **THEN** existe una sola receta y ambas respuestas devuelven el mismo `id`.

### Requirement: Receta inmutable

El sistema SHALL tratar la receta emitida como documento inmutable: la API no expone PUT/PATCH/DELETE y la base rechaza UPDATE, DELETE y TRUNCATE.

#### Scenario: Métodos de edición no expuestos

- **WHEN** se hace `PUT`, `PATCH` o `DELETE` sobre `/api/pacientes/{id}/recetas/{rid}`
- **THEN** el sistema responde `405`.

#### Scenario: Mutación directa en la base

- **WHEN** una sentencia SQL intenta modificar o borrar una receta
- **THEN** la base la rechaza y la fila persiste.

#### Scenario: TRUNCATE rechazado (borde)

- **WHEN** se intenta `TRUNCATE` de la tabla de recetas
- **THEN** la base rechaza la sentencia.

### Requirement: Consulta de recetas

El sistema SHALL listar las recetas de un paciente (más recientes primero) con tipo, estado, partner, `simulada`, enlace al PDF y `evolucion_id`, y devolver el detalle de una, solo para su clínica.

#### Scenario: Listado

- **WHEN** un odontólogo lista las recetas de un paciente con una receta y una orden
- **THEN** recibe ambas, la más reciente primero, con su enlace al PDF.

#### Scenario: Receta de otro paciente

- **WHEN** se pide un `rid` de otro paciente de la misma clínica
- **THEN** el sistema responde `404`.

#### Scenario: Paciente sin recetas (borde)

- **WHEN** se lista un paciente sin recetas
- **THEN** el sistema responde `200` con lista vacía.

### Requirement: RBAC y consentimiento de datos en recetas

El sistema SHALL permitir emitir solo al odontólogo vinculado al paciente con `consentimiento_datos = true`, leer solo a admin y odontólogo, y responder `403` al recepcionista en todas las rutas de recetas.

#### Scenario: Recepción sin acceso

- **WHEN** un recepcionista llama a cualquier ruta de `/api/pacientes/{id}/recetas`
- **THEN** el sistema responde `403`, no llama al partner y no audita.

#### Scenario: Sin consentimiento de datos

- **WHEN** un odontólogo emite para un paciente con `consentimiento_datos = false`
- **THEN** el sistema responde `403` antes de validar el cuerpo y de consultar la configuración del partner.

#### Scenario: Admin solo lee (borde)

- **WHEN** un admin intenta emitir
- **THEN** el sistema responde `403`.

### Requirement: Recetas auditadas

El sistema SHALL registrar en la auditoría clínica un evento `crear` por cada emisión exitosa (entidad `receta`) y un evento `leer` por cada listado o detalle, con diff limitado a ids y partner, sin medicamentos, estudios ni diagnóstico.

#### Scenario: Emisión auditada

- **WHEN** se emite una receta
- **THEN** existe un evento `crear` sobre la entidad `receta` con su id, `evolucion_id` y partner.

#### Scenario: Reintento idempotente no duplica (borde)

- **WHEN** se repite una emisión con la misma clave
- **THEN** sigue existiendo un único evento `crear` para esa receta.

#### Scenario: Diff sin contenido clínico

- **WHEN** se inspecciona el diff de los eventos de recetas
- **THEN** no contiene medicamentos, estudios ni diagnóstico.

### Requirement: Recetas aisladas por clínica y exportadas

El sistema SHALL guardar cada receta con `clinica_id` e índice `(clinica_id, paciente_id, …)`, ninguna consulta SHALL devolver recetas de otra clínica, y la exportación del tenant SHALL incluir un `recetas.csv` solo con las recetas de la clínica.

#### Scenario: Paciente de otra clínica

- **WHEN** un odontólogo de la clínica A emite o lista recetas de un paciente de la clínica B
- **THEN** el sistema responde `404` y no llama al partner.

#### Scenario: Consulta cruzada en la base

- **WHEN** se consultan recetas filtrando por la clínica A con ids de la clínica B
- **THEN** el resultado tiene 0 filas.

#### Scenario: Exportación con recetas (borde)

- **WHEN** un admin de la clínica A exporta y ambas clínicas tienen recetas
- **THEN** el ZIP incluye `recetas.csv` con las recetas de A, su conteo en el manifest, y ninguna de B.
