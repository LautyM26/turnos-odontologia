# Reglas de Negocio

> Cada regla tiene código `RN-{DOMINIO}-{NN}`. Trazan al discovery (§06 mercado, §07 oportunidades, §09 MVP, §10 regulatorio). Las marcadas **(S)** son inferencia de modelado necesaria para operar el MVP.

## Dominio: Agenda (RN-AG)

- **RN-AG-01**: el sillón es un recurso de agenda junto a profesional y equipo; ningún turno activo puede solaparse en (sillón, rango) ni en (profesional, rango) — prevención dura.
- **RN-AG-02**: cada prestación tiene duración propia; el turno hereda la duración de la prestación, no un slot fijo.
- **RN-AG-03**: los bloqueos (almuerzo, admin, feriados) impiden reservas en su rango.
- **RN-AG-04**: el sobreturno solo lo crea un rol autorizado y queda marcado como tal con motivo.
- **RN-AG-05**: la reserva online por enlace no exige registro ni cuenta; queda abierta a pacientes nuevos (contra-ejemplo Bilog: solo registrados).
- **RN-AG-06**: la lista de espera ofrece el hueco automáticamente ante una cancelación (orden de prioridad); si se acepta, el turno se reasigna. (S — operatoria del "relleno automático".)

## Dominio: Turnos y asistencia (RN-TU)

- **RN-TU-01**: estados de turno: reservado → confirmado → asistido | ausente | cancelado; las transiciones son explícitas y auditadas.
- **RN-TU-02**: el recordatorio sale por WhatsApp oficial (plantilla aprobada) con ventana de confirmación.
- **RN-TU-03**: confirmar, cancelar y reprogramar por WhatsApp actualiza la agenda (bidireccional real, no aviso de una vía).
- **RN-TU-04**: todo ausente entra a recuperación (seguimiento con monto visible) y alimenta el score de riesgo del paciente.

## Dominio: WhatsApp (RN-WA)

- **RN-WA-01**: solo API oficial de WhatsApp Business; prohibido el QR no oficial (riesgo de bloqueo del número).
- **RN-WA-02**: costo por mensaje transparente en pesos (plantillas Meta: utilidad dentro de ventana gratis; tarifa ARS vigente desde 1/7/2026).
- **RN-WA-03**: cada mensaje guarda plantilla, dirección, estado y costo para exponerlo al consultorio.

## Dominio: Clínica (RN-CL)

- **RN-CL-01**: toda evolución lleva autor (profesional) y fecha/hora; sin autor no se guarda.
- **RN-CL-02**: la HC es append-only con auditoría: ningún cambio borra historia; toda corrección deja traza (Ley 26.529).
- **RN-CL-03**: odontograma FDI con permanentes y temporales como base del MVP (dentición mixta, versionado fino y BOP son posteriores).
- **RN-CL-04**: el recall se dispara desde el odontograma o el plan, no con campañas genéricas.
- **RN-CL-05**: imágenes simples como adjuntos; DICOM/radiología integrada es etapa posterior.

## Dominio: Presupuesto y plan (RN-PR)

- **RN-PR-01**: cada presupuesto aceptado genera la secuencia de turnos sugerida.
- **RN-PR-02**: lo no agendado entra en seguimiento con monto visible (tablero de ingresos recuperables: no convertidos, inactivos).
- **RN-PR-03**: montos siempre en ARS, precio público sin packs (decisión comercial).

## Dominio: Caja y seña (RN-CA)

- **RN-CA-01**: el turno online se confirma al pagar la seña por Mercado Pago, que va directo a la cuenta del profesional; la seña bloquea el horario (referencia Turnito).
- **RN-CA-02**: la seña es obligatoria solo para pacientes con historial/riesgo de faltas (combina score de riesgo tipo DrApp + relleno tipo DentalCore).
- **RN-CA-03**: caja con seña y saldo por turno/presupuesto; anulaciones solo con rol y traza.

## Dominio: Facturación ARCA (RN-AF)

- **RN-AF-01**: la factura electrónica B/C con CAE y QR se emite desde el cobro (no antes).
- **RN-AF-02**: datos fiscales del consultorio (CUIT) configurados antes de facturar; sin CUIT no hay CAE.

## Dominio: Obras sociales (RN-OS)

- **RN-OS-01 (MVP)**: se registran obra social, plan y afiliado del paciente (bajo costo; prepara etapa 2).
- **RN-OS-02 (etapa 2)**: cálculo de cobertura y copago, lotes exportables y RNO generado desde el odontograma.
- **RN-OS-03 (etapa 2)**: validación en línea por financiador solo vía alianzas con círculos o integradores (Frontini); requiere acuerdo por financiador.

## Dominio: Cumplimiento y seguridad (RN-CU)

- **RN-CU-01**: datos de salud = datos sensibles (Ley 25.326): consentimiento, política de privacidad pública y ubicación de datos declarada.
- **RN-CU-02**: consentimientos con firma electrónica y constancia (fecha, IP, dispositivo, hash; documento bloqueado) según Ley 25.506.
- **RN-CU-03**: receta electrónica solo por plataforma registrada en ReNaPDiS (obligatoria desde 1/1/2025; Res. 1959/2024 y 2214/2025); hasta tener propia, vía partner.
- **RN-CU-04**: respaldo y exportación completa (CSV/PDF) sin costo ni retención.
- **RN-CU-05**: página de cumplimiento pública (leyes 26.529, 25.326, 25.506, 27.706 a validar con asesoría legal).

## Dominio: Excepciones globales

- **RN-GL-01**: ante contradicción entre fuentes del discovery, vale Claude R2 (base verificada); lo no evidenciado se marca NE y se verifica en demo, nunca se hardcodea como cierto.
- **RN-GL-02**: ninguna métrica autodeclarada de competidores ("reduce ausencias X %", conteos de clientes) puede usarse como compromiso del producto.
- **RN-GL-03**: precios de competidores en USD o sin publicar no fijan nuestro precio: el nuestro es público en ARS con mensajería transparente.
