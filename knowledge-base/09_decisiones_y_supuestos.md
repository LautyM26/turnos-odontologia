# Decisiones y Supuestos

> Trazan a `discovery/Discovery Consolidado Turnos Odontologia.pdf` (§§02, 04, 07, 09, 10). Formato DD/SU según plantilla canónica.

## Decisiones documentadas

### DD-01 — Factura ARCA va en el MVP
**Decisión**: FE B/C con CAE y QR desde el cobro entra al MVP como IMP.
**Contexto**: las fuentes estaban empatadas 2–2 entre IMP y DIF (§09).
**Alternativas consideradas**: (a) dejarla como DIF de lanzamiento; (b) postergarla a F2.
**Justificación**: Gemini y Claude la señalan como el mayor punto de fricción administrativa del consultorio argentino, y DrApp demuestra que es alcanzable.
**Trade-offs aceptados**: suma integración fiscal al camino crítico del MVP; exige CUIT/configuración antes de facturar y cola de reintentos ante caídas de ARCA.

### DD-02 — WhatsApp solo por API oficial, nunca por QR
**Decisión**: integración exclusivamente con WhatsApp Business API oficial, bidireccional, con costo transparente en pesos.
**Contexto**: todos los verticales la ofrecen como adicional pago, "individual", con cupos o por QR no oficial (§01); DentalCore usa QR no oficial (§03).
**Alternativas consideradas**: (a) QR no oficial más barato; (b) aviso de una vía (solo recordatorio).
**Justificación**: el QR arriesga bloqueo del número; la tarifa Meta en ARS vigente desde 1/7/2026 (plantillas de utilidad dentro de ventana gratis) hace viable el costo transparente.
**Trade-offs aceptados**: costo por plantilla y gestión de plantillas aprobadas; a cambio, confirmación/cancelación/reprogramación que sí actualiza la agenda.

### DD-03 — Obras sociales en dos niveles (MVP mínimo → validación vía alianzas)
**Decisión**: MVP solo registra OS/plan/afiliado; etapa 2 calcula cobertura/copago, genera RNO y lotes; validación en línea solo vía alianzas con círculos o integradores (Frontini como posible socio, no competidor).
**Contexto**: la validación en línea (DentalTec, +15 OS) requiere acuerdos por financiador: es una barrera de entrada (§06).
**Alternativas consideradas**: validar en línea desde el MVP.
**Justificación**: bajo costo inicial que prepara la etapa 2 sin bloquear el lanzamiento en negociaciones por financiador.
**Trade-offs aceptados**: en MVP no hay validación real de afiliado/práctica.

### DD-04 — Sillón como recurso con motor de reglas documentado
**Decisión**: la agenda modela sillón + profesional + equipo con duración por prestación, bloqueos, sobreturnos por rol y anti-solapamiento duro — y se documenta públicamente.
**Contexto**: es el vacío más claro del mercado: nadie lo documenta (§01, §06); Órbita declara agenda por sillón con prevención de choque pero sin FE (GPT, sin verificar).
**Alternativas consideradas**: slots fijos sin recurso sillón.
**Justificación**: ataca solapamientos y refleja la operatoria real del consultorio; documentarlo es en sí un diferenciador.
**Trade-offs aceptados**: motor de agenda más complejo que slots fijos.

### DD-05 — Precio público en ARS, sin packs, mensajería transparente
**Decisión**: posicionamiento comercial explícito contra adicionales y tarifas dolarizadas (decisión comercial, no de desarrollo — §09).
**Contexto**: precios opacos o en USD con inflación 1,7 % mensual / 33,5 % interanual (INDEC ago-2026); WhatsApp cobrado aparte en incumbentes (§06, §10).
**Alternativas consideradas**: pricing por packs como Bilog/DentalTec.
**Justificación**: 2 fuentes lo sostienen como diferenciador (§07).
**Trade-offs aceptados**: compromete a publicar y mantener precios; no lo implementa código, lo comunica el sitio.

