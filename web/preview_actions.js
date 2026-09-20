import { createIconButton } from "./icons.js";

export function handlePreviewKey(event, actions) {
  if (
    event.isComposing ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    event.target?.closest?.(
      'input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"]',
    )
  )
    return false;
  const action = { ArrowLeft: actions.previous, ArrowRight: actions.next, ArrowDown: actions.save }[
    event.key
  ];
  if (!action) return false;
  event.preventDefault();
  event.stopImmediatePropagation();
  // 长按保存不重复写盘；左右键仍支持连续浏览。
  if (event.key !== "ArrowDown" || !event.repeat) action();
  return true;
}

export function createPreviewActions(document, actions) {
  const root = document.createElement("div");
  root.className = "tyis-preview-actions";
  const previous = createIconButton(document, "previous", "上一张（←）");
  const next = createIconButton(document, "next", "下一张（→）");
  const save = createIconButton(document, "download", "保存当前图片（↓）");
  const position = document.createElement("span");
  position.className = "tyis-preview-position";
  const hint = document.createElement("span");
  hint.className = "tyis-preview-hint";
  const status = document.createElement("span");
  status.className = "tyis-preview-status";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  previous.addEventListener("click", () => actions.previous?.());
  next.addEventListener("click", () => actions.next?.());
  save.addEventListener("click", () => actions.save?.());
  root.append(previous, position, next, save, hint, status);
  function update(value) {
    previous.disabled = !value.hasPrevious;
    next.disabled = !value.hasNext;
    save.hidden = !value.canSave;
    save.disabled = Boolean(value.saving);
    position.textContent = value.position || "";
    hint.textContent = value.canSave ? "← → 切图 · ↓ 保存" : "← → 切图";
    status.textContent = value.message || "";
  }
  return { root, update };
}
