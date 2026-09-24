import { element } from "../../core/dom.js";
import { normalizePresentation } from "../../core/presentation.js";
import { createIcon, createIconButton } from "../icons.js";
import { openImageViewer } from "../image_viewer.js";
import { renderCollectionDetails } from "../../features/detail/collection_detail.js";
import { renderEditorialDetails } from "../../features/detail/editorial_detail.js";
import { renderVideoDetail } from "../../features/video/detail.js";
import {
  createPreviewActions,
  handlePreviewKey,
  selectPreviewSaveAction,
} from "../../features/preview/preview_actions.js";
import { renderFacts } from "./facts.js";
import { defaultCopy, defaultOpenSource, sectionWithTitle, textSection } from "./actions.js";
import {
  renderCivitai,
  renderLocal,
  renderWallhaven,
  renderXiaohongshu,
} from "./source_details.js";
import { createDialogShell } from "./shell.js";

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
  const isVideo = item.kind === "video";
  const priorFocus = document.activeElement;
  const { overlay, dialog } = createDialogShell(document, item.title || "素材详情");

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
    save: saveCurrentAsset,
  };
  const previewActions = createPreviewActions(document, actions);
  let videoDetail = null;
  if (isVideo) {
    videoDetail = renderVideoDetail(document, detail, context);
    stage.append(videoDetail.root);
  } else stage.append(imageFrame, previewActions.root, thumbs);

  const panel = element(document, "aside", "tyis-detail-panel");
  panel.append(renderFacts(document, item));
  if (item.kind === "video" && detail.content) {
    const section = sectionWithTitle(document, "视频说明");
    section.append(element(document, "p", "tyis-detail-copy", detail.content));
    panel.append(section);
  } else if (item.provider === "civitai")
    panel.append(renderCivitai(document, item, detail, copyText));
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
  let downloadButton = null;
  let downloadStatus = null;
  if (item.download_mode !== "none") {
    downloadButton = element(
      document,
      "button",
      "tyis-primary-button",
      item.provider === "xiaohongshu"
        ? "下载整篇"
        : item.download_mode === "gallery"
          ? "下载图集"
          : item.kind === "video"
            ? "下载视频"
            : "下载图片",
    );
    downloadButton.type = "button";
    downloadButton.dataset.action = "download";
    downloadButton.prepend(createIcon(document, "download", 16));
    downloadButton.addEventListener("click", () => {
      if (isVideo) saveCurrentAsset();
      else onDownload(item);
    });
    actionBar.append(downloadButton);
  }
  if (item.source_url) {
    const source = element(document, "button", "tyis-subtle-button", "打开来源");
    source.type = "button";
    source.prepend(createIcon(document, "external-link", 15));
    source.addEventListener("click", () => onOpenSource(item.source_url, document));
    actionBar.append(source);
  }
  if (isVideo) {
    downloadStatus = element(document, "span", "tyis-preview-status");
    downloadStatus.setAttribute("role", "status");
    downloadStatus.setAttribute("aria-live", "polite");
    actionBar.append(downloadStatus);
  }
  panel.append(actionBar);
  body.append(stage, panel);
  dialog.append(header, body);
  overlay.append(dialog);
  document.body.append(overlay);

  function openFullscreen() {
    if (isVideo) return;
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
    const saveAction = selectPreviewSaveAction({
      item,
      imageIndex,
      onDownload,
      onDownloadImage,
    });
    return {
      hasPrevious: imageIndex > 0 || Boolean(onPreviousItem),
      hasNext: imageIndex + 1 < images.length || Boolean(onNextItem),
      canSave: Boolean(saveAction) && (isVideo || images.length > 0),
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
    if (isVideo) {
      if (downloadButton) downloadButton.disabled = saving;
      if (downloadStatus) downloadStatus.textContent = saveMessage;
    }
  }
  function navigate(direction) {
    if (closed) return;
    if (isVideo) {
      (direction < 0 ? onPreviousItem : onNextItem)?.(false);
      return;
    }
    const index = imageIndex + direction;
    if (index >= 0 && index < images.length) selectImage(index);
    else (direction < 0 ? onPreviousItem : onNextItem)?.(Boolean(viewer));
  }
  async function saveCurrentAsset() {
    const saveAction = selectPreviewSaveAction({
      item,
      imageIndex,
      onDownload,
      onDownloadImage,
    });
    if (closed || saving || !saveAction || (!isVideo && images.length === 0)) return;
    saving = true;
    const selected = imageIndex;
    saveMessage = isVideo ? "正在下载视频…" : `正在保存第 ${selected + 1} 张…`;
    syncPreview();
    try {
      const message = await saveAction();
      saveMessage =
        isVideo && message === null
          ? "视频下载失败，请重试"
          : message || (isVideo ? "视频已下载" : `第 ${selected + 1} 张已保存`);
    } catch (error) {
      saveMessage = error.message || (isVideo ? "视频下载失败，请重试" : "图片保存失败，请重试");
    } finally {
      saving = false;
      if (!closed) syncPreview();
    }
  }
  function close() {
    if (closed) return;
    closed = true;
    viewer?.close();
    videoDetail?.destroy();
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
    if (priorFocus?.isConnected) priorFocus.focus();
    onClose();
  }
  function update(nextDetail) {
    if (closed || !nextDetail?.item) return;
    const nextItem = nextDetail.item;
    item = nextItem;
    if (isVideo) videoDetail?.update(nextDetail);
    const collection = panel.querySelector(".tyis-collection-info");
    if (collection) collection.replaceWith(renderCollectionDetails(document, nextDetail));
    const editorial = panel.querySelector(".tyis-editorial-info");
    if (editorial) editorial.replaceWith(renderEditorialDetails(document, nextDetail));
    if (!isVideo && nextDetail.images?.length) {
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
