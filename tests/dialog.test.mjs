import { sourceDescriptor } from "./provider-fixtures.mjs";
import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { openAssetDialog } from "../web/dialog.js";

function key(document, value, options = {}, target = document) {
  const event = new document.defaultView.KeyboardEvent("keydown", {
    key: value,
    bubbles: true,
    cancelable: true,
    ...options,
  });
  target.dispatchEvent(event);
  return event;
}

test("详情和全屏方向键切图同步，保存的始终是当前图片", async () => {
  const document = new JSDOM("<body></body>").window.document;
  const saved = [];
  const view = openAssetDialog({
    document,
    detail: detail(),
    onDownloadImage: async (item, index) => {
      saved.push([item.id, index]);
      return "已保存：output/ty-node/current.png";
    },
  });
  assert.equal(key(document, "ArrowRight").defaultPrevented, true);
  assert.match(view.mainImage.src, /two.png$/);
  view.mainImage.click();
  key(document, "ArrowLeft");
  assert.match(document.querySelector(".tyis-image-viewer-image").src, /one.png$/);
  assert.match(view.mainImage.src, /one.png$/);
  key(document, "ArrowDown");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(saved, [["101", 0]]);
  assert.match(document.querySelector(".tyis-image-viewer").textContent, /已保存/);
  key(document, "Escape");
  key(document, "ArrowRight");
  key(document, "ArrowDown");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(saved, [
    ["101", 0],
    ["101", 1],
  ]);
  view.close();
  key(document, "ArrowDown");
  assert.equal(saved.length, 2);
});

test("图集边界进入相邻作品并保留全屏状态，普通首尾不循环", () => {
  const document = new JSDOM("<body></body>").window.document;
  let next;
  const view = openAssetDialog({
    document,
    detail: detail(),
    onNextItem: (fullscreen) => {
      next = fullscreen;
    },
  });
  key(document, "ArrowLeft");
  assert.match(view.mainImage.src, /one.png$/);
  view.selectImage(1);
  view.mainImage.click();
  key(document, "ArrowRight");
  assert.equal(next, true);
  view.close();
});

test("迟到详情不会把已选第二张重置为第一张，全屏同步更新原图", () => {
  const document = new JSDOM("<body></body>").window.document;
  const view = openAssetDialog({ document, detail: detail() });
  view.selectImage(1);
  view.mainImage.click();
  view.update({ ...detail(), images: ["https://example.com/a.jpg", "https://example.com/b.jpg"] });
  assert.match(view.mainImage.src, /b.jpg$/);
  assert.match(document.querySelector(".tyis-image-viewer-image").src, /b.jpg$/);
  view.close();
});

