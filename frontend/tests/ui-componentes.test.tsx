/** Componentes base del design system (C-07 D4): accesibilidad y estados. */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/shared/ui/Button";
import { Drawer } from "@/shared/ui/Drawer";
import { EstadoBadge } from "@/shared/ui/EstadoBadge";
import { Field, Input } from "@/shared/ui/Field";

describe("Field", () => {
  it("asocia label, ayuda y error al control", () => {
    render(
      <Field id="dni" label="DNI" ayuda="Sin puntos" error="DNI inválido">
        {(control) => <Input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText("DNI");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("DNI inválido Sin puntos");
  });

  it("sin error no marca inválido", () => {
    render(
      <Field id="nombre" label="Nombre">
        {(control) => <Input {...control} />}
      </Field>,
    );
    expect(screen.getByLabelText("Nombre")).not.toHaveAttribute("aria-invalid");
  });
});

describe("Button", () => {
  it("cargando deshabilita y marca aria-busy", async () => {
    const onClick = vi.fn();
    render(
      <Button cargando onClick={onClick}>
        Guardar
      </Button>,
    );
    const boton = screen.getByRole("button", { name: "Guardar" });
    expect(boton).toBeDisabled();
    expect(boton).toHaveAttribute("aria-busy", "true");
    await userEvent.click(boton);
    expect(onClick).not.toHaveBeenCalled();
  });
});

function DrawerDePrueba() {
  const [abierto, setAbierto] = useState(true);
  return (
    <>
      <p>{abierto ? "abierto" : "cerrado"}</p>
      <Drawer abierto={abierto} titulo="Nuevo turno" onCerrar={() => setAbierto(false)}>
        <button type="button">Dentro</button>
      </Drawer>
    </>
  );
}

describe("Drawer", () => {
  it("muestra el título accesible y cierra con el botón y con Escape", async () => {
    render(<DrawerDePrueba />);
    const dialogo = screen.getByRole("dialog", { name: "Nuevo turno" });
    expect(dialogo).toHaveAttribute("open");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar panel" }));
    expect(screen.getByText("cerrado")).toBeInTheDocument();
  });

  it("Escape (evento cancel) pide cerrar", () => {
    const onCerrar = vi.fn();
    render(
      <Drawer abierto titulo="Detalle" onCerrar={onCerrar}>
        contenido
      </Drawer>,
    );
    const dialogo = screen.getByRole("dialog", { name: "Detalle" });
    dialogo.dispatchEvent(new Event("cancel", { cancelable: true }));
    expect(onCerrar).toHaveBeenCalledTimes(1);
  });
});

describe("EstadoBadge", () => {
  it.each([
    ["reservado", "Reservado"],
    ["confirmado", "Confirmado"],
    ["asistido", "Asistido"],
    ["ausente", "Ausente"],
    ["cancelado", "Cancelado"],
  ])("%s se muestra con texto %s", (estado, texto) => {
    render(<EstadoBadge estado={estado} />);
    expect(screen.getByText(texto)).toBeInTheDocument();
  });
});

describe("Tabs y Avatar (C-20)", () => {
  it("Tabs marca la pestaña actual con aria-current", async () => {
    const { MemoryRouter } = await import("react-router");
    const { Tabs } = await import("@/shared/ui/Tabs");
    render(
      <MemoryRouter initialEntries={["/p/ficha"]}>
        <Tabs
          etiqueta="Secciones"
          pestanas={[
            { to: "/p/ficha", etiqueta: "Ficha" },
            { to: "/p/odontograma", etiqueta: "Odontograma" },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Ficha" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Odontograma" })).not.toHaveAttribute("aria-current");
  });

  it("Avatar muestra las iniciales (apellido + nombre)", async () => {
    const { Avatar } = await import("@/shared/ui/Avatar");
    const { container } = render(<Avatar nombre="Ana" apellido="Sintético" />);
    expect(container).toHaveTextContent("SA");
  });
});
