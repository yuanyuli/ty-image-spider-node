import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createImageSpiderExtension } from "../web/ty_image_spider.js";

const providers = [
  {
    provider: {
      id: "civitai",
      label: "Civitai",
      filters: [{ name: "sfw", label: "仅 SFW", kind: "toggle", default: true }],
      capabilities: { bulk_download: true },
    },
    status: { available: true, message: "就绪" },
  },
  {
    provider: {
      id: "wallhaven",
      label: "Wallhaven",
      filters: [],
      capabilities: { bulk_download: true },
    },
    status: { available: false, message: "未连接" },
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

test("Are.na 切换精选频道时清除自定义链接", async () => {
  const entries = [
    ...providers,
    {
      provider: {
        id: "arena",
        label: "Are.na",
        filters: [
          {
            name: "category",
            label: "精选频道",
            kind: "select",
            default: "graphic",
            options: [
              { value: "graphic", label: "平面设计" },
              { value: "photography", label: "摄影" },
            ],
          },
        ],
        capabilities: {},
      },
      status: { available: true },
    },
  ];
  const { extension, NodeType, document } = harness((path) =>
    response(path.endsWith("/providers") ? entries : { items: [] }),
  );
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  const root = node.domWidgets[0].element;
  root.querySelector('[data-source-group="editorial"]').click();
  root.querySelector('[data-provider="arena"]').click();
  node.tyImageSpider.state.set({
    filters: { query: "https://www.are.na/user/custom", category: "graphic" },
  });
  const field = root.querySelector('select[name="category"]');
  field.value = "photography";
  field.dispatchEvent(new document.defaultView.Event("change", { bubbles: true }));
  assert.equal(node.tyImageSpider.state.get().filters.query, "");
});

function response(data) {
  return Promise.resolve({
    ok: true,
    status: 200,
    async json() {
      return { ok: true, data };
    },
  });
}

function harness(
  fetchApi = (path) => response(path.endsWith("/providers") ? providers : { items: [] }),
) {
  const dom = new JSDOM("<!doctype html><body></body>", { url: "https://localhost/" });
  const document = dom.window.document;
  const counts = new Map();
  const add = document.addEventListener.bind(document);
  const remove = document.removeEventListener.bind(document);
  document.addEventListener = (type, listener, options) => {
    counts.set(type, (counts.get(type) || 0) + 1);
    add(type, listener, options);
  };
  document.removeEventListener = (type, listener, options) => {
    counts.set(type, Math.max(0, (counts.get(type) || 0) - 1));
    remove(type, listener, options);
  };
  document.listenerCount = (type) => counts.get(type) || 0;

  const app = { graph: { change() {} }, registerExtension() {} };
  const api = { fetchApi };
  const extension = createImageSpiderExtension({ app, api, document });
  class NodeType {
    constructor() {
      this.widgets = [
        {
          name: "state_json",
          value: "{}",
          options: {},
          callback(value) {
            this.value = value;
          },
        },
      ];
      this.domWidgets = [];
      this.size = [480, 720];
    }

    addDOMWidget(name, type, element, options) {
      const entry = { name, type, element, options };
      this.domWidgets.push(entry);
      return entry;
    }

    setSize(value) {
      this.size = value;
    }

    setDirtyCanvas() {}
  }
  return { dom, document, app, api, extension, NodeType };
}

test("重复 configure 不重复安装控件和监听器", async () => {
  const { extension, NodeType, document } = harness();
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();

  node.onNodeCreated();
  await node.tyImageSpider.ready;
  node.onConfigure({});
  node.onConfigure({});

  assert.equal(node.domWidgets.filter((entry) => entry.name === "ty_image_spider").length, 1);
  assert.equal(document.listenerCount("keydown"), 1);
  assert.equal(node.widgets[0].hidden, true);

  node.onRemoved();
  assert.equal(document.listenerCount("keydown"), 0);
});

test("忽略其他工作流误投递到同 ID 节点的图片预览", async () => {
  const { extension, NodeType } = harness();
  NodeType.prototype.onExecuted = function (message) {
    this.imgs = message.images;
    this.imageIndex = 0;
  };
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;

  node.onExecuted({ images: [{ filename: "foreign-workflow.png" }] });

  assert.equal(node.imgs, undefined);
  assert.equal(node.imageIndex, undefined);
});

test("素材源响应前同步显示初始组件骨架", async () => {
  let resolveProviders;
  const fetchApi = (path) => {
    if (path.endsWith("/providers")) {
      return new Promise((resolve) => {
        resolveProviders = resolve;
      });
    }
    return response({ items: [] });
  };
  const { extension, NodeType } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();

  node.onNodeCreated();

  const root = node.domWidgets[0].element;
  assert.match(root.textContent, /正在加载素材源/);
  assert.ok(root.querySelector(".tyis-controls-loading"));
  assert.ok(root.querySelector(".tyis-gallery"));
  assert.equal(root.querySelectorAll(".tyis-skeleton").length, 6);

  resolveProviders(await response(providers));
  await node.tyImageSpider.ready;
});

test("素材源列表读取失败时保留错误组件", async () => {
  const { extension, NodeType } = harness(() =>
    Promise.resolve({
      ok: false,
      status: 500,
      async json() {
        return { ok: false, error: { message: "素材源读取失败" } };
      },
    }),
  );
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();

  node.onNodeCreated();
  await node.tyImageSpider.ready;

  const root = node.domWidgets[0].element;
  assert.match(root.textContent, /素材源读取失败/);
  assert.ok(root.querySelector('[data-action="retry-providers"]'));
});

test("后发素材源检查结果不会被较慢的旧请求覆盖", async () => {
  const pending = [];
  let call = 0;
  const fetchApi = (path) => {
    if (!path.endsWith("/providers")) return response({ items: [] });
    call += 1;
    if (call === 1) return response(providers);
    return new Promise((resolve) => pending.push(resolve));
  };
  const { extension, NodeType } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;

  node.tyImageSpider.checkProviders();
  node.tyImageSpider.checkProviders();
  const available = structuredClone(providers);
  available[1].status = { available: true, message: "已连接" };
  pending[1](await response(available));
  await Promise.resolve();
  pending[0](await response(providers));
  await Promise.all(pending.map(() => Promise.resolve()));

  await new Promise((resolve) => setTimeout(resolve, 0));
  const source = node.domWidgets[0].element.querySelector('[data-provider="wallhaven"]');
  source.click();
  assert.match(node.domWidgets[0].element.textContent, /已连接/);
  assert.equal(node.domWidgets[0].element.querySelector('[data-action="search"]').disabled, false);
});

test("后发搜索结果不会被较慢的旧请求覆盖", async () => {
  const pending = [];
  const fetchApi = (path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search")) {
      return new Promise((resolve) => pending.push(resolve));
    }
    return response({});
  };
  const { extension, NodeType } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;

  const oldSearch = node.tyImageSpider.search();
  const newSearch = node.tyImageSpider.search();
  pending[1]({
    ok: true,
    status: 200,
    async json() {
      return { ok: true, data: { items: [{ provider: "civitai", id: "new" }] } };
    },
  });
  await newSearch;
  pending[0]({
    ok: true,
    status: 200,
    async json() {
      return { ok: true, data: { items: [{ provider: "civitai", id: "old" }] } };
    },
  });
  await oldSearch;

  assert.equal(node.tyImageSpider.state.get().items[0].id, "new");
});

test("配置恢复普通来源结果并清理小红书持久结果", async () => {
  const { extension, NodeType } = harness();
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.widgets[0].value = JSON.stringify({
    provider: "civitai",
    filters: { query: "cat" },
    items: [{ provider: "civitai", id: "101" }],
  });

  node.onNodeCreated();
  await node.tyImageSpider.ready;
  node.onConfigure({});

  assert.equal(node.tyImageSpider.state.get().items[0].id, "101");
  node.widgets[0].value = JSON.stringify({
    provider: "xiaohongshu",
    filters: { query: "穿搭" },
    items: [{ provider: "xiaohongshu", id: "secret" }],
  });
  node.onConfigure({});
  assert.deepEqual(node.tyImageSpider.state.get().items, []);
  assert.equal(node.tyImageSpider.state.get().provider, "civitai");
  assert.equal(node.domWidgets[0].element.querySelector('[data-provider="xiaohongshu"]'), null);
});

test("旧工作流恢复时重新检索以恢复提示词角标和分页游标", async () => {
  let searches = 0;
  const { extension, NodeType } = harness((path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search")) {
      searches += 1;
      return response({
        items: [
          {
            provider: "civitai",
            id: "22566974",
            has_prompt: true,
            prompt: "prompt from restored search",
            preview_url: "https://image.civitai.com/22566974.png",
          },
        ],
        next_cursor: "cursor-2",
      });
    }
    return response({});
  });
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.widgets[0].value = JSON.stringify({
    provider: "civitai",
    filters: { query: "" },
    items: [{ provider: "civitai", id: "22566974", has_prompt: false }],
  });
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  node.onConfigure({});
  await new Promise((resolve) => setTimeout(resolve, 0));

  const root = node.domWidgets[0].element;
  assert.equal(searches, 1);
  assert.match(root.querySelector(".tyis-prompt-badge").textContent, /提示词/);
  assert.equal(root.querySelector('[aria-label="下一页"]').hidden, false);
});

