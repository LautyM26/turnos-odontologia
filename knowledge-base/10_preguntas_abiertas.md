# Preguntas Abiertas

> Todo traza a `discovery/Discovery Consolidado Turnos Odontologia.pdf` (§§02, 05, 08, 10, 11, 12). Las PA-0X son el question round corto que pide el flujo: lo que el PDF no responde no se inventa.

## Inconsistencias detectadas

### IN-01 — Origen de Dentalink
**Documento A dice**: Perplexity: argentino.
**Documento B dice**: GPT/Gemini/Claude: Chile (Healthatom).
**Impacto**: posicionamiento y adaptación AR del referente clínico.
**Resolución propuesta**: vale Chile (DD-07). Resuelto.

### IN-02 — Precio de Dentalink
**Documento A dice**: Gemini: desde USD 29/mes.
**Documento B dice**: GPT/Claude: solo cotización ("varían según las necesidades").
**Impacto**: comparación de precios.
**Resolución propuesta**: pedir en demo (§08).

### IN-03 — Adaptación argentina de Dentalink (ARCA, Mercado Pago, OS)
**Documento A dice**: GPT: OS ✔, ARCA ◐.
**Documento B dice**: Gemini: sin ARCA nativa. Claude: ARCA/MP/OS no evidenciados.
**Impacto**: define si el líder clínico es amenaza local real.
**Resolución propuesta**: pregunta clave de demo §08.

### IN-04 — "ARCA nativo" de Reservo
**Documento A dice**: Perplexity/Gemini: módulo ARCA nativo, "solución argentina destacada".
**Documento B dice**: Claude no lo relevó; única fuente es el blog del propio Reservo (dominio .cl).
**Impacto**: si fuera real, cambia el mapa fiscal.
**Resolución propuesta**: verificación rápida sin demo completa (§08, §11). Sin verificar.

### IN-05 — Dentiqa: origen y precio
**Documento A dice**: Perplexity: Argentina. GPT: LatAm/México, AR$135.000 Starter. Gemini: USD 89/mes.
**Impacto**: comparación y descarte.
**Resolución propuesta**: origen probable México/LatAm; precio a confirmar. Sin verificar.

### IN-06 — ¿AgendaPro tiene odontograma?
**Documento A dice**: GPT: ficha odontológica ◐. Claude: ficha clínica genérica solo desde Premium.
**Documento B dice**: Gemini: no.
**Impacto**: si agenda/ficha vs. odontograma real.
**Resolución propuesta**: probable que no (ficha genérica, no odontograma). Verificar en demo si importa.

### IN-07 — ¿CalDoc tiene odontograma?
**Documento A dice**: GPT ✔.
**Documento B dice**: Gemini: historia digital sin odontograma.
**Impacto**: mapa de competidores.
**Resolución propuesta**: sin verificar (actor periférico).

### IN-08 — DentalSoft (chatbot WhatsApp 24/7 + liquidación OS)
**Documento A dice**: Gemini lo afirma.
**Documento B dice**: Claude: casi todo NE.
**Impacto**: hallazgo solo-Gemini.
**Resolución propuesta**: verificación rápida §08. Sin verificar.

### IN-09 — Dentaly (AR) vs. Dentally (UK)
**Documento A dice**: Gemini: "Dentaly" (dentaly.com.ar, AR, referente de periodontograma).
**Documento B dice**: Claude: "Dentally" (Henry Schein One, UK, referencia de nube pura).
**Impacto**: no confundirlos.
**Resolución propuesta**: son productos distintos. Aclarado.

### IN-10 — Clientes y precios de Bilog
**Documento A dice**: Odonthia (competidor): +3.000 clínicas, USD 0/25/40.
**Documento B dice**: sitio oficial: +1.500, cotiza por usuario.
**Impacto**: dimensionamiento del incumbente.
**Resolución propuesta**: vale sitio oficial (+1.500, sin precios públicos). Resuelto.

