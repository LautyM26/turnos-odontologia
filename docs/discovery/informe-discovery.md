# Discovery: sistemas de gestión de turnos y agenda para consultorios odontológicos en Argentina

**Materia:** Metodología I — Trabajo de Integración

**Carrera:** Tecnicatura Universitaria en Programación

**Fecha:** 2026-10-13

**Integrantes y responsabilidades**

| Integrante | Responsabilidad en el trabajo |
|---|---|
| Uriel Vega | Etapas 1–3: fundación del proyecto, Discovery y base de conocimiento (KB) |
| Lautaro Mejias | Etapas 4–6: roadmap, skills y reglas del proyecto, changes |
| Matheo Bazán | Etapa 7: memoria persistente (Engram) y ciclo OPSX del change `crear-turno-sin-solapamientos`; cierre y verificación de este informe |

**Cómo se hizo (declaración de uso de IA)**

1. **Relevamiento inicial (corte 2026-09-23).** El equipo consultó cuatro asistentes de IA (Perplexity, ChatGPT, Gemini y Claude, este último en dos rondas) y consolidó sus resultados en `discovery/Discovery Consolidado Turnos Odontologia.pdf` (46 sistemas, matrices de puntuación, demos y MVP). Ese documento no tenía URLs por afirmación. Es la base de la KB y de `CHANGES.md`.
2. **Re-verificación contra fuentes primarias (2026-10-13).** Un agente de IA (Claude, en Claude Code) abrió los sitios oficiales, las páginas de precios, los centros de ayuda, las tiendas de apps, los changelogs y la documentación de API de 18 sistemas. Etiquetó cada dato como *Comprobado*, *Afirmación comercial* o *No evidenciado* y lo contrastó con el informe previo. Las páginas se leyeron con una herramienta de descarga que resume el contenido, así que las citas son paráfrasis.
3. **Redacción.** Este informe también lo redactó la IA a partir de los dos insumos anteriores. Los puntajes se calcularon con un script en Python, no a mano.
4. **Verificación humana.** Ningún dato de este informe se probó en uso real ni en demo. Las 12 fuentes de la sección *Verificación de fuentes* las abrió y contrastó personalmente Matheo Bazán el 2026-10-13 (columna "Comprobado personalmente por").

<div style="page-break-after: always"></div>

## Resumen ejecutivo

**Qué se investigó.** Se buscó qué software usan, o pueden contratar, los consultorios y clínicas odontológicas argentinas para la agenda, los turnos, la historia clínica y la administración. También se buscaron los vacíos que deja el mercado. Se re-verificaron 18 sistemas: 10 verticales odontológicos argentinos, 3 generalistas que operan en Argentina, 4 regionales (Chile y Perú) y 1 referencia internacional (Reino Unido). Cada dato tiene su URL y la fecha de consulta. Otros 28 sistemas del informe previo quedan listados, pero no se re-verificaron.

**Hallazgos principales.**

- **No hay un líder completo, y la evidencia pública es más débil de lo que parecía.** Con la regla "lo no evidenciado puntúa como ausente y lo comercial tiene tope parcial", el mejor sistema llega a 3,60/5 (DentalCore). Los referentes regionales caen fuerte: Dentalink baja de 3,63 a 2,53 porque casi todo lo que publica es afirmación comercial y no muestra adaptación a Argentina.
- **El informe generado por IA tenía errores relevantes.** Se encontraron **31 afirmaciones corregidas o no respaldadas**: precios desactualizados (DentalCore, DrApp, OdontoApp, DentApp, Dentally, Odonthia), funciones mal atribuidas (odontograma "1–32" de OdontoClinIA, "+20 obras sociales" de DentalCore) y, sobre todo, una conclusión de mercado que ya no se sostiene.
- **"Nadie usa la API oficial de WhatsApp" es falso hoy.** DentalCore lo declara en su página de precios ("API oficial de Meta, sin QR") y Órbita se presenta como *Tech Provider* de Meta. El WhatsApp oficial pasa de **vacío del mercado** a **paridad competitiva**.
- **ARCA y Mercado Pago empiezan a ser estándar entre los verticales argentinos.** DentalCore y Dentidad emiten Factura C electrónica (Comprobado), Bilog factura electrónicamente en Argentina (changelog) y Dentidad cobra señas con Mercado Pago.
- **El vacío más claro sigue siendo la agenda odontológica con reglas.** Sillón como recurso, duración por prestación y anti-solapamiento: 17 de 18 sistemas no lo evidencian. Solo Órbita lo declara, con capturas de pantalla y sin documentación técnica.
- **Nadie combina todo lo siguiente en un solo producto:** agenda con reglas por sillón, reserva sin registro con seña, WhatsApp bidireccional, ARCA y una historia clínica auditada. DentalCore no tiene reserva online. Dentidad no declara el tipo de WhatsApp ni el anti-solapamiento. Órbita no evidencia ARCA ni Mercado Pago.

**MVP recomendado.** Se mantiene el MVP del informe previo (§09), que es la base de la KB y de `CHANGES.md`: agenda multiprofesional y multisillón con anti-solapamiento, reserva online sin registro, WhatsApp bidireccional, ficha con odontograma FDI, evolución con autor y auditoría, presupuesto, caja con seña por Mercado Pago, factura ARCA, datos de obra social, roles, respaldo y exportación, y política de privacidad. Cambia la justificación: lo que nos diferencia ya no es "WhatsApp oficial", sino **reglas de agenda explícitas + la integración completa + cumplimiento demostrable**. La decisión del equipo de usar **WhatsApp por QR** (2026-10-08) va en contra de esta evidencia y se trata como riesgo en la sección D.

---

## A. Tabla comparativa (18 sistemas)

**Leyenda.** **(C) Comprobado:** se ve en una tabla de precios o planes, en documentación, en un changelog, en una tienda de apps o en texto funcional específico del sitio oficial. **(AC) Afirmación comercial:** texto de marketing sin demostración. **No evidenciado:** las páginas abiertas no lo dicen; puede existir en una página que no se abrió, pero no se asume. Todas las fuentes se consultaron el **2026-10-13**; los números entre corchetes remiten a *Referencias*.

**Orden por relevancia para Argentina:** primero los verticales odontológicos argentinos, después los generalistas que operan en Argentina, después los regionales y al final la referencia internacional. Dentro de cada grupo, se ordena por la cantidad de evidencia sobre las funciones del MVP.

### A.1 Identidad, agenda y turnos

