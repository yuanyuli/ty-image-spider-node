import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { createImageSpiderExtension } from "../web/ty_image_spider.js";

const providers = [
  {
    provider: {
      id: "civitai",
      label: "Civitai",
      filters: [],
      capabilities: { bulk_download: true },
    },
    status: { available: true, message: "就绪" },
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
});