### IN-11 — Precios de DentalCore
**Documento A dice**: julio: USD 49/149 (con plan gratuito en metadescripción).
**Documento B dice**: hoy: USD 69/139/399; la página no muestra gratuito.
**Impacto**: el competidor más agresivo se mueve rápido (advertencia §11).
**Resolución propuesta**: Pro 69 / Premium 139 / Enterprise desde 399. Resuelto (a re-verificar: el mercado cambió entre julio y septiembre 2026).

### IN-12 — WhatsApp en Turnito (plan gratis)
**Documento A dice**: el blog dice que sí.
**Documento B dice**: la tabla de planes dice que no.
**Impacto**: referencia de reserva sin fricción.
**Resolución propuesta**: no incluido: requiere plan Advanced. Resuelto.

### IN-13 — WhatsApp en Doctoralia AR
**Documento A dice**: la página de producto lo anuncia.
**Documento B dice**: la tabla de planes lista email, push y SMS.
**Impacto**: referencia lado-paciente.
**Resolución propuesta**: contradictorio en el propio sitio. Pedir en demo.

### IN-14 — Precio de Doctocliq / precio de DrApp
**Documento A dice**: Doctocliq: USD 19 (GPT/Cl R1) vs. 29 con rango 19–49 (Cl R2). DrApp: ARS 32.800 vs. 16.499 anual (versión previa).
**Documento B dice**: —
**Impacto**: comparación.
**Resolución propuesta**: Doctocliq rango 19–49 + freemium 30 citas (parcial); DrApp tomar 32.800 + IVA por profesional (parcial).

### IN-15 — "70 % de pacientes vía financiadores"
**Documento A dice**: Gemini lo afirma sin fuente.
**Documento B dice**: ninguna otra fuente lo respalda.
**Impacto**: no usar en pitch sin respaldo (§05).
**Resolución propuesta**: sin fuente; validar antes de usar.

### IN-16 — Problemas del Excel (Anexo §12)
**Documento A dice**: matriz Gemini con puntajes-fecha (04/05 = 4,5), total Dentatools 3,98 (da 4,03), A.3 de ChatGPT truncada, dos matrices Claude sin rótulo, orden R2 incorrecto (DentalTec antes que DrApp), "#" con decimales, escalas ✓/~/— vs. ✔/◐/—.
**Documento B dice**: valores corregidos en §04 "Gemini (corregida)" y R2 como vigente.
**Impacto**: el Excel no es usable tal cual.
**Resolución propuesta**: aplicar los 8 arreglos listados en §12 antes de reutilizarlo.

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|-----------|----------|---------|---------|
| Alta | PA-01 — Stack ✅ RESUELTA (ronda usuario 1, 2026-10-07): Python + FastAPI + PostgreSQL + React/Vite. El discovery exigía nube sin imponer tecnología. Ver DD-08. | `02`, `08` ✅ desbloqueados | Equipo técnico + dueño |
| Alta | PA-02 — Despliegue ✅ RESUELTA (ronda usuario 1): SÍ, SaaS multi-tenant en la nube, un tenant por clínica con datos aislados (estándar DrApp/Dentalink). Ver DD-09, SU-01 validado. | Arquitectura, `08` ✅ | Dueño |
| Alta | PA-03 — Roles ✅ RESUELTA (ronda usuario 1): los 4 roles alcanzan para iniciar, con permisos granulares — odontólogo tercerizado ve solo su agenda; sobreturnos los maneja admin/recepcionista. Ver SU-02 validado. | `03`, RBAC ✅ | Dueño + piloto |
| Alta | PA-04 — Legal: ABIERTA, supuesto Sprint 1 (ronda usuario 1). Validar con asesoría las leyes 26.529 (HC), 25.326 (datos sensibles), 25.506 (firma), 27.553 + DNU 345/2024, Res. 1959/2024 y 2214/2025 (ReNaPDiS), 27.706 y facturación ARCA antes de diseñar HC y receta (§10). Ver SU-08. | HC, receta, cumplimiento | Asesoría legal |
| Media | PA-05 — WhatsApp: ABIERTA, supuesto Sprint 1 (ronda usuario 1). Definir BSP/proveedor, quién gestiona y asume el costo transparente en ARS por tipo de plantilla. Tipo de WhatsApp de Bilog sin confirmar (§11). Ver SU-07. | Costos, `08` env vars | Dueño |
| Media | PA-06 — Mercado Pago: ABIERTA, supuesto Sprint 1 (ronda usuario 1). Definir cuenta (¿profesional directo como §07?), credenciales y política de reembolso ante cancelación. Ver SU-07. | Flujos 1/3/7 | Dueño |
| Media | PA-07 — ARCA: PARCIALMENTE VALIDADA (ronda usuario 1) — el consultorio propio es el piloto que aportará CUIT/régimen (B/C) y criterio (por profesional o por clínica). Comportamiento ante caída de ARCA (cola visible) sigue a validar. | Flujo 7, Sprint 1 | Dueño + contador |
| Media | PA-08 — Partner recetas: ABIERTA, supuesto Sprint 1 (ronda usuario 1). ¿Farmalink, Innovamed u otro registrado en ReNaPDiS? ¿Alcance a órdenes de estudios (Res. 2214/2025)? Temprano vía partner (DD-06). Ver SU-08. | Flujo 9 / etapa temprana | Dueño |
| Media | PA-09 — Prestaciones y duraciones: PARCIALMENTE VALIDADA (ronda usuario 1) — fuente identificada: el consultorio propio fija catálogo inicial, duración por prestación, bloqueos y política de sobreturnos. Falta cargar el catálogo como seed. Ver SU-06. | Seed data, `04` | Piloto |
| Media | PA-10 — Actores solo-GPT (Dentidad, Órbita, DentApp) y solo-Gemini (DentalSoft, Dentaly, Dentatools, Benty, RivoClin): ¿verificar antes del roadmap o aceptar como periféricos? Órbita declara agenda por sillón (relevante para DD-04). | Roadmap / demos | Equipo |
| Baja | PA-11 — Reseñas y seguridad no re-verificadas: Capterra/G2, videos DentalTec, páginas /seguridad de Odonthia y DrApp (§11). ¿Se re-verifican o se acepta NE? | Benchmark | Equipo |
| Baja | PA-12 — Métricas base: PENDIENTE DEL PILOTO (ronda usuario 1) — la línea base de ausentismo/ocupación se releva en el consultorio propio (las de competidores son autodeclaradas y no valen). Ver SU-06. | `01` métricas | Piloto |

