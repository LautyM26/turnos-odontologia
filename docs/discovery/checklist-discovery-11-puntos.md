# Checklist de Discovery (11 puntos) — Turnos Odontología

> Este archivo reconstruye en un formato versionable el checklist de 11 puntos que debía cubrir la investigación de Discovery. Sintetiza dos fuentes: el informe `docs/discovery/informe-discovery.md` (re-verificación del 2026-10-13) y la base de conocimiento (`knowledge-base/`). Cada punto cita los archivos o IDs de la KB que lo desarrollan. Fecha: 2026-10-13.

## 1. Problema

Los consultorios odontológicos argentinos reparten su trabajo entre varias herramientas que no se integran. Ninguna evidencia, en un solo producto, la agenda con reglas por sillón, la reserva sin fricción con seña, WhatsApp bidireccional, la factura ARCA y una historia clínica auditada (informe §C.3). El dolor principal es el **ausentismo** (agenda que no se llena sola). Le siguen la **doble carga administrativa** (cobro, factura, obra social) y el **cumplimiento** de las leyes 26.529 y 25.326 sin soporte del software. Ver `01_vision_y_objetivos.md` (Propósito).

## 2. Usuarios

Cuatro roles humanos y los sistemas externos (`03_actores_y_roles.md`, SU-02 validado):

- **Paciente:** reserva por enlace sin cuenta, confirma por WhatsApp y paga la seña.
- **Recepcionista o administrativo:** agenda, caja, lista de espera. Sin acceso clínico, salvo datos de contacto y obra social.
- **Odontólogo** (dueño o tercerizado): ficha, odontograma y evolución con autoría. El tercerizado ve solo su agenda.
- **Administrador o dueño:** configuración, sillones y reglas, precios, reportes, respaldo.

Segmento prioritario: el consultorio independiente y la clínica chica. El piloto es el consultorio propio (SU-06).

## 3. Casos de uso

Las 17 historias de usuario de `06_funcionalidades.md` (US-001 a US-017) y los 9 flujos de `07_flujos_principales.md`. Los centrales son:

- Reservar un turno online con seña (Flujo 1, US-003, US-011).
- Recordar y confirmar por WhatsApp de forma bidireccional (Flujo 2, US-005).
- Reprogramar (Flujo 3, US-006).
- Cancelación que dispara la lista de espera (Flujo 4, US-004).
- Atención clínica con ficha, odontograma y evolución (Flujo 5, US-007 a US-009).
- Presupuesto → plan → turnos (Flujo 6, US-010, US-013).
- Caja → factura ARCA (Flujo 7, US-012).
- Consentimiento firmado (Flujo 8, US-016).

## 4. Competidores

18 sistemas re-verificados con URL (informe §A). Los relevantes por segmento:

- **Verticales argentinos:** Bilog (incumbente), DentalCore, Órbita, Dentidad, DentalTec, OdontoClinIA, Odonthia, DentApp, OdontoApp, OdontoGRAMA.
- **Generalistas en Argentina:** DrApp, Turnito, Doctoralia Pro.
- **Regionales:** AgendaPro, Dentalink, Doctocliq, Dentidesk.
- **Referencia internacional:** Dentally.

Matriz §B (top 5): DentalCore 3,60 · Dentidad 3,35 · Dentally (ref.) 3,35 · Bilog 3,13 · Órbita 2,70. Ningún sistema supera 4.

Demos recomendadas: Órbita, DentalCore, Bilog, Dentalink y Dentidad (informe §D.1).

## 5. Funcionalidades necesarias (MVP imprescindible)

Según el informe §D.3 y `01_vision_y_objetivos.md`:

- Agenda multiprofesional y multisillón (US-001).
- Reglas de agenda con anti-solapamiento (US-002; RN-AG-01 a RN-AG-04).
- Reserva sin registro (US-003; RN-AG-05).
- WhatsApp bidireccional (US-005 y US-006; RN-TU-02 y RN-TU-03).
- Ficha con anamnesis y odontograma FDI (US-007 y US-008; RN-CL-03).
- Evolución con autor y auditoría (US-009; RN-CL-01 y RN-CL-02).
- Presupuesto y plan (US-010).
- Caja con seña por Mercado Pago (US-011; RN-CA-01 y RN-CA-03).
- Factura ARCA (US-012; RN-AF-01 y RN-AF-02; DD-01).
- Datos de obra social (US-017; RN-OS-01).
- Roles, respaldo y exportación (US-014; RN-CU-04).
- Privacidad y cumplimiento (US-015; RN-CU-01 y RN-CU-05).

## 6. Funcionalidades opcionales

**Diferenciadores de lanzamiento:**

- Lista de espera con relleno automático (US-004; RN-AG-06).
- Seña según riesgo de ausencia (RN-CA-02).
- Presupuesto → turnos con seguimiento (RN-PR-01 y RN-PR-02).
- Recall desde el plan o el odontograma (US-013; RN-CL-04).
- Consentimientos con firma electrónica (US-016; RN-CU-02).
- Precio en ARS sin packs (RN-PR-03; DD-05).

**Etapas posteriores:** periodontograma (el primero en la cola: 6 competidores ya lo evidencian), receta ReNaPDiS propia, obras sociales con copago, lotes, RNO y validación en línea (RN-OS-02 y RN-OS-03), liquidaciones, DICOM, IA clínica, portal completo, API pública.

