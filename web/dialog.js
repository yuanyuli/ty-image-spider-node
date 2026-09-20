import { normalizePresentation } from "./presentation.js";
import { createIcon, createIconButton } from "./icons.js";
import { openImageViewer } from "./image_viewer.js";
import { renderCollectionDetails } from "./collection_detail.js";
import { renderEditorialDetails } from "./editorial_detail.js";
import { createPreviewActions, handlePreviewKey } from "./preview_actions.js";

export function openAssetDialog(context) {
  const {
    document,
    detail,
    onDownload = () => {},
    onOpenSource = defaultOpenSource,
    copyText = defaultCopy,
    onClose = () => {},
    onDownloadImage,
    onPreviousItem,
    onNextItem,
    initialImageIndex = 0,
    startFullscreen = false,
  } = context;
  let item = detail.item;
  let images = detail.images?.length ? detail.images : item.preview_url ? [item.preview_url] : [];
  let imageIndex = initialImageIndex === -1 ? Math.max(0, images.length - 1) : 0;
  let selectLastOnUpdate = initialImageIndex === -1;
  let closed = false;
  let viewer = null;
  let saving = false;
  let saveMessage = "";
  const priorFocus = document.activeElement;
  const overlay = element(document, "div", "tyis-dialog-backdrop");
  const dialog = element(document, "section", "tyis-dialog");
  dialog.tabIndex = -1;
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", item.title || "素材详情");

  const header = element(document, "header", "tyis-dialog-header");
  const heading = element(document, "div", "tyis-dialog-heading");
  heading.append(
    element(
      document,
      "span",
      `tyis-dialog-source is-${item.provider}`,
      normalizePresentation(context.descriptor || { id: item.provider }).detailLabel,
    ),
    element(document, "h2", "", item.title || `素材 ${item.id}`),
  );
  const closeButton = createIconButton(document, "close", "关闭详情");
  header.append(heading, closeButton);

  const body = element(document, "div", "tyis-dialog-body");
  const stage = element(document, "div", "tyis-detail-stage");
  const imageFrame = element(document, "div", "tyis-detail-image-frame");
  const mainImage = element(document, "img", "tyis-detail-image");
  mainImage.alt = item.title || "素材大图";
  if (images[imageIndex]) mainImage.src = images[imageIndex];
  mainImage.title = "全屏查看图片";
  mainImage.tabIndex = 0;
  imageFrame.append(mainImage);
  const thumbs = element(document, "div", "tyis-thumbs");
  function renderThumbs() {
    thumbs.replaceChildren();
    images.forEach((url, index) => {
      const button = element(document, "button", "tyis-thumb");
      button.type = "button";
      button.setAttribute("aria-label", `查看第 ${index + 1} 张图片`);
      button.setAttribute("aria-pressed", String(index === imageIndex));
      const image = element(document, "img");
      image.src = url;
      image.alt = "";
      button.append(image);
      button.addEventListener("click", () => selectImage(index));
      thumbs.append(button);
    });
  }
  renderThumbs();
  const actions = {
    previous: () => navigate(-1),
    next: () => navigate(1),
    save: saveCurrentImage,
  };
  const previewActions = createPreviewActions(document, actions);
  stage.append(imageFrame, previewActions.root, thumbs);

  const panel = element(document, "aside", "tyis-detail-panel");
  panel.append(renderFacts(document, item));
  if (item.provider === "civitai") panel.append(renderCivitai(document, item, detail, copyText));
  else if (item.provider === "wallhaven") panel.append(renderWallhaven(document, item));
  else if (item.provider === "xiaohongshu") panel.append(renderXiaohongshu(document, item, detail));
  else if (item.kind === "collection") panel.append(renderCollectionDetails(document, detail));
  else if (item.kind === "editorial") panel.append(renderEditorialDetails(document, detail));
  else if (item.provider === "behance" || item.provider === "filmgrab") {
    if (detail.content) {
      const section = sectionWithTitle(document, "作品说明");
      section.append(element(document, "p", "tyis-detail-copy", detail.content));
      panel.append(section);
    }
  } else panel.append(renderLocal(document, detail));
  const actionBar = element(document, "div", "tyis-detail-actions");
  if (item.download_mode !== "none") {
    const download = element(
      document,
      "button",
      "tyis-primary-button",
      item.provider === "xiaohongshu"
        ? "下载整篇"
        : item.download_mode === "gallery"
          ? "下载图集"
          : "下载图片",
    );
    download.type = "button";
    download.dataset.action = "download";
    download.prepend(createIcon(document, "download", 16));
    download.addEventListener("click", () => onDownload(item));
    actionBar.append(download);
  }
  if (item.source_url) {
    const source = element(document, "button", "tyis-subtle-button", "打开来源");
    source.type = "button";
    source.prepend(createIcon(document, "external-link", 15));
    source.addEventListener("click", () => onOpenSource(item.source_url, document));
    actionBar.append(source);
  }
  panel.append(actionBar);
  body.append(stage, panel);
  dialog.append(header, body);
  overlay.append(dialog);
  document.body.append(overlay);

  function openFullscreen() {
    if (!mainImage.src) return;
    viewer?.close();
    viewer = openImageViewer({
      document,
      src: mainImage.src,
      alt: mainImage.alt,
      actions,
      controls: controlsState(),
      onClose: () => {
        viewer = null;
      },
    });
  }
  mainImage.addEventListener("click", openFullscreen);
  mainImage.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      mainImage.click();
    }
  });
  function selectImage(index) {
    if (!images[index]) return;
    imageIndex = index;
    selectLastOnUpdate = false;
    mainImage.src = images[index];
    [...thumbs.children].forEach((button, position) => {
      button.setAttribute("aria-pressed", String(position === index));
    });
    syncPreview();
  }
  function controlsState() {
    return {
      hasPrevious: imageIndex > 0 || Boolean(onPreviousItem),
      hasNext: imageIndex + 1 < images.length || Boolean(onNextItem),
      canSave: Boolean(onDownloadImage) && item.download_mode !== "none" && images.length > 0,
      saving,
      message: saveMessage,
      position: images.length
        ? context.itemPosition
          ? images.length > 1
            ? `作品 ${context.itemPosition} · ${imageIndex + 1} / ${images.length} 张`
            : context.itemPosition
          : `${imageIndex + 1} / ${images.length}`
        : "无图片",
    };
  }
  function syncPreview() {
    const controls = controlsState();
    previewActions.update(controls);
    viewer?.update({ src: mainImage.src, alt: mainImage.alt, controls });
  }
  function navigate(direction) {
    if (closed) return;
    const index = imageIndex + direction;
    if (index >= 0 && index < images.length) selectImage(index);
    else (direction < 0 ? onPreviousItem : onNextItem)?.(Boolean(viewer));
  }
  async function saveCurrentImage() {
    if (closed || saving || !controlsState().canSave) return;
    saving = true;
    const selected = imageIndex;
    saveMessage = `正在保存第 ${selected + 1} 张…`;
    syncPreview();
    try {
      const message = await onDownloadImage(item, selected);
      saveMessage = message || `第 ${selected + 1} 张已保存`;
    } catch (error) {
      saveMessage = error.message || "图片保存失败，请重试";
    } finally {
      saving = false;
      if (!closed) syncPreview();
    }
  }
  function close() {
    if (closed) return;
    closed = true;
    viewer?.close();
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
    if (priorFocus?.isConnected) priorFocus.focus();
    onClose();
  }
  function update(nextDetail) {
    if (closed || !nextDetail?.item) return;
    const nextItem = nextDetail.item;
    item = nextItem;
    const collection = panel.querySelector(".tyis-collection-info");
    if (collection) collection.replaceWith(renderCollectionDetails(document, nextDetail));
    const editorial = panel.querySelector(".tyis-editorial-info");
    if (editorial) editorial.replaceWith(renderEditorialDetails(document, nextDetail));
    if (nextDetail.images?.length) {
      images = [...nextDetail.images];
      imageIndex = selectLastOnUpdate ? images.length - 1 : Math.min(imageIndex, images.length - 1);
      selectLastOnUpdate = false;
      mainImage.src = images[imageIndex];
      renderThumbs();
    }
    const nextPrompt = nextItem.prompt;
    const prompt = overlay.querySelector(".tyis-prompt-copy");
    const unavailable = overlay.querySelector(".tyis-prompt-unavailable");
    if (prompt && nextPrompt) prompt.textContent = nextPrompt;
    else if (unavailable && nextPrompt) {
      unavailable.replaceWith(
        textSection(document, "正向提示词", nextPrompt, copyText, "copy-prompt"),
      );
    }
    dialog.setAttribute("aria-label", nextItem.title || `素材详情`);
    syncPreview();
  }
  function onKeyDown(event) {
    if (viewer) return;
    if (handlePreviewKey(event, actions)) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll("button,[href],[tabindex]")].filter(
      (node) => !node.disabled && !node.hidden && node.tabIndex !== -1,
    );
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }
  closeButton.addEventListener("click", close);
  overlay.addEventListener("pointerdown", (event) => {
    if (event.target === overlay) close();
  });
  document.addEventListener("keydown", onKeyDown, true);
  closeButton.focus();
  syncPreview();
  if (startFullscreen) openFullscreen();
  return { overlay, dialog, mainImage, close, selectImage, update };
}

