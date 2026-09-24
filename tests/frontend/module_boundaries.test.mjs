import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = new URL("../../", import.meta.url);

function filesUnder(relativeDirectory, extension) {
  const directory = new URL(relativeDirectory, ROOT);
  if (!existsSync(directory)) return [];
  const result = [];
  const visit = (path) => {
    for (const entry of readdirSync(path, { withFileTypes: true })) {
      const child = join(path, entry.name);
      if (entry.isDirectory()) visit(child);
      else if (extname(entry.name) === extension) result.push(child);
    }
  };
  visit(fileURLToPath(directory));
  return result;
}

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

test("视频 feature 声明边界且不反向导入 app", () => {
  const boundary = new URL("web/features/video/BOUNDARY.md", ROOT);
  assert.equal(existsSync(boundary), true, "缺少视频前端边界声明");
  const files = filesUnder("web/features/video", ".js");
  for (const path of files) {
    const source = readFileSync(path, "utf8");
    assert.doesNotMatch(source, /from\s+["'][^"']*\/app\//);
  }
});

test("通用 UI 不按具体视频来源分支", () => {
  for (const path of filesUnder("web/ui", ".js")) {
    const source = readFileSync(path, "utf8");
    assert.doesNotMatch(source, /["'](?:prelinger|commons-video|nasa-video)["']/);
  }
});