| # | Producto / proveedor | País · segmento | Modalidad | Agenda (multiprof. / sillón / anti-solapamiento) | Reserva online | WhatsApp (tipo) | Recordatorios | Fuente y fecha |
|---|---|---|---|---|---|---|---|---|
| 1 | **Bilog** / Bilog Soluciones Informáticas | AR · odontológico (consultorios, clínicas, financiadores) | Web + apps iOS/Android (C) | Agenda diaria y semanal (C); multiprofesional compartida (AC); sillón y anti-solapamiento: No evidenciado | Por link o QR, "incluso si es su primera consulta" (AC) | Recordatorios y confirmaciones (AC); tipo: No evidenciado | WhatsApp, SMS y email (AC) | bilog.com.ar/planes, /llms.txt, /soluciones/consultorios; App Store [1–7] · 2026-10-13 |
| 2 | **DentalCore** / Alfredo Di Tullio (unipersonal, La Plata) | AR · odontológico | Web 100 % nube (C) | Día, 3 días, semana y mes; multiprofesional; bloqueos (C); sillón y anti-solapamiento: No evidenciado | No evidenciado (portal del paciente "todavía no disponible", C); confirmar o cancelar por link (C) | **API oficial de Meta, "sin QR"** (C) | WhatsApp a las 48 h y 24 h, apagado por defecto (C) | dentalcore.app, /features, /pricing, /faq [11–14] · 2026-10-13 |
| 3 | **Órbita** / Órbita Global (La Plata) | AR · odontológico (clínicas) | Web, nube AWS (C) | **Agenda por sillón; si el turno choca "no se guarda"**; bloqueos, sobreturno marcado, lista de espera, multiprofesional (AC con capturas) | "Turnero" por enlace (AC) | **API oficial de Meta, Tech Provider**; producto aparte "Órbita Chat" (AC) | 48 h y 24 h, con reintento (AC, vía Órbita Chat) | hiorbita.com, /erp/funcionalidades, /precios, /comparativa [51–54] · 2026-10-13 |
| 4 | **Dentidad** / Solvianweb (Río Tercero, Cba.) | AR · odontológico | Web, nube (C) | Multiprofesional según plan (C); sillón y anti-solapamiento: No evidenciado | Reserva online desde el plan Clínica (C); portal por enlace sin contraseña (C) | "Soporte WhatsApp Business"; tipo: No evidenciado | WhatsApp y email (AC) | dentidad.com [48] · 2026-10-13 |
| 5 | **DentalTec** / Tándem Digital (inferido; San Juan) | AR · odontológico, círculos y obras sociales | Web (AC) | Por odontólogo, día y franja; multientidad (AC); sillón y anti-solapamiento: No evidenciado | No evidenciado | Packs pagos (C); tipo: No evidenciado; el paciente responde para confirmar (AC) | WhatsApp automático (AC) | web.dentaltec.com.ar, /funcionalidades, /preguntas-frecuentes [18–20] · 2026-10-13 |
| 6 | **OdontoClinIA** / EMPRINET 4.0 (ClinIA) | AR · odontológico (módulo); también CAPS y municipios | SaaS (AC) | Por profesional, especialidad o consultorio (AC); anti-solapamiento: No evidenciado | Web: No evidenciado; agente IA que agenda por WhatsApp (AC) | Agente IA (AC); tipo: No evidenciado | Automáticos (AC) | clinia.com.ar/odontologia, /sobre-clinia [21–22] · 2026-10-13 |
| 7 | **Odonthia** / Genera Impacto | AR · odontológico | Web, nube (Supabase/AWS São Paulo) (C) | Agenda en el plan gratis (C); "varios sillones" en Max (AC); anti-solapamiento: No evidenciado | No evidenciado | Manual gratis; automático en planes pagos (C); tipo: No evidenciado | WhatsApp automático en planes pagos (C) | odonthia.com, /planes, /seguridad [40–42] · 2026-10-13 |
| 8 | **DentApp** / Codilium | AR · odontológico | Web SaaS (C) | Por doctor, con sincronización a Google Calendar (C); sillón y anti-solapamiento: No evidenciado | No evidenciado | Desde el plan Clínica Plus (C); tipo: No evidenciado | Email (Profesional) y WhatsApp (Clínica Plus en adelante) (C) | dentapp.ar, /privacy [49] · 2026-10-13 |
| 9 | **OdontoApp** / Sovil | AR (+19 países) · odontológico | Web, nube (C) | Diaria, semanal y mensual (C); "varios profesionales, sillones y sedes" (AC); tope de 30 y 120 turnos/mes en Gratuito y Básico (C); anti-solapamiento: No evidenciado | No evidenciado | Recordatorios desde el plan Básico (C); tipo: No evidenciado | WhatsApp automático al agendar (C) | odontoapp.com.ar y bundle de precios [46–47] · 2026-10-13 |
| 10 | **OdontoGRAMA** / SolSoftware (San Luis) | AR · odontológico | Web, nube (C) | "Agendas personalizables con control de asistencia" (C); el resto: No evidenciado | No evidenciado | No evidenciado | No evidenciado | odontograma.com.ar, solsoftware.com.ar [44–45] · 2026-10-13 |
| 11 | **DrApp** / Grupo Cormos (dato solo de terceros) | AR · generalista de salud | Web + app (AC) | Multiusuario, varias sedes y consultorios (AC); sillón y anti-solapamiento: No evidenciado | 24/7 vía Crontu; el paciente confirma, cancela o reprograma (AC) | Con costo adicional (C); tipo: No evidenciado | Mail y WhatsApp (C) | drapp.com.ar, /precios, /ia [15–17] · 2026-10-13 |
| 12 | **Turnito** / Grupo Vansur | AR · turnos multirrubro (no clínico) | Web (C) | 3, 5 o ilimitadas agendas según plan; turnos recurrentes; Google Calendar (C); anti-solapamiento: No evidenciado | **Por enlace sin registro; el horario se bloquea recién cuando entra el pago** (C) | Cupo mensual: Plus 30, Advance 100, Pro 250 (C); tipo: No evidenciado | Sí (C) | turnito.app, /planes, /app-turnos-medicos [37–39] · 2026-10-13 |
| 13 | **Doctoralia Pro** / Docplanner | ES/PL, opera en AR · generalista + marketplace | SaaS + app (C) | Agenda (AC); lista de espera en el plan VIP (C); sillón y anti-solapamiento: No evidenciado | 24/7 desde web, perfil y Google My Business (AC) | Anunciado en la página de agenda (AC), ausente en la tabla de planes: contradictorio | Email y push (Starter); se suma SMS en Plus y VIP (C) | pro.doctoralia.com/ar/precio; página de agenda para especialistas [33–36] · 2026-10-13 |
| 14 | **AgendaPro** / AgendaPro | CL, opera en AR · multirrubro (con landing dental) | SaaS (C) | De 2 a 20 profesionales según plan; bloqueos; multisucursal (C); sillón y anti-solapamiento: No evidenciado | Sitio de reservas en todos los planes (C); sin registro (AC) | Complemento desde ARS 7.900/mes por 50 mensajes (C); tipo: No evidenciado | WhatsApp, SMS y email, con segundo aviso (AC) | agendapro.com/ar/planes, landing dental, centro de ayuda [26–30] · 2026-10-13 |
| 15 | **Dentalink** / Healthatom | CL (LatAm y ES) · odontológico regional | SaaS (AC) | Agenda; multicentro en el plan Pro (AC); sillón y anti-solapamiento: No evidenciado | Agendamiento online (AC) | WhatsApp Business vía Contact Center IA, con costo extra (AC) | Confirmaciones automáticas (AC) | softwaredentalink.com, /planes, /contact-center [8–10] · 2026-10-13 |
| 16 | **Doctocliq** / Zolupro S.A.C. | PE · odontológico y estético regional | Web + apps (C) | Multiprofesional ("doctores temporales") (C); sillón y anti-solapamiento: No evidenciado | No evidenciado | Cupo de 50/100/100 por mes (C; las tarjetas dicen 150); IA "Soyla" como add-on (C); "Meta Business Partner" (AC) | WhatsApp, email y SMS (AC) | doctocliq.com, /planes; App Store [23–25] · 2026-10-13 |
| 17 | **Dentidesk** / DENTIDESK (Santiago) | CL · odontológico regional | SaaS (C) | "Usuarios con agenda" (C); sillón y anti-solapamiento: No evidenciado | Widget de reserva online (C, changelog 18-03-2026) | Manual desde la ficha o el turno (C, 06-02-2026); automático "próximamente" (C) | Automático por WhatsApp: no disponible (C) | dentidesk.com, /blog [31–32] · 2026-10-13 |
| 18 | **Dentally** (ref.) / Henry Schein One UK | UK, AU, CA, IE, NZ; no opera en AR · referencia internacional | Nube pura, navegador (C) | Calendario único; precio por sillón (*surgery*); avisos de huecos libres de último momento (C); anti-solapamiento: No evidenciado | Portal: reserva 24/7 por enlace, formularios, OTP (C; planes Essentials y Pro) | No evidenciado | SMS y email automáticos; recall (C) | dentally.com/pricing, /dentally-portal, /practice-admin [55–60] · 2026-10-13 |

### A.2 Clínica, administración y precio

