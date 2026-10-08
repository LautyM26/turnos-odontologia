import { Route, Routes } from "react-router";

import { ComprobantePage } from "./pages/ComprobantePage";
import { CumplimientoPage } from "./pages/CumplimientoPage";
import { HomePage } from "./pages/HomePage";
import { ReservarPage } from "./pages/ReservarPage";

export function App() {
  return (
    <main className="bg-background text-foreground">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/reservar/:token" element={<ReservarPage />} />
        <Route path="/cumplimiento" element={<CumplimientoPage />} />
        <Route path="/comprobantes/:id" element={<ComprobantePage />} />
      </Routes>
    </main>
  );
}
