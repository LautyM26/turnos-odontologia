import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("setup de tests", () => {
  it("renderiza y usa matchers de jest-dom", () => {
    render(<button type="button">Hola</button>);
    expect(screen.getByRole("button", { name: "Hola" })).toBeInTheDocument();
  });

  it("limpia el DOM entre tests (cleanup)", () => {
    expect(screen.queryByRole("button", { name: "Hola" })).not.toBeInTheDocument();
  });

  it("stubs de dialog y scrollIntoView", () => {
    const d = document.createElement("dialog");
    d.showModal();
    expect(d.open).toBe(true);
    d.close();
    expect(d.open).toBe(false);
    expect(() => document.body.scrollIntoView()).not.toThrow();
  });
});