| # | Producto | Odontograma / HC | ARCA | Mercado Pago | Obras sociales | Precio publicado | Fuente y fecha |
|---|---|---|---|---|---|---|---|
| 1 | Bilog | Odontograma (AC); anamnesis y PDF de ficha (C, changelog); periodontograma: No evidenciado | Facturación electrónica "solo Argentina" desde v7.7.0 (C, changelog); ARCA no figura por nombre | No evidenciado | Liquidación de honorarios y prestaciones de OS; auditoría para financiadores (AC) | Freemium gratis: 1 profesional, 1 usuario, 50 pacientes (C). Lite y Premium "cotización por usuario"; montos: No evidenciado | bilog.com.ar/planes; App Store [2, 5, 7] · 2026-10-13 |
| 2 | DentalCore | Odontograma, periodontograma, imágenes, consentimientos firmados, 17 motores CDSS (C) | **Factura C/B con CAE y QR en cada cobro** (C) | QR o link (C) | Convenios, copago y liquidación por período; solo OSDE, Swiss Medical y PAMI precargadas (C) | **Plan único USD 50/mes (2 usuarios) + USD 10 por usuario adicional**; sin plan gratis ni prueba; garantía de 14 días (C) | dentalcore.app/pricing, /features [12–13] · 2026-10-13 |
| 3 | Órbita | Odontograma versionado; periodontograma de 6 sitios, todavía sin gráfico; HC firmada con matrícula (AC) | No evidenciado | No evidenciado | Convenios con presentación por lotes y débito calculado; liquidación a profesionales (AC) | Preventa: Consultorio USD 25/mes y Clínica USD 113/mes (C); la comparativa del mismo sitio dice "desde USD 33"; Órbita Chat USD 200 (150 con pago anual) (C) | hiorbita.com/precios, /comparativa [52–53] · 2026-10-13 |
| 4 | Dentidad | Anamnesis de adultos y pediátrica; odontograma por pieza y cara; consentimientos firmados (C); periodontograma: No evidenciado | **Factura C electrónica ARCA** (C); no está claro qué planes la incluyen | **Señas por Mercado Pago** (C) | Más de 70 OS precargadas (AC) | Esencial ARS 25.000, Clínica ARS 42.500, Multisede ARS 150.000, IVA incluido (C); el FAQ del mismo sitio dice 50.000/85.000/300.000; 14 días gratis | dentidad.com [48] · 2026-10-13 |
| 5 | DentalTec | Odontograma interactivo con CIE-10 (AC); periodontograma: No evidenciado | Integración ARCA (AC) | No evidenciado | **Valida en línea afiliado y práctica con más de 15 OS**; cierre Círculo → Federación → Confederación (AC) | Licencia: No evidenciado ("costo por odontólogo"); packs de WhatsApp de USD 9, 25 y 48 por 50, 150 y 300 mensajes (C) | web.dentaltec.com.ar, /funcionalidades [18–19] · 2026-10-13 |
| 6 | OdontoClinIA | Odontograma con numeración FDI de 52 piezas (AC); periodontograma: No evidenciado | "Prevé" factura ARCA (AC, promesa) | No evidenciado | Verificación de cobertura por la API PUCO de la SSS (AC). Recetario **registrado en ReNaPDiS, N.º 248** (C) | No publicado: cotización por institución y demo de 45 min (C) | clinia.com.ar/odontologia [21] · 2026-10-13 |
| 7 | Odonthia | Odontograma FDI con temporales; evolución con autor que conserva la versión anterior (AC); **firma electrónica con hash SHA-256, IP y documento bloqueado** (C) | No emite (C, comparativa propia) | Solo para pagar la suscripción (C) | Tarifario y copago (AC); no liquida OS (C) | Gestión gratis; plan IA ARS 20.900/mes; Max ARS 46.900/mes (C); US$26 y US$44 fuera de Argentina | odonthia.com/planes, /seguridad [41–42] · 2026-10-13 |
| 8 | DentApp | HC y evolución, odontograma por pieza, recetas vía RCTA (C); dictado con IA (AC); periodontograma: No evidenciado | No evidenciado ("genera facturas", sin mencionar ARCA) | Pagos con Mercado Pago (C; no aclara si es cobro al paciente) | Solo "integraciones a medida" en el plan Empresarial (AC) | Profesional ARS 24.900, Clínica Plus ARS 54.900, Clínica Pro ARS 74.900, IVA incluido; 30 días gratis (C) | dentapp.ar [49] · 2026-10-13 |
| 9 | OdontoApp | HC, odontograma de 32 dientes, periodontograma, imágenes (C); evolución solo en el plan Profesional (C) | No evidenciado | No evidenciado | No evidenciado | Gratuito (10 pacientes); Básico ARS 36.000/mes; Profesional ARS 48.500/mes; 14 días de prueba (C) | odontoapp.com.ar, bundle de precios [46–47] · 2026-10-13 |
| 10 | OdontoGRAMA | Ficha con imágenes, tratamientos y diagnósticos; odontograma (AC) | No evidenciado | No evidenciado | "Facturación a prepagas y obras sociales" (AC) | No evidenciado (solo cuenta gratis de prueba, C) | odontograma.com.ar [44] · 2026-10-13 |
| 11 | DrApp | HC por especialidad; odontograma por dictado de voz (AC) | Facturación electrónica ARCA (AC) | Cobro anticipado de turnos (AC) | No evidenciado | **ARS 34.700 por profesional/mes + IVA**; 15 días gratis (C) | drapp.com.ar/precios, /ia [16–17] · 2026-10-13 |
| 12 | Turnito | No aplica: no es software clínico (solo ficha de clientes en Pro) (C) | No evidenciado | Mercado Pago, Talo, transferencia y PayPal; comisión del 5 / 3,5 / 1 / 0 % según plan (C) | Dato de OS en la ficha (AC) | USD 0/8/18/30 en /planes y ARS 0/9.900/20.300/34.800 + IVA en la home (C, inconsistente) | turnito.app, /planes [37–38] · 2026-10-13 |
| 13 | Doctoralia Pro | "Episodios clínicos" (AC); odontograma: No evidenciado | No evidenciado | No evidenciado | No evidenciado | Starter ARS 25.000, Plus 35.000, VIP 55.000 por mes con pago anual y permanencia anual; no hay plan gratis en la página argentina (C) | pro.doctoralia.com/ar/precio, /condiciones-del-plan [33–34] · 2026-10-13 |
| 14 | AgendaPro | Ficha clínica y consentimiento desde el plan Premium (C); odontograma: No evidenciado | No evidenciado | Artículo de ayuda "Cómo vender con AgendaPro y Mercado Pago" (C, solo título); señas al reservar (AC) | No evidenciado | ARS 13.900 / 33.900 / 44.900 / 314.900, IVA incluido (C) | agendapro.com/ar/planes; ayuda [27, 30] · 2026-10-13 |
| 15 | Dentalink | Odontograma, periodontograma, ortodoncia, consentimientos (AC) | No evidenciado | No evidenciado | No evidenciado | No publicado: "Solicita tu cotización"; IA, firma, rayos X y telemedicina son extras (C) | softwaredentalink.com/planes [9] · 2026-10-13 |
| 16 | Doctocliq | Odontograma y presupuestos en todos los planes (C); periodontograma (C, App Store); notación FDI/ADA: No evidenciado | No: facturación como add-on solo para PE, MX, CO, EC y RD (C) | No evidenciado | No evidenciado | USD 0 (30 pacientes/mes), 19, 29 y 49 (C) | doctocliq.com/planes; App Store [24–25] · 2026-10-13 |
| 17 | Dentidesk | Odontograma con 3 nomenclaturas, dictado por voz, consentimiento digital (C) | No: SII de Chile y Alegra para RD (C) | No evidenciado | No evidenciado | No publicado; prueba de 15 días (C) | dentidesk.com, /blog [31–32] · 2026-10-13 |
| 18 | Dentally (ref.) | *Charting* con dentición mixta, periodoncia, planes de tratamiento (C); notas con IA (AC) | No aplica (no opera en AR) | No evidenciado | No aplica (reclamos al NHS en UK, C) | **Desde £125/mes sin IVA** (Starter, 1 sillón) (C) | dentally.com/pricing [55] · 2026-10-13 |

**Otros sistemas mencionados en el informe previo y no re-verificados** (28; siguen como "sin verificar"): DentalSoft, Dentaly (dentaly.com.ar, distinto de Dentally), Dentatools, Benty, CalDoc, MednIA, RivoClin, Gendu, Kommo, Reservo (su "ARCA nativo" sigue respaldado solo por su propio blog), Dentiqa, DentalBox, Naclix, Dentalware, Odeen, OdontoDrive, Citalo, Odensys, Medesk, Odontic, Open Dental, Curve Dental, Clinic Cloud, Clinicorp, Simples Dental, DenPro, Frontini (posible socio para obras sociales) y Salud Digital. Periféricos: DentalPro, Dentia, SimpleTurno, Medicloud y GeoSalud.

**Colisiones de nombre detectadas:** OdontoApp de Sovil no es la app "OdontoApp" de App Store (otro desarrollador). El sitio comercial de DentApp es dentapp.ar; dentapp.com.ar es solo un login sin datos. Órbita es hiorbita.com; orbitadental.com es un producto mexicano y orbita.com.ar es una inmobiliaria. Dentally (UK) no es Dentaly (AR).

---

## B. Matriz de puntuación (0–5, ponderada)

**Pesos:** Turnos y automatización 25 % · Clínica 20 % · Integraciones locales y WhatsApp 15 % · Administración, cobros y facturación 15 % · Experiencia del paciente 10 % · Seguridad, exportación y trazabilidad 10 % · Precio y adopción 5 %.

