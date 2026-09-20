import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { openImageViewer } from "../web/image_viewer.js";

function wheel(window, target, options) {
  const event = new window.WheelEvent("wheel", { bubbles: true, cancelable: true, ...options });
  target.dispatchEvent(event);
  return event;
}

test("切换全屏图片恢复全图并清除上张的缩放和拖拽", () => {
  const dom = new JSDOM("<body></body>");
  const view = openImageViewer({ document: dom.window.document, src: "https://example.com/a.jpg" });
  wheel(dom.window, view.stage, { deltaY: -120 });
  view.update({ src: "https://example.com/b.jpg", alt: "下一张" });
  assert.match(view.image.src, /b.jpg$/);
  assert.match(view.image.style.transform, /translate\(0px, 0px\) scale\(1\)/);
  assert.equal(view.image.alt, "下一张");
  view.close();
});

test("全屏查看器支持滚轮缩放并可双击复位", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const { document } = dom.window;
  const view = openImageViewer({
    document,
    src: "https://image.civitai.com/example.png",
    alt: "示例图片",
  });

  const event = wheel(dom.window, view.stage, { deltaY: -120, clientX: 400, clientY: 300 });

  assert.equal(event.defaultPrevented, true);
  assert.match(view.image.style.transform, /scale\(1\.2\)/);
  assert.equal(view.overlay.getAttribute("aria-label"), "全屏查看示例图片");

  view.stage.dispatchEvent(new dom.window.MouseEvent("dblclick", { bubbles: true }));
  assert.match(view.image.style.transform, /translate\(0px, 0px\) scale\(1\)/);
  view.close();
});

test("全屏查看器支持指针拖拽、Escape 关闭并恢复焦点", () => {
  const dom = new JSDOM("<!doctype html><body><button id='prior'>先前</button></body>", {
    url: "https://localhost/",
  });
  const { document, PointerEvent = dom.window.MouseEvent } = dom.window;
  const prior = document.querySelector("#prior");
  prior.focus();
  const view = openImageViewer({ document, src: "https://example.com/image.jpg", alt: "图片" });

  view.stage.dispatchEvent(
    new PointerEvent("pointerdown", { bubbles: true, button: 0, clientX: 100, clientY: 100 }),
  );
  document.dispatchEvent(
    new PointerEvent("pointermove", { bubbles: true, clientX: 145, clientY: 125 }),
  );
  document.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));

  assert.match(view.image.style.transform, /translate\(45px, 25px\)/);
  document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(document.body.contains(view.overlay), false);
  assert.equal(document.activeElement, prior);
});

test("全屏查看器约束键盘焦点并在指针取消时停止拖拽", () => {
  const dom = new JSDOM("<!doctype html><body><button id='outside'>外部</button></body>", {
    url: "https://localhost/",
  });
  const { document, PointerEvent = dom.window.MouseEvent } = dom.window;
  const view = openImageViewer({ document, src: "https://example.com/image.jpg", alt: "图片" });
  const buttons = [...view.overlay.querySelectorAll("button")];

  buttons.at(-1).focus();
  document.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }),
  );
  assert.equal(document.activeElement, buttons[0]);
  buttons[0].focus();
  document.dispatchEvent(
    new dom.window.KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    }),
  );
  assert.equal(document.activeElement, buttons.at(-1));

  view.stage.dispatchEvent(
    new PointerEvent("pointerdown", { bubbles: true, button: 0, clientX: 10, clientY: 10 }),
  );
  document.dispatchEvent(new PointerEvent("pointercancel", { bubbles: true }));
  document.dispatchEvent(
    new PointerEvent("pointermove", { bubbles: true, clientX: 80, clientY: 60 }),
  );
  assert.match(view.image.style.transform, /translate\(0px, 0px\)/);
  assert.equal(view.stage.classList.contains("is-dragging"), false);
  view.close();
});