## Respuestas ronda usuario 1 (2026-10-07) — cierre parcial kb-creator

1. **Stack (PA-01): DECIDIDA** → DD-08. 2. **Nube multi-tenant (PA-02): CONFIRMADA** → DD-09 / SU-01 validado.
3. **Roles (PA-03): CONFIRMADOS** → SU-02 validado (tercerizado solo su agenda; sobreturnos admin/recepcionista).
4. **Piloto (PA-07/09/12): CONFIRMADO** → SU-06 (consultorio propio; catálogo/duraciones/agenda real desde el piloto; métricas base pendientes).
5. **Pagos y mensajes (PA-05/06): SUPUESTO Sprint 1** → SU-07. 6. **Legal y recetas (PA-04/08): SUPUESTO Sprint 1** → SU-08.
Lo no respondido más allá de esto queda como supuesto marcado y se valida en Sprint 1.

## Question round sugerido (para cerrar gaps sin asumir)

> Responder corto; lo no respondido queda como supuesto marcado y se valida en Sprint 1.

1. Stack (PA-01): ¿hay restricción no negociable (ej. "tiene que ser X") o decidimos nosotros y proponemos?
2. Nube multi-tenant (PA-02/SU-01): ¿sí o hay requisito on-premise?
3. Roles (PA-03): ¿los 4 roles alcanzan? ¿Quién autoriza sobreturnos y anula caja?
4. Piloto (PA-07/09/12): ¿hay 1–2 consultorios para fijar prestaciones/duración, CUIT de prueba y línea base de ausentismo?
5. Pagos y mensajes (PA-05/06): ¿cuenta de Mercado Pago y BSP de WhatsApp ya existen o se tramitan?
6. Legal y recetas (PA-04/08): ¿hay asesoría legal y partner ReNaPDiS elegido (o lo elegimos)?
