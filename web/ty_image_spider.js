import { createCacheTasks } from "./cache_tasks.js";
import { normalizePresentation } from "./presentation.js";
import { createApiClient } from "./api.js";
import { openAssetDialog } from "./dialog.js";
import { createGallery } from "./gallery.js";
import { createSearchHistory } from "./search_history.js";
import { renderSourceControls } from "./source_controls.js";
import { createMovieSearch } from "./movie_search.js";
import {
  createProviderSessions,
  createRequestGuard,
  createSpiderState,
  serializeWorkflowState,
} from "./state.js";

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
  const executed = nodeType.prototype.onExecuted;
  const removed = nodeType.prototype.onRemoved;
  nodeType.prototype.onNodeCreated = function (...args) {
    const result = created?.apply(this, args);
    clearComfyPreview(this);
    mountNode(this, dependencies);
    return result;
  };
  nodeType.prototype.onConfigure = function (...args) {
    const result = configured?.apply(this, args);
    clearComfyPreview(this);
    mountNode(this, dependencies).restore();
    return result;
  };
  nodeType.prototype.onExecuted = function (...args) {
    const result = executed?.apply(this, args);
    clearComfyPreview(this);
    this.setDirtyCanvas?.(true, true);
    return result;
  };
  nodeType.prototype.onRemoved = function (...args) {
    this.tyImageSpider?.dispose();
    this.tyImageSpider = null;
    return removed?.apply(this, args);
  };
}

function clearComfyPreview(node) {
  delete node.imgs;
  delete node.images;
  delete node.imageIndex;
  delete node.previewMediaType;
}

