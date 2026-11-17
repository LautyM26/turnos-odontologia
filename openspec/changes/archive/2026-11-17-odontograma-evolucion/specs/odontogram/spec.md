# Spec Delta — odontogram

## Purpose

Gobierna el odontograma FDI del paciente: el registro por pieza y por cara de hallazgos y prestaciones, con dentición permanente, temporal o mixta, conservado como versiones inmutables que sirven de base para presupuestar y hacer recall.

## ADDED Requirements

### Requirement: Guardado del odontograma como versión nueva

El sistema SHALL guardar cada `POST /api/pacientes/{id}/odontograma` como una versión completa nueva del odontograma (`version` = vigente + 1), con autor (usuario autenticado) y fecha/hora del servidor, y SHALL responder `201` con la versión creada. Ninguna versión previa SHALL modificarse ni borrarse (RN-CL-02).

#### Scenario: Primer odontograma de un paciente (happy path)

- **GIVEN** un paciente con consentimiento y sin odontograma
- **WHEN** un odontólogo envía `version_esperada = 0`, `denticion = "permanente"` y la pieza `16` con caries en la cara `O`
- **THEN** el sistema responde `201` con `version = 1`, su id como autor y la fecha/hora del servidor.

#### Scenario: Nueva versión conserva la anterior

- **GIVEN** un odontograma en versión 1
- **WHEN** el odontólogo guarda con `version_esperada = 1` la pieza `16` con obturación en `O`
- **THEN** el sistema crea la versión 2 y la versión 1 sigue disponible sin cambios en el historial.

#### Scenario: Odontograma sin hallazgos (borde)

- **WHEN** un odontólogo guarda `version_esperada = 0` con `piezas` vacío
- **THEN** el sistema responde `201` con `version = 1` y sin piezas marcadas.

#### Scenario: Autor o fecha en el cuerpo

- **WHEN** el cuerpo incluye un campo no declarado, por ejemplo `autor_usuario_id` o `created_at`
- **THEN** el sistema responde `422` y no crea versión.

### Requirement: Control de concurrencia del odontograma

El sistema SHALL rechazar con `409` un guardado cuyo `version_esperada` no coincida con la versión vigente, incluso ante dos guardados concurrentes sobre la misma versión, sin crear versiones duplicadas.

#### Scenario: Guardado sobre versión vieja (error de negocio)

- **GIVEN** un odontograma cuya versión vigente es la 2
- **WHEN** se envía `version_esperada = 1`
- **THEN** el sistema responde `409` y no crea versión nueva.

#### Scenario: Dos guardados simultáneos (borde)

- **WHEN** dos requests con `version_esperada = 2` llegan en paralelo
- **THEN** exactamente uno crea la versión 3 y el otro recibe `409`.

### Requirement: Piezas FDI válidas según la dentición

El sistema SHALL aceptar solo códigos FDI de la dentición declarada: `permanente` = cuadrantes 1–4, piezas 1–8 (32 piezas); `temporal` = cuadrantes 5–8, piezas 1–5 (20 piezas); `mixta` = la unión de ambos sets. Cualquier otro código, o un código de la dentición no declarada, SHALL responder `422` sin crear versión (RN-CL-03).

#### Scenario: Pieza temporal en dentición temporal (happy path)

- **WHEN** un odontólogo guarda `denticion = "temporal"` con la pieza `85` marcada
- **THEN** el sistema responde `201`.

#### Scenario: Pieza temporal en dentición permanente (error de negocio)

- **WHEN** se guarda `denticion = "permanente"` con la pieza `55`
- **THEN** el sistema responde `422` indicando la pieza inválida y no crea versión.

#### Scenario: Códigos fuera del rango FDI (borde)

- **WHEN** se guarda `denticion = "mixta"` con alguna de las piezas `10`, `19`, `49`, `56`, `86` o `90`
- **THEN** el sistema responde `422`.

#### Scenario: Límites del rango FDI (borde)

- **WHEN** se guarda `denticion = "mixta"` con las piezas `11`, `48`, `51` y `85`
- **THEN** el sistema responde `201`.

### Requirement: Caras y estados del catálogo MVP

El sistema SHALL aceptar por pieza un estado de pieza opcional y un estado por cara, solo con las caras `V`, `L`, `M`, `D`, `O` y los estados del catálogo MVP. Cada marca SHALL indicar si es `existente` o `a_realizar`. Una pieza `ausente` o `extraida` SHALL no tener caras marcadas. Lo que esté fuera del catálogo SHALL responder `422`.

