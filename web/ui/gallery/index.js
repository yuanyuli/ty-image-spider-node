import { element } from "../../core/dom.js";
import { renderCard } from "./card.js";
import { emptyState } from "./states.js";
import { createGalleryToolbar } from "./toolbar.js";

export function createGallery(context) {
  const {
    document,
    provider = "civitai",
    capabilities = {},
    descriptor = { id: provider },
    onOpen = () => {},
    onDownload = () => {},
    onDownloadPage = () => {},
    onCache = () => {},
    onCancelCache = () => {},
    onPrevious = () => {},
    onNext = () => {},
  } = context;
  const root = element(document, "section", "tyis-gallery");
  const {
    toolbar,
    count,
    bulkDownloadButton,
    cacheButton,
    cancelCacheButton,
    previousButton,
    nextButton,
  } = createGalleryToolbar({ document, capabilities, descriptor });
  const grid = element(document, "div", "tyis-grid");
  root.append(toolbar, grid);

  let currentItems = [];
  let hasPrevious = false;
  let nextCursor = null;
  bulkDownloadButton.addEventListener("click", () => onDownloadPage(currentItems));
  cacheButton.addEventListener("click", onCache);
  cancelCacheButton.addEventListener("click", onCancelCache);
  previousButton.addEventListener("click", () => onPrevious());
  nextButton.addEventListener("click", () => nextCursor && onNext(nextCursor));

  function render(items = [], page = {}) {
    currentItems = [...items];
    hasPrevious = page.has_previous === true;
    nextCursor = page.next_cursor || null;
    count.textContent = `${currentItems.length} 项素材`;
    previousButton.disabled = false;
    previousButton.hidden = !hasPrevious;
    nextButton.disabled = false;
    nextButton.hidden = !nextCursor;
    grid.replaceChildren();
    if (currentItems.length === 0) {
      grid.append(emptyState(document, "没有找到素材", "调整关键词或筛选条件后重试"));
      return;
    }
    for (const item of currentItems)
      grid.append(renderCard(document, item, provider, onOpen, onDownload, descriptor));
  }

  function setLoading(preservePagination = false) {
    count.textContent = "正在检索";
    const keepResults = currentItems.length > 0;
    previousButton.hidden = !hasPrevious || (!preservePagination && !keepResults);
    previousButton.disabled = true;
    nextButton.hidden = !nextCursor || (!preservePagination && !keepResults);
    nextButton.disabled = true;
    if (keepResults) return;
    grid.replaceChildren();
    for (let index = 0; index < 6; index += 1) {
      grid.append(element(document, "div", "tyis-skeleton"));
    }
  }

  function setError(message) {
    count.textContent = currentItems.length ? "检索失败 · 显示上次结果" : "检索失败";
    previousButton.disabled = false;
    previousButton.hidden = !currentItems.length || !hasPrevious;
    nextButton.disabled = false;
    nextButton.hidden = !currentItems.length || !nextCursor;
    if (currentItems.length) return;
    grid.replaceChildren(emptyState(document, message || "读取失败", "请检查素材源状态"));
  }

  function setUnavailable(message, action = "") {
    count.textContent = "来源不可用";
    previousButton.hidden = true;
    nextButton.hidden = true;
    grid.replaceChildren(emptyState(document, message || "当前素材源不可用", action));
  }

  function setCacheStatus(status) {
    const running = status?.state === "running";
    cacheButton.disabled = running;
    cacheButton.textContent = running
      ? `新增 ${status.cached || 0}/${status.target || 100}`
      : "新增缓存100张";
    cancelCacheButton.hidden = !running;
    if (status) cacheButton.title = status.message || "";
  }

  return {
    root,
    grid,
    bulkDownloadButton,
    cacheButton,
    cancelCacheButton,
    previousButton,
    nextButton,
    render,
    setLoading,
    setError,
    setUnavailable,
    setCacheStatus,
  };
}
