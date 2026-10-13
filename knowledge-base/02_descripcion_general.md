# Descripción General

> Fuente: `discovery/Discovery Consolidado Turnos Odontologia.pdf`. El discovery NO impone tecnología específica (la nube es exigencia de capacidades, no de stack). Stack DECIDIDO en ronda de respuestas usuario 1 (2026-10-07, PA-01): Python + FastAPI + PostgreSQL + React/Vite. Ver `09_decisiones_y_supuestos.md` (DD-08) y `10_preguntas_abiertas.md` (PA-01 resuelta).

## Stack tecnológico — DECIDIDO (ronda usuario 1, PA-01)

| Capa | Tecnologías | Versión mínima |
|------|--------------|----------------|
| Frontend | **React + Vite** (decidido, ronda usuario 1) | — |
| Backend | **Python + FastAPI** (decidido, ronda usuario 1) | — |
| Base de datos | **PostgreSQL** (decidida, ronda usuario 1) | — |
| Mensajería | WhatsApp por QR con número dedicado (DD-10, 2026-10-08), detrás de un adapter/puerto; migrable a API oficial en F2 | — |
| Cobros | Mercado Pago (seña y saldo; seña ligada al presupuesto en etapa posterior) | — |
| Facturación | ARCA factura electrónica B/C con CAE y QR, emitida desde el cobro | — |
| Receta electrónica | Vía partner registrado en ReNaPDiS (Res. 1959/2024); propia es F2 | — |

**Confirmado SU-01 (ronda usuario 1, PA-02):** SaaS web multi-tenant en la nube, un tenant por clínica con datos aislados — estándar validado por referentes regionales (DrApp, Dentalink). Origen: agenda en la nube, reserva online, multisede y precios por profesional/sillón en todo el mapa de competidores. Ver `09_decisiones_y_supuestos.md`.

## Arquitectura general

```
Paciente (enlace reserva / WhatsApp) ─┐
                                      ├─→ App web SaaS ─→ API ─→ DB (HC, agenda, caja)
Recepcionista / Odontólogo (panel) ───┘        │             ├─→ WhatsApp (sesión QR, número dedicado)
                                               ├─→ Mercado Pago (seña/saldo)
                                               ├─→ ARCA (FE con CAE desde el cobro)
                                               └─→ Partner recetas (ReNaPDiS) [etapa temprana]
Etapa 2: ─→ Obras sociales (cobertura/copago/lotes → validación en línea vía círculos/Frontini)
```

Justificación (desde el discovery): el cuadrante vacío es clínica + integración AR + obras sociales + WhatsApp oficial todo junto. El MVP ataca agenda + WhatsApp oficial + caja/ARCA + HC/odontograma; las obras sociales entran en dos niveles (primero cálculo/RNO/lotes, después validación en línea por alianzas) porque requieren acuerdos por financiador (barrera de entrada).

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| WhatsApp (sesión QR, número dedicado) | Recordatorio, confirmar/cancelar/reprogramar bidireccional; chatbot transaccional; lista de espera | Sesión QR no oficial (DD-10) detrás de adapter/puerto; eventos entrantes de la sesión en lugar de webhooks Meta. Sin plantillas aprobadas ni tarifa oficial. Riesgo: bloqueo del número/ToS, caída de sesión; mitigado con monitoreo, reconexión, backup de sesión y fallback email/manual. Migración a API oficial en F2 |
| Mercado Pago | Seña como condición de reserva; seña condicionada a riesgo de ausencia; saldo | SDK/API pagos |
| ARCA (ex AFIP) | Factura electrónica B/C con CAE y QR desde el cobro | Web service fiscal |
| ReNaPDiS / partner recetas (Farmalink, Innovamed u otro registrado) | Receta electrónica y órdenes de estudios (Res. 2214/2025) | Integración vía partner registrado (propia es F2) |
| Obras sociales / círculos / Frontini "Odontología Digital" | Etapa 2: cobertura, copago, lotes exportables, RNO; luego validación en línea | Alianzas por financiador / integrador (Frontini como posible socio, no competidor) |
| Google Calendar | Mencionado en DentApp como referencia; no exigido en MVP | Por confirmar (PA) |

Uso no oficial por QR: **adoptado** por decisión del equipo el 2026-10-08 (DD-10), que reemplaza el descarte original (DD-02). El Discovery re-verificado (2026-10-13) halló que DentalCore y Órbita declaran usar la API oficial, así que esta decisión es un trade-off deliberado contra la evidencia, con riesgo de bloqueo asumido.

## API REST (si aplica)

El MVP no incluye API pública (F2 unánime §09). Referencia: DrApp tiene API pública con webhooks (rara en LatAm); Dentally/Open Dental también. Si se expone API en etapa posterior, los recursos mínimos serían: profesionales, sillones/recursos, turnos, pacientes, historia clínica/evoluciones, odontograma, presupuestos/planes, cobros/señas, facturas, obras sociales/afiliados, consentimientos, mensajes WhatsApp.
