/** Adjuntos: validación previa, listado, descarga autenticada y subida (spec clinical-record-web). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_BYTES, validarArchivo } from "@/features/clinica/adjuntos/validar";

import { renderApp, tablaPaciente } from "./helpers/app";
import { adjunto, meAdmin, meRecepcion, paciente } from "./helpers/fixtures";

const RUTA = "/pacientes/7/adjuntos";
const pdf = (bytes = 3, nombre = "estudio.pdf", tipo = "application/pdf") =>
  new File([new Uint8Array(bytes)], nombre, { type: tipo });

afterEach(() => vi.unstubAllGlobals());

describe("validarArchivo", () => {
  it("acepta JPEG (.jpeg y .jpg), PNG y PDF", () => {
    expect(validarArchivo(pdf())).toBeNull();
    expect(validarArchivo(pdf(3, "foto.jpeg", "image/jpeg"))).toBeNull();
    expect(validarArchivo(pdf(3, "foto.JPG", "image/jpeg"))).toBeNull();
    expect(validarArchivo(pdf(3, "rx.png", "image/png"))).toBeNull();
  });

  it("rechaza .docx, MIME incorrecto y extensión engañosa", () => {
    const docx = pdf(
      3,
      "x.docx",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(validarArchivo(docx)).toBe("Solo se aceptan fotos JPG/PNG o PDF");
    expect(validarArchivo(pdf(3, "x.exe", "application/pdf"))).toBe(
      "Solo se aceptan fotos JPG/PNG o PDF",
    );
    expect(validarArchivo(pdf(3, "x.pdf", "text/plain"))).toBe(
      "Solo se aceptan fotos JPG/PNG o PDF",
    );
  });

  it("tamaño: 10 MiB exactos pasan, 10 MiB + 1 byte no; vacío no", () => {
    expect(validarArchivo(pdf(MAX_BYTES))).toBeNull();
    expect(validarArchivo(pdf(MAX_BYTES + 1))).toBe("El archivo supera el tamaño máximo permitido");
    expect(validarArchivo(pdf(0))).toBe("El archivo está vacío");
  });
});

const filas = async () =>
  within(await screen.findByRole("list", { name: "Adjuntos del paciente" })).getAllByRole(
    "listitem",
  );

const lista = [
  adjunto({ id: 2, tipo: "foto", mime: "image/jpeg", tamano_bytes: 1_572_864, subido_por: 20 }),
  adjunto({ id: 1 }),
];
const conAdjuntos = (items = lista, extra = {}, me = undefined as undefined | typeof meAdmin) =>
  tablaPaciente({ "GET /api/pacientes/7/adjuntos": { json: items }, ...extra }, me);

describe("Listado y descarga", () => {
  it("lista tipo, tamaño legible, autor y fecha", async () => {
    renderApp(RUTA, conAdjuntos());
    const items = await filas();
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Foto");
    expect(items[0]).toHaveTextContent("1,5 MB");
    expect(items[0]).toHaveTextContent("Profesional Demo Dos");
    expect(items[1]).toHaveTextContent("PDF");
    expect(items[1]).toHaveTextContent("200 KB");
    expect(items[1]).toHaveTextContent("Vos");
    expect(items[1]).toHaveTextContent("10/11/2026");
    expect(screen.getAllByRole("button", { name: /Descargar/ })).toHaveLength(2);
  });

  it("estado vacío indica los tipos aceptados", async () => {
    renderApp(RUTA, conAdjuntos([]));
    expect(await screen.findByText(/Todavía no hay adjuntos.*JPG, PNG o PDF/)).toBeInTheDocument();
  });

  it("Descargar usa la sesión (Authorization) y no pone el token en la URL", async () => {
    const crear = vi.fn(() => "blob:demo");
    const revocar = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: crear, revokeObjectURL: revocar }));
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const { api } = renderApp(
      RUTA,
      conAdjuntos(lista, { "GET /api/pacientes/7/adjuntos/1/contenido": { text: "%PDF-1.4" } }),
    );
    await userEvent.click(
      (await screen.findAllByRole("button", { name: /Descargar/ }))[1] as HTMLElement,
    );
    await waitFor(() => expect(click).toHaveBeenCalled());
    const llamada = api.de("GET /api/pacientes/7/adjuntos/1/contenido")[0];
    expect(llamada?.headers.get("Authorization")).toBe("Bearer tok");
    expect(llamada?.url).not.toContain("tok");
    expect(crear).toHaveBeenCalled();
    expect(revocar).toHaveBeenCalledWith("blob:demo");
    click.mockRestore();
  });
});

describe("Subida", () => {
  const nuevo = adjunto({ id: 3, tamano_bytes: 3 });
  const subir = async (archivo: File, setup = userEvent.setup()) => {
    await setup.upload(await screen.findByLabelText("Archivo"), archivo);
    await setup.click(screen.getByRole("button", { name: "Subir adjunto" }));
  };

  it("multipart con el único campo file; Subiendo… y el nuevo queda primero", async () => {
    let liberar: () => void = () => undefined;
    const puerta = new Promise<void>((r) => {
      liberar = r;
    });
    const { api } = renderApp(
      RUTA,
      conAdjuntos(lista, {
        "POST /api/pacientes/7/adjuntos": async () => {
          await puerta;
          return { status: 201, json: nuevo };
        },
      }),
    );
    await subir(pdf(3, "estudio.pdf"));
    expect(await screen.findByRole("button", { name: "Subiendo…" })).toBeDisabled();
    liberar();
    expect(await screen.findByText("Adjunto subido")).toBeInTheDocument();
    const cuerpo = api.de("POST /api/pacientes/7/adjuntos")[0]?.body as FormData;
    expect([...cuerpo.keys()]).toEqual(["file"]);
    expect(api.de("POST /api/pacientes/7/adjuntos")[0]?.headers.has("Content-Type")).toBe(false);
    const filas = within(screen.getByRole("list", { name: "Adjuntos del paciente" })).getAllByRole(
      "listitem",
    );
    expect(filas).toHaveLength(3);
    expect(filas[0]).toHaveTextContent("3 B");
  });

  it(".docx: mensaje y ninguna request", async () => {
    const { api } = renderApp(RUTA, conAdjuntos());
    await subir(pdf(3, "x.docx", "application/msword"), userEvent.setup({ applyAccept: false }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Solo se aceptan fotos JPG/PNG o PDF",
    );
    expect(api.de("POST /api/pacientes/7/adjuntos")).toHaveLength(0);
  });

  it.each([
    [415, "El contenido del archivo no es una foto ni un PDF válido"],
    [413, "El archivo supera el tamaño máximo permitido"],
    [422, "El archivo está vacío o no es válido"],
  ])("el servidor responde %s: mensaje claro y lista sin cambios", async (status, mensaje) => {
    renderApp(
      RUTA,
      conAdjuntos(lista, { "POST /api/pacientes/7/adjuntos": { status, json: { detail: "x" } } }),
    );
    await subir(pdf());
    expect(await screen.findByRole("alert")).toHaveTextContent(mensaje);
    expect(
      within(screen.getByRole("list", { name: "Adjuntos del paciente" })).getAllByRole("listitem"),
    ).toHaveLength(2);
  });
});

describe("Acceso", () => {
  it("recepción: Sin acceso clínico", async () => {
    renderApp(
      RUTA,
      conAdjuntos(
        lista,
        { "GET /api/pacientes/7/adjuntos": { status: 403, json: { detail: "Rol insuficiente" } } },
        meRecepcion,
      ),
    );
    expect(
      await screen.findByText("Sin acceso clínico: tu rol no permite ver la historia clínica"),
    ).toBeInTheDocument();
  });

  it("admin sin rol odontólogo: lista sin subir", async () => {
    renderApp(RUTA, conAdjuntos(lista, {}, meAdmin));
    await filas();
    expect(screen.queryByLabelText("Archivo")).not.toBeInTheDocument();
  });

  it("sin consentimiento: subida deshabilitada con aviso y adjuntos visibles", async () => {
    renderApp(
      RUTA,
      conAdjuntos(lista, {
        "GET /api/pacientes/7": {
          json: paciente({ consentimiento_datos: false, consentimiento_datos_at: null }),
        },
      }),
    );
    await filas();
    expect(screen.getByLabelText("Archivo")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Subir adjunto" })).toBeDisabled();
  });

  it("error 500 al listar: Reintentar", async () => {
    renderApp(
      RUTA,
      conAdjuntos(lista, {
        "GET /api/pacientes/7/adjuntos": { status: 500, json: { detail: "boom" } },
      }),
    );
    expect(await screen.findByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(within(screen.getByRole("alert")).getByText("boom")).toBeInTheDocument();
  });
});
