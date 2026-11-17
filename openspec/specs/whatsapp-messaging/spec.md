# whatsapp-messaging Specification

## Purpose
Canal WhatsApp de la clínica por sesión QR con número dedicado (DD-10, RN-WA-01..03, RN-TU-02/03, US-005, Flujo 2): recordatorios cuya respuesta confirma o cancela el turno de verdad, costo visible en pesos y bandeja de fallos con fallback manual cuando la sesión cae.

> Datos de los escenarios 100 % sintéticos: clínicas A y B, profesional P, paciente "Paciente Sintético 1" con teléfono `+5491100000001`, turno T reservado para `2031-03-11 10:00` UTC. "Ahora" = `2031-03-10 12:00` UTC. Precio por mensaje `12.50` ARS.

## Requirements

### Requirement: Una sesión de WhatsApp por clínica

El sistema SHALL mantener como máximo una sesión de WhatsApp (un número dedicado) por clínica, con su último estado conocido (`desconocido`, `iniciando`, `escanear_qr`, `activa`, `caida`, `detenida`) y la fecha del servidor del último cambio. Los eventos de una sesión SHALL afectar solo a datos de su clínica.

#### Scenario: Evento de sesión actualiza el estado

- **GIVEN** la sesión de la clínica A está `activa`
- **WHEN** llega un evento autenticado de que esa sesión falló
- **THEN** el estado de la sesión de A pasa a `caida` y la de B no cambia.

### Requirement: Consulta del estado de la sesión

El sistema SHALL responder en `GET /api/whatsapp/sesion` a `admin` y `recepcionista` con el estado de la sesión de su clínica, el número vinculado si lo hay, la fecha del último cambio y, solo cuando el estado es `escanear_qr`, la imagen del QR a escanear. Otros roles SHALL recibir `403`; sin token, `401`.

#### Scenario: Sesión esperando escaneo (happy path)

- **GIVEN** la sesión de A está en `escanear_qr`
- **WHEN** el admin de A pide `GET /api/whatsapp/sesion`
- **THEN** el sistema responde `200` con `estado = "escanear_qr"` y el QR en base64.

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo pide `GET /api/whatsapp/sesion`
- **THEN** el sistema responde `403`.

### Requirement: Reconexión de la sesión solo por admin

El sistema SHALL permitir solo al `admin` pedir en `POST /api/whatsapp/sesion/reconectar` que se inicie o reinicie la sesión de su clínica, configurando el envío de eventos firmados hacia el sistema, y SHALL responder con el nuevo estado. `recepcionista` y `odontologo` SHALL recibir `403`.

#### Scenario: Admin reconecta

- **GIVEN** la sesión de A está `caida`
- **WHEN** el admin de A pide reconectar
- **THEN** el sistema responde `200` con el estado devuelto por el gateway (por ejemplo `escanear_qr`).

#### Scenario: Recepción no puede reconectar

- **WHEN** un recepcionista pide reconectar
- **THEN** el sistema responde `403`.

### Requirement: Canal no configurado no impide operar

Sin gateway de WhatsApp configurado, el sistema SHALL arrancar y operar normalmente; los endpoints de sesión SHALL responder `501` con un mensaje de configuración, y los recordatorios que correspondan SHALL quedar registrados como fallos en la bandeja.

#### Scenario: Sesión sin gateway

- **GIVEN** no hay gateway configurado
- **WHEN** el admin pide `GET /api/whatsapp/sesion`
- **THEN** el sistema responde `501` con un mensaje que indica configurar el canal, y `/api/health` sigue respondiendo `200`.

### Requirement: Recordatorio previo al turno

El sistema SHALL enviar por WhatsApp un único recordatorio por turno `reservado`, activo, cuyo inicio esté dentro de la ventana configurada (24 h por defecto) y cuyo paciente tenga teléfono. El texto SHALL incluir fecha y hora en la zona de la clínica, el profesional y las opciones `1` confirmar, `2` cancelar y `3` reprogramar. Turnos confirmados, cancelados, ausentes, asistidos o fuera de la ventana SHALL NOT recibir recordatorio.