| # | Sistema | Turnos 25 % | Clínica 20 % | Integr./WA 15 % | Admin. 15 % | Paciente 10 % | Seguridad 10 % | Precio 5 % | **Total /5** | Total R2 (23/09) | Confianza |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | DentalCore | 3,0 | 4,5 | 4,0 | 4,0 | 2,0 | 4,0 | 3,0 | **3,60** | 3,45 | Media (proveedor unipersonal, sin adopción publicada) |
| 2 | Dentidad | 3,0 | 4,0 | 3,0 | 3,5 | 4,0 | 2,5 | 3,5 | **3,35** | — (nuevo) | Baja-media (sin clientes publicados; precios con discrepancia interna) |
| 3 | Dentally (ref.) | 4,0 | 4,0 | 1,5 | 2,5 | 4,5 | 4,5 | 1,0 | **3,35** | — (nuevo) | Alta en evidencia; no opera en AR |
| 4 | Bilog | 3,0 | 3,5 | 2,5 | 4,0 | 3,0 | 2,5 | 3,0 | **3,13** | 3,63 | Media |
| 5 | Órbita | 3,0 | 3,0 | 2,0 | 2,5 | 2,5 | 3,0 | 2,5 | **2,70** | — (nuevo) | Baja-media (preventa; AC con capturas) |
| 6 | AgendaPro | 3,5 | 1,5 | 2,5 | 2,5 | 3,5 | 2,0 | 4,0 | **2,68** | 3,03 | Media |
| 7 | OdontoClinIA | 3,0 | 3,0 | 3,0 | 2,0 | 2,5 | 2,5 | 1,5 | **2,68** | 3,30 | Baja-media |
| 8 | DrApp | 3,0 | 2,0 | 3,0 | 2,5 | 3,0 | 2,0 | 3,5 | **2,65** | 3,43 | Media-baja (casi todo AC) |
| 9 | Dentidesk | 2,5 | 4,0 | 1,5 | 2,0 | 3,0 | 2,5 | 2,0 | **2,60** | 2,73 | Media (changelog fechado) |
| 10 | DentApp | 2,5 | 3,5 | 2,5 | 2,0 | 1,0 | 3,0 | 3,5 | **2,58** | — (nuevo) | Baja-media (sin adopción publicada) |
| 11 | Doctocliq | 3,0 | 3,5 | 1,5 | 1,5 | 2,5 | 2,0 | 4,0 | **2,55** | 3,28 | Media |
| 12 | Dentalink | 3,0 | 3,0 | 1,5 | 2,5 | 3,0 | 2,0 | 1,5 | **2,53** | 3,63 | Baja (casi todo AC) |
| 13 | Odonthia | 2,5 | 3,5 | 1,0 | 1,5 | 1,5 | 4,0 | 5,0 | **2,50** | 2,28 | Media |
| 14 | DentalTec | 2,5 | 2,0 | 3,0 | 3,0 | 1,5 | 3,0 | 1,5 | **2,45** | 3,40 | Baja (AC; contadores con placeholders) |
| 15 | OdontoApp | 2,5 | 3,5 | 1,0 | 1,5 | 1,0 | 3,0 | 4,0 | **2,30** | — (nuevo) | Media-baja (adopción mínima) |
| 16 | Turnito | 3,5 | 0,0 | 2,5 | 1,5 | 4,5 | 1,0 | 4,0 | **2,23** | 2,33 | Alta (no es software clínico) |
| 17 | Doctoralia Pro | 3,0 | 1,0 | 1,0 | 1,0 | 3,0 | 1,0 | 3,0 | **1,80** | 2,63 | Media |
| 18 | OdontoGRAMA | 2,0 | 2,0 | 0,5 | 2,5 | 0,5 | 1,5 | 2,5 | **1,68** | 1,90 | Baja |

Los totales se calcularon con un script en Python como suma de productos (puntaje × peso) en aritmética decimal, con una segunda cuenta en coma flotante como control cruzado. Se redondearon a dos decimales (por ejemplo, 3,125 → 3,13 y 2,675 → 2,68). Hay dos empates: AgendaPro y OdontoClinIA (2,675), y Dentidad y Dentally (3,35). En el segundo, Dentidad va primero porque Dentally es una referencia extranjera.

### Nota metodológica

| Nota | Significado |
|---|---|
| 0 | Ausente o **No evidenciado** en las fuentes abiertas |
| 1 | Mención aislada, o solo como adicional pago sin detalle |
| 2 | Básico o limitado (cubre una parte menor del criterio) |
| 3 | Parcial, o completo pero sostenido **solo por afirmación comercial** (tope para AC) |
| 4 | Sólido y mayormente **Comprobado** |
| 5 | Completo, Comprobado y con detalle (tabla de planes, documentación o changelog) |

- **No evidenciado puntúa como ausencia (0–1).** Se penaliza, no se asume. Una función real que el proveedor no publica baja el puntaje: la matriz mide **capacidad evidenciada públicamente**, no la calidad real del producto. Por eso un puntaje bajo no descarta una demo (ver D).
- **Las afirmaciones comerciales puntúan como mucho "parcial" (3).** Para llegar a 3,5 o más hace falta al menos un elemento Comprobado en el criterio. Esta regla explica la mayoría de las bajas respecto de Claude R2, que puntuaba lo declarado.
- **Las métricas autodeclaradas nunca son evidencia** (cantidad de clientes, "–40 % ausentismo", "–64 % débitos"). En "Precio y adopción" solo cuentan la transparencia de precio, la moneda, el plan gratis o la prueba, y la permanencia.
- **Límite del método.** Los tres lotes de investigación aplicaron la etiqueta (C) con criterios un poco distintos: el lote 3 contó el texto funcional específico del sitio como Comprobado. Esto puede favorecer a Dentidad, OdontoApp y DentApp. Además, **las diferencias menores a 0,2 puntos no son significativas**: el pelotón entre 2,45 y 2,70 está prácticamente empatado.

### Ajustes respecto de Claude R2 (por evidencia del 2026-10-13)

- **DentalCore (3,45 → 3,60):** Integr./WA sube de 2,5 a 4,0 (WhatsApp por API oficial, ARCA y Mercado Pago comprobados); Seguridad sube de 2,0 a 4,0 (auditoría de accesos, exportación FHIR/PDF, backups cifrados con prueba de restauración); Paciente baja de 3,5 a 2,0 (sin reserva online ni portal); Turnos baja de 3,5 a 3,0 (no se encontró el auto-relleno de huecos y los recordatorios vienen apagados).
- **Bilog (3,63 → 3,13):** Integr. baja de 3,5 a 2,5 (tipo de WhatsApp no evidenciado; declara que no tiene API pública); Turnos, Clínica, Admin. y Seguridad bajan 0,5 cada uno (reglas de agenda, periodontograma, Mercado Pago y seguridad no evidenciados; liquidación de OS solo AC). Paciente se mantiene en 3,0, porque la reserva para pacientes nuevos ahora figura como AC.
- **Dentalink (3,63 → 2,53):** se aplica el tope AC a Turnos, Clínica y Paciente (todo es marketing); no se encontraron los "+50 reportes"; Seguridad baja a 2,0 (políticas sin abrir, roles no evidenciados); Precio baja a 1,5 (solo cotización y módulos clave como extras).
- **DrApp (3,43 → 2,65):** tope AC en Integr., Paciente y Admin. (ARCA, Mercado Pago, API y Crontu son AC); Seguridad baja a 2,0 (no evidenciada); Precio sube a 3,5 (ARS 34.700 publicado, prueba de 15 días).
- **DentalTec (3,40 → 2,45):** casi todo AC; reserva online no evidenciada (Paciente 1,5); licencia sin precio (Precio 1,5); contadores del sitio con placeholders ("0+").
- **OdontoClinIA (3,30 → 2,68):** Admin. baja a 2,0 (ARCA solo "prevista"); Integr. baja a 3,0 (solo el recetario ReNaPDiS está comprobado); el odontograma ahora figura como FDI, pero sigue siendo AC.
- **Doctocliq (3,28 → 2,55):** no aparecen la reserva online ni el odontograma FDI/ADA que "genera" el presupuesto; la facturación es un add-on fuera de Argentina; Precio baja a 4,0 (USD).
- **AgendaPro (3,03 → 2,68):** WhatsApp como complemento pago; señas solo en la landing y en títulos de ayuda; Precio sube a 4,0 (ARS con IVA publicado).
- **Dentidesk (2,73 → 2,60):** Integr. sube a 1,5 (ya tiene WhatsApp manual); Turnos baja a 2,5 (el automático sigue pendiente).
- **Doctoralia Pro (2,63 → 1,80):** sin plan gratis en Argentina; "Reserva con Google" corregido a un vínculo con Google My Business; seguridad no evidenciada; WhatsApp contradictorio.
- **Turnito (2,33 → 2,23):** Paciente sube a 4,5 (reserva sin cuenta y seña que bloquea el horario, ambas Comprobadas); Seguridad baja a 1,0 y Precio a 4,0 (monedas inconsistentes entre páginas).
- **Odonthia (2,28 → 2,50):** Seguridad sube a 4,0 (página /seguridad comprobada); Clínica sube a 3,5 (firma electrónica con hash); Paciente baja a 1,5 (sin reserva online).
- **OdontoGRAMA (1,90 → 1,68):** Integr. y Paciente bajan a 0,5 (nada evidenciado).
- **Nuevos sin puntaje R2:** Dentidad, Órbita, DentApp y OdontoApp (solo los nombraba ChatGPT y figuraban "sin verificar") y Dentally, que estaba en R1 como referencia con 3,83 y baja a 3,35 por no tener integraciones locales ni WhatsApp.