test("按住保存键和下载进行中不重复保存，失败可重试，输入区不拦截方向键", async () => {
  const document = new JSDOM("<body></body>").window.document;
  let rejectSave;
  let calls = 0;
  const view = openAssetDialog({
    document,
    detail: detail(),
    onDownloadImage: () => {
      calls++;
      return new Promise((_, reject) => {
        rejectSave = reject;
      });
    },
  });
  for (const tag of ["input", "textarea", "select", "div"]) {
    const input = document.createElement(tag);
    if (tag === "div") input.setAttribute("contenteditable", "true");
    view.dialog.append(input);
    assert.equal(key(document, "ArrowDown", {}, input).defaultPrevented, false);
  }
  key(document, "ArrowDown", { repeat: true });
  assert.equal(calls, 0);
  key(document, "ArrowDown");
  key(document, "ArrowDown");
  assert.equal(calls, 1);
  rejectSave(new Error("磁盘写入失败"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(view.dialog.textContent, /磁盘写入失败/);
  key(document, "ArrowDown");
  assert.equal(calls, 2);
  rejectSave(new Error("重试失败"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.close();
});

test("专题图集显示下载范围并更新说明和缩略图", () => {
  const document = new JSDOM("<body></body>").window.document;
  const item = {
    provider: "colossal",
    id: "42",
    kind: "editorial",
    download_mode: "gallery",
    title: "摄影专题",
    metadata: { description: "初始说明" },
  };
  let downloaded;
  const view = openAssetDialog({
    document,
    detail: { item, images: ["https://www.thisiscolossal.com/one.jpg"] },
    onDownload: (value) => (downloaded = value),
  });
  assert.equal(view.dialog.querySelector('[data-action="download"]').textContent, "下载图集");
  view.update({
    item,
    content: "摄影师与作品介绍",
    images: ["https://www.thisiscolossal.com/one.jpg", "https://www.thisiscolossal.com/two.jpg"],
  });
  assert.match(view.dialog.textContent, /摄影师与作品介绍/);
  view.dialog.querySelector('[aria-label="查看第 2 张图片"]').click();
  assert.match(view.dialog.querySelector(".tyis-detail-image").src, /two.jpg$/);
  view.dialog.querySelector('[data-action="download"]').click();
  assert.equal(downloaded, item);
  view.close();
});

test("馆藏详情显示作品资料，迟到的说明更新不会被当作提示词", () => {
  const document = new JSDOM("<body></body>").window.document;
  const item = {
    provider: "vam",
    id: "O499248",
    kind: "collection",
    title: "Upton Pyne",
    author: "Jem Southam",
    metadata: {
      collection: "V&A",
      category: "Photograph",
      rights: "图片使用条件",
      original_url: "https://framemark.vam.ac.uk/collections/image/full/full/0/default.jpg",
    },
  };
  const view = openAssetDialog({ document, detail: { item, images: [] } });
  assert.match(view.dialog.textContent, /馆藏资料/);
  assert.match(view.dialog.textContent, /图片使用条件/);
  assert.equal(view.dialog.querySelector(".tyis-prompt-unavailable"), null);
  view.update({
    item: { ...item, metadata: { ...item.metadata, medium: "photographic paper" } },
    content: "Landscape study",
    images: [item.metadata.original_url],
  });
  assert.match(view.dialog.textContent, /Landscape study/);
  assert.match(view.dialog.textContent, /photographic paper/);
  view.close();
});

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

  const view = openAssetDialog({
    document: dom.window.document,
    detail: value,
    descriptor: sourceDescriptor(value.item.provider),
  });

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

  const view = openAssetDialog({
    document: dom.window.document,
    detail: value,
    descriptor: sourceDescriptor(value.item.provider),
  });

  assert.match(view.overlay.textContent, /2390 浏览/);
  assert.match(view.overlay.textContent, /43 收藏/);
  assert.match(view.overlay.textContent, /general/);
  assert.match(view.overlay.textContent, /mountains/);
  assert.equal(view.overlay.querySelectorAll(".tyis-color-swatch").length, 2);
  assert.equal(view.overlay.querySelector(".tyis-dialog-source").textContent, "WALLHAVEN");
  view.close();
});

test("新增来源详情显示明确来源名", () => {
  const expected = {
    aperture: "APERTURE",
    printmag: "PRINT MAGAZINE",
    nasa: "NASA IMAGE LIBRARY",
  };
  for (const [provider, label] of Object.entries(expected)) {
    const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
    const value = detail();
    value.item = { ...value.item, provider };

    const view = openAssetDialog({
      document: dom.window.document,
      detail: value,
      descriptor: sourceDescriptor(value.item.provider),
    });

    assert.equal(view.overlay.querySelector(".tyis-dialog-source").textContent, label);
    view.close();
  }
});

test("详情异步更新保留已打开的全屏查看器", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const value = detail();
  const view = openAssetDialog({
    document: dom.window.document,
    detail: value,
    descriptor: sourceDescriptor(value.item.provider),
  });
  view.mainImage.click();
  const viewer = dom.window.document.querySelector(".tyis-image-viewer");
  view.update({ ...value, item: { ...value.item, prompt: "补全后的提示词" } });
  assert.equal(dom.window.document.querySelector(".tyis-image-viewer"), viewer);
  assert.match(view.overlay.textContent, /补全后的提示词/);
  view.close();
});

test("详情异步返回原图时替换预览并更新图集", () => {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const value = detail();
  const view = openAssetDialog({
    document: dom.window.document,
    detail: value,
    descriptor: sourceDescriptor(value.item.provider),
  });
  view.update({
    ...value,
    images: ["https://example.com/original.jpg", "https://example.com/second.jpg"],
  });
  assert.equal(view.mainImage.src, "https://example.com/original.jpg");
  view.selectImage(1);
  assert.equal(view.mainImage.src, "https://example.com/second.jpg");
  view.close();
});