## 7. Reglas de negocio

Hay 30 reglas en `05_reglas_de_negocio.md`. Las críticas son:

- **RN-AG-01:** sin solapamiento por sillón ni por profesional (prevención dura). En el proyecto se implementa con *exclusion constraints* GiST y responde 409 (regla dura 8).
- **RN-AG-02:** el fin del turno es el inicio más la duración de la prestación, y se calcula solo en el servidor (regla dura 6).
- **RN-AG-04:** el sobreturno lo crea solo un rol autorizado, con motivo.
- **RN-CL-02:** la historia clínica es append-only (regla dura 15, Ley 26.529).
- **RN-AF-01:** la factura se emite solo desde el cobro.
- **RN-PR-03:** los montos se guardan en NUMERIC y en ARS (regla dura 7).
- **RN-GL-02:** las métricas autodeclaradas de los competidores nunca valen como evidencia.

## 8. Integraciones

Ver `02_descripcion_general.md` (Integraciones externas) y DD-02, DD-06:

- **WhatsApp:** decisión vigente del equipo (2026-10-08): **sesión por QR con número dedicado**, en lugar de la API oficial (DD-02 y RN-WA-01 todavía sin actualizar; ver riesgo R1).
- **Mercado Pago:** seña y saldo (PA-06).
- **ARCA:** factura B/C con CAE y QR (PA-07).
- **Receta electrónica:** vía un partner registrado en ReNaPDiS (RN-CU-03, PA-08).
- **Obras sociales:** primero datos y, más adelante, alianzas con círculos o con Frontini (DD-03).

## 9. Restricciones

- **Stack:** Python + FastAPI + PostgreSQL 16 + React/Vite (DD-08).
- **Despliegue:** SaaS multi-tenant, un tenant por clínica con datos aislados (DD-09; regla dura 10).
- **Legales:** leyes 26.529 (historia clínica), 25.326 (datos sensibles), 25.506 (firma) y 27.553 + Res. 1959/2024 y 2214/2025 (receta).
- **Datos de prueba:** prohibido usar datos reales de pacientes en el repositorio o los seeds (regla dura 14).
- **Secretos:** ningún secreto en el navegador (regla dura 12).
- **Moneda y tiempo:** montos en ARS NUMERIC; tiempos en TIMESTAMPTZ.

## 10. Riesgos

| ID | Riesgo | Mitigación |
|---|---|---|
| R1 | **WhatsApp por QR:** bloqueo del número y violación de los términos de Meta; sesión inestable; sin plantillas aprobadas ni costo trazable. Los competidores mejor posicionados (DentalCore, Órbita) usan la API oficial | Aislar la mensajería detrás de una interfaz propia, documentar la sesión, la reconexión y el backup (regla 17), y re-evaluar antes de C-15/C-17 (informe §D.4) |
| R2 | **Diferencial erosionado:** el WhatsApp oficial y el precio en ARS ya son paridad; Órbita declara anti-solapamiento | Apoyarse en reglas de agenda documentadas y demostrables + integración completa + cumplimiento |
| R3 | **Dependencia de ARCA, Mercado Pago y el partner de recetas:** caídas o cambios de API | Cola visible para la factura ante una caída de ARCA (PA-07); proveedores intercambiables |
| R4 | **Legal:** historia clínica y receta sin validación profesional | Asesoría legal antes de diseñar HC y receta (PA-04, SU-08) |
| R5 | **Evidencia débil del discovery:** 31 correcciones al informe generado por IA; nada se probó en uso real | Demos de §D.1 y verificación humana de las URLs (tabla "Verificación de fuentes") |
| R6 | **Mercado cambiante:** los precios y planes cambiaron entre julio y octubre de 2026 | Re-verificar antes de fijar el precio propio (RN-GL-03) |

## 11. Preguntas abiertas

De `10_preguntas_abiertas.md`, más lo que surgió en la re-verificación:

- **PA-04** (legal), **PA-05** (WhatsApp: ahora hay que decidir entre QR y API oficial con esta evidencia), **PA-06** (cuenta de Mercado Pago y reembolsos), **PA-07** (ARCA: CUIT, régimen, caída del servicio), **PA-08** (partner de recetas) y **PA-12** (línea base de ausentismo del piloto).
- **PA-10:** actores que solo nombraba ChatGPT. **Resuelta en parte:** Dentidad, Órbita y DentApp se re-verificaron y entraron a la tabla; los que solo nombraba Gemini (DentalSoft, Dentaly, Dentatools, Benty, RivoClin) siguen sin verificar.
- **IN-11** (precios de DentalCore): resuelta con el plan único de USD 50. **IN-12** (WhatsApp de Turnito): corregida, se incluye desde el plan Plus. **IN-13** (WhatsApp de Doctoralia): sigue siendo contradictorio.
- **Nuevas:**
  - ¿Bilog acepta realmente pacientes nuevos sin registro?
  - ¿Qué planes de Dentidad incluyen ARCA?
  - ¿El anti-solapamiento de Órbita es real y concurrente?
  - ¿Cuándo se actualizan DD-02 y RN-WA-01 para reflejar la decisión del QR?
