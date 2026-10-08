# Visión y Objetivos

> Fuente única: `discovery/Discovery Consolidado Turnos Odontologia.pdf` (corte 23/09/2026, 46 sistemas, base Claude R2).
> Todo lo afirmado abajo traza a ese documento. Lo inferido se marca como **Suposición**.

## Propósito del sistema

Construir el sistema de turnos y gestión odontológica para Argentina que hoy no existe: un solo producto que combine profundidad clínica (odontograma, historia clínica), circuito administrativo local (ARCA, Mercado Pago, obras sociales) y WhatsApp Business API oficial bidireccional con costo transparente.

Contexto: el discovery cruzó 4 fuentes (Perplexity, ChatGPT, Gemini, Claude R1/R2) y concluye que no hay un líder completo (franja 3,3–3,6/5, nadie supera 4 con evidencia verificada). El mercado tiene dos polos —profundidad clínica sin adaptación argentina vs. circuito administrativo local con automatización rezagada— y un vacío: nadie integra clínica + agenda + integración AR (fiscal y cobro) + obras sociales + WhatsApp oficial en un solo producto.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|-------|--------------------|-----------------------|
| Odontólogo / profesional | Atender con historia clínica y odontograma confiables, sin doble carga administrativa | Evolución con autoría y auditoría; presupuesto que genera plan y turnos; receta electrónica vía partner |
| Recepcionista / administrativo | Llenar la agenda y cobrar sin fricción ni solapamientos | Confirmar/cancelar/reprogramar por WhatsApp oficial; lista de espera con relleno automático; caja con seña y saldo |
| Administrador / dueño de clínica | Rentabilidad y cumplimiento: menos ausentismo, cobro asegurado, papeles en regla | Precio en ARS transparente; reportes (presupuestos no convertidos, inactivos); respaldo y exportación completa |
| Paciente | Reservar, confirmar y pagar su turno sin crear cuentas ni instalar apps | Reserva online por enlace sin registro; seña por Mercado Pago; recordatorios y reprogramación por WhatsApp |
| Consultorio independiente (segmento) | Acceder a circuito de obra social sin depender de un círculo ni de Excel manual | Datos de OS/plan/afiliado desde el MVP; cálculo de cobertura y RNO en etapa 2; validación en línea vía alianzas |

## Alcance v1.0 (MVP — decisión consolidada §09)

IMP = imprescindible, DIF = diferenciador de lanzamiento. Consenso total salvo nota:

- IMP — Agenda multiprofesional y multisillón, vista día/semana.
- IMP — Reglas de agenda explícitas: duración por prestación, bloqueos, sobreturnos por rol, anti-solapamiento duro. (Vacío documentado del mercado.)
- IMP — Reserva online por enlace, sin registro y abierta a pacientes nuevos.
- IMP — WhatsApp Business API oficial bidireccional: recordatorio, confirmar, cancelar y reprogramar. Oficial, no por QR.
- IMP — Ficha con anamnesis + odontograma FDI (permanentes y temporales).
- IMP — Evolución con autor y fecha + auditoría de HC (exigido por Ley 26.529).
- IMP — Presupuesto y plan de tratamiento.
- IMP — Caja con seña y saldo por Mercado Pago.
- IMP — Factura electrónica ARCA desde el cobro (decisión tomada con empate 2–2; ver DD-01).
- IMP — Datos de obra social, plan y afiliado (bajo costo; prepara etapa 2).
- IMP — Roles, permisos, respaldo y exportación completa (CSV/PDF).
- IMP — Política de privacidad y página de cumplimiento (leyes 26.529, 25.326 y 25.506). Bajo costo y argumento de venta.
- DIF — Lista de espera con relleno automático de huecos (candidato a IMP: ataca el ausentismo, dolor nº 1).
- DIF — Seña condicionada al riesgo de ausencia.
- DIF — Presupuesto → turnos, con seguimiento de lo no agendado y recuperación de ausentes.
- DIF — Recall clínico desde el plan de tratamiento.
- DIF — Consentimientos con firma electrónica y constancia.
- DIF — Precio público en ARS, sin packs; costo de mensajería transparente (decisión comercial, no de desarrollo).

## Fuera de alcance (etapa posterior — F2 unánime §09)

- Periodontograma (debería llegar pronto: es estándar clínico, pero F2).
- Receta electrónica ReNaPDiS propia (cubrir temprano vía partner; obligatoria desde 2025).
- Obras sociales: cobertura, copago y lotes; luego validación en línea (vía alianzas con círculos o integradores como Frontini).
- Liquidación a profesionales.
- Imágenes, DICOM y radiología.
- IA clínica (dictado, CDSS, lectura de radiografías). El dictado al odontograma queda para etapa posterior (DrApp ya tiene carga por voz).
- Inventario, laboratorio y multisucursal avanzada.
- Portal completo del paciente, telemedicina, marketplace, API pública, marketing.

## Métricas de éxito

> Las cifras comerciales de competidores ("reduce ausencias 40 %", "64 % menos débitos", conteos de clientes) son autodeclaradas y NO se toman como evidencia (§02). Las métricas de abajo son propuestas de medición propia, no promesas del discovery.

- Ausentismo: % de turnos con falta / cancelación tardía (línea base a relevar en el consultorio piloto propio — ronda usuario 1, PA-12 pendiente; objetivo: bajar con recordatorios + seña + relleno).
- Ocupación: % de huecos de sillón ocupados por semana; nº de huecos recuperados vía lista de espera.
- Conversión: % de presupuestos aceptados que generan turnos; monto en seguimiento no agendado.
- Cobro: % de turnos online con seña cobrada; tiempo de cobro a factura ARCA con CAE.
- Cumplimiento: 100 % de evoluciones con autor/fecha; consentimientos firmados con constancia; exportación completa disponible.
