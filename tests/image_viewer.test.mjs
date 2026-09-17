import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { openImageViewer } from "../web/image_viewer.js";

function wheel(window, target, options) {
  const event = new window.WheelEvent("wheel", { bubbles: true, cancelable: true, ...options });
  target.dispatchEvent(event);
  return event;
}

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
