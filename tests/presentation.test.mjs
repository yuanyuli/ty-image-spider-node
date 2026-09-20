import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";
import { renderSourceControls } from "../web/source_controls.js";
import { createGallery } from "../web/gallery.js";
import { openAssetDialog } from "../web/dialog.js";

function source(id, group, order, extra = {}) {
  return {
    provider: {
      id,
      label: `来源${id}`,
      presentation: {
        group_id: group,
        group_label: `分类${group}`,
        group_order: order,
        source_order: order,
        short_label: `标记${id}`,
        detail_label: `详情${id}`,
        cache_description: "本来源缓存规则",
        ...extra,
      },
    },
    status: { available: true },
  };
}

test("任意新来源的分组和组内顺序由描述符决定，隐藏来源不显示", () => {
  const document = new JSDOM("<body/>").window.document;
  const providers = [
    source("b", "design", 20),
    source("a", "design", 10),
    source("c", "art", 30),
    source("hidden", "hidden", 1, { visible: false }),
  ];
  const view = renderSourceControls({ document, providers, provider: "a" });
  assert.deepEqual(
    [...view.root.querySelectorAll(".tyis-source-group")].map((n) => n.textContent),
    ["分类design", "分类art"],
  );
  assert.deepEqual(
    [...view.root.querySelectorAll(".tyis-source-tab")].map((n) => n.dataset.provider),
    ["a", "b"],
  );
  view.root.querySelector('[data-source-group="art"]').click();
  assert.equal(view.root.querySelector(".tyis-source-tab").dataset.provider, "c");
});

test("缩略图、缓存说明、详情标题使用任意新来源的描述符", () => {
  const document = new JSDOM("<body/>").window.document;
  const descriptor = source("new", "design", 10).provider;
  const item = { provider: "new", id: "1", title: "图片", download_mode: "none" };
  const gallery = createGallery({ document, provider: "new", descriptor });
  gallery.render([item]);
  assert.equal(gallery.root.querySelector(".tyis-source-mark").textContent, "标记new");
  assert.equal(gallery.cacheButton.title, "本来源缓存规则");
  const dialog = openAssetDialog({ document, descriptor, detail: { item } });
  assert.equal(dialog.dialog.querySelector(".tyis-dialog-source").textContent, "详情new");
  dialog.close();
});

test("旧描述符无新字段时回退到其他和原始名称", () => {
  const document = new JSDOM("<body/>").window.document;
  const descriptor = { id: "old", label: "旧来源" };
  const controls = renderSourceControls({
    document,
    providers: [{ provider: descriptor }],
    provider: "old",
  });
  assert.equal(controls.root.querySelector(".tyis-source-group").textContent, "其他");
  const gallery = createGallery({ document, provider: "old", descriptor });
  gallery.render([{ provider: "old", id: "1" }]);
  assert.equal(gallery.root.querySelector(".tyis-source-mark").textContent, "旧来源");
});
