import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const names = ["tokens", "workspace", "controls", "gallery", "dialog", "viewer", "video"];

test("样式入口只导入七个职责文件并保留关键选择器", () => {
  const entry = readFileSync("web/ty_image_spider.css", "utf8").trim();
  assert.deepEqual(
    entry.split(/\r?\n/),
    names.map((name) => `@import url("./styles/${name}.css");`),
  );
  const combined = names.map((name) => readFileSync(`web/styles/${name}.css`, "utf8")).join("\n");
  for (const selector of [
    ".tyis-workspace",
    ".tyis-source-groups",
    ".tyis-grid",
    ".tyis-dialog",
    ".tyis-image-viewer",
    ".tyis-video-player",
  ]) {
    assert.equal(combined.includes(selector), true, selector);
  }
});