### DD-06 — Receta electrónica temprana vía partner, propia en F2
**Decisión**: cubrir receta/órdenes (obligatorias desde 1/1/2025, Res. 1959/2024 y 2214/2025, ReNaPDiS) vía partner registrado (Farmalink/Innovamed/u otro); receta propia queda F2.
**Contexto**: sin receta homologada el odontólogo usa otra plataforma; OdontoClinIA tiene ReNaPDiS N.º 248 verificable; DrApp integra Farmalink/Innovamed (§03, §10).
**Alternativas consideradas**: receta propia en MVP.
**Justificación**: registrarse en ReNaPDiS y homologar es costoso para el MVP; el partner cubre la obligatoriedad legal.
**Trade-offs aceptados**: dependencia de un tercero para prescribir.

### DD-07 — Claude R2 como base ante contradicciones; Gemini solo como opinión
**Decisión**: ante conflicto entre fuentes vale Claude R2 (verificada contra primarias); Perplexity solo como lista de nombres; Gemini (puntajes 3,5–4,25 incluso sin verificar) solo como ideas/oportunidades.
**Contexto**: §02 confiabilidad, §04 matrices, §05 contradicciones, §12 problemas del Excel (fechas, totales, tablas truncadas).
**Alternativas consideradas**: promediar puntajes.
**Justificación**: R2 penaliza lo no evidenciado (NE); promediar mezclaría evidencia con afirmaciones sin fuente.
**Trade-offs aceptados**: se descartan puntajes altos de Gemini para Reservo/DentalSoft/Dentaly/Dentatools (sin verificar).

## Supuestos inferidos

### SU-01 — SaaS web multi-tenant en la nube
**Supuesto**: el producto es SaaS web multi-tenant (una instancia, clínicas como tenants).
**Origen**: agenda en la nube, reserva online, multisede y precios por profesional/sillón en todo el mapa §03; inferido para `02_descripcion_general.md`.
**Riesgo si es falso**: cambia toda la arquitectura (on-premise/mono-tenant exigiría otro modelo de despliegue y facturación).
**Cómo validar**: confirmar con el dueño: ¿nube multi-tenant sí/no? (ver PA-02).

### SU-02 — Al menos 4 roles humanos (admin, odontólogo, recepcionista, paciente)
**Supuesto**: el MVP distingue esos 4 roles.
**Origen**: requisito "roles y permisos" §09 + referencia Dentally (permisos granulares); inferido para `03_actores_y_roles.md`.
**Riesgo si es falso**: re-modelar permisos y pantallas.
**Cómo validar**: pregunta P3 en `10_preguntas_abiertas.md`.

### SU-03 — Stack sin definir; integraciones sí definidas
**Supuesto**: lenguaje/framework/DB quedan a decisión técnica (PA-01); lo no negociable es WhatsApp oficial + Mercado Pago + ARCA + partner ReNaPDiS.
**Origen**: el discovery no menciona stack en ningún §; sí exige esas 4 integraciones (§09).
**Riesgo si es falso**: ninguno si se decide a tiempo; alto si se posterga (bloquea `02` y `08`).
**Cómo validar**: ronda corta de preguntas (ver salida: question round).

### SU-04 — Ventanas operativas típicas (recordatorio 24 h, pre-bloqueo ~15 min, timeouts de oferta)
**Supuesto**: recordatorio 24 h antes; pre-bloqueo de horario expira en minutos; oferta de lista de espera expira.
**Origen**: operatoria mínima necesaria para los flujos `07`; el discovery no fija estos valores.
**Riesgo si es falso**: fricción con la operatoria real del consultorio (demasiados/faltos avisos, huecos retenidos).
**Cómo validar**: confirmar con 1–2 consultorios piloto antes del Sprint 1.

### SU-05 — Demos priorizadas como orden de verificación
**Supuesto**: el orden Dentalink → DentalCore → Bilog → DentalTec → DrApp (§08) es también el orden en que conviene verificar huecos (ARCA nativo de Reservo, WhatsApp de Bilog/DentalSoft, reglas de agenda de todos).
**Origen**: §08 y §11 del discovery.
**Riesgo si es falso**: se mira primero al competidor equivocado.
**Cómo validar**: barata — verificación rápida de Reservo/DentalSoft sin demo completa, como indica §08.
