import assert from "node:assert/strict";
import test from "node:test";

test("前端子模块导入不会自动注册 ComfyUI 扩展", async () => {
  globalThis.window = {};
  await import("../../web/core/state.js");
  await import("../../web/features/cache/tasks.js");
  assert.equal(window.__TY_IMAGE_SPIDER_REGISTERED__, undefined);
  delete globalThis.window;
});

test("根前端入口只组合扩展并保留导出", async () => {
  globalThis.window = { __TY_IMAGE_SPIDER_DISABLE_AUTO_REGISTER__: true };
  const entry = await import("../../web/ty_image_spider.js");
  assert.equal(typeof entry.createImageSpiderExtension, "function");
  delete globalThis.window;
});