---

## C. Análisis competitivo

### C.1 Estándar de mercado (su ausencia descalifica)

- **Agenda multiprofesional en la nube:** los 18 declaran agenda, y 12 la tienen Comprobada en planes o documentación.
- **Odontograma e historia clínica digital:** los 14 sistemas odontológicos lo tienen (DrApp también, por dictado de voz). AgendaPro y Doctoralia solo ofrecen una ficha genérica, y Turnito, nada.
- **Recordatorios automáticos por WhatsApp,** casi siempre **como cupo o adicional pago:** packs en USD (DentalTec), complemento de ARS 7.900 por 50 mensajes (AgendaPro), cupos de 30 a 250 (Turnito), 50 a 150 (Doctocliq), solo en planes superiores (DentApp, OdontoApp, Odonthia) o con costo extra (DrApp, Dentalink). El WhatsApp "incluido y sin tope" no es la norma.
- **Prueba gratuita o freemium:** 10 de 18 lo publican (plan o cuenta gratis: Bilog, Odonthia, OdontoApp, Doctocliq, Turnito y OdontoGRAMA; prueba de 14 a 30 días: DrApp, Dentidad, DentApp y Dentidesk). Entre los verticales argentinos, DentalCore y Órbita son la excepción.
- **Nuevo piso para los verticales argentinos: factura electrónica.** DentalCore (C), Dentidad (C) y Bilog (C, changelog) emiten; DrApp y DentalTec lo afirman (AC). Esto **respalda la decisión DD-01** (ARCA en el MVP): sin factura electrónica, un producto argentino queda por debajo del piso.
- **Precio publicado en ARS:** 8 de 18 publican en pesos (Dentidad, DentApp, OdontoApp, Odonthia, DrApp, AgendaPro, Doctoralia y Turnito, este último también en USD). La crítica del informe previo ("precios opacos o en USD") hoy aplica solo a una parte: DentalCore, Órbita, Doctocliq y los packs de DentalTec están en USD, y Dentalink, Dentidesk, OdontoClinIA y DentalTec no publican precio.

### C.2 Diferenciadores reales (pocos lo tienen y está evidenciado)

| Diferenciador | Quién lo evidencia | Nivel de evidencia |
|---|---|---|
| WhatsApp por API oficial de Meta | DentalCore (C); Órbita (AC, Tech Provider). Dentalink y Doctocliq lo sugieren ("WhatsApp Business", "Meta Business Partner", AC) | Medio |
| Factura ARCA automática en cada cobro | DentalCore (C), Dentidad (C) | Medio-alto |
| Reserva sin registro + seña que bloquea el horario | Turnito (C); Dentidad (reserva + seña MP, C); AgendaPro (AC) | Alto en Turnito |
| Agenda por sillón con anti-solapamiento | Solo Órbita (AC con capturas: "el turno no se guarda") | Bajo |
| Validación en línea con obras sociales | DentalTec (AC, más de 15 OS); OdontoClinIA (cobertura vía PUCO, AC) | Bajo-medio |
| Recetario registrado en ReNaPDiS | OdontoClinIA N.º 248 (C, solo prescripción); DentApp vía RCTA (C); DrApp con Farmalink e Innovamed (AC); DentalCore "pendiente" | Medio |
| Seguridad y trazabilidad publicadas | Odonthia /seguridad (C), DentalCore FAQ (C), Dentally /security (C); Órbita con registro de accesos imborrable (AC) | Medio |
| API pública documentada | Solo Dentally (C, developer.dentally.co). DrApp y DentApp Empresarial (AC). Bilog declara que **no** tiene | Bajo en AR |
| Soporte a la decisión clínica (CDSS) | DentalCore (17 motores con fuente, C) | Único |

### C.3 Vacíos del mercado argentino

1. **Reglas de agenda odontológica.** 17 de 18 sistemas no evidencian anti-solapamiento ni tratan el sillón como recurso de agenda (OdontoApp y Odonthia solo nombran "sillones" en su marketing). Duración por prestación y sobreturno marcado: solo Órbita lo declara (AC). Este sigue siendo **el vacío más claro**, aunque ya no es absoluto.
2. **Tipo y costo de WhatsApp sin declarar.** De los 16 sistemas que ofrecen WhatsApp, 12 no dicen si usan la API oficial o una sesión por QR, y casi nadie publica el costo por mensaje en pesos.
3. **Nadie integra todo.** No hay evidencia de un producto que combine agenda con reglas por sillón, reserva sin registro con seña, WhatsApp bidireccional, ARCA y una historia clínica auditada. Los tres más cercanos tienen un hueco cada uno: DentalCore (sin reserva ni portal), Dentidad (sin reglas de agenda y con tipo de WhatsApp sin declarar) y Órbita (sin ARCA ni Mercado Pago evidenciados).
4. **Lista de espera que ofrece el hueco automáticamente.** Solo Doctoralia VIP (C) y Órbita (AC). El "auto-relleno" que el informe previo atribuía a DentalCore **no se encontró**.
5. **Cumplimiento.** Nadie publica ISO 27001 (DentalCore aclara que no la tiene). La Ley 26.529 solo la citan Odonthia (/seguridad) y DentApp (/privacy). La ubicación de los datos solo la declara Odonthia (AWS São Paulo).
6. **Obras sociales para el consultorio independiente.** La validación en línea sigue atada a los círculos (DentalTec). El resto ofrece, como mucho, un tarifario o copago (Odonthia) o liquidación por período (DentalCore, Bilog, Órbita, AC).
7. **Receta odontológica homologada.** Los verticales odontológicos la tienen "pendiente" o "próximamente" (DentalCore, Órbita). Las excepciones son OdontoClinIA y DentApp.

### C.4 Oportunidades de innovación

- **Agenda con reglas explícitas y públicas.** Sillón + profesional + duración por prestación + bloqueos + sobreturno autorizado por rol, con anti-solapamiento garantizado en la base de datos y propuesta de horarios alternativos. Órbita muestra que el mercado lo valora; nadie lo documenta técnicamente. Coincide con el change `crear-turno-sin-solapamientos` (reglas duras 6 y 8 del proyecto).
- **WhatsApp bidireccional con costo transparente en pesos.** Hoy domina el pack en USD o el cupo. Mostrar en la caja cuánto costó cada mensaje es distintivo, aunque la API oficial ya no lo sea.
- **Seña según riesgo + lista de espera automática.** Combina la seña que bloquea el horario (Turnito) con el riesgo de ausencia que declara DrApp. Nadie lo integra en odontología.
- **Presupuesto → plan → turnos, con recall desde el odontograma.** Ningún sistema evidencia que un presupuesto aceptado genere la secuencia de turnos.
- **Cumplimiento como argumento comercial.** Una página pública de seguridad, historia clínica append-only con auditoría, exportación completa sin costo y ubicación de datos declarada. Odonthia y DentalCore muestran que se puede publicar, y nadie lo hace completo.
- **Obras sociales en dos niveles.** Primero datos y copago (bajo costo); después validación vía alianzas (Frontini o círculos).
- **Precio en ARS "todo incluido".** Como el precio en ARS ya es común, el diferencial pasa a ser no cobrar packs de mensajería ni módulos por separado.

---

## D. Recomendación final

### D.1 Cinco competidores para demo

Se ajusta la lista del informe previo (Dentalink, DentalCore, Bilog, DentalTec, DrApp). Entran **Órbita** y **Dentidad**, porque ponen a prueba las dos hipótesis centrales del MVP (anti-solapamiento e integración local completa). **DentalTec** y **DrApp** pasan a verificación rápida: la validación en línea de OS y la API pública son de etapa posterior.

