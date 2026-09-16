import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createGallery } from "../web/gallery.js";

function item(overrides = {}) {
  return {
    provider: "xiaohongshu",
    id: "note-1",
    title: "秋季穿搭",
    author: "小葵",
    preview_url: "https://sns-img-bd.xhscdn.com/a.webp",
    image_count: 1,
    has_prompt: false,
    download_mode: "note",
    stats: { likes: "128" },
    ...overrides,
  };
}

test("小红书画廊隐藏整页下载并显示多图数量", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({
    document: dom.window.document,
    provider: "xiaohongshu",
    capabilities: { bulk_download: false },
  });

  view.render([item({ image_count: 6 })], { next_cursor: null });

  assert.equal(view.bulkDownloadButton.hidden, true);
  assert.match(view.root.textContent, /6 张/);
  assert.equal(view.root.querySelectorAll(".tyis-card").length, 1);
});

test("画廊操作分别发出详情、单项下载、整页下载和下一页事件", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const calls = [];
  const view = createGallery({
    document: dom.window.document,
    provider: "civitai",
    capabilities: { bulk_download: true },
    onOpen: (value) => calls.push(["open", value.id]),
    onDownload: (value) => calls.push(["download", value.id]),
    onDownloadPage: (values) => calls.push(["page", values.length]),
    onNext: (cursor) => calls.push(["next", cursor]),
  });
  view.render([item({ provider: "civitai", id: "101", has_prompt: true })], {
    next_cursor: "cursor-2",
  });

  view.root.querySelector(".tyis-card-media").click();
  view.root.querySelector('[data-action="download"]').click();
  view.bulkDownloadButton.click();
  view.nextButton.click();

  assert.deepEqual(calls, [
    ["open", "101"],
    ["download", "101"],
    ["page", 1],
    ["next", "cursor-2"],
  ]);
});

test("加载、错误和空状态保持画廊稳定结构", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({ document: dom.window.document, provider: "local" });

  view.setLoading();
  assert.equal(view.root.querySelectorAll(".tyis-skeleton").length, 6);
  view.setError("读取失败");
  assert.match(view.root.textContent, /读取失败/);
  view.render([], {});
  assert.match(view.root.textContent, /没有找到素材/);
});