#### Scenario: Recordatorio enviado una sola vez (happy path)

- **GIVEN** el turno T está `reservado` y empieza dentro de 22 h
- **WHEN** el proceso de recordatorios corre dos veces seguidas
- **THEN** se envía exactamente un mensaje saliente con texto base `recordatorio_24h` al teléfono del paciente y queda registrado como `enviado`.

#### Scenario: Turno fuera de la ventana

- **GIVEN** un turno `reservado` que empieza dentro de 30 h
- **WHEN** corre el proceso de recordatorios
- **THEN** no se envía ningún mensaje para ese turno.

#### Scenario: Turno cancelado no recibe recordatorio

- **GIVEN** un turno `cancelado` que empieza dentro de 10 h
- **WHEN** corre el proceso de recordatorios
- **THEN** no se envía ningún mensaje para ese turno.

### Requirement: Ritmo de envío limitado

El sistema SHALL espaciar los envíos de recordatorios de modo de no superar el máximo configurado de mensajes por minuto por sesión, para reducir el riesgo de bloqueo del número (DD-10).

#### Scenario: Lote mayor que el límite

- **GIVEN** un límite de 20 mensajes por minuto y 3 recordatorios pendientes
- **WHEN** corre el proceso de recordatorios
- **THEN** entre dos envíos consecutivos transcurren al menos 3 segundos.

### Requirement: Fallo de envío va a la bandeja sin tocar el turno

Si un recordatorio no puede enviarse (gateway caído o no configurado, sesión no activa, número bloqueado o paciente sin teléfono), el sistema SHALL registrar el mensaje en estado `error` con su motivo, SHALL dejarlo visible en la bandeja de fallos y SHALL NOT cambiar el estado del turno (RN-WA-01). Los errores transitorios SHALL reintentarse en corridas posteriores hasta el máximo de intentos configurado mientras el turno siga sin empezar; el teléfono faltante no SHALL reintentarse.

#### Scenario: Sesión caída (borde)

- **GIVEN** la sesión de A está caída y T necesita recordatorio
- **WHEN** corre el proceso de recordatorios
- **THEN** el mensaje de T queda en `error` con motivo de sesión no disponible, aparece en `GET /api/whatsapp/fallos` y T sigue `reservado`.

#### Scenario: Reintento exitoso al volver la sesión

- **GIVEN** el recordatorio de T quedó en `error` tras 1 intento y la sesión vuelve a estar activa
- **WHEN** corre otra vez el proceso de recordatorios
- **THEN** el mismo mensaje pasa a `enviado` con 2 intentos y no se crea un segundo recordatorio para T.

#### Scenario: Paciente sin teléfono

- **GIVEN** el paciente de un turno a recordar solo tiene email
- **WHEN** corre el proceso de recordatorios
- **THEN** queda un fallo `sin_telefono` en la bandeja y no se reintenta.

### Requirement: Webhook de eventos autenticado

El sistema SHALL aceptar sin JWT en `POST /api/webhooks/whatsapp` solo eventos con una firma HMAC-SHA512 válida del cuerpo crudo hecha con el secreto configurado; firma ausente o inválida SHALL responder `401` sin efectos. Con el secreto sin configurar SHALL responder `503` sin efectos. Eventos de tipo desconocido o de una sesión que no corresponde a ninguna clínica SHALL responder `200` sin efectos.

#### Scenario: Firma inválida (error)

- **WHEN** llega un evento de respuesta "SI" con una firma que no corresponde al cuerpo
- **THEN** el sistema responde `401` y T no cambia.

#### Scenario: Sesión desconocida

- **WHEN** llega un evento firmado de una sesión que no es de ninguna clínica
- **THEN** el sistema responde `200` y no registra mensajes ni cambia turnos.

### Requirement: Interpretación de la respuesta del paciente

