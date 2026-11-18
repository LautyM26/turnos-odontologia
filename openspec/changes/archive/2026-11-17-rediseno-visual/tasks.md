# Tasks — rediseno-visual (C-20)

> Solo frontend. Antes de la tarea 1.1, el usuario aprueba `design.md` (D1–D6).
> Después de cada grupo: `npx tsc --noEmit`, `npx vitest run` y biome sobre los archivos tocados.

## 1. Tema y base compartida

- [x] 1.1 Tokens de modo oscuro en `styles.css` (`[data-theme="dark"]` + `prefers-color-scheme` sin elección), script anti-flash en `index.html`, `shared/ui/tema.ts` y `ToggleTema` (D1). Verificar con `frontend/tests/tema.test.tsx`: sistema por defecto; claro y oscuro aplican el atributo y persisten; "sistema" lo quita; storage no disponible sin error.
- [x] 1.2 `PageHeader`, `Tabs` y `Avatar` en `shared/ui`; `ToggleTema` en la barra de `AppLayout` (D3). Verificar en `ui-componentes.test.tsx`: Tabs con `aria-current` y Avatar con iniciales; `app-shell.test.tsx` en verde.
- [x] 1.3 `PublicLayout` con header (monograma, Ingresar, tema) y footer legal (D2). Verificar que los tests de reserva y legales sigan verdes.

## 2. Landing de producto

- [x] 2.1 Capturas reales para la landing con Playwright sobre la base de demo (`scripts/e2e/capturas_landing.py`, datos sintéticos) en `frontend/public/landing/` (≤ 250 KB c/u) (D2).
- [x] 2.2 `HomePage`: hero partido, bento de 5 diferenciales, "Cómo funciona" y CTA final, con `useReveal` (IntersectionObserver) y reduced-motion (D2). Verificar con `frontend/tests/landing.test.tsx`: "Ingresar" → `/login`, "Reservar turno" → `/reservar/clinica-piloto`, imágenes con alt, enlaces legales y cero pedidos a `/api`.

## 3. Pantallas de la app

- [x] 3.1 Login rediseñado (split desktop / una columna móvil) (D4). `app-shell.test.tsx` en verde.
- [x] 3.2 Pacientes (lista responsiva + Avatar + skeleton/EmptyState) y layout del paciente (cabecera + Tabs) (D4). Suites `pacientes*`/`ficha*` en verde.
- [x] 3.3 Ficha y anamnesis con Cards y Field (D4). Suites de ficha en verde.
- [x] 3.4 Odontograma: restyle de contenedor, toolbar, leyenda y `PanelPieza` sin tocar `OdontogramaGrafico` ni `borrador.ts` (D4). Suites `odontograma-*` en verde, incluido el test de convención de colores.
- [x] 3.5 Evoluciones (timeline) y adjuntos (grilla de tarjetas + zona de subida) (D4). Suites `evoluciones*` y `adjuntos*` en verde.

## 4. Público: reserva, reprogramación, legales

- [x] 4.1 Reserva y comprobante con el layout público; "Reprogramar" en el comprobante si `cancelable` (D4, D5). Verificar en `reprogramar.test.tsx` (bloque "comprobante"): link visible en un turno futuro y oculto en uno cancelado.
- [x] 4.2 `ReprogramarPage` + API (`opcionesReprogramacion`, `reprogramar` con alternativas del 409) + ruta `/reprogramar/:token` (D5). Verificar con `frontend/tests/reprogramar.test.tsx`: carga en paralelo, confirmar → "Turno reprogramado", 409 → alternativas, 422, 404 y 429.
- [x] 4.3 Legales, comprobantes y 404 rediseñados (D4). `legal.test.tsx` y `app-shell.test.tsx` en verde.

## 5. Cierre

- [x] 5.1 Frontend completo: `tsc`, `npm run build`, `vitest run` en verde (2 corridas) y biome sobre lo tocado; sin em-dash en la UI; contraste de pares críticos medido en claro y oscuro. Backend sin cambios (`git diff --stat backend` vacío).
- [x] 5.2 Evidencia Playwright en claro y oscuro, desktop y móvil: landing, login, agenda, paciente/odontograma, evoluciones, reserva, reprogramar. Revisión contra el checklist del `MASTER.md` y del taste-skill; todo en `verify.md`.
- [x] 5.3 `MASTER.md` (sección de modo oscuro), README (landing y tema) y `docs/CONTINUAR.md` (C-20 hecho; `/reprogramar` resuelto).

## Workflow follow-up

- `/opsx:archive rediseno-visual` tras la revisión humana y con `verify.md` completo.
- Marcar C-20 `[x]` en `CHANGES.md`.
