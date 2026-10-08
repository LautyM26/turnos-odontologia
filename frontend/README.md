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

`/` · `/reservar/:token` · `/cumplimiento` · `/comprobantes/:id`.
