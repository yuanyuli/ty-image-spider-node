import { createIconButton } from "./icons.js";
import { createPreviewActions, handlePreviewKey } from "./preview_actions.js";

const MIN_SCALE = 1;
const MAX_SCALE = 8;

export function openImageViewer({
  document,
  src,
  alt = "图片",
  onClose = () => {},
  actions,
  controls,
}) {
  const priorFocus = document.activeElement;
  const overlay = document.createElement("div");
  overlay.className = "tyis-image-viewer";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", `全屏查看${alt}`);

  const stage = document.createElement("div");
  stage.className = "tyis-image-viewer-stage";
  const image = document.createElement("img");
  image.className = "tyis-image-viewer-image";
  image.src = src;
  image.alt = alt;
  image.draggable = false;
  stage.append(image);

  const toolbar = document.createElement("div");
  toolbar.className = "tyis-image-viewer-toolbar";
  const resetButton = createIconButton(document, "reset", "复位图片");
  const closeButton = createIconButton(document, "close", "关闭全屏图片");
  resetButton.addEventListener("click", reset);
  closeButton.addEventListener("click", close);
  toolbar.append(resetButton, closeButton);
  overlay.append(stage, toolbar);
  const previewActions = actions ? createPreviewActions(document, actions) : null;
  if (previewActions) {
    previewActions.update(controls || {});
    overlay.append(previewActions.root);
  }
  document.body.append(overlay);

  let scale = MIN_SCALE;
  let x = 0;
  let y = 0;
  let drag = null;
  let closed = false;
  render();

  function render() {
    image.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
    stage.classList.toggle("is-zoomed", scale > MIN_SCALE);
    stage.classList.toggle("is-dragging", drag !== null);
  }

  function reset() {
    scale = MIN_SCALE;
    x = 0;
    y = 0;
    drag = null;
    render();
  }

  function update(value) {
    if (closed) return;
    if (value.src && value.src !== image.getAttribute("src")) {
      image.src = value.src;
      reset();
    }
    if (value.alt !== undefined) {
      image.alt = value.alt;
      overlay.setAttribute("aria-label", `全屏查看${value.alt}`);
    }
    if (value.controls) previewActions?.update(value.controls);
  }

  function onWheel(event) {
    event.preventDefault();
    event.stopPropagation();
    const nextScale = Math.min(
      MAX_SCALE,
      Math.max(MIN_SCALE, scale * (event.deltaY < 0 ? 1.2 : 1 / 1.2)),
    );
    const rect = stage.getBoundingClientRect();
    const focusX = event.clientX - rect.left - rect.width / 2;
    const focusY = event.clientY - rect.top - rect.height / 2;
    const ratio = nextScale / scale;
    x = focusX - (focusX - x) * ratio;
    y = focusY - (focusY - y) * ratio;
    scale = nextScale;
    if (scale === MIN_SCALE) {
      x = 0;
      y = 0;
    }
    render();
  }

  function onPointerDown(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    drag = { x: event.clientX - x, y: event.clientY - y };
    render();
  }

  function onPointerMove(event) {
    if (!drag) return;
    event.preventDefault();
    x = event.clientX - drag.x;
    y = event.clientY - drag.y;
    render();
  }

  function onPointerUp() {
    drag = null;
    render();
  }

  function onKeyDown(event) {
    if (actions && handlePreviewKey(event, actions)) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopImmediatePropagation();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...overlay.querySelectorAll("button")].filter(
      (node) => !node.disabled && !node.hidden,
    );
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener("pointermove", onPointerMove, true);
    document.removeEventListener("pointerup", onPointerUp, true);
    document.removeEventListener("pointercancel", onPointerUp, true);
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
    if (priorFocus?.isConnected) priorFocus.focus();
    onClose();
  }

  stage.addEventListener("wheel", onWheel, { passive: false });
  stage.addEventListener("pointerdown", onPointerDown);
  stage.addEventListener("dblclick", reset);
  document.addEventListener("pointermove", onPointerMove, true);
  document.addEventListener("pointerup", onPointerUp, true);
  document.addEventListener("pointercancel", onPointerUp, true);
  document.addEventListener("keydown", onKeyDown, true);
  closeButton.focus();

  return { overlay, stage, image, close, reset, update };
}
