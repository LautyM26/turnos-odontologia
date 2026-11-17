import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { crearRouter } from "./router";
import "./styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("No se encontró #root");
}

createRoot(rootElement).render(
  <StrictMode>
    <RouterProvider router={crearRouter()} />
  </StrictMode>,
);