El sistema SHALL registrar cada mensaje entrante con costo 0, asociarlo al último recordatorio enviado a ese número en esa clínica cuyo turno no empezó, e interpretar su primera palabra sin distinguir mayúsculas, tildes ni signos: `1`, `si`, `confirmo`, `confirmar` → confirmar; `2`, `no`, `cancelo`, `cancelar` → cancelar; `3`, `reprogramar`, `cambiar` → reprogramar; cualquier otra → no interpretable.

#### Scenario: Variantes de confirmación

- **WHEN** llegan por separado "1", "SI", "Sí, confirmo" y "confirmar"
- **THEN** todas se interpretan como confirmar.

#### Scenario: Mensaje vacío o emoji (borde)

- **WHEN** llega un mensaje vacío o solo "👍"
- **THEN** se interpreta como no interpretable.

### Requirement: La respuesta del paciente actualiza la agenda

Confirmar y cancelar SHALL aplicar la transición de estado del turno asociado con actor `paciente_whatsapp`, en la misma transacción que registra el mensaje entrante, y luego SHALL responder al paciente con el texto base correspondiente (RN-TU-03). Reprogramar SHALL dejar el pedido en la bandeja sin cambiar el turno.

#### Scenario: Respuesta "SI" confirma el turno (happy path)

- **GIVEN** a T se le envió el recordatorio
- **WHEN** llega del teléfono del paciente el mensaje "Sí!"
- **THEN** T pasa a `confirmado`, el historial registra `reservado → confirmado` con actor `paciente_whatsapp` y sin usuario, y el paciente recibe el texto base `confirmacion`.

#### Scenario: Respuesta "2" cancela y libera el hueco

- **GIVEN** a T se le envió el recordatorio
- **WHEN** llega el mensaje "2"
- **THEN** T pasa a `cancelado`, su horario queda libre para otro turno y el paciente recibe el texto base `cancelacion`.

#### Scenario: Pedido de reprogramación

- **WHEN** llega el mensaje "reprogramar"
- **THEN** T no cambia, el mensaje queda en la bandeja como pedido de reprogramación y el paciente recibe el texto base `reprogramacion`.

### Requirement: Evento duplicado no repite efectos

El sistema SHALL procesar cada mensaje entrante una sola vez por clínica según su identificador externo: un evento repetido, incluso simultáneo, SHALL responder `200` sin registrar otro mensaje, sin repetir la transición y sin reenviar la respuesta al paciente.

#### Scenario: Mismo evento dos veces (borde)

- **WHEN** el gateway entrega dos veces el mismo evento "SI" de T
- **THEN** existe un solo mensaje entrante, un solo registro `reservado → confirmado` en el historial y una sola respuesta `confirmacion`.

### Requirement: Respuestas que no mueven la agenda van a la bandeja

El sistema SHALL dejar en la bandeja, sin cambiar ningún turno, los mensajes entrantes no interpretables, los que no se asocian a ningún recordatorio vigente y las respuestas que piden una transición imposible (por ejemplo confirmar un turno ya cancelado). A un mensaje no interpretable SHALL NOT responderle automáticamente.

#### Scenario: Texto libre

- **WHEN** llega el mensaje "hola, ¿a qué hora era?"
- **THEN** T no cambia, el mensaje queda en la bandeja como no interpretado y no se envía respuesta automática.

#### Scenario: Confirmar un turno ya cancelado (error de negocio)

- **GIVEN** T ya está `cancelado`
- **WHEN** llega el mensaje "1"
- **THEN** T sigue `cancelado`, no se registra transición y el mensaje queda en la bandeja.

#### Scenario: Número sin recordatorio

- **WHEN** llega "SI" de un número al que no se le envió recordatorio
- **THEN** ningún turno cambia y el mensaje queda en la bandeja sin turno asociado.

### Requirement: Estado de entrega de los mensajes salientes

El sistema SHALL actualizar el estado de un mensaje saliente según los acuses del gateway (`enviado` → `entregado` → `leido`) y SHALL ignorar acuses que retrocedan el estado o de mensajes desconocidos.

