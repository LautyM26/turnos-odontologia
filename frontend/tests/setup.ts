/** Setup global de Vitest: matchers de jest-dom, cleanup y stubs de APIs que jsdom no trae. */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom no implementa <dialog>.showModal/close ni scrollIntoView.
HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement): void {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement): void {
  this.removeAttribute("open");
  this.dispatchEvent(new Event("close"));
};
Element.prototype.scrollIntoView = function scrollIntoView(): void {};
