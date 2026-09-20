import { createIconButton } from "./icons.js";
import { renderTmdbHelp } from "./tmdb_help.js";

export function openMoviePicker({ document, page }) {
  const priorFocus = document.activeElement;
  const overlay = document.createElement("div");
  overlay.className = "tyis-dialog-backdrop";
  const dialog = document.createElement("section");
  dialog.className = "tyis-dialog tyis-movie-picker";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "选择电影版本");
  const header = document.createElement("header");
  header.className = "tyis-dialog-header";
  const title = document.createElement("h2");
  title.textContent = page.message || "选择电影版本";
  const close = createIconButton(document, "close", "取消选择电影");
  header.append(title, close);
  const list = document.createElement("div");
  list.className = "tyis-movie-list";
  let finish;
  let closed = false;
  const result = new Promise((resolve) => {
    finish = resolve;
  });
  function complete(selection = null) {
    if (closed) return;
    closed = true;
    overlay.remove();
    document.removeEventListener("keydown", onKey, true);
    priorFocus?.focus?.();
    finish(selection);
  }
  for (const choice of page.choices || []) {
    const row = document.createElement("article");
    row.className = "tyis-movie-choice";
    const poster = document.createElement("img");
    poster.alt = `${choice.title} 海报`;
    poster.loading = "lazy";
    if (isAllowed(choice.poster_url, ["image.tmdb.org"])) poster.src = choice.poster_url;
    else poster.hidden = true;
    const text = document.createElement("div");
    for (const [tag, content] of [
      ["strong", choice.title],
      ["span", choice.subtitle],
      ["p", choice.description],
    ]) {
      const line = document.createElement(tag);
      line.textContent = content || "";
      text.append(line);
    }
    const actions = document.createElement("div");
    actions.className = "tyis-movie-choice-actions";
    const select = document.createElement("button");
    select.type = "button";
    select.className = "tyis-primary-button";
    select.textContent = "选择这部电影";
    select.addEventListener("click", () => complete(choice.selection));
    actions.append(select);
    if (isAllowed(choice.source_url, ["www.themoviedb.org", "film-grab.com"])) {
      const source = document.createElement("a");
      source.textContent = "查看资料";
      source.href = choice.source_url;
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      actions.append(source);
    }
    text.append(actions);
    row.append(poster, text);
    list.append(row);
  }
  dialog.append(header, list, renderTmdbHelp(document));
  overlay.append(dialog);
  close.addEventListener("click", () => complete());
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) complete();
  });
  function onKey(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopImmediatePropagation();
      complete();
    }
    if (event.key === "Tab") {
      const focusable = [...dialog.querySelectorAll("button, a, summary")].filter(
        (element) => !element.closest("details:not([open])") || element.tagName === "SUMMARY",
      );
      const first = focusable[0],
        last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }
  document.addEventListener("keydown", onKey, true);
  document.body.append(overlay);
  close.focus();
  return { result, close: () => complete() };
}

function isAllowed(value, hosts) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && hosts.includes(url.hostname);
  } catch (_) {
    return false;
  }
}