#### Scenario: Acuse de lectura

- **GIVEN** el recordatorio de T está `enviado`
- **WHEN** llega el acuse de leído de ese mensaje
- **THEN** el mensaje pasa a `leido`; un acuse posterior de entregado no lo hace retroceder.

### Requirement: Registro de mensajes con costo en pesos

El sistema SHALL guardar cada mensaje con clínica, turno (si lo hay), texto base usado, dirección, teléfono, estado, intentos y costo en ARS con precisión decimal exacta; el costo de un saliente SHALL ser el precio configurado vigente al momento del envío exitoso y el de un entrante, `0` (RN-WA-02/03). El sistema SHALL responder en `GET /api/whatsapp/mensajes?turno_id=` a `admin` y `recepcionista` con los mensajes de ese turno de su clínica.

#### Scenario: Costo registrado en ARS

- **GIVEN** el precio configurado es `12.50`
- **WHEN** se envía con éxito el recordatorio de T
- **THEN** el mensaje queda con `costo_ars = "12.50"` exacto (sin redondeo binario).

### Requirement: Resumen de costos por período

El sistema SHALL responder en `GET /api/whatsapp/costos?desde&hasta` a `admin` y `recepcionista` con el total en ARS y la cantidad de mensajes por texto base y dirección de su clínica en ese rango de fechas del servidor; un rango invertido o mayor a 366 días SHALL responder `422`.

#### Scenario: Total del mes

- **GIVEN** en marzo se enviaron 3 recordatorios a `12.50` y llegaron 2 respuestas
- **WHEN** el admin pide los costos de marzo
- **THEN** el total es `"37.50"` ARS, con 3 salientes `recordatorio_24h` y 2 entrantes a costo 0.

### Requirement: Bandeja de fallos con resolución manual

El sistema SHALL responder en `GET /api/whatsapp/fallos` a `admin` y `recepcionista` con los mensajes de su clínica pendientes de atención (salientes en `error` y entrantes que no movieron la agenda), sin resolver, con turno, paciente, motivo y fecha. `POST /api/whatsapp/fallos/{id}/resolver` SHALL marcarlo resuelto con el usuario y la fecha del servidor, y desde entonces SHALL dejar de figurar. Un id de otra clínica SHALL responder `404`.

#### Scenario: Recepción avisa a mano y resuelve

- **GIVEN** el recordatorio de T está en la bandeja por sesión caída
- **WHEN** la recepcionista llama al paciente y pide resolver ese fallo
- **THEN** el sistema responde `200` y el fallo ya no aparece en `GET /api/whatsapp/fallos`.

### Requirement: Mensajería aislada por clínica

Mensajes, sesiones y fallos SHALL estar aislados por clínica: las consultas de una clínica SHALL devolver 0 filas de otra, y un mensaje entrante de la sesión de A SHALL NOT asociarse a turnos ni pacientes de B aunque el teléfono coincida.

#### Scenario: Mismo teléfono en dos clínicas

- **GIVEN** el mismo teléfono es paciente en A y en B, y solo B le envió recordatorio
- **WHEN** llega "SI" por la sesión de A
- **THEN** ningún turno de B cambia y el mensaje queda en la bandeja de A sin turno asociado.

#### Scenario: Bandeja de otra clínica

- **WHEN** la recepcionista de B pide `GET /api/whatsapp/fallos`
- **THEN** no ve ningún fallo de A.

### Requirement: Textos base internos sembrados

El sistema SHALL disponer de cinco textos base en español rioplatense (`recordatorio_24h`, `confirmacion`, `cancelacion`, `reprogramacion`, `oferta_hueco`), propios de la plataforma y sin aprobación de Meta (DD-10), cuyas variables se completan en el servidor.

#### Scenario: Textos disponibles tras migrar

- **WHEN** se aplican las migraciones sobre una base vacía
- **THEN** existen exactamente esos cinco textos base y el downgrade los elimina sin residuos.
