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

### DD-08 — Stack decidido: Python + FastAPI + PostgreSQL + React/Vite
**Decisión**: stack del producto = backend Python + FastAPI, base PostgreSQL, frontend React + Vite.
**Contexto**: el discovery exige capacidades en la nube pero no impone tecnología (PA-01); la ronda de respuestas usuario 1 (2026-10-07) propone avanzar con este stack y queda DECIDIDO.
**Alternativas consideradas**: (a) seguir con stack indefinido; (b) otra combinación — no propuesta en la ronda.
**Justificación**: el Discovery exige capacidades en la nube sin imponer tecnología; decidir ahora desbloquea `02`, `08` y el Sprint 1.
**Trade-offs aceptados**: compromiso con este stack para el MVP; integraciones no negociables sin cambio (WhatsApp oficial + Mercado Pago + ARCA + partner ReNaPDiS).

### DD-09 — Nube multi-tenant confirmada (un tenant por clínica, datos aislados)
**Decisión**: SaaS multi-tenant en la nube, un tenant por clínica con datos aislados.
**Contexto**: SU-01 / PA-02; ronda usuario 1 (2026-10-07) lo confirma como estándar validado por referentes regionales (DrApp, Dentalink).
**Alternativas consideradas**: on-premise / mono-tenant — descartadas.
**Justificación**: estándar regional validado; sostiene agenda en la nube, reserva online y modelo por profesional/sillón.
**Trade-offs aceptados**: exige aislamiento de datos por tenant y despliegue cloud desde el día 1.

## Supuestos inferidos

### SU-01 — SaaS web multi-tenant en la nube ✅ VALIDADO (ronda usuario 1, 2026-10-07)
**Supuesto**: el producto es SaaS web multi-tenant (una instancia, clínicas como tenants).
**Origen**: agenda en la nube, reserva online, multisede y precios por profesional/sillón en todo el mapa §03; inferido para `02_descripcion_general.md`.
**Validación**: CONFIRMADO por el usuario — SaaS multi-tenant, un tenant por clínica con datos aislados; estándar de DrApp/Dentalink. Ver DD-09. Ya no es supuesto abierto.

### SU-02 — 4 roles humanos + permisos granulares ✅ VALIDADO (ronda usuario 1, 2026-10-07)
**Supuesto**: el MVP distingue admin, odontólogo, recepcionista, paciente-enlace.
**Origen**: requisito "roles y permisos" §09 + referencia Dentally (permisos granulares); inferido para `03_actores_y_roles.md`.
**Validación**: CONFIRMADO por el usuario — los 4 roles alcanzan para iniciar; granularidad: odontólogo tercerizado ve solo su agenda; sobreturnos los maneja admin/recepcionista. Ya no es supuesto abierto.

### SU-03 — Stack decidido; integraciones no negociables ✅ RESUELTO (ronda usuario 1, 2026-10-07)
**Supuesto original**: lenguaje/framework/DB quedaban a decisión técnica (PA-01); lo no negociable es WhatsApp oficial + Mercado Pago + ARCA + partner ReNaPDiS.
**Origen**: el discovery no menciona stack en ningún §; sí exige esas 4 integraciones (§09).
**Resolución**: stack DECIDIDO — Python + FastAPI + PostgreSQL + React/Vite (DD-08). PA-01 cerrada. Las 4 integraciones siguen no negociables.

### SU-04 — Ventanas operativas típicas (recordatorio 24 h, pre-bloqueo ~15 min, timeouts de oferta)
**Supuesto**: recordatorio 24 h antes; pre-bloqueo de horario expira en minutos; oferta de lista de espera expira.
**Origen**: operatoria mínima necesaria para los flujos `07`; el discovery no fija estos valores.
**Riesgo si es falso**: fricción con la operatoria real del consultorio (demasiados/faltos avisos, huecos retenidos).
**Cómo validar**: confirmar con el consultorio piloto propio antes del Sprint 1 (piloto identificado en ronda usuario 1: PA-07/09/12).

### SU-06 — Piloto: consultorio propio (parcialmente validado, ronda usuario 1, 2026-10-07)
**Supuesto**: el consultorio odontológico propio es el entorno piloto principal para fijar catálogo de prestaciones, duraciones y probar la agenda real.
**Origen**: respuesta usuario ronda 1 (PA-07/09/12).
**Estado**: fuente de seed data IDENTIFICADA (prestaciones/duraciones/agenda real se fijan con el piloto). Métricas base (ausentismo/ocupación, PA-12) aún pendientes de medir en el piloto.
**Cómo validar**: cargar catálogo + duraciones del piloto como seed antes del Sprint 1; relevar línea base de ausentismo/ocupación en el piloto.

### SU-07 — Pagos y mensajes: supuestos Sprint 1 (PA-05/PA-06 ABIERTOS)
**Supuesto**: quién gestiona y asume el costo transparente de la API oficial de WhatsApp (BSP/plantillas en ARS) y la cuenta de Mercado Pago (titularidad, credenciales, reembolsos) queda como supuesto a definir en Sprint 1.
**Origen**: respuesta usuario ronda 1 — "queda como supuesto para el Sprint 1".
**Plan de validación (Sprint 1)**: definir BSP y quién paga cada tipo de plantilla (costo ARS a exponer); definir cuenta MP (¿profesional directo?), credenciales y política de reembolso ante cancelación.

### SU-08 — Legal y recetas: supuestos Sprint 1 (PA-04/PA-08 ABIERTOS)
**Supuesto**: encuadre normativo (leyes 26.529, 25.326, 25.506, 27.553 + DNU 345/2024, Res. 1959/2024 y 2214/2025, ley 27.706, facturación ARCA) a validar con asesoría legal; receta ReNaPDIS temprana vía partner.
**Origen**: respuesta usuario ronda 1 — "queda como supuesto para el Sprint 1"; el Discovery indica validar con asesoría y cubrir receta temprana vía partner.
**Plan de validación (Sprint 1)**: consulta con asesoría legal antes de diseñar HC/receta; elegir partner ReNaPDiS (Farmalink/Innovamed/u otro registrado) y alcance (¿órdenes de estudios?).

### SU-05 — Demos priorizadas como orden de verificación
**Supuesto**: el orden Dentalink → DentalCore → Bilog → DentalTec → DrApp (§08) es también el orden en que conviene verificar huecos (ARCA nativo de Reservo, WhatsApp de Bilog/DentalSoft, reglas de agenda de todos).
**Origen**: §08 y §11 del discovery.
**Riesgo si es falso**: se mira primero al competidor equivocado.
**Cómo validar**: barata — verificación rápida de Reservo/DentalSoft sin demo completa, como indica §08.
