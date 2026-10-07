# Descripción General

> Fuente: `discovery/Discovery Consolidado Turnos Odontologia.pdf`. El discovery NO define stack (lenguaje/framework/DB). Ver § Stack y `10_preguntas_abiertas.md` (PA-01).

## Stack tecnológico

| Capa | Tecnologías | Versión mínima |
|------|--------------|----------------|
| Frontend | **Por definir** — el discovery no lo especifica (ver PA-01) | — |
| Backend | **Por definir** — el discovery no lo especifica (ver PA-01) | — |
| Base de datos | **Por definir** — requerida por HC/auditoría, agenda y caja (ver PA-01) | — |
| Mensajería | WhatsApp Business API oficial (plantillas aprobadas, cobro por plantilla entregada) | API vigente Meta al 2026 |
| Cobros | Mercado Pago (seña y saldo; seña ligada al presupuesto en etapa posterior) | — |
| Facturación | ARCA factura electrónica B/C con CAE y QR, emitida desde el cobro | — |
| Receta electrónica | Vía partner registrado en ReNaPDiS (Res. 1959/2024); propia es F2 | — |

**Suposición SU-01:** se asume SaaS web multi-tenant en la nube (ver `09_decisiones_y_supuestos.md`). Origen: agenda en la nube, reserva online, multisede y precios por profesional/sillón en todo el mapa de competidores. Si el producto fuera on-premise o mono-tenant, cambiaría toda la arquitectura.

## Arquitectura general

```
Paciente (enlace reserva / WhatsApp) ─┐
                                      ├─→ App web SaaS ─→ API ─→ DB (HC, agenda, caja)
Recepcionista / Odontólogo (panel) ───┘        │             ├─→ WhatsApp Business API oficial
                                               ├─→ Mercado Pago (seña/saldo)
                                               ├─→ ARCA (FE con CAE desde el cobro)
                                               └─→ Partner recetas (ReNaPDiS) [etapa temprana]
Etapa 2: ─→ Obras sociales (cobertura/copago/lotes → validación en línea vía círculos/Frontini)
```

Justificación (desde el discovery): el cuadrante vacío es clínica + integración AR + obras sociales + WhatsApp oficial todo junto. El MVP ataca agenda + WhatsApp oficial + caja/ARCA + HC/odontograma; las obras sociales entran en dos niveles (primero cálculo/RNO/lotes, después validación en línea por alianzas) porque requieren acuerdos por financiador (barrera de entrada).

## Integraciones externas

| Servicio | Propósito | Tipo |
|----------|-----------|------|
| WhatsApp Business API (Meta) | Recordatorio, confirmar/cancelar/reprogramar bidireccional; chatbot transaccional; lista de espera | API oficial + webhooks (plantillas aprobadas). Costo por plantilla entregada; utilidad dentro de ventana gratis. Tarifa ARS vigente desde 1/7/2026 |
| Mercado Pago | Seña como condición de reserva; seña condicionada a riesgo de ausencia; saldo | SDK/API pagos |
| ARCA (ex AFIP) | Factura electrónica B/C con CAE y QR desde el cobro | Web service fiscal |
| ReNaPDiS / partner recetas (Farmalink, Innovamed u otro registrado) | Receta electrónica y órdenes de estudios (Res. 2214/2025) | Integración vía partner registrado (propia es F2) |
| Obras sociales / círculos / Frontini "Odontología Digital" | Etapa 2: cobertura, copago, lotes exportables, RNO; luego validación en línea | Alianzas por financiador / integrador (Frontini como posible socio, no competidor) |
| Google Calendar | Mencionado en DentApp como referencia; no exigido en MVP | Por confirmar (PA) |

Uso no oficial por QR (ej. DentalCore): explícitamente descartado — arriesga bloqueo del número.

## API REST (si aplica)

El MVP no incluye API pública (F2 unánime §09). Referencia: DrApp tiene API pública con webhooks (rara en LatAm); Dentally/Open Dental también. Si se expone API en etapa posterior, los recursos mínimos serían: profesionales, sillones/recursos, turnos, pacientes, historia clínica/evoluciones, odontograma, presupuestos/planes, cobros/señas, facturas, obras sociales/afiliados, consentimientos, mensajes WhatsApp.
