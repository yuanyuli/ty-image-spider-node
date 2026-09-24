import { element } from "../../core/dom.js";

export function emptyState(document, title, note) {
  const root = element(document, "div", "tyis-empty");
  root.append(element(document, "strong", "", title));
  if (note) root.append(element(document, "span", "", note));
  return root;
}
