import { createApiClient } from "./api.js";
import { openAssetDialog } from "./dialog.js";
import { createGallery } from "./gallery.js";
import { renderSourceControls } from "./source_controls.js";
import { createRequestGuard, createSpiderState, serializeWorkflowState } from "./state.js";

const INSTALLED = Symbol("tyImageSpiderInstalled");

export function createImageSpiderExtension({ app, api, document }) {
  return {
    name: "ty.image.spider",
    async beforeRegisterNodeDef(nodeType, nodeData) {
      if (nodeData.name !== "TyImageSpider" || nodeType.prototype[INSTALLED]) return;
      nodeType.prototype[INSTALLED] = true;
      installLifecycle(nodeType, { app, api, document });
    },
  };
}

function installLifecycle(nodeType, dependencies) {
  const created = nodeType.prototype.onNodeCreated;
  const configured = nodeType.prototype.onConfigure;
  const removed = nodeType.prototype.onRemoved;
  nodeType.prototype.onNodeCreated = function (...args) {
    const result = created?.apply(this, args);
    mountNode(this, dependencies);
    return result;
  };
  nodeType.prototype.onConfigure = function (...args) {
    const result = configured?.apply(this, args);
    mountNode(this, dependencies).restore();
    return result;
  };
  nodeType.prototype.onRemoved = function (...args) {
    this.tyImageSpider?.dispose();
    this.tyImageSpider = null;
    return removed?.apply(this, args);
  };
}