function renderFacts(document, item) {
  const section = element(document, "section", "tyis-detail-section");
  const list = element(document, "dl", "tyis-facts");
  fact(document, list, "作者", item.author || "未知");
  if (item.created_at) fact(document, list, "时间", item.created_at);
  if (item.width && item.height) fact(document, list, "尺寸", `${item.width} × ${item.height}`);
  if (item.image_count > 1) fact(document, list, "图集", `${item.image_count} 张`);
  section.append(list);
  return section;
}

function renderCivitai(document, item, detail, copyText) {
  const root = document.createDocumentFragment();
  if (item.prompt)
    root.append(textSection(document, "正向提示词", item.prompt, copyText, "copy-prompt"));
  else root.append(element(document, "p", "tyis-prompt-unavailable", "该素材未提供公开提示词"));
  if (item.negative_prompt)
    root.append(textSection(document, "负向提示词", item.negative_prompt, copyText));
  const resources = [...(item.metadata?.models || []), ...(item.metadata?.loras || [])];
  if (resources.length) {
    const section = sectionWithTitle(document, "使用资源");
    const chips = element(document, "div", "tyis-resource-list");
    for (const resource of resources) {
      chips.append(element(document, "span", `tyis-resource is-${resource.type}`, resource.name));
    }
    section.append(chips);
    root.append(section);
  }
  if (detail.workflow) root.append(codeSection(document, "Workflow", detail.workflow));
  return root;
}

