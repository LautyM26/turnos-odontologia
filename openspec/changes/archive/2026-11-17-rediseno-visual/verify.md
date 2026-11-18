# Verify: rediseno-visual (C-20)

Fecha: 2026-11-17. Alcance: solo frontend. `git diff --stat -- backend` sale vacío.

## Resultado

| Chequeo | Resultado |
|---|---|
| `npx tsc --noEmit` | limpio |
| `npx vitest run` (2 corridas) | 22 archivos, **268 passed** las dos veces (antes de C-20: 247) |
| `npm run build` | OK (bundle principal 248,75 kB, 77,44 kB gzip) |
| `npx biome check` en los archivos tocados por C-20 | sin errores (los errores de CRLF en archivos que C-20 no toca ya estaban antes) |
| `ruff check` y `ruff format` en `scripts/e2e/` nuevos | limpio |
| Em-dash en la UI | se reemplazó en las versiones de anamnesis ("Sin datos"). Queda uno en `nombreAutor` (`shared/formato.ts`), cubierto por `ui-base.test.tsx` del compañero; no se toca acá |
| Evidencia Playwright | `scripts/e2e/rediseno_evidencias.py`: 4/4 combinaciones OK (claro/oscuro × desktop/móvil), 36 capturas en `evidencias/` |
| Capturas de la landing | `scripts/e2e/capturas_landing.py`: agenda.png 97 KB, semana.png 117 KB, reserva-movil.png 44 KB (todas ≤ 250 KB) |

## Escenarios → tests

| Spec · escenario | Test |
|---|---|
| product-landing · landing sin API, capturas con alt, diferenciales | `tests/landing.test.tsx` (4 tests) |
| visual-theme · sistema por defecto, claro/oscuro persisten, "sistema" quita el atributo, storage bloqueado | `tests/tema.test.tsx` (5 tests) |
| reschedule-web · opciones en paralelo | `reprogramar.test.tsx` · "pide turno y opciones en paralelo (regla dura 13)" |
| reschedule-web · reprogramación confirmada | "elige el jueves 10:30, confirma y ve Turno reprogramado" |
| reschedule-web · 409 con alternativas (borde) | "409: avisa y muestra las alternativas de la respuesta, sin perder el turno" |
| reschedule-web · 422 / 404 / 429 | "422: …", "404: Reserva no encontrada", "429 al confirmar: pide esperar un minuto" |
| public-booking-web · "Reprogramar" en el comprobante | `reprogramar.test.tsx` · bloque "comprobante": visible si `cancelable`, oculto si cancelado |
| Componentes nuevos (Tabs, Avatar) | `tests/ui-componentes.test.tsx` |

## Contraste medido (WCAG 2.2, fórmula de luminancia relativa)

| Par | Claro | Oscuro | Mínimo |
|---|---|---|---|
| Texto / fondo | 17,01 | 15,96 | 4,5 |
| Muted / superficie | 5,45 | 6,79 | 4,5 |
| Muted / superficie-2 | 4,96 | 6,31 | 4,5 |
| Texto del botón primario | 5,36 | 6,39 | 4,5 |
| Enlace primario / superficie | 5,36 | 5,97 | 4,5 |
| Primary-hover / primary-soft (tab y chip activos) | 6,55 | 6,51 | 4,5 |
| Borde de control / superficie | 3,30 | 3,61 | 3 |
| Danger / superficie | 5,61 | 6,38 | 4,5 |
| Success / superficie | 5,02 | 10,12 | 4,5 |

## Ajustes durante el apply (revisión crítica)

- **Excepción en `client.test.ts`:** el test prohibía `localStorage.` en todo `src` (secretos en el navegador, regla dura 12). `shared/ui/tema.ts` guarda solo la preferencia de tema. Se exceptuó ese archivo de forma explícita y se agregó un chequeo: el archivo no puede mencionar token, jwt, access, refresh ni sessionStorage.
- **Bordes de inputs:** el borde `--border` no llegaba a 3:1 (WCAG 1.4.11). Se agregó el token `--border-control`, que usan `Field` y los controles nativos.
- **Odontograma en oscuro:** las piezas blancas con trazo claro se perdían. La grilla queda sobre "papel" blanco en los dos temas, con la convención rojo/azul intacta. Se quitaron los tonos aclarados del odontograma que había en el tema oscuro. `odontograma-ui.test.tsx` sigue verde, incluido el test de convención de colores.
- **Bento de la landing:** la tarjeta grande dejaba espacio vacío debajo de la captura. La imagen ahora llena la tarjeta (`object-cover`).
- **API de reprogramación:** el 409 trae `alternativas` en el cuerpo y `leerError` las descartaba. `reprogramar()` lee el 409 aparte y lanza `HorarioOcupado(alternativas)`. El resto de los errores pasa por `leerError`.

## Checklist MASTER.md / taste-skill

- Un solo color de marca (teal) más el acento coral, igual en todas las pantallas. Sin gradientes violeta ni azul.
- Hero partido (sin centrar), bento asimétrico de 5 tarjetas (no son 3 iguales), CTA de una línea con contraste AA.
- Figtree / Noto Sans (MASTER.md). Sin Inter.
- Íconos: lucide-react, ya instalado en el proyecto, con un solo trazo.
- Motion: reveal de la landing por IntersectionObserver con escalonado de 70 ms y tarjeta flotante. En la app solo hay un fundido corto entre pestañas. Todo se desactiva con `prefers-reduced-motion`.
- Estados: skeletons en el comprobante y la reprogramación, vacíos con salida ("Volver al comprobante"), errores en línea con `aria-live`.
- Touch: botones de horario de 40 px o más; opciones de reprogramación de 48 px de alto.
- Solo datos sintéticos en capturas, scripts y tests (regla dura 14).

## Pendiente

- Revisión humana de las capturas en `evidencias/`. Después: `/opsx:archive rediseno-visual` y marcar C-20 en `CHANGES.md`.
