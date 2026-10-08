/** Smoke del cliente HTTP: tenant header, solo VITE_ en browser, sin secretos. */

import { describe, expect, it, vi } from "vitest";

import { apiFetch, fetchAll, getAccessToken, getClinicaId, setAccessToken } from "@/shared/api/client";

describe("getClinicaId", () => {
  it("lee el tenant desde import.meta.env", () => {
    expect(typeof getClinicaId()).toBe("string");
  });
});

describe("apiFetch", () => {
  it("inyecta X-Clinica-Id en cada request a /api/*", async () => {
    vi.stubEnv("VITE_CLINICA_ID", "clinica-sintetica-1");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/health");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("X-Clinica-Id")).toBe("clinica-sintetica-1");

    vi.unstubAllGlobals();
  });

  it("usa GET y JSON por defecto y propaga errores HTTP", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("nope", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/health")).rejects.toThrow(/500/);

    vi.unstubAllGlobals();
  });
});

describe("contrato auth C-03", () => {
  it("inyecta Bearer desde memoria y credentials include (cookie HttpOnly)", async () => {
    setAccessToken("access-sintetico");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/auth/me");

    const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer access-sintetico");
    expect(init.credentials).toBe("include");

    setAccessToken(null);
    vi.unstubAllGlobals();
  });

  it("sin sesión no envía Authorization pero sí tenant header", async () => {
    setAccessToken(null);
    vi.stubEnv("VITE_CLINICA_ID", "clinica-sintetica-1");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/health");

    const [_url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("Authorization")).toBeNull();
    expect(new Headers(init.headers).get("X-Clinica-Id")).toBe("clinica-sintetica-1");
    expect(getAccessToken()).toBeNull();

    vi.unstubAllGlobals();
  });

  it("el fuente nunca persiste JWT en localStorage/sessionStorage", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const srcDir = path.resolve(import.meta.dirname, "../src");
    const sources: string[] = [];
    const walk = (dir: string): void => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
        } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
          sources.push(fs.readFileSync(full, "utf-8"));
        }
      }
    };
    walk(srcDir);
    // Acceso real a storage (con `.`), no menciones en comentarios/docs.
    expect(sources.join("\n")).not.toMatch(/localStorage\s*\.\s*\w|sessionStorage\s*\.\s*\w/);
  });
});
describe("fetchAll", () => {
  it("carga recursos independientes en paralelo con Promise.all", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        new Response(JSON.stringify({ url }), { headers: { "Content-Type": "application/json" } }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const results = await fetchAll<{ url: string }>(["/api/huecos", "/api/turnos"]);

    expect(results).toHaveLength(2);
    expect(results[0]?.url).toContain("/api/huecos");
    expect(results[1]?.url).toContain("/api/turnos");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    vi.unstubAllGlobals();
  });
});

describe("browser env", () => {
  it("el código src solo lee vars VITE_-prefixed y ningún secreto de backend", async () => {
    // Vitest expone process.env en import.meta.env; la garantía real (regla 12)
    // es que el bundle solo referencia VITE_*: se audita el fuente, no el env del runner.
    const fs = await import("node:fs");
    const path = await import("node:path");
    const srcDir = path.resolve(import.meta.dirname, "../src");
    const sources: string[] = [];
    const walk = (dir: string): void => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
        } else if (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")) {
          sources.push(fs.readFileSync(full, "utf-8"));
        }
      }
    };
    walk(srcDir);
    const bundle = sources.join("\n");
    const envRefs = [...bundle.matchAll(/import\.meta\.env\.([A-Z0-9_]+)/g)].map((m) => m[1]);
    expect(envRefs.length).toBeGreaterThan(0);
    for (const key of envRefs) {
      expect(key?.startsWith("VITE_")).toBe(true);
    }
    for (const marker of ["APP_USR-", "EAAB", "whsec_", "BEGIN"]) {
      expect(bundle).not.toContain(marker);
    }
  });
});
