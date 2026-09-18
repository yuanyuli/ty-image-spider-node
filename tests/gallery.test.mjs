import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
  const style = dom.window.document.createElement("style");
  style.textContent = readFileSync(new URL("../web/ty_image_spider.css", import.meta.url), "utf8");
  dom.window.document.head.append(style);
  const view = createGallery({
    document: dom.window.document,
    provider: "xiaohongshu",
    capabilities: { bulk_download: false },
  });

  view.render([item({ image_count: 6 })], { next_cursor: null });
  dom.window.document.body.append(view.root);

  assert.equal(view.bulkDownloadButton.hidden, true);
  assert.equal(dom.window.getComputedStyle(view.bulkDownloadButton).display, "none");
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

test("下载按钮不嵌套在可点击媒体按钮中", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({
    document: dom.window.document,
    provider: "civitai",
    capabilities: { bulk_download: true },
  });
  view.render([item({ provider: "civitai", id: "101" })]);

  const media = view.root.querySelector(".tyis-card-media");
  assert.equal(media.tagName, "DIV");
  assert.equal(media.querySelector('[data-action="download"]').tagName, "BUTTON");
});

test("翻页加载时保留下一页入口并在结果返回后恢复可用", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({ document: dom.window.document, provider: "civitai" });
  view.render([item({ id: "101" })], { next_cursor: "cursor-2" });
  view.setLoading(true);
  assert.equal(view.nextButton.hidden, false);
  assert.equal(view.nextButton.disabled, true);
  view.render([item({ id: "102" })], { next_cursor: "cursor-3" });
  assert.equal(view.nextButton.disabled, false);
  assert.equal(view.nextButton.hidden, false);
});

test("画廊显示并触发上一页", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const calls = [];
  const view = createGallery({
    document: dom.window.document,
    provider: "civitai",
    onPrevious: () => calls.push("previous"),
  });
  view.render([item({ id: "102" })], { has_previous: true });

  assert.equal(view.previousButton.hidden, false);
  view.previousButton.click();
  assert.deepEqual(calls, ["previous"]);
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

test("来源不可用状态不会伪装成空搜索结果", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({ document: dom.window.document, provider: "xiaohongshu" });

  view.setUnavailable("OpenCLI Chrome 扩展未连接", "安装扩展后重新检查");

  assert.match(view.root.textContent, /来源不可用/);
  assert.match(view.root.textContent, /OpenCLI Chrome 扩展未连接/);
  assert.match(view.root.textContent, /安装扩展后重新检查/);
  assert.doesNotMatch(view.root.textContent, /没有找到素材/);
});

test("Wallhaven 卡片显示来源标记与收藏数据", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({ document: dom.window.document, provider: "wallhaven" });

  view.render([
    item({
      provider: "wallhaven",
      id: "zp9vkg",
      author: "wall-user",
      stats: { views: 2390, favorites: 43 },
    }),
  ]);

  assert.equal(view.root.querySelector(".tyis-source-mark").textContent, "W");
  assert.match(view.root.textContent, /43 收藏/);
});

test("Civitai 卡片在图片区域醒目标记提示词状态", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const view = createGallery({ document: dom.window.document, provider: "civitai" });

  view.render([
    item({ provider: "civitai", id: "with", has_prompt: true }),
    item({ provider: "civitai", id: "without", has_prompt: false }),
  ]);

  const badges = [...view.root.querySelectorAll(".tyis-prompt-badge")];
  assert.deepEqual(
    badges.map((badge) => badge.textContent),
    ["提示词", "无提示词"],
  );
  assert.equal(badges[0].classList.contains("has-prompt"), true);
  assert.equal(badges[1].classList.contains("is-empty"), true);
});