| # | Competidor | Por qué | Qué probar en la demo |
|---|---|---|---|
| 1 | **Órbita** | Es el único que declara anti-solapamiento por sillón y WhatsApp oficial. Ataca directamente nuestro diferencial | Intentar dos turnos en el mismo sillón y horario, también en paralelo; ver si se rechaza en el servidor y cómo se ofrecen alternativas. Sobreturno por rol. Si Órbita Chat confirma, cancela y reprograma actualizando la agenda. Si emite factura ARCA. Estado real de la preventa |
| 2 | **DentalCore** | Es el que tiene más evidencia comprobada (WhatsApp oficial, ARCA en cada cobro, auditoría) | Plantilla de WhatsApp aprobada y respuesta del paciente sobre la agenda. Emitir una factura con CAE real. Cómo se resuelve la reserva sin portal. Exportación FHIR/PDF completa. Continuidad de un proveedor unipersonal. Referencias de clientes |
| 3 | **Bilog** | Es el incumbente local (más de 20 años, freemium real, liquidación de OS) | Crear un sobreturno y un solapamiento. Si existen sillones como recurso. Tipo de WhatsApp y su costo. Reserva de un paciente nuevo sin DNI ni email. Factura electrónica (¿ARCA?). Liquidación de OS de punta a punta. Precio real de Lite y Premium |
| 4 | **Dentalink** | Es el estándar clínico y de automatización de la región, pero sin evidencia pública de adaptación argentina | Cuenta argentina con ARCA, Mercado Pago y OS. Tipo de integración del Contact Center IA por WhatsApp. Gestión de sillones y multicentro. Precio en pesos, con extras incluidos |
| 5 | **Dentidad** | Ofrece reserva + seña MP + Factura C ARCA + portal sin contraseña a un precio bajo en ARS | Reserva de un paciente nuevo con seña que bloquea el horario. Qué plan incluye ARCA. Tipo de WhatsApp. Anti-solapamiento. Precio real (25.000 frente a 50.000). Adopción y soporte |

**Verificación rápida (sin demo completa):** DrApp (diferencia entre WhatsApp "semiautomático" y automático, odontograma real, API), DentalTec (validación de OS fuera de un círculo y su costo), y Reservo y DentalSoft (pendientes del informe previo).

### D.2 Tres productos de referencia de UX

| Área | Referencia | Qué mirar |
|---|---|---|
| Reserva sin fricción y seña | **Turnito** | Reserva por enlace sin cuenta ni app; el horario se bloquea recién cuando entra el pago (C) |
| Portal del paciente y permisos | **Dentally** (UK) | Portal con reserva 24/7 por enlace, formularios y OTP; niveles de permiso por usuario; API documentada (C) |
| Firma, trazabilidad y seguridad | **Odonthia** | Firma electrónica con fecha, IP, dispositivo y hash, con documento bloqueado; evolución que conserva la versión anterior; página /seguridad pública (C/AC) |

Mención aparte: la agenda por sillón de Órbita (capturas en /erp/funcionalidades) sirve como referencia visual del rechazo por choque y de la oferta de alternativas.

### D.3 MVP

Se mantiene la decisión del informe previo (§09), sobre la que se construyeron la KB (`knowledge-base/01_vision_y_objetivos.md`) y `CHANGES.md`. La evidencia nueva cambia algunas justificaciones (anotadas entre paréntesis), pero no la ubicación de ninguna funcionalidad.

**Imprescindible (sin esto no compite)**

1. Agenda multiprofesional y multisillón, vista día/semana.
2. Reglas de agenda: duración por prestación, bloqueos, sobreturno por rol y **anti-solapamiento duro** (sigue siendo el vacío más claro; Órbita solo lo declara).
3. Reserva online por enlace, sin registro y abierta a pacientes nuevos (Bilog ahora declara reserva para pacientes nuevos: deja de ser el contraejemplo, pero hay que confirmarlo en demo).
4. WhatsApp bidireccional: recordatorio, confirmar, cancelar y reprogramar, actualizando la agenda (ahora es paridad competitiva, no diferenciador; ver D.4).
5. Ficha con anamnesis + odontograma FDI (permanentes y temporales).
6. Evolución con autor y fecha + auditoría de la historia clínica (Ley 26.529).
7. Presupuesto y plan de tratamiento.
8. Caja con seña y saldo por Mercado Pago.
9. Factura electrónica ARCA desde el cobro (reforzado: ya es el piso de los verticales argentinos).
10. Datos de obra social, plan y afiliado.
11. Roles, permisos, respaldo y exportación completa (CSV/PDF).
12. Política de privacidad y página de cumplimiento (leyes 26.529, 25.326 y 25.506).

**Diferenciador de lanzamiento**

1. Lista de espera con relleno automático de huecos (sigue siendo candidata a imprescindible: Doctoralia VIP y Órbita ya lo ofrecen).
2. Seña condicionada al riesgo de ausencia.
3. Presupuesto → turnos, con seguimiento de lo no agendado y recuperación de ausentes.
4. Recall clínico desde el plan de tratamiento o el odontograma.
5. Consentimientos con firma electrónica y constancia (referencia: Odonthia).
6. Precio público en ARS sin packs, con costo de mensajería transparente (decisión comercial, no de desarrollo).

**Etapas posteriores**

- Periodontograma. **Primero en la cola:** 6 sistemas ya lo evidencian (DentalCore, OdontoApp, Doctocliq, Dentally en C; Dentalink y Órbita en AC), así que se está volviendo estándar.
- Receta electrónica ReNaPDiS. Cubrirla temprano vía partner (DentApp con RCTA y OdontoClinIA demuestran que es alcanzable).
- Obras sociales: cobertura, copago, lotes y RNO; después, validación en línea vía alianzas.
- Liquidación a profesionales; inventario, laboratorio y multisucursal avanzada.
- Imágenes avanzadas, DICOM y radiología; IA clínica (dictado, CDSS, lectura de radiografías).
- Portal completo del paciente, telemedicina, marketplace, API pública y marketing.

### D.4 Lo que la evidencia nueva debilita (y su impacto)

| Afirmación del informe previo | Evidencia 2026-10-13 | Impacto en el producto |
|---|---|---|
| "Ningún vertical odontológico argentino declara usar la API oficial de WhatsApp" | DentalCore lo declara en /pricing ("sin QR", C); Órbita se presenta como Tech Provider de Meta (AC) | El WhatsApp oficial deja de ser un diferenciador y pasa a ser **paridad**. La propuesta de valor se apoya en reglas de agenda + integración completa + cumplimiento |
| "Las reglas de agenda no las documenta nadie" | Órbita declara anti-solapamiento por sillón en la base de datos (AC con capturas) | Sigue siendo un vacío de **documentación técnica**, no de oferta. Hay que publicar nuestras reglas y demostrarlas (409 + alternativas) |
| "Bilog solo deja reservar a pacientes registrados" | El sitio dice "incluso si es su primera consulta" (AC) | Deja de servir como contraejemplo de RN-AG-05; la regla se mantiene |
| "Precios opacos o en USD" | 8 de 18 publican en ARS | El diferencial de precio pasa a ser "todo incluido", no "en pesos" |
| "Auto-relleno de huecos de DentalCore" | No encontrado | La lista de espera automática sigue siendo poco común: refuerza el DIF 1 |

**Decisión posterior al discovery: WhatsApp por QR con número dedicado (equipo, 2026-10-08).** Después del corte del informe previo, el equipo decidió abandonar la API oficial (DD-02 / RN-WA-01) por considerarla poco confiable, e implementar WhatsApp mediante una sesión por QR con un número dedicado (regla dura 17 de `CLAUDE.md`). Esta decisión **va en contra de la dirección que muestra la evidencia**: los dos competidores locales mejor posicionados en WhatsApp (DentalCore y Órbita) usan la API oficial, y Órbita la usa como argumento de venta contra los bots "sobre librerías no oficiales". Riesgos:

- **Bloqueo del número** por Meta y **incumplimiento de los términos de servicio**: se pierden de golpe los recordatorios y las confirmaciones, que son el núcleo del flujo contra el ausentismo.
- **Sesión inestable:** desconexiones, re-escaneo del QR y dependencia de un teléfono físico.
- **Sin plantillas aprobadas** ni costo trazable por mensaje (RN-WA-02/03).
- **Argumento comercial más débil** frente a competidores que declaran la vía oficial.