test("切换来源后恢复各自已经加载的图片", async () => {
  const { extension, NodeType } = harness();
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  node.tyImageSpider.state.set({
    items: [{ provider: "civitai", id: "c-1" }],
    filters: { query: "cat" },
  });
  node.tyImageSpider.render();

  node.domWidgets[0].element.querySelector('[data-provider="wallhaven"]').click();
  node.domWidgets[0].element.querySelector('[data-provider="civitai"]').click();

  assert.equal(node.tyImageSpider.state.get().items[0].id, "c-1");
});

test("改变非文本筛选项会立即发起新检索", async () => {
  let searches = 0;
  const fetchApi = (path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search")) {
      searches += 1;
      return response({ items: [] });
    }
    return response({});
  };
  const { extension, NodeType, dom } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  const checkbox = node.domWidgets[0].element.querySelector('[name="sfw"]');
  checkbox.checked = false;
  checkbox.dispatchEvent(new dom.window.Event("change"));
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(searches, 1);
});

test("输入关键词时不反复写入 ComfyUI 工作流", async () => {
  const { extension, NodeType, app, dom } = harness();
  let graphChanges = 0;
  app.graph.change = () => {
    graphChanges += 1;
  };
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;

  const query = node.domWidgets[0].element.querySelector('[name="query"]');
  query.value = "秋";
  query.dispatchEvent(new dom.window.Event("input"));
  query.value = "秋季穿搭";
  query.dispatchEvent(new dom.window.Event("input"));

  assert.equal(graphChanges, 0);
  assert.equal(node.tyImageSpider.state.get().filters.query, "秋季穿搭");
  await node.tyImageSpider.search("秋季穿搭");
  assert.equal(graphChanges > 0, true);
});

