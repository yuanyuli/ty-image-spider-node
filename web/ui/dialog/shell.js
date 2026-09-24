import { element } from "../../core/dom.js";

export function createDialogShell(document, label) {
  const overlay = element(document, "div", "tyis-dialog-backdrop");
  const dialog = element(document, "section", "tyis-dialog");
  dialog.tabIndex = -1;
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", label || "素材详情");
  return { overlay, dialog };
}