Mitigación mínima recomendada: (a) aislar la mensajería detrás de una interfaz propia (un "puerto"), para poder migrar a la API oficial sin tocar el dominio; (b) documentar la sesión, la reconexión y el backup, como exige la regla 17; (c) número dedicado y volúmenes bajos; (d) **re-evaluar la decisión antes del change de WhatsApp** (C-15/C-17), con esta evidencia a la vista. Nota de consistencia: la KB (DD-02, RN-WA-01, RN-TU-02) todavía dice "solo API oficial" y tiene que actualizarse para reflejar la decisión vigente o su reversión.

---

## Verificación de fuentes

Fuentes elegidas entre las URLs que la investigación marcó para re-verificación (* o RV). Se priorizaron aquellas donde el informe generado por IA **estaba equivocado**. Hay al menos una por tipo: sitio oficial, página de precios, centro de ayuda, tienda de apps, changelog y documentación > **Nota.** La IA abrió primero estas URLs mediante una herramienta que resume las páginas (verificación asistida). Después, **Matheo Bazán abrió personalmente cada URL en el navegador el 2026-10-13**, contrastó la columna "Qué se encontró" y lo dejó registrado en la última columna. humanas.

| # | URL | Tipo | Qué afirmaba el informe previo | Qué se encontró en la URL (2026-10-13) | Resultado | Corrección aplicada | Comprobado personalmente por / fecha |
|---|---|---|---|---|---|---|---|
| 1 | https://hiorbita.com/ (y /erp/funcionalidades) | Sitio oficial | Órbita "reconoce que todavía no emite comprobante electrónico" | No hay ninguna mención a comprobante electrónico, ARCA ni facturación en las páginas abiertas; solo admite pendientes la receta electrónica y el gráfico de periodontograma. Declara WhatsApp por API oficial de Meta | **No respaldado** | ARCA queda como "No evidenciado"; WhatsApp oficial (AC) | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 2 | https://www.clinia.com.ar/odontologia | Sitio oficial | El odontograma de OdontoClinIA "numera 1–32, no FDI" | "Numeración FDI de 52 piezas" (caras, caries, corona, endodoncia, extracción) | **Corregido** | Odontograma FDI de 52 piezas (AC) | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 3 | https://www.dentalcore.app/pricing | Página de precios | Pro USD 69 · Premium 139 · Enterprise desde 399; "WhatsApp no oficial por QR" | Plan único de USD 50/mes con 2 usuarios + USD 10 por usuario; sin plan gratis ni prueba; garantía de 14 días; WhatsApp "API oficial de Meta… sin QR" | **Corregido** | Precio y tipo de WhatsApp actualizados; puntaje Integr./WA de 2,5 a 4,0 | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 4 | https://dentally.com/pricing | Página de precios | "Desde £50 por consultorio" (dato de tercero) | Starter £125/mes sin IVA (1 sillón); Essentials £220; Pro £320; escala de 1 a 9 sillones | **Corregido** | Desde £125/mes; el dato de £50 de terceros está desactualizado | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 5 | https://doctocliq.com/planes | Página de precios | "Gratis (30 citas/mes)"; "odontograma FDI/ADA que genera presupuesto"; "facturación solo en PE, MX, EC y CO" | Límite de "30 pacientes/mes"; odontograma y presupuestos en todos los planes, sin mencionar FDI/ADA ni generación automática; facturación como add-on pago, también para RD | **Corregido** / No respaldado (FDI/ADA) | Límite por pacientes; FDI/ADA "No evidenciado"; facturación como add-on | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 6 | https://turnito.app/planes (y la home) | Página de precios | "WhatsApp no incluido: requiere plan Advanced" | WhatsApp desde el plan Plus (30 mensajes/mes), Advance 100, Pro 250; precios en USD en /planes y en ARS en la home | **Corregido** | WhatsApp desde Plus; se anota la inconsistencia de moneda | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 7 | https://www.drapp.com.ar/precios | Página de precios | ARS 32.800 por profesional/mes + IVA | ARS 34.700 por profesional/mes + IVA; 15 días de prueba; más de 15 profesionales, plan a medida; WhatsApp con costo adicional | **Corregido** (probable actualización posterior al corte) | ARS 34.700 | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 8 | https://www.bilog.com.ar/planes | Página de precios | Freemium para 1 profesional y 50 pacientes; Lite y Premium se cotizan por usuario | Freemium "sin costo": 1 profesional, 1 usuario, hasta 50 pacientes; Lite y Premium "cotización por usuario" | **Confirmado** | Se agrega "1 usuario" | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 9 | https://www.dentalcore.app/faq | Centro de ayuda | "Nadie publica ISO 27001, ubicación de datos ni adecuación explícita a las leyes" | "Pensada para ayudarte a cumplir" la Ley 25.326; declara **no** estar certificada ISO 27001; backups semanales por clínica | **Confirmado** (con matiz) | Nadie certifica ISO 27001, pero DentalCore publica su postura explícitamente | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 10 | https://apps.apple.com/ar/app/bilog-gesti%C3%B3n-odontol%C3%B3gica/id1554140449 | Tienda de apps (con changelog) | WhatsApp de Bilog "individual"; "posible API oficial inferida de plantillas en el changelog" | Changelog de la 7.1.1 a la 7.22.0 (6-oct-2026): facturación electrónica solo en Argentina (7.7.0), anamnesis, IA para radiografías; **no menciona** el tipo de WhatsApp; 3,5/5 con 15 valoraciones | **No respaldado** | Tipo de WhatsApp: "No evidenciado"; se agrega la facturación electrónica (C) | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 11 | https://dentidesk.com/blog | Changelog / blog oficial | WhatsApp "próximamente"; fiscal solo con el SII chileno | WhatsApp integrado **manual** desde el 06-02-2026; el automático sigue como "próximo" (13-08-2026); Alegra (RD) desde el 14-05-2026 | **Corregido** | WhatsApp manual existe; fiscal en Chile y RD | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

| 12 | https://developer.dentally.co/ | Documentación de API | Dentally tiene "API abierta" | API REST oficial con entornos Production, Sandbox, APAC y Canada; paginación y versionado | **Confirmado** | Ninguna (las integraciones a medida son solo del plan Pro) | Comprobado personalmente por Matheo Bazán / 2026-10-13 |

### Hallazgos: afirmaciones incorrectas o no respaldadas del informe generado por IA

Se listan las 31 correcciones encontradas en los tres lotes de re-verificación (una por línea), para la reflexión sobre el uso de IA en el discovery.

**Precios desactualizados o mal atribuidos**

1. DentalCore: "Pro USD 69 / Premium 139 / Enterprise 399" → plan único de USD 50 + USD 10 por usuario; sin plan gratis ni prueba.
2. DrApp: ARS 32.800 → ARS 34.700 por profesional + IVA.
3. OdontoApp: "desde AR$ 33.500" → Básico ARS 36.000, Profesional ARS 48.500.
4. DentApp: "desde AR$ 20.900" → ARS 24.900 con IVA (20.578 es el neto; 20.900 no aparece).
5. Dentally: "desde £50 por consultorio" (tercero) → £125/mes en el sitio oficial.
6. Odonthia: "IA desde US$26" → ese precio es fuera de Argentina; en Argentina, ARS 20.900 y ARS 46.900.
7. Doctoralia Pro: plan "Gratis" → no figura en la página de precios de Argentina; se exige plan pago y permanencia anual.
8. Doctocliq: "gratis hasta 30 citas/mes" → 30 pacientes/mes.

**Funcionalidades atribuidas sin respaldo o mal descriptas**

