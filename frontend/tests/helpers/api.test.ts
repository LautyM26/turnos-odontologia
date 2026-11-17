import { afterEach, describe, expect, it } from "vitest";

import { type ApiMock, mockApi } from "./api";

let api: ApiMock | undefined;
afterEach(() => api?.restaurar());

describe("mockApi", () => {
  it("falla explícito con una ruta no mockeada", async () => {
    api = mockApi({});
    await expect(fetch("/api/x")).rejects.toThrow(/no mockeada GET \/api\/x/);
  });

  it("responde por método+ruta (sin query) y registra llamadas y cuerpo", async () => {
    api = mockApi({
      "GET /api/a": { json: { ok: 1 } },
      "POST /api/a": { status: 201, json: { ok: 2 } },
    });
    const r1 = await fetch("/api/a?q=1");
    const r2 = await fetch("/api/a", { method: "POST", body: JSON.stringify({ x: 1 }) });
    expect(await r1.json()).toEqual({ ok: 1 });
    expect(r2.status).toBe(201);
    expect(api.llamadas.map((l) => l.orden)).toEqual([0, 1]);
    expect(api.cuerpo("POST /api/a")).toEqual({ x: 1 });
    expect(api.de("GET /api/a")).toHaveLength(1);
  });
});
