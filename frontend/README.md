# Frontend — Turnos Odontología (C-01 foundation)

React 19 + Vite 8 + TS strict + Tailwind v4 CSS-first + Vitest.

## Dev local

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxy /api → :8000)
npm test         # vitest run
npx tsc --noEmit # typecheck
npm run build    # dist/
```

## Reglas (verificadas en CI)

- Sin `useMemo`/`useCallback`/`memo`/`forwardRef`; componentes PascalCase con `React.ComponentProps`.
- Solo `VITE_`-prefixed vía `import.meta.env` (regla 12); tenant via `X-Clinica-Id`.
- Cargas paralelas con `Promise.all` / `fetchAll` (regla 13); 409 → mostrar alternativas (C-07).
- Tokens semánticos (`bg-primary`), sin `bg-${x}` dinámico, sin `tailwind.config.js`.
- Datos sintéticos en tests (regla 14).

## Rutas públicas

`/` · `/reservar/:token` · `/cumplimiento` · `/privacidad` (C-18) · `/comprobantes/:id` · `/login`.
Viven en `src/router.tsx`, **fuera** de `AppLayout`: no piden sesión.

## Sesión y rutas protegidas (C-10)

- **Access token solo en memoria** (`src/shared/api/client.ts`); el refresh vive en la cookie HttpOnly
  `Path=/api/auth` que gestiona el navegador. Nada en `localStorage`/`sessionStorage` (hay un test que lo audita).
- `src/features/auth/session.ts`: `iniciarSesion`, `renovarSesion` (single-flight: el backend rota y blacklistea
  el refresh, dos refresh paralelos serían un replay), `requireSession` (loader), `cerrarSesion`, `useSesion`.
- Ante un `401` el cliente renueva **una** vez y reintenta **una** vez; si el refresh falla lleva a `/login?expirada=1`.
- `X-Clinica-Id`: `VITE_CLINICA_ID` si existe, si no el `tenant_id` de la sesión, nunca vacío.
- Árbol de rutas (router de datos de React Router 7):

```
PublicLayout   /  /reservar/:token  /cumplimiento  /privacidad  /comprobantes/:id
/login         (con sesión → /pacientes)
AppLayout      loader = requireSession()  → /login?redirectTo=… si no hay sesión
  /pacientes                         listado + búsqueda (?buscar=)
  /pacientes/:pacienteId             encabezado + pestañas (loader: paciente, historia, profesionales en paralelo)
    ficha | odontograma | evoluciones | adjuntos
```

**Cómo agrega C-07 la agenda:** una entrada más en los `children` de `AppLayout` (`{ path: "/agenda", lazy: … }`)
y un `NavLink` en `src/features/auth/AppLayout.tsx`. El login, el cliente HTTP y el guard ya están hechos.

## Demo clínica

Backend + frontend + datos de demo: ver la sección "Demo clínica" del README raíz. E2E real:
`python scripts/e2e/clinica_demo.py` (Python Playwright; variables documentadas en el script).
Opcional: `VITE_PROXY_TARGET` cambia el destino del proxy `/api` de Vite (default `http://localhost:8000`).