9. DentalCore: "WhatsApp no oficial por QR" → API oficial de Meta, "sin QR".
10. DentalCore: "más de 20 convenios de OS" → solo OSDE, Swiss Medical y PAMI precargadas.
11. DentalCore: "auto-relleno de huecos" → no encontrado (solo un asistente de voz que "encuentra el hueco").
12. OdontoClinIA: "odontograma 1–32, no FDI" → FDI de 52 piezas.
13. Órbita: "reconoce que no emite comprobante electrónico" → no aparece en ninguna página; queda "No evidenciado".
14. Doctocliq: "odontograma FDI/ADA que genera presupuesto" → ni FDI/ADA ni la generación automática figuran.
15. Doctocliq: "facturación solo PE/MX/EC/CO" → también RD, y es un add-on pago.
16. Dentidesk: "WhatsApp próximamente" → el WhatsApp manual existe desde febrero de 2026; el pendiente es el automático.
17. Dentidesk: "fiscal solo SII chileno" → también Alegra (RD).
18. Turnito: "WhatsApp solo en el plan Advanced" → desde el plan Plus (30 mensajes).
19. Doctoralia: "reserva desde Google" → solo un vínculo con Google My Business; la función "Reserve with Google" no está evidenciada.
20. Bilog: "WhatsApp incluido individual" → no encontrado; el tipo queda "No evidenciado".
21. Bilog: "posible API oficial de WhatsApp" (inferida) → no respaldada; además, Bilog declara que no tiene API pública.
22. Bilog: "solo reservan pacientes registrados con DNI y email" → el sitio dice "incluso si es su primera consulta" (AC).
23. Dentalink: "+50 reportes" → no encontrado.
24. Dentidad: "confirmación y ausencia por WhatsApp" → solo hay evidencia de recordatorios.
25. Dentidad: "ARCA solo en multisede" → la Factura C ARCA figura como función general; el alcance por plan no está claro.
26. DrApp: "odontograma superficial" → solo se evidencia un odontograma por dictado de voz, sin detalle.

**Conclusiones de mercado que cambian**

27. "Ningún vertical odontológico argentino declara usar la API oficial de WhatsApp" → falso: DentalCore (C) y Órbita (AC) la declaran.
28. "Las reglas de agenda no las documenta nadie" → Órbita declara anti-solapamiento por sillón (AC); el vacío pasa a ser de documentación técnica.
29. "Precios opacos o en USD" → 8 de 18 publican en ARS.

**Identificación y URLs**

30. Dominios incorrectos o caídos: dentalcore.com.ar y dentalink.com no resuelven (los oficiales son dentalcore.app y softwaredentalink.com); el sitio comercial de DentApp es dentapp.ar, no dentapp.com.ar; pro.doctoralia.com.ar no resuelve.
31. Datos de proveedor no verificables: la forma "S.R.L." de Bilog y "Grupo Cormos" para DrApp solo aparecen en fuentes de terceros.

**Inconsistencias internas de los propios proveedores** (no son errores de la IA, pero conviene saberlas): Dentidad lista dos tablas de precios distintas; Órbita dice "USD 25" y "desde USD 33"; Turnito publica en USD y en ARS; Doctocliq tiene cupos de WhatsApp distintos en la tabla y en las tarjetas; DentalTec y Turnito muestran contadores sin completar ("0+", "reduce el 0%").

**No re-verificado en esta ronda:** el marco regulatorio (leyes 26.529, 25.326, 25.506, 27.553, Res. 1959/2024 y 2214/2025), la tarifa de Meta en ARS y los datos de inflación del INDEC citados en el informe previo. Tampoco las reseñas de Capterra y G2 (Capterra devolvió HTTP 403), los videos oficiales ni las tiendas de Google Play. Siguen como dato del informe previo, a validar con asesoría (PA-04).

---

## Referencias

Todas las URLs se consultaron el **2026-10-13**, salvo [0].

0. *Discovery consolidado: software de turnos y gestión odontológica en Argentina* (Perplexity, ChatGPT, Gemini, Claude R1/R2). Corte 2026-09-23. `discovery/Discovery Consolidado Turnos Odontologia.pdf`. Documento interno.

**Bilog**

1. https://www.bilog.com.ar — sitio oficial
2. https://www.bilog.com.ar/planes — página de precios
3. https://bilog.com.ar/llms.txt — sitio oficial (resumen publicado para IA)
4. https://bilog.com.ar/soluciones/consultorios — sitio oficial
5. https://bilog.com.ar/soluciones/clinicas — sitio oficial
6. https://bilog.com.ar/funcionalidades — sitio oficial
7. https://apps.apple.com/ar/app/bilog-gesti%C3%B3n-odontol%C3%B3gica/id1554140449 — tienda de apps (changelog)

**Dentalink**

8. https://www.softwaredentalink.com/?c=cl — sitio oficial
9. https://www.softwaredentalink.com/planes — página de precios
10. https://www.softwaredentalink.com/inteligencia-artificial/contact-center — sitio oficial

**DentalCore**

11. https://www.dentalcore.app — sitio oficial
12. https://www.dentalcore.app/pricing — página de precios
13. https://www.dentalcore.app/features — sitio oficial
14. https://www.dentalcore.app/faq — centro de ayuda

**DrApp**

15. https://www.drapp.com.ar/ — sitio oficial
16. https://www.drapp.com.ar/precios — página de precios
17. https://www.drapp.com.ar/ia — sitio oficial

**DentalTec**

18. https://web.dentaltec.com.ar/ — sitio oficial
19. https://web.dentaltec.com.ar/funcionalidades — sitio oficial
20. https://web.dentaltec.com.ar/preguntas-frecuentes — centro de ayuda

**OdontoClinIA**

21. https://www.clinia.com.ar/odontologia — sitio oficial
22. https://www.clinia.com.ar/sobre-clinia — sitio oficial

**Doctocliq**

23. https://doctocliq.com — sitio oficial
24. https://doctocliq.com/planes — página de precios
25. https://apps.apple.com/us/app/doctocliq/id1445399223?l=es — tienda de apps

**AgendaPro**

26. https://agendapro.com/ar — sitio oficial
27. https://agendapro.com/ar/planes — página de precios
28. https://agendapro.com/ar/dental/software-odontologico — sitio oficial (landing)
29. https://agendapro.com/ar/centro-medico/software-para-centro-medico — sitio oficial (landing)
30. http://ayuda.agendapro.com/es/collections/3452302-pago-en-linea-y-pos — centro de ayuda

**Dentidesk**

31. https://dentidesk.com — sitio oficial
32. https://dentidesk.com/blog — changelog / blog oficial

**Doctoralia Pro**

33. https://pro.doctoralia.com/ar/precio — página de precios
34. https://pro.doctoralia.com/ar/preguntas-frecuentes/condiciones-del-plan-doctoralia — centro de ayuda
35. https://pro.doctoralia.com/ar/agenda-doctoralia-para-especialistas — sitio oficial
36. https://pro.doctoralia.com/ar — sitio oficial

**Turnito**

37. https://turnito.app — sitio oficial y precios
38. https://turnito.app/planes — página de precios
39. https://turnito.app/app-turnos-medicos/ — sitio oficial

**Odonthia**

40. https://odonthia.com — sitio oficial
41. https://odonthia.com/planes — página de precios
42. https://odonthia.com/seguridad — sitio oficial (seguridad)
43. https://odonthia.com/blog/mejores-software-odontologicos-argentina-2026 — blog oficial (comparativa del propio proveedor, con sesgo)

**OdontoGRAMA**

44. https://www.odontograma.com.ar — sitio oficial
45. https://www.solsoftware.com.ar — sitio oficial del proveedor

**OdontoApp**

46. https://odontoapp.com.ar/ — sitio oficial (incluye FAQ y datos estructurados)
47. https://odontoapp.com.ar/assets/index-DgrEVzzX.js — página de precios (datos de la tabla de planes dentro del bundle del sitio)

**Dentidad**

48. https://dentidad.com/ — sitio oficial y precios

**DentApp**

49. https://www.dentapp.ar (incluye /privacy y /terms) — sitio oficial y precios
50. https://dentapp.com.ar/login — login de otro producto homónimo (colisión; descartado)

**Órbita**

51. https://hiorbita.com/ — sitio oficial
52. https://hiorbita.com/precios — página de precios
53. https://hiorbita.com/comparativa — comparativa del propio proveedor
54. https://hiorbita.com/erp/funcionalidades — sitio oficial

**Dentally**

55. https://dentally.com/pricing (redirige a https://www.dentally.com/en-gb/pricing) — página de precios
56. https://www.dentally.com/en-gb/ — sitio oficial
57. https://www.dentally.com/en-gb/product/dentally-portal — sitio oficial
58. https://www.dentally.com/en-gb/dental-software-features/practice-admin — sitio oficial
59. https://www.dentally.com/en-gb/security — sitio oficial (seguridad)
60. https://www.dentally.com/en-gb/cloud-based-dental-software — sitio oficial
61. https://developer.dentally.co/ — documentación de API

**Consultadas y descartadas (colisiones o sin contenido):** https://orbitadental.com/ (producto mexicano) · https://orbita.com.ar (inmobiliaria) · https://sovil.com.ar (sin mención de OdontoApp) · https://dentaltec.com.ar/ (error "No pudimos cargar DentalTec") · https://www.capterra.com/p/10047210/Dentalcore/ (HTTP 403, no usada como evidencia).
