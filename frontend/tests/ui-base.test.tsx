/** Base de UI compartida: resultados por sección, estados, diálogo y formato. */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/shared/api/client";
import { CONSENTIMIENTO_FALTANTE, cargarSeguro, clasificarError } from "@/shared/api/resultado";
import { fechaHora, nombreAutor, nombreProfesional, tamano } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";
import { EstadoSeccion } from "@/shared/ui/EstadoSeccion";

import { meOdontologo, profesionales } from "./helpers/fixtures";

describe("clasificarError / cargarSeguro", () => {
  it("403 por consentimiento -> sin-consentimiento", () => {
    const e = new ApiError(403, CONSENTIMIENTO_FALTANTE);
    expect(clasificarError(e).tipo).toBe("sin-consentimiento");
  });

  it("otro 403 -> sin-acceso; 404 -> no-encontrado; 500 y red -> error", () => {
    expect(clasificarError(new ApiError(403, "Rol insuficiente")).tipo).toBe("sin-acceso");
    expect(clasificarError(new ApiError(404, "x")).tipo).toBe("no-encontrado");
    expect(clasificarError(new ApiError(500, "boom"))).toEqual({ tipo: "error", mensaje: "boom" });
    expect(clasificarError(new TypeError("fetch failed")).tipo).toBe("error");
  });

  it("cargarSeguro devuelve ok con los datos o el error clasificado sin lanzar", async () => {
    expect(await cargarSeguro(Promise.resolve(5))).toEqual({ tipo: "ok", datos: 5 });
    expect((await cargarSeguro(Promise.reject(new ApiError(403, "Rol insuficiente")))).tipo).toBe(
      "sin-acceso",
    );
  });

  it("la constante de consentimiento coincide con la del backend", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const backend = fs.readFileSync(
      path.resolve(import.meta.dirname, "../../backend/app/api/pacientes.py"),
      "utf-8",
    );
    expect(backend).toContain(`CONSENTIMIENTO_FALTANTE = "${CONSENTIMIENTO_FALTANTE}"`);
  });
});

describe("EstadoSeccion", () => {
  it("cargando con aria-busy", () => {
    render(<EstadoSeccion estado={{ tipo: "cargando" }} />);
    expect(screen.getByText("Cargando…").closest("[aria-busy]")).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("vacío muestra el mensaje", () => {
    render(<EstadoSeccion estado={{ tipo: "vacio", mensaje: "Nada por acá" }} />);
    expect(screen.getByText("Nada por acá")).toBeInTheDocument();
  });

  it("error con Reintentar que llama al callback", async () => {
    const onReintentar = vi.fn();
    render(<EstadoSeccion estado={{ tipo: "error", mensaje: "Falló", onReintentar }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Falló");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onReintentar).toHaveBeenCalledOnce();
  });

  it("sin acceso clínico y sin consentimiento tienen su texto", () => {
    const { rerender } = render(<EstadoSeccion estado={{ tipo: "sin-acceso" }} />);
    expect(
      screen.getByText("Sin acceso clínico: tu rol no permite ver la historia clínica"),
    ).toBeInTheDocument();
    rerender(<EstadoSeccion estado={{ tipo: "sin-consentimiento" }} />);
    expect(
      screen.getByText("Sin consentimiento de datos: no se pueden cargar datos de salud"),
    ).toBeInTheDocument();
  });
});

describe("Aviso", () => {
  it("error usa role alert; éxito usa role status", () => {
    render(
      <>
        <Aviso tipo="error">Mal</Aviso>
        <Aviso tipo="exito">Bien</Aviso>
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Mal");
    expect(screen.getByRole("status")).toHaveTextContent("Bien");
  });
});

describe("DialogoConfirmacion", () => {
  function montar(onConfirmar = vi.fn(), onCancelar = vi.fn()) {
    render(
      <DialogoConfirmacion
        abierto
        titulo="¿Seguro?"
        confirmar="Sí, seguir"
        onConfirmar={onConfirmar}
        onCancelar={onCancelar}
      >
        Explicación del efecto
      </DialogoConfirmacion>,
    );
    return { onConfirmar, onCancelar };
  }

  it("abre modal con título y explicación, foco en Cancelar", () => {
    montar();
    expect(screen.getByRole("dialog", { name: "¿Seguro?" })).toBeInTheDocument();
    expect(screen.getByText("Explicación del efecto")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
  });

  it("confirmar y cancelar llaman a su callback", async () => {
    const { onConfirmar, onCancelar } = montar();
    await userEvent.click(screen.getByRole("button", { name: "Sí, seguir" }));
    expect(onConfirmar).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCancelar).toHaveBeenCalledOnce();
  });

  it("Escape (evento cancel del dialog) cancela", () => {
    const { onCancelar } = montar();
    screen.getByRole("dialog").dispatchEvent(new Event("cancel", { cancelable: true }));
    expect(onCancelar).toHaveBeenCalledOnce();
  });

  it("cerrado no muestra el diálogo", () => {
    render(
      <DialogoConfirmacion
        abierto={false}
        titulo="X"
        confirmar="Ok"
        onConfirmar={() => undefined}
        onCancelar={() => undefined}
      >
        c
      </DialogoConfirmacion>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("formato", () => {
  it("fecha en Buenos Aires: un instante UTC que cambia de día", () => {
    const s = fechaHora("2026-11-11T01:30:00Z");
    expect(s).toContain("10/11/2026");
    expect(s).toContain("22:30");
    expect(fechaHora("2026-11-10T15:30:00Z")).toContain("12:30");
  });

  it("tamaños en B/KB/MB", () => {
    expect(tamano(512)).toBe("512 B");
    expect(tamano(204_800)).toBe("200 KB");
    expect(tamano(1_572_864)).toBe("1,5 MB");
  });

  it("nombre de autor: Vos / profesional / Usuario #id", () => {
    expect(nombreAutor(10, meOdontologo, profesionales)).toBe("Vos");
    expect(nombreAutor(20, meOdontologo, profesionales)).toBe("Profesional Demo Dos");
    expect(nombreAutor(99, meOdontologo, profesionales)).toBe("Usuario #99");
    expect(nombreAutor(null, meOdontologo, profesionales)).toBe("—");
  });

  it("nombre de profesional con fallback", () => {
    expect(nombreProfesional(1, profesionales)).toBe("Profesional Demo Uno");
    expect(nombreProfesional(77, profesionales)).toBe("Profesional #77");
  });
});

describe("tokens (4.1)", () => {
  it("el fuente no arma clases Tailwind dinámicas (bg con interpolación)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const hallados: string[] = [];
    const walk = (dir: string): void => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, e.name);
        if (e.isDirectory()) walk(full);
        else if (/\.(ts|tsx)$/.test(e.name)) {
          if (/(?:bg|text|border|ring)-\$\{/.test(fs.readFileSync(full, "utf-8")))
            hallados.push(full);
        }
      }
    };
    walk(path.resolve(import.meta.dirname, "../src"));
    expect(hallados).toEqual([]);
  });
});
