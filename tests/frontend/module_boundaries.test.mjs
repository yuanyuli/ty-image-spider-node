import assert from "node:assert/strict";
import test from "node:test";

test("前端子模块导入不会自动注册 ComfyUI 扩展", async () => {
  globalThis.window = {};
  await import("../../web/core/state.js");
  await import("../../web/features/cache/tasks.js");
  assert.equal(window.__TY_IMAGE_SPIDER_REGISTERED__, undefined);
  delete globalThis.window;
});
