/** Modo claro / oscuro (C-20 D1, spec visual-theme). */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToggleTema } from "@/shared/ui/ToggleTema";
import { aplicarTema, leerTema } from "@/shared/ui/tema";

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.restoreAllMocks();
});

describe("tema", () => {
  it("por defecto sigue al sistema (sin atributo)", () => {
    expect(leerTema()).toBe("sistema");
    render(<ToggleTema />);
    expect(screen.getByRole("button", { name: "Tema: Sistema" })).toBeInTheDocument();
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("elegir Oscuro aplica data-theme y persiste; Claro lo cambia", async () => {
    render(<ToggleTema />);
    await userEvent.click(screen.getByRole("button", { name: "Tema: Sistema" }));
    await userEvent.click(screen.getByRole("button", { name: "Oscuro" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem("tema")).toBe("oscuro");
    expect(leerTema()).toBe("oscuro");
    await userEvent.click(screen.getByRole("button", { name: "Tema: Oscuro" }));
    await userEvent.click(screen.getByRole("button", { name: "Claro" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });

  it("Sistema quita el atributo y la elección guardada", () => {
    aplicarTema("oscuro");
    aplicarTema("sistema");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(window.localStorage.getItem("tema")).toBeNull();
  });

  it("Escape cierra el menú", async () => {
    render(<ToggleTema />);
    const boton = screen.getByRole("button", { name: "Tema: Sistema" });
    await userEvent.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");
    await userEvent.keyboard("{Escape}");
    expect(boton).toHaveAttribute("aria-expanded", "false");
  });

  it("sin storage disponible no falla", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    expect(() => aplicarTema("oscuro")).not.toThrow();
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(leerTema()).toBe("sistema");
  });
});