function renderXiaohongshu(document, item, detail) {
  const root = document.createDocumentFragment();
  if (detail.content) {
    const section = sectionWithTitle(document, "笔记正文");
    section.append(element(document, "p", "tyis-detail-copy", detail.content));
    root.append(section);
  }
  const stats = element(document, "div", "tyis-stat-row");
  for (const [key, label] of [
    ["likes", "赞"],
    ["collects", "收藏"],
    ["comments", "评论"],
  ]) {
    if (item.stats?.[key] !== undefined) {
      stats.append(element(document, "span", "", `${item.stats[key]} ${label}`));
    }
  }
  if (stats.children.length) root.append(stats);
  return root;
}

function renderWallhaven(document, item) {
  const root = document.createDocumentFragment();
  const stats = element(document, "div", "tyis-stat-row");
  if (item.stats?.views !== undefined) {
    stats.append(element(document, "span", "", `${item.stats.views} 浏览`));
  }
  if (item.stats?.favorites !== undefined) {
    stats.append(element(document, "span", "", `${item.stats.favorites} 收藏`));
  }
  if (item.metadata?.category) {
    stats.append(element(document, "span", "", item.metadata.category));
  }
  if (stats.children.length) root.append(stats);

  if (item.tags?.length) {
    const section = sectionWithTitle(document, "标签");
    const tags = element(document, "div", "tyis-resource-list");
    for (const tag of item.tags) tags.append(element(document, "span", "tyis-resource", tag));
    section.append(tags);
    root.append(section);
  }

  const colors = (item.metadata?.colors || []).filter((value) => /^#[0-9a-f]{6}$/i.test(value));
  if (colors.length) {
    const section = sectionWithTitle(document, "色板");
    const palette = element(document, "div", "tyis-color-palette");
    for (const color of colors) {
      const swatch = element(document, "span", "tyis-color-swatch");
      swatch.style.backgroundColor = color;
      swatch.title = color;
      swatch.setAttribute("aria-label", color);
      palette.append(swatch);
    }
    section.append(palette);
    root.append(section);
  }
  return root;
}

function renderLocal(document, detail) {
  return codeSection(document, "图片 Metadata", detail.metadata || {});
}

function textSection(document, title, value, copyText, action) {
  const section = sectionWithTitle(document, title);
  const head = section.querySelector(".tyis-detail-section-title");
  const copy = createIconButton(document, "copy", `复制${title}`);
  if (action) copy.dataset.action = action;
  copy.addEventListener("click", async () => copyText(value, document));
  head.append(copy);
  section.append(element(document, "p", "tyis-prompt-copy", value));
  return section;
}

function codeSection(document, title, value) {
  const details = element(document, "details", "tyis-code-section");
  const summary = element(document, "summary", "", title);
  const code = element(document, "pre", "", JSON.stringify(value, null, 2));
  details.append(summary, code);
  return details;
}

function sectionWithTitle(document, title) {
  const section = element(document, "section", "tyis-detail-section");
  section.append(element(document, "div", "tyis-detail-section-title", title));
  return section;
}

function fact(document, list, key, value) {
  list.append(element(document, "dt", "", key), element(document, "dd", "", value));
}

async function defaultCopy(value, document) {
  await document.defaultView?.navigator?.clipboard?.writeText(value);
}

function defaultOpenSource(url, document) {
  document.defaultView?.open(url, "_blank", "noopener,noreferrer");
}

function element(document, tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
