import { createIcon, createIconButton } from "./icons.js";

export function createGallery(context) {
  const {
    document,
    provider = "civitai",
    capabilities = {},
    onOpen = () => {},
    onDownload = () => {},
    onDownloadPage = () => {},
    onNext = () => {},
  } = context;
  const root = element(document, "section", "tyis-gallery");
  const toolbar = element(document, "div", "tyis-gallery-toolbar");
  const count = element(document, "span", "tyis-result-count", "0 项素材");
  const actions = element(document, "div", "tyis-gallery-actions");
  const bulkDownloadButton = element(document, "button", "tyis-subtle-button", "下载本页");
  bulkDownloadButton.type = "button";
  bulkDownloadButton.prepend(createIcon(document, "download", 15));
  bulkDownloadButton.hidden = capabilities.bulk_download !== true;
  const nextButton = element(document, "button", "tyis-subtle-button", "下一页");
  nextButton.type = "button";
  nextButton.append(createIcon(document, "next", 15));
  nextButton.hidden = true;
  actions.append(bulkDownloadButton, nextButton);
  toolbar.append(count, actions);
  const grid = element(document, "div", "tyis-grid");
  root.append(toolbar, grid);

  let currentItems = [];
  let nextCursor = null;
  bulkDownloadButton.addEventListener("click", () => onDownloadPage(currentItems));
  nextButton.addEventListener("click", () => nextCursor && onNext(nextCursor));

  function render(items = [], page = {}) {
    currentItems = [...items];
    nextCursor = page.next_cursor || null;
    count.textContent = `${currentItems.length} 项素材`;
    nextButton.hidden = !nextCursor;
    grid.replaceChildren();
    if (currentItems.length === 0) {
      grid.append(emptyState(document, "没有找到素材", "调整关键词或筛选条件后重试"));
      return;
    }
    for (const item of currentItems)
      grid.append(renderCard(document, item, provider, onOpen, onDownload));
  }

  function setLoading() {
    count.textContent = "正在检索";
    nextButton.hidden = true;
    grid.replaceChildren();
    for (let index = 0; index < 6; index += 1) {
      grid.append(element(document, "div", "tyis-skeleton"));
    }
  }

  function setError(message) {
    count.textContent = "检索失败";
    nextButton.hidden = true;
    grid.replaceChildren(emptyState(document, message || "读取失败", "请检查素材源状态"));
  }

  function setUnavailable(message, action = "") {
    count.textContent = "来源不可用";
    nextButton.hidden = true;
    grid.replaceChildren(emptyState(document, message || "当前素材源不可用", action));
  }

  return {
    root,
    grid,
    bulkDownloadButton,
    nextButton,
    render,
    setLoading,
    setError,
    setUnavailable,
  };
}

function renderCard(document, item, provider, onOpen, onDownload) {
  const card = element(document, "article", `tyis-card is-${provider}`);
  const media = element(document, "button", "tyis-card-media");
  media.type = "button";
  media.setAttribute("aria-label", `查看 ${item.title || "素材"}`);
  const image = element(document, "img", "tyis-card-image");
  image.alt = item.title || "素材预览";
  image.loading = "lazy";
  if (item.preview_url) image.src = item.preview_url;
  else image.classList.add("is-empty");
  image.addEventListener("error", () => image.classList.add("is-error"));
  const top = element(document, "div", "tyis-card-topline");
  top.append(sourceMark(document, provider));
  if (provider === "civitai") {
    top.append(
      element(
        document,
        "span",
        `tyis-prompt-badge ${item.has_prompt ? "has-prompt" : "is-empty"}`,
        item.has_prompt ? "提示词" : "无提示词",
      ),
    );
  }
  if ((item.image_count || 1) > 1) {
    top.append(element(document, "span", "tyis-image-count", `${item.image_count} 张`));
  }
  const hoverActions = element(document, "div", "tyis-card-actions");
  if (item.download_mode !== "none") {
    const download = createIconButton(
      document,
      "download",
      provider === "xiaohongshu" ? "下载整篇" : "下载图片",
    );
    download.dataset.action = "download";
    download.addEventListener("click", (event) => {
      event.stopPropagation();
      onDownload(item);
    });
    hoverActions.append(download);
  }
  media.addEventListener("click", () => onOpen(item));
  media.append(image, top, hoverActions);

  const footer = element(document, "div", "tyis-card-footer");
  const title = element(document, "strong", "tyis-card-title", item.title || `素材 ${item.id}`);
  title.title = title.textContent;
  const meta = element(document, "div", "tyis-card-meta");
  const author = item.author || (provider === "local" ? "本地输出" : "未知作者");
  meta.append(element(document, "span", "", author));
  if (provider === "xiaohongshu" && item.stats?.likes !== undefined) {
    meta.append(element(document, "span", "", `${item.stats.likes} 赞`));
  } else if (provider === "wallhaven" && item.stats?.favorites !== undefined) {
    meta.append(element(document, "span", "", `${item.stats.favorites} 收藏`));
  }
  footer.append(title, meta);
  card.append(media, footer);
  return card;
}

function sourceMark(document, provider) {
  const labels = { civitai: "C", wallhaven: "W", xiaohongshu: "RED", local: "LOCAL" };
  return element(document, "span", `tyis-source-mark is-${provider}`, labels[provider] || provider);
}

function emptyState(document, title, note) {
  const root = element(document, "div", "tyis-empty");
  root.append(element(document, "strong", "", title));
  if (note) root.append(element(document, "span", "", note));
  return root;
}

function element(document, tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
