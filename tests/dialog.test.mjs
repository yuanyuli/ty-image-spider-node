import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { openAssetDialog } from "../web/dialog.js";

function detail() {
  return {
    item: {
      provider: "civitai",
      id: "101",
      title: "Cinematic cat",
      author: "alice",
      source_url: "https://civitai.com/images/101",
      prompt: "cinematic cat",
      negative_prompt: "blur",
      metadata: {
        models: [{ type: "model", name: "Base XL" }],
        loras: [{ type: "lora", name: "Detail LoRA" }],
      },
      stats: {},
    },
    images: ["https://image.civitai.com/one.png", "https://image.civitai.com/two.png"],
    content: "",
    workflow: { nodes: [] },
    metadata: {},
  };
}

test("详情弹窗切换图片、复制提示词并恢复先前焦点", async () => {
  const dom = new JSDOM("<!doctype html><body><button id='prior'>先前</button></body>", {
    url: "https://localhost/",
  });
  const document = dom.window.document;
  const copied = [];
  const prior = document.querySelector("#prior");
  prior.focus();

  const view = openAssetDialog({
    document,
    detail: detail(),
    copyText: async (value) => copied.push(value),
  });
  view.overlay.querySelectorAll(".tyis-thumb")[1].click();
  assert.equal(view.mainImage.src, "https://image.civitai.com/two.png");

  view.overlay.querySelector('[data-action="copy-prompt"]').click();
  await Promise.resolve();
  assert.deepEqual(copied, ["cinematic cat"]);

  view.mainImage.click();
  assert.ok(document.querySelector(".tyis-image-viewer"));
  assert.equal(document.querySelector(".tyis-image-viewer-image").src, view.mainImage.src);
  document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(document.querySelector(".tyis-image-viewer"), null);

  document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(document.body.contains(view.overlay), false);
  assert.equal(document.activeElement, prior);
});

test("Civitai 没有公开提示词时给出明确状态", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const value = detail();
  value.item.prompt = undefined;
  value.item.negative_prompt = undefined;
  value.item.has_prompt = false;

  const view = openAssetDialog({ document: dom.window.document, detail: value });

  assert.match(view.overlay.textContent, /该素材未提供公开提示词/);
  view.close();
});

test("小红书详情显示正文、图集和整篇下载操作", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const calls = [];
  const value = detail();
  value.item = {
    ...value.item,
    provider: "xiaohongshu",
    title: "秋季通勤",
    source_url: "https://www.xiaohongshu.com/explore/a?xsec_token=signed",
    prompt: undefined,
  };
  value.content = "三套适合上班的叠穿思路";

  const view = openAssetDialog({
    document: dom.window.document,
    detail: value,
    onDownload: (item) => calls.push(item.id),
  });

  assert.match(view.overlay.textContent, /三套适合上班/);
  assert.match(view.overlay.textContent, /下载整篇/);
  view.overlay.querySelector('[data-action="download"]').click();
  assert.deepEqual(calls, ["101"]);
  view.close();
});

test("Wallhaven 详情显示统计、分类、标签和色板", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const value = detail();
  value.item = {
    provider: "wallhaven",
    id: "zp9vkg",
    author: "wall-user",
    source_url: "https://wallhaven.cc/w/zp9vkg",
    width: 3840,
    height: 2160,
    stats: { views: 2390, favorites: 43 },
    tags: ["mountains", "night"],
    metadata: {
      category: "general",
      colors: ["#000000", "#ffffff"],
      original_source: "https://example.com/original",
    },
  };

  const view = openAssetDialog({ document: dom.window.document, detail: value });

  assert.match(view.overlay.textContent, /2390 浏览/);
  assert.match(view.overlay.textContent, /43 收藏/);
  assert.match(view.overlay.textContent, /general/);
  assert.match(view.overlay.textContent, /mountains/);
  assert.equal(view.overlay.querySelectorAll(".tyis-color-swatch").length, 2);
  assert.equal(view.overlay.querySelector(".tyis-dialog-source").textContent, "WALLHAVEN");
  view.close();
});