function mountNode(node, { app, api, document }) {
  if (node.tyImageSpider) return node.tyImageSpider;
  ensureStyles(document);
  const stateWidget = node.widgets?.find((widget) => widget.name === "state_json");
  hideWidget(stateWidget);
  const state = createSpiderState();
  const sessions = createProviderSessions();
  const history = createSearchHistory(document.defaultView?.localStorage);
  const guard = createRequestGuard();
  const providerGuard = createRequestGuard();
  const client = createApiClient(api.fetchApi.bind(api));
  const movieSearch = createMovieSearch({ document, client });
  const root = element(document, "div", "tyis-workspace");
  const masthead = element(document, "header", "tyis-masthead");
  const brand = element(document, "div", "tyis-brand");
  brand.append(
    element(document, "strong", "", "TY Image Spider"),
    element(document, "span", "", "素材审片台"),
  );
  const activity = element(document, "span", "tyis-activity", "待命");
  masthead.append(brand, activity);
  const downloadLocation = element(document, "div", "tyis-download-location");
  downloadLocation.hidden = true;
  const controlsHost = element(document, "div", "tyis-controls-host");
  const galleryHost = element(document, "div", "tyis-gallery-host");
  root.append(masthead, downloadLocation, controlsHost, galleryHost);
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
  let restoreNeedsSearch = false;
  const cacheTasks = createCacheTasks({
    client,
    onUpdate(job) {
      if (job.provider !== state.get().provider) return;
      gallery?.setCacheStatus(job);
      setActivity(job.message || `已缓存 ${job.cached || 0} 张`);
    },
    onError(error, provider) {
      if (provider === state.get().provider) setActivity(error.message || "缓存操作失败", true);
    },
  });
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
    render() {
      sessions.save(state.get().provider, state.get());
      renderControls();
      renderGallery();
    },
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
      // 是否开放入口由来源描述符决定。
      providers = nextProviders.filter((entry) => normalizePresentation(entry.provider).visible);
      const current = providers.some((entry) => entry.provider.id === state.get().provider)
        ? state.get().provider
        : providers[0]?.provider.id || "civitai";
      state.set({ provider: current, filters: withDefaults(current, state.get().filters) });
      sessions.save(current, state.get());
      renderControls();
      renderGallery();
      if (restoreNeedsSearch) {
        restoreNeedsSearch = false;
        search();
      }
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
      getRecentQueries: () => history.list(value.provider),
      onSourceChange(provider) {
        guard.invalidate();
        movieSearch.cancel();
        sessions.save(value.provider, state.get());
        const restored = sessions.load(provider);
        state.set({ provider, ...restored, filters: withDefaults(provider, restored.filters) });
        persist();
        renderControls();
        renderGallery();
      },
      onSearch(query) {
        search(query);
      },
      onMovieLookup(query) {
        search(query, null, false, "reset", true);
      },
      onRefresh() {
        search(undefined, null, true);
      },
      onCheck() {
        setActivity("正在检查素材源");
        controller.ready = loadProviders();
      },
      async onConnect() {
        setActivity("正在连接 OpenCLI");
        try {
          const result = await client.requestJson(
            "/ty-image-spider/providers/xiaohongshu/connect",
            {
              method: "POST",
            },
          );
          setActivity(result.message || "OpenCLI 已连接");
          controller.ready = loadProviders();
          await controller.ready;
        } catch (error) {
          setActivity(error.message || "OpenCLI 连接失败", true);
        }
      },
      onFilterChange(name, value) {
        state.set({ filters: { ...state.get().filters, [name]: value } });
        if (state.get().provider === "arena" && name === "category") {
          state.set({ filters: { ...state.get().filters, query: "" } });
        }
        sessions.save(state.get().provider, state.get());
        if (name === "query") return;
        persist();
        renderControls();
        search();
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
      descriptor,
      capabilities: descriptor?.capabilities || {},
      onOpen: openDetail,
      onDownload: downloadItem,
      onDownloadPage: downloadPage,
      onCache: startCache,
      onCancelCache: cancelCache,
      onPrevious: () => {
        const previous = state.get().previousCursors;
        search(undefined, previous.at(-1) ?? null, false, "previous");
      },
      onNext: (cursor) => search(undefined, cursor, false, "next"),
    });
    galleryHost.replaceChildren(gallery.root);
    if (current?.status?.available === false) {
      gallery.setUnavailable(current.status.message, current.status.action);
    } else {
      gallery.render(value.items || [], {
        next_cursor: value.nextCursor,
        has_previous: value.previousCursors.length > 0,
      });
    }
    gallery.setCacheStatus(cacheTasks.get(value.provider));
  }

  async function startCache() {
    const current = state.get();
    const { query = "", ...filters } = current.filters;
    setActivity("正在启动后台缓存");
    await cacheTasks.start({ provider: current.provider, query, filters });
  }

  async function cancelCache() {
    await cacheTasks.cancel(state.get().provider);
  }

  async function search(
    queryOverride,
    cursor = null,
    refresh = false,
    navigation = "reset",
    movieLookup = false,
  ) {
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
    movieSearch.cancel();
    const previousCursors = [...current.previousCursors];
    if (navigation === "next") previousCursors.push(current.currentCursor ?? null);
    else if (navigation === "previous") previousCursors.pop();
    else previousCursors.length = 0;
    gallery?.setLoading(navigation !== "reset");
    setActivity("检索中");
    const { query: _ignored, ...filters } = state.get().filters;
    try {
      const page = await movieSearch.search(
        {
          provider: state.get().provider,
          query,
          filters: movieLookup ? { ...filters, movie_lookup: true } : filters,
          cursor,
          refresh,
        },
        () => guard.isCurrent(ticket) && !disposed,
      );
      if (!guard.isCurrent(ticket) || disposed) return;
      if (!page) {
        gallery?.render(current.items || [], {
          next_cursor: current.nextCursor,
          has_previous: current.previousCursors.length > 0,
        });
        setActivity("已取消电影选择");
        return;
      }
      state.set({
        items: page.items || [],
        nextCursor: page.next_cursor || null,
        currentCursor: cursor,
        previousCursors,
        summary: { query, count: page.items?.length || 0, stale: Boolean(page.stale) },
        error: null,
      });
      history.add(current.provider, query);
      sessions.save(state.get().provider, state.get());
      gallery?.render(state.get().items, {
        next_cursor: state.get().nextCursor,
        has_previous: state.get().previousCursors.length > 0,
      });
      setActivity(page.stale ? "缓存结果" : `${state.get().items.length} 项素材`);
      persist();
    } catch (error) {
      if (!guard.isCurrent(ticket) || disposed) return;
      state.set({ error });
      const message = [error.message, error.action].filter(Boolean).join("。 ");
      gallery?.setError(message);
      setActivity(message || "检索失败", true);
    }
  }

  async function openDetail(item) {
    dialog?.close();
    dialog = openAssetDialog({
      document,
      descriptor: providers.find((entry) => entry.provider.id === item.provider)?.provider,
      detail: { item, images: item.preview_url ? [item.preview_url] : [] },
      onDownload: downloadItem,
      onClose: () => {
        dialog = null;
      },
    });
    const openedDialog = dialog;
    setActivity("读取详情");
    try {
      const detail = await client.requestJson("/ty-image-spider/detail", {
        method: "POST",
        body: { item },
      });
      const updatedItem = detail?.item;
      const currentState = state.get();
      if (updatedItem?.id && updatedItem.provider === currentState.provider) {
        const updatedItems = currentState.items.map((candidate) =>
          candidate.provider === updatedItem.provider && candidate.id === updatedItem.id
            ? { ...candidate, ...updatedItem }
            : candidate,
        );
        if (updatedItems.some((candidate, index) => candidate !== currentState.items[index])) {
          state.set({ items: updatedItems });
          sessions.save(state.get().provider, state.get());
          gallery?.render(state.get().items, {
            next_cursor: state.get().nextCursor,
            has_previous: state.get().previousCursors.length > 0,
          });
          persist();
        }
      }
      if (disposed || dialog !== openedDialog) return;
      openedDialog.update(detail);
      setActivity("就绪");
    } catch (error) {
      setActivity(error.message || "详情读取失败", true);
    }
  }

  async function downloadItem(item) {
    downloadLocation.hidden = true;
    setActivity("下载中");
    try {
      const result = await client.requestJson("/ty-image-spider/download", {
        method: "POST",
        body: { item },
      });
      showDownloadResult(result);
    } catch (error) {
      setActivity(error.message || "下载失败", true);
    }
  }

  async function downloadPage(items) {
    downloadLocation.hidden = true;
    setActivity("下载本页");
    try {
      const result = await client.requestJson("/ty-image-spider/download-page", {
        method: "POST",
        body: { provider: state.get().provider, items },
      });
      showDownloadResult(result);
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
    if (saved.provider === "xiaohongshu") saved = { provider: "civitai", filters: {} };
    const provider = typeof saved.provider === "string" ? saved.provider : state.get().provider;
    const filters = saved.filters && typeof saved.filters === "object" ? saved.filters : {};
    const items = provider === "xiaohongshu" || !Array.isArray(saved.items) ? [] : saved.items;
    const hasPagination = Object.prototype.hasOwnProperty.call(saved, "nextCursor");
    restoreNeedsSearch = provider !== "xiaohongshu" && items.length > 0 && !hasPagination;
    state.set({
      provider,
      filters,
      items,
      summary: saved.summary,
      nextCursor: typeof saved.nextCursor === "string" ? saved.nextCursor : null,
      currentCursor: typeof saved.currentCursor === "string" ? saved.currentCursor : null,
      previousCursors: Array.isArray(saved.previousCursors) ? saved.previousCursors : [],
    });
    sessions.save(provider, state.get());
    if (providers.length) {
      renderControls();
      renderGallery();
      if (restoreNeedsSearch) {
        restoreNeedsSearch = false;
        search();
      }
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

  function downloadResultMessage(result) {
    const files = Array.isArray(result?.files) ? result.files.filter(Boolean) : [];
    if (!files.length) return result?.message || "下载完成";
    const outputRoot = typeof result?.output_root === "string" ? result.output_root.trim() : "";
    const paths = files.map((file) => {
      if (!outputRoot) return `output/ty-node/${file}`;
      const normalizedRoot = outputRoot.replace(/[\\/]+$/, "");
      const normalizedFile = String(file).replaceAll("/", "\\");
      return `${normalizedRoot}\\${normalizedFile}`;
    });
    return `${result?.message || "下载完成"}：${paths.join("、")}`;
  }

  function showDownloadResult(result) {
    setActivity(result?.message || "下载完成");
    downloadLocation.textContent = downloadResultMessage(result);
    downloadLocation.title = downloadLocation.textContent;
    downloadLocation.hidden = false;
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    guard.invalidate();
    movieSearch.cancel();
    providerGuard.invalidate();
    cacheTasks.dispose();
    dialog?.close();
    document.removeEventListener("keydown", onKeyDown, true);
    root.remove();
  }

  function withDefaults(provider, filters = {}) {
    const descriptor = providers.find((entry) => entry.provider.id === provider)?.provider;
    const defaults = Object.fromEntries(
      (descriptor?.filters || []).map((field) => [field.name, field.default]),
    );
    return { query: "", ...defaults, ...filters };
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
