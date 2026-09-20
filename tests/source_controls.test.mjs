import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createIcon, createIconButton } from "../web/icons.js";

test("手动修改电影名后片单选择同步，不保留上一部电影", () => {
  const dom = new JSDOM("<body></body>");
  const view = renderSourceControls({
    document: dom.window.document,
    providers: [
      {
        provider: {
          id: "filmgrab",
          label: "FilmGrab",
          search_presets: [{ value: "花样年华", label: "花样年华" }],
        },
        status: { available: true },
      },
    ],
    provider: "filmgrab",
    filters: { query: "花样年华" },
  });
  view.query.value = "低俗小说";
  view.query.dispatchEvent(new dom.window.Event("input"));
  assert.equal(view.root.querySelector('[name="search_preset"]').value, "");
  view.query.value = "花样年华";
  view.query.dispatchEvent(new dom.window.Event("input"));
  assert.equal(view.root.querySelector('[name="search_preset"]').value, "花样年华");
});
import { renderSourceControls } from "../web/source_controls.js";

test("中文片单选择后填充中文搜索词并只发起一次搜索", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const calls = [];
  const view = renderSourceControls({
    document: dom.window.document,
    providers: [
      {
        provider: {
          id: "filmgrab",
          label: "FilmGrab",
          search_placeholder: "中文片名或留空浏览",
          search_presets: [{ value: "花样年华", label: "花样年华 · 东方色彩" }],
        },
      },
    ],
    provider: "filmgrab",
    onSearch: (value) => calls.push(value),
  });
  const select = view.root.querySelector('[name="search_preset"]');
  select.value = "花样年华";
  select.dispatchEvent(new dom.window.Event("change"));
  assert.equal(view.query.value, "花样年华");
  assert.deepEqual(calls, ["花样年华"]);
  assert.match(view.query.placeholder, /中文片名/);
  select.value = "";
  select.dispatchEvent(new dom.window.Event("change"));
  assert.deepEqual(calls, ["花样年华", ""]);
});

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
    status: {
      available: false,
      message: "未连接",
      action: "安装并连接 OpenCLI Chrome 扩展",
    },
  },
];

test("来源导航按用途分组且切换分类不会提前切换来源", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const changes = [];
  const entries = [
    ["civitai", "Civitai"],
    ["wallhaven", "Wallhaven"],
    ["aperture", "Aperture"],
    ["printmag", "PRINT"],
    ["loc", "美国国会图书馆"],
    ["nasa", "NASA"],
    ["filmgrab", "FilmGrab"],
    ["local", "本地历史"],
  ].map(([id, label]) => ({
    provider: { id, label, filters: [], capabilities: {} },
    status: { available: true },
  }));
  const view = renderSourceControls({
    document: dom.window.document,
    providers: entries,
    provider: "aperture",
    onSourceChange: (value) => changes.push(value),
  });

  const groups = [...view.root.querySelectorAll("[data-source-group]")];
  assert.deepEqual(
    groups.map((button) => button.textContent),
    ["AI 与壁纸", "摄影与设计", "艺术馆藏", "电影", "本地"],
  );
  assert.equal(
    view.root.querySelector('[data-source-group="editorial"]').getAttribute("aria-selected"),
    "true",
  );
  assert.deepEqual(
    [...view.root.querySelectorAll("[data-provider]")].map((button) => button.dataset.provider),
    ["aperture", "printmag"],
  );

  view.root.querySelector('[data-source-group="collections"]').click();
  assert.deepEqual(changes, []);
  assert.deepEqual(
    [...view.root.querySelectorAll("[data-provider]")].map((button) => button.dataset.provider),
    ["loc", "nasa"],
  );
  view.root.querySelector('[data-provider="nasa"]').click();
  assert.deepEqual(changes, ["nasa"]);
});

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

test("不可用来源禁用检索并显示恢复操作", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  let checked = 0;
  const view = renderSourceControls({
    document: dom.window.document,
    providers,
    provider: "xiaohongshu",
    onCheck: () => {
      checked += 1;
    },
  });

  assert.equal(view.root.querySelector('[data-action="search"]').disabled, true);
  assert.equal(view.query.disabled, true);
  assert.match(view.root.textContent, /未连接/);
  assert.match(view.root.textContent, /安装并连接 OpenCLI Chrome 扩展/);
  view.root.querySelector('[data-action="check-provider"]').click();
  assert.equal(checked, 1);
});

test("不可用来源即使没有操作文案也能重新检查", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const withoutAction = structuredClone(providers);
  withoutAction[1].status.action = "";
  const view = renderSourceControls({
    document: dom.window.document,
    providers: withoutAction,
    provider: "xiaohongshu",
  });

  assert.ok(view.root.querySelector('[data-action="check-provider"]'));
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

test("小红书来源提供一键连接操作", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  let connected = 0;
  const view = renderSourceControls({
    document: dom.window.document,
    providers,
    provider: "xiaohongshu",
    onConnect: () => {
      connected += 1;
    },
  });

  view.root.querySelector('[data-action="connect-opencli"]').click();
  assert.equal(connected, 1);
});

test("搜索框使用节点历史词而不触发浏览器原生自动填充", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const available = structuredClone(providers);
  available[1].status = { available: true, message: "已连接" };
  const searches = [];
  const view = renderSourceControls({
    document: dom.window.document,
    providers: available,
    provider: "xiaohongshu",
    getRecentQueries: () => ["秋季穿搭", "摄影"],
    onSearch: (query) => searches.push(query),
  });
  dom.window.document.body.append(view.root);

  assert.equal(view.query.autocomplete, "off");
  view.query.dispatchEvent(new dom.window.Event("focus"));
  const suggestion = view.root.querySelector('[data-recent-query="秋季穿搭"]');
  assert.ok(suggestion);
  suggestion.click();

  assert.equal(view.query.value, "秋季穿搭");
  assert.deepEqual(searches, ["秋季穿搭"]);
});

test("Wallhaven 榜单范围仅在热门榜排序时可用", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  const wallhaven = [
    {
      provider: {
        id: "wallhaven",
        label: "Wallhaven",
        filters: [
          {
            name: "sorting",
            label: "排序",
            kind: "select",
            default: "relevance",
            options: [{ value: "relevance", label: "相关度" }],
          },
          {
            name: "top_range",
            label: "榜单范围",
            kind: "select",
            default: "1M",
            options: [{ value: "1M", label: "一月" }],
          },
        ],
        capabilities: {},
      },
      status: { available: true },
    },
  ];

  const inactive = renderSourceControls({
    document: dom.window.document,
    providers: wallhaven,
    provider: "wallhaven",
    filters: { sorting: "relevance" },
  });
  assert.equal(inactive.root.querySelector('[name="top_range"]').disabled, true);

  const active = renderSourceControls({
    document: dom.window.document,
    providers: wallhaven,
    provider: "wallhaven",
    filters: { sorting: "toplist" },
  });
  assert.equal(active.root.querySelector('[name="top_range"]').disabled, false);
});