test("翻页控件支持返回上一页并恢复游标历史", async () => {
  const requests = [];
  const fetchApi = (path, options = {}) => {
    if (path.endsWith("/providers")) return response(providers);
    if (!path.endsWith("/search")) return response({});
    const body = JSON.parse(options.body);
    requests.push(body.cursor ?? null);
    if (body.cursor === "cursor-2") {
      return response({
        items: [{ provider: "civitai", id: "page-2" }],
        next_cursor: "cursor-3",
      });
    }
    return response({
      items: [{ provider: "civitai", id: "page-1" }],
      next_cursor: "cursor-2",
    });
  };
  const { extension, NodeType } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;

  await node.tyImageSpider.search();
  const root = node.domWidgets[0].element;
  root.querySelector(".tyis-gallery .tyis-subtle-button:last-child").click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(node.tyImageSpider.state.get().items[0].id, "page-2");
  assert.equal(root.querySelector('[aria-label="上一页"]')?.hidden, false);

  root.querySelector('[aria-label="上一页"]').click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(node.tyImageSpider.state.get().items[0].id, "page-1");
  assert.deepEqual(requests, [null, "cursor-2", null]);
});

test("翻页请求失败时保留当前卡片和翻页入口", async () => {
  let searches = 0;
  const fetchApi = (path, options = {}) => {
    if (path.endsWith("/providers")) return response(providers);
    if (!path.endsWith("/search")) return response({});
    searches += 1;
    if (searches === 3) {
      return Promise.resolve({
        ok: false,
        status: 500,
        async json() {
          return { ok: false, error: { message: "服务器处理请求时发生错误" } };
        },
      });
    }
    const cursor = JSON.parse(options.body).cursor;
    return response({
      items: [{ provider: "civitai", id: cursor ? "page-2" : "page-1" }],
      next_cursor: cursor ? "cursor-3" : "cursor-2",
    });
  };
  const { extension, NodeType } = harness(fetchApi);
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  await node.tyImageSpider.search();
  await node.tyImageSpider.search(undefined, "cursor-2", false, "next");

  const root = node.domWidgets[0].element;
  root.querySelector('[aria-label="上一页"]').click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(root.textContent, /服务器处理请求时发生错误/);
  assert.match(root.textContent, /page-2/);
  assert.equal(root.querySelector('[aria-label="上一页"]').hidden, false);
  assert.equal(root.querySelector('[aria-label="下一页"]').hidden, false);
});

