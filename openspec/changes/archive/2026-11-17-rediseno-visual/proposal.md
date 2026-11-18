# Proposal — rediseno-visual (C-20)

## Why

C-07 estrenó el sistema de diseño (`design-system/turnos-odontologia/MASTER.md`): tokens teal, Figtree/Noto Sans, Lucide, componentes de `shared/ui` y el shell con sidebar. Las pantallas de C-10 (pacientes, ficha, odontograma, evoluciones, adjuntos), C-06 (reserva pública y comprobante) y C-18 (páginas legales) **solo heredan** los tokens: siguen con la maquetación básica de su primera versión.

La home `/` es un placeholder ("Turnos Odontología · Reservá tu turno online"). Para la presentación en video del TPI, el sistema tiene que verse coherente y actual de punta a punta.

La pantalla pública de reprogramación del chatbot de C-17 (`/reprogramar/{token}`) todavía no existe, aunque su backend ya está. El usuario la asignó a este change.

## What Changes

- **Landing de producto** en `/`:
  - hero con una **captura real** de la agenda (datos sintéticos de `seed_demo_agenda.py`);
  - los diferenciales del producto: agenda por sillón, reserva online sin cuenta, historia clínica con odontograma, WhatsApp, cumplimiento legal;
  - CTAs "Ingresar" (staff) y "Reservar turno" (demo `/reservar/clinica-piloto`).
- **Modo oscuro:** sigue la preferencia del sistema, con un botón para alternar (claro, oscuro o sistema) en la barra superior y en las páginas públicas. La preferencia se recuerda en el navegador.
- **Rediseño con el sistema de diseño** de:
  - login;
  - listado y búsqueda de pacientes;
  - layout del paciente (encabezado y pestañas);
  - ficha y anamnesis;
  - **odontograma: solo restyle** (contenedor, toolbar, leyenda y panel de pieza), sin tocar la lógica, el gráfico FDI ni la convención rojo = a realizar / azul = existente;
  - evoluciones;
  - adjuntos;
  - reserva pública y comprobante;
  - comprobantes;
  - páginas legales;
  - 404.
- **Nueva pantalla pública `/reprogramar/{token}`:**
  - muestra el turno actual y hasta 3 opciones de horario (`GET /api/public/reservas/{token}/opciones`);
  - confirma con `POST …/reprogramar {inicio}`;
  - ante un `409`, ofrece las `alternativas` que devuelve la API.
  - El comprobante (`/reserva/{token}`) suma el acceso "Reprogramar".
- **Motion:**
  - en las páginas públicas, entradas escalonadas, reveal al scroll y microinteracciones (dials variance 7 / motion 6);
  - en la app, transiciones sobrias (motion 4);
  - siempre respetando `prefers-reduced-motion`.

### Decisiones tomadas con el usuario (2026-11-17)

1. Landing de producto con capturas reales y CTAs Ingresar / Reservar turno (demo).
2. Motion media en lo público y sobria en la app.
3. Modo oscuro con preferencia del sistema más toggle.
4. Odontograma: restyle sin tocar la lógica ni la convención de colores.
5. `/reprogramar/{token}` entra en este change (antes estaba asignado a C-07).

## Non-goals

- Cambios de backend o de contratos HTTP. Todo consume endpoints existentes.
- Funcionalidades nuevas en las pantallas clínicas: mismo comportamiento y mismos permisos.
- Rediseñar el dibujo del odontograma (piezas y caras).
- Branding definitivo (logo propio): se usa un monograma simple.
- Pantallas de C-11 a C-14 (presupuestos, caja, facturación).

## Capabilities

### New Capabilities

- `product-landing`: página pública de presentación del producto con acceso a ingresar y a reservar.
- `visual-theme`: sistema visual aplicado a toda la app (tokens, tipografía, modo claro y oscuro con toggle, motion por contexto, accesibilidad base).
- `reschedule-web`: pantalla pública para reprogramar un turno con el enlace.

### Modified Capabilities

- `public-booking-web`: el comprobante ofrece "Reprogramar" mientras el turno se puede cambiar.

## Impact

- **Solo `frontend/`:**
  - `src/styles.css` (tokens de modo oscuro);
  - `src/shared/ui/*` (toggle de tema y componentes faltantes: Tabs, PageHeader);
  - `src/pages/*` (landing, legales, 404, comprobante);
  - `src/features/auth/LoginPage.tsx`;
  - `src/features/clinica/**` (solo presentación);
  - `src/features/reserva/*` y la nueva `src/features/reserva/ReprogramarPage.tsx`;
  - `src/router.tsx`;
  - `public/landing/*` (capturas).
- **Tests:** las suites existentes siguen verdes (o se actualizan sin cambiar su intención); tests nuevos de tema, landing y reprogramación.
- Dependencias nuevas: ninguna (Lucide ya está; motion con CSS e IntersectionObserver).
- Governance: BAJO (solo frontend).
