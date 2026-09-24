import { element } from "../../core/dom.js";
import { createIconButton } from "../icons.js";

export function textSection(document, title, value, copyText, action) {
  const section = sectionWithTitle(document, title);
  const head = section.querySelector(".tyis-detail-section-title");
  const copy = createIconButton(document, "copy", `复制${title}`);
  if (action) copy.dataset.action = action;
  copy.addEventListener("click", async () => copyText(value, document));
  head.append(copy);
  section.append(element(document, "p", "tyis-prompt-copy", value));
  return section;
}

export function codeSection(document, title, value) {
  const details = element(document, "details", "tyis-code-section");
  const summary = element(document, "summary", "", title);
  const code = element(document, "pre", "", JSON.stringify(value, null, 2));
  details.append(summary, code);
  return details;
}

export function sectionWithTitle(document, title) {
  const section = element(document, "section", "tyis-detail-section");
  section.append(element(document, "div", "tyis-detail-section-title", title));
  return section;
}

export async function defaultCopy(value, document) {
  await document.defaultView?.navigator?.clipboard?.writeText(value);
}

export function defaultOpenSource(url, document) {
  document.defaultView?.open(url, "_blank", "noopener,noreferrer");
}