test("卡片立即打开预览，关闭后迟到详情不会重开", async () => {
  let finishDetail;
  const { extension, NodeType, document } = harness((path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search"))
      return response({
        items: [
          { provider: "civitai", id: "101", preview_url: "https://image.civitai.com/101.png" },
        ],
      });
    return new Promise((resolve) => {
      finishDetail = resolve;
    });
  });
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  await node.tyImageSpider.search();
  node.domWidgets[0].element.querySelector(".tyis-card-media").click();
  assert.ok(document.querySelector(".tyis-dialog"));
  document.querySelector('[aria-label="关闭详情"]').click();
  finishDetail(await response({ item: { provider: "civitai", id: "101", prompt: "late prompt" } }));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(document.querySelector(".tyis-dialog"), null);
});

test("详情返回提示词后同步更新当前缩略图角标", async () => {
  let finishDetail;
  const { extension, NodeType } = harness((path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search")) {
      return response({
        items: [
          {
            provider: "civitai",
            id: "101",
            has_prompt: false,
            preview_url: "https://image.civitai.com/101.png",
          },
        ],
      });
    }
    return new Promise((resolve) => {
      finishDetail = resolve;
    });
  });
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  await node.tyImageSpider.search();
  const root = node.domWidgets[0].element;
  root.querySelector(".tyis-card-media").click();
  finishDetail(
    await response({
      item: {
        provider: "civitai",
        id: "101",
        has_prompt: true,
        prompt: "detail prompt",
      },
    }),
  );
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(root.querySelector(".tyis-prompt-badge").textContent, "提示词");
});

test("下载完成后显示可见的绝对保存路径", async () => {
  const { extension, NodeType } = harness((path) => {
    if (path.endsWith("/providers")) return response(providers);
    if (path.endsWith("/search")) {
      return response({
        items: [
          {
            provider: "civitai",
            id: "101",
            preview_url: "https://image.civitai.com/101.png",
            download_mode: "single",
          },
        ],
      });
    }
    if (path.endsWith("/download")) {
      return response({
        files: ["ty-image-spider/civitai/101.png"],
        output_root: "C:\\path\\to\\ComfyUI\\output\\ty-node",
        message: "图片已下载",
      });
    }
    return response({});
  });
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  const node = new NodeType();
  node.onNodeCreated();
  await node.tyImageSpider.ready;
  await node.tyImageSpider.search();
  const root = node.domWidgets[0].element;
  root.querySelector('[data-action="download"]').click();
  await new Promise((resolve) => setTimeout(resolve, 0));

  const location = root.querySelector(".tyis-download-location");
  assert.equal(location.hidden, false);
  assert.match(root.querySelector(".tyis-activity").textContent, /图片已下载/);
  assert.match(
    location.textContent,
    /C:\\path\\to\\ComfyUI\\output\\ty-node\\ty-image-spider\\civitai\\101\.png/,
  );
});
