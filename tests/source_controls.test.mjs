import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createIcon, createIconButton } from "../web/icons.js";
import { renderSourceControls } from "../web/source_controls.js";

const providers = [
  {
    provider: {
      id: "civitai",
      label: "Civitai",
      filters: [
        {
          name: "site",
          label: "站点",
          kind: "select",
          default: "civitai.com",
          options: [
            { value: "civitai.com", label: "civitai.com" },
            { value: "civitai.red", label: "civitai.red" },
          ],
        },
        { name: "sfw", label: "仅 SFW", kind: "toggle", default: true, options: [] },
        {
          name: "count",
          label: "数量",
          kind: "number",
          default: 12,
          minimum: 1,
          maximum: 100,
          options: [],
        },
      ],
      capabilities: { bulk_download: true },
    },
    status: { available: true, message: "可用" },
  },
  {
    provider: {
      id: "xiaohongshu",
      label: "小红书",
      filters: [],
      capabilities: { bulk_download: false },
    },
    status: { available: false, message: "未连接" },
  },
];

test("来源控件按描述符渲染并发出语义事件", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const events = [];
  const view = renderSourceControls({
    document: dom.window.document,
    providers,
    provider: "civitai",
    filters: { query: "cat" },
    onSourceChange: (value) => events.push(["sourcechange", value]),
    onSearch: (query) => events.push(["search", query]),
    onRefresh: () => events.push(["refresh"]),
    onFilterChange: (name, value) => events.push(["filterchange", name, value]),
  });

  assert.equal(view.root.querySelectorAll("[data-provider]").length, 2);
  assert.equal(view.root.querySelector('[name="site"]').value, "civitai.com");
  assert.equal(view.root.querySelector('[name="sfw"]').checked, true);
  assert.equal(view.root.querySelector('[name="count"]').max, "100");

  view.root.querySelector('[data-provider="xiaohongshu"]').click();
  view.root.querySelector('[name="site"]').value = "civitai.red";
  view.root.querySelector('[name="site"]').dispatchEvent(new dom.window.Event("change"));
  view.root.querySelector('[data-action="search"]').click();
  view.root.querySelector('[data-action="refresh"]').click();

  assert.deepEqual(events, [
    ["sourcechange", "xiaohongshu"],
    ["filterchange", "site", "civitai.red"],
    ["search", "cat"],
    ["refresh"],
  ]);
});

test("图标与图标按钮具备可访问标签且尺寸稳定", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const icon = createIcon(dom.window.document, "search");
  const button = createIconButton(dom.window.document, "refresh", "刷新结果");

  assert.equal(icon.getAttribute("aria-hidden"), "true");
  assert.equal(icon.getAttribute("width"), "18");
  assert.equal(button.title, "刷新结果");
  assert.equal(button.getAttribute("aria-label"), "刷新结果");
});