#### Scenario: Marcas válidas por cara (happy path)

- **WHEN** se guarda la pieza `36` con caries `a_realizar` en `M` y obturación `existente` en `O`
- **THEN** el sistema responde `201` y la versión devuelve ambas marcas tal como se enviaron.

#### Scenario: Cara o estado desconocidos (error de negocio)

- **WHEN** se guarda una cara `X` o un estado `blanqueamiento`
- **THEN** el sistema responde `422` y no crea versión.

#### Scenario: Pieza ausente con caras marcadas (borde)

- **WHEN** se guarda la pieza `26` con estado de pieza `ausente` y una caries en la cara `O`
- **THEN** el sistema responde `422`.

### Requirement: Odontograma vigente

El sistema SHALL exponer `GET /api/pacientes/{id}/odontograma/actual` con la versión de mayor número, su dentición, piezas, autor y fecha/hora. Si el paciente no tiene odontograma, SHALL responder `200` con `version = 0` y sin piezas.

#### Scenario: Consulta del vigente (happy path)

- **GIVEN** un odontograma con versiones 1 y 2
- **WHEN** un odontólogo pide el odontograma actual
- **THEN** el sistema devuelve la versión 2.

#### Scenario: Paciente sin odontograma (borde)

- **WHEN** se pide el odontograma actual de un paciente sin versiones
- **THEN** el sistema responde `200` con `version = 0` y `piezas` vacío.

### Requirement: Historial de versiones del odontograma

El sistema SHALL exponer `GET /api/pacientes/{id}/odontograma` con todas las versiones del odontograma del paciente en orden descendente, cada una con número, dentición, piezas, autor y fecha/hora.

#### Scenario: Consulta del historial (happy path)

- **GIVEN** un odontograma con 3 versiones
- **WHEN** un admin pide el historial
- **THEN** el sistema retorna las versiones 3, 2 y 1 con su autor y fecha.

#### Scenario: Historial vacío (borde)

- **WHEN** se pide el historial de un paciente sin odontograma
- **THEN** el sistema responde `200` con una lista vacía.

### Requirement: Odontograma sin edición ni borrado

El sistema SHALL no exponer `PUT`, `PATCH` ni `DELETE` sobre el odontograma (`405`). La base de datos SHALL rechazar `UPDATE`, `DELETE` y `TRUNCATE` directos sobre las versiones.

#### Scenario: Intento de editar por API (error de negocio)

- **WHEN** se envía `PUT`, `PATCH` o `DELETE` a `/api/pacientes/{id}/odontograma`
- **THEN** el sistema responde `405` y las versiones existentes no cambian.

#### Scenario: UPDATE directo rechazado (borde)

- **WHEN** se ejecuta `UPDATE` sobre una versión de odontograma con la conexión de la aplicación
- **THEN** la base de datos rechaza la sentencia y la versión queda intacta.

### Requirement: Gate de consentimiento para el odontograma

El sistema SHALL rechazar con `403` el guardado de odontograma de un paciente con `consentimiento_datos = false`, sin persistir nada y antes de validar el cuerpo. La lectura de versiones ya existentes SHALL seguir disponible tras una revocación.

#### Scenario: Guardado sin consentimiento (error de negocio)

- **WHEN** un odontólogo guarda el odontograma de un paciente sin consentimiento
- **THEN** el sistema responde `403` y no crea versión.

#### Scenario: Lectura tras revocar el consentimiento (borde)

- **GIVEN** un paciente con odontograma en versión 1 al que luego se le revocó el consentimiento
- **WHEN** un odontólogo pide el odontograma actual
- **THEN** el sistema devuelve la versión 1.

### Requirement: Aislamiento del odontograma por clínica

El sistema SHALL acotar toda lectura y escritura de odontograma a la clínica del JWT: un paciente de otra clínica SHALL responder `404`, y una consulta de versiones con otro `clinica_id` SHALL devolver 0 filas.

#### Scenario: Odontograma de un paciente de otra clínica (error de negocio)

- **WHEN** un odontólogo de la clínica A pide o guarda el odontograma de un paciente de la clínica B
- **THEN** el sistema responde `404` y no crea ni audita nada.

#### Scenario: Consulta cruzada a nivel repositorio (borde)

- **GIVEN** versiones de odontograma en la clínica B
- **WHEN** se consultan las versiones de ese paciente con el `clinica_id` de la clínica A
- **THEN** el resultado tiene 0 filas.