function mountNode(node, { app, api, document }) {
  if (node.tyImageSpider) return node.tyImageSpider;
  ensureStyles(document);
  const stateWidget = node.widgets?.find((widget) => widget.name === "state_json");
  hideWidget(stateWidget);
  const state = createSpiderState();
  const guard = createRequestGuard();
  const providerGuard = createRequestGuard();
  const client = createApiClient(api.fetchApi.bind(api));
  const root = element(document, "div", "tyis-workspace");
  const masthead = element(document, "header", "tyis-masthead");
  const brand = element(document, "div", "tyis-brand");
  brand.append(
    element(document, "strong", "", "TY Image Spider"),
    element(document, "span", "", "素材审片台"),
  );
  const activity = element(document, "span", "tyis-activity", "待命");
  masthead.append(brand, activity);
  const controlsHost = element(document, "div", "tyis-controls-host");
  const galleryHost = element(document, "div", "tyis-gallery-host");
  root.append(masthead, controlsHost, galleryHost);
  node.addDOMWidget?.("ty_image_spider", "TY_IMAGE_SPIDER", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => 620,
  });
  resizeNode(node);

  let providers = [];
  let gallery = null;
  let dialog = null;
  let disposed = false;
  renderInitialState();
  const onKeyDown = (event) => {
    if (document.querySelector(".tyis-image-viewer")) return;
    if (event.key === "Escape" && dialog) dialog.close();
  };
  document.addEventListener("keydown", onKeyDown, true);

  const controller = {
    state,
    ready: null,
    search,
    checkProviders: loadProviders,
    restore,
    dispose,
  };
  node.tyImageSpider = controller;
  controller.ready = loadProviders();
  return controller;

  async function loadProviders() {
    const ticket = providerGuard.begin();
    try {
      const nextProviders = await client.requestJson("/ty-image-spider/providers");
      if (!providerGuard.isCurrent(ticket) || disposed) return;
      providers = nextProviders;
      const current = providers.some((entry) => entry.provider.id === state.get().provider)
        ? state.get().provider
        : providers[0]?.provider.id || "civitai";
      state.set({ provider: current });
      renderControls();
      renderGallery();
      setActivity("就绪");
    } catch (error) {
      if (!providerGuard.isCurrent(ticket) || disposed) return;
      setActivity(error.message || "素材源读取失败", true);
      renderProviderError(error);
    }
  }

  function renderInitialState() {
    setActivity("正在加载素材源");
    const controls = element(document, "section", "tyis-controls tyis-controls-loading");
    const sourceBar = element(document, "div", "tyis-source-bar");
    sourceBar.append(
      element(document, "strong", "", "正在加载素材源"),
      element(document, "span", "tyis-source-status", "连接中"),
    );
    const searchPlaceholder = element(document, "div", "tyis-search-placeholder");
    controls.append(sourceBar, searchPlaceholder);
    controlsHost.replaceChildren(controls);
    gallery = createGallery({ document });
    galleryHost.replaceChildren(gallery.root);
    gallery.setLoading();
  }

  function renderProviderError(error) {
    const controls = element(document, "section", "tyis-controls tyis-controls-error");
    const message = element(
      document,
      "strong",
      "tyis-provider-error-message",
      error.message || "素材源读取失败",
    );
    const retry = element(document, "button", "tyis-subtle-button", "重新加载");
    retry.type = "button";
    retry.dataset.action = "retry-providers";
    retry.addEventListener("click", () => {
      renderInitialState();
      controller.ready = loadProviders();
    });
    controls.append(message, retry);
    controlsHost.replaceChildren(controls);
    gallery = createGallery({ document });
    galleryHost.replaceChildren(gallery.root);
    gallery.setError(error.message || "素材源读取失败");
  }

  function renderControls() {
    const value = state.get();
    const controls = renderSourceControls({
      document,
      providers,
      provider: value.provider,
      filters: value.filters,
      onSourceChange(provider) {
        guard.invalidate();
        state.set({ provider, filters: { query: "" }, items: [], nextCursor: null, error: null });
        persist();
        renderControls();
        renderGallery();
      },
      onSearch(query) {
        search(query);
      },
      onRefresh() {
        search(undefined, null, true);
      },
      onCheck() {
        setActivity("正在检查素材源");
        controller.ready = loadProviders();
      },
      onFilterChange(name, value) {
        state.set({ filters: { ...state.get().filters, [name]: value } });
        persist();
      },
    });
    controlsHost.replaceChildren(controls.root);
  }

  function renderGallery() {
    const value = state.get();
    const current = providers.find((entry) => entry.provider.id === value.provider);
    const descriptor = current?.provider;
    gallery = createGallery({
      document,
      provider: value.provider,
      capabilities: descriptor?.capabilities || {},
      onOpen: openDetail,
      onDownload: downloadItem,
      onDownloadPage: downloadPage,
      onNext: (cursor) => search(undefined, cursor),
    });
    galleryHost.replaceChildren(gallery.root);
    if (current?.status?.available === false) {
      gallery.setUnavailable(current.status.message, current.status.action);
    } else {
      gallery.render(value.items || [], { next_cursor: value.nextCursor });
    }
  }

  async function search(queryOverride, cursor = null, refresh = false) {
    const current = state.get();
    const source = providers.find((entry) => entry.provider.id === current.provider);
    if (source?.status?.available === false) {
      gallery?.setUnavailable(source.status.message, source.status.action);
      setActivity(source.status.message || "素材源不可用", true);
      return;
    }
    const query = queryOverride === undefined ? current.filters.query || "" : queryOverride;
    if (queryOverride !== undefined) {
      state.set({ filters: { ...current.filters, query } });
      persist();
    }
    const ticket = guard.begin();
    gallery?.setLoading();
    setActivity("检索中");
    const { query: _ignored, ...filters } = state.get().filters;
    try {
      const page = await client.requestJson("/ty-image-spider/search", {
        method: "POST",
        body: { provider: state.get().provider, query, filters, cursor, refresh },
      });
      if (!guard.isCurrent(ticket) || disposed) return;
      state.set({
        items: page.items || [],
        nextCursor: page.next_cursor || null,
        summary: { query, count: page.items?.length || 0, stale: Boolean(page.stale) },
        error: null,
      });
      gallery?.render(state.get().items, { next_cursor: state.get().nextCursor });
      setActivity(page.stale ? "缓存结果" : `${state.get().items.length} 项素材`);
      persist();
    } catch (error) {
      if (!guard.isCurrent(ticket) || disposed) return;
      state.set({ error });
      gallery?.setError(error.message);
      setActivity(error.message || "检索失败", true);
    }
  }

  async function openDetail(item) {
    setActivity("读取详情");
    try {
      const detail = await client.requestJson("/ty-image-spider/detail", {
        method: "POST",
        body: { item },
      });
      if (disposed) return;
      dialog?.close();
      dialog = openAssetDialog({
        document,
        detail,
        onDownload: downloadItem,
        onClose: () => {
          dialog = null;
        },
      });
      setActivity("就绪");
    } catch (error) {
      setActivity(error.message || "详情读取失败", true);
    }
  }

  async function downloadItem(item) {
    setActivity("下载中");
    try {
      const result = await client.requestJson("/ty-image-spider/download", {
        method: "POST",
        body: { item },
      });
      setActivity(result.message || "下载完成");
    } catch (error) {
      setActivity(error.message || "下载失败", true);
    }
  }

  async function downloadPage(items) {
    setActivity("下载本页");
    try {
      const result = await client.requestJson("/ty-image-spider/download-page", {
        method: "POST",
        body: { provider: state.get().provider, items },
      });
      setActivity(result.message || "下载完成");
    } catch (error) {
      setActivity(error.message || "下载失败", true);
    }
  }

  function restore() {
    let saved = {};
    try {
      saved = JSON.parse(stateWidget?.value || "{}");
    } catch (_) {
      saved = {};
    }
    if (!saved || typeof saved !== "object") return;
    const provider = typeof saved.provider === "string" ? saved.provider : state.get().provider;
    const filters = saved.filters && typeof saved.filters === "object" ? saved.filters : {};
    const items = provider === "xiaohongshu" || !Array.isArray(saved.items) ? [] : saved.items;
    state.set({ provider, filters, items, summary: saved.summary, nextCursor: null });
    if (providers.length) {
      renderControls();
      renderGallery();
    }
  }

  function persist() {
    if (!stateWidget) return;
    const serialized = serializeWorkflowState(state.get());
    stateWidget.value = serialized;
    stateWidget.callback?.(serialized);
    node.setDirtyCanvas?.(true, true);
    app.graph?.change?.();
  }

  function setActivity(message, error = false) {
    activity.textContent = message;
    activity.classList.toggle("is-error", error);
    activity.title = message;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    guard.invalidate();
    providerGuard.invalidate();
    dialog?.close();
    document.removeEventListener("keydown", onKeyDown, true);
    root.remove();
  }
}

function hideWidget(widget) {
  if (!widget || widget.__tyImageSpiderHidden) return;
  widget.__tyImageSpiderHidden = true;
  widget.hidden = true;
  widget.computeSize = () => [0, -4];
  widget.draw = () => {};
  widget.options = { ...widget.options, hidden: true };
  if (widget.element) widget.element.style.display = "none";
}

function resizeNode(node) {
  const width = Math.max(Number(node.size?.[0]) || 480, 440);
  const height = Math.max(Number(node.size?.[1]) || 720, 680);
  node.setSize?.([width, height]);
}

function ensureStyles(document) {
  if (document.querySelector('link[data-ty-image-spider="styles"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("./ty_image_spider.css", import.meta.url).href;
  link.dataset.tyImageSpider = "styles";
  document.head.append(link);
}

function element(document, tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

if (typeof window !== "undefined" && !window.__TY_IMAGE_SPIDER_DISABLE_AUTO_REGISTER__) {
  Promise.all([import("../../scripts/app.js"), import("../../scripts/api.js")]).then(
    ([{ app }, { api }]) =>
      app.registerExtension(createImageSpiderExtension({ app, api, document })),
  );
}
