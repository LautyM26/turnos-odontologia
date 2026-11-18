/**
 * Árbol de rutas (router de datos de React Router 7).
 *
 * - Públicas (fuera de la sesión): /, /reservar/:slug y /reserva/:token (C-06),
 *   /reprogramar/:token (C-20), /cumplimiento,
 *   /privacidad (C-18), /comprobantes/:id y /login.
 * - Protegidas: hijas de AppLayout, cuyo loader exige sesión; /agenda (C-07) usa ancho completo.
 */

import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouteObject,
  redirect,
} from "react-router";

import { AppLayout } from "@/features/auth/AppLayout";
import { LoginPage } from "@/features/auth/LoginPage";
import { getIdentidad, limpiarSesion, requireSession } from "@/features/auth/session";
import { onSesionExpirada } from "@/shared/api/client";
import { PublicLayout } from "@/shared/ui/PublicLayout";

import { ComprobantePage } from "./pages/ComprobantePage";
import { CumplimientoPage } from "./pages/CumplimientoPage";
import { HomePage } from "./pages/HomePage";
import { PrivacidadPage } from "./pages/PrivacidadPage";

export const rutas: RouteObject[] = [
  {
    Component: PublicLayout,
    children: [
      { path: "/", Component: HomePage },
      { path: "/reservar/:slug", lazy: () => import("@/features/reserva/ReservarPage") },
      { path: "/reserva/:token", lazy: () => import("@/features/reserva/ReservaPage") },
      { path: "/reprogramar/:token", lazy: () => import("@/features/reserva/ReprogramarPage") },
      { path: "/cumplimiento", Component: CumplimientoPage },
      { path: "/privacidad", Component: PrivacidadPage },
      { path: "/comprobantes/:id", Component: ComprobantePage },
    ],
  },
  {
    path: "/login",
    Component: LoginPage,
    loader: () => (getIdentidad() === null ? null : redirect("/pacientes")),
  },
  {
    Component: AppLayout,
    loader: ({ request }) => requireSession(new URL(request.url)),
    children: [
      {
        path: "/agenda",
        lazy: () => import("@/features/agenda/AgendaPage"),
        handle: { anchoCompleto: true },
      },
      { path: "/pacientes", lazy: () => import("@/features/clinica/pacientes/PacientesPage") },
      {
        path: "/pacientes/:pacienteId",
        lazy: () => import("@/features/clinica/pacientes/PacienteLayout"),
        children: [
          { index: true, element: <Navigate to="ficha" replace /> },
          { path: "ficha", lazy: () => import("@/features/clinica/pacientes/FichaTab") },
          {
            path: "odontograma",
            lazy: () => import("@/features/clinica/odontograma/OdontogramaTab"),
          },
          {
            path: "evoluciones",
            lazy: () => import("@/features/clinica/evoluciones/EvolucionesTab"),
          },
          { path: "adjuntos", lazy: () => import("@/features/clinica/adjuntos/AdjuntosTab") },
        ],
      },
      {
        path: "*",
        lazy: () => import("@/shared/ui/NoEncontrada"),
      },
    ],
  },
];

/** Router del navegador, o en memoria (tests) si se pasan entradas. */
export function crearRouter(entradas?: string[]) {
  const router = entradas
    ? createMemoryRouter(rutas, { initialEntries: entradas })
    : createBrowserRouter(rutas);
  onSesionExpirada(() => {
    limpiarSesion();
    void router.navigate("/login?expirada=1", { replace: true });
  });
  return router;
}
