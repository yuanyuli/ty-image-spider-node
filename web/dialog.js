import { createIcon, createIconButton } from "./icons.js";

export function openAssetDialog(context) {
  const {
    document,
    detail,
    onDownload = () => {},
    onOpenSource = defaultOpenSource,
    copyText = defaultCopy,
    onClose = () => {},
  } = context;
  const item = detail.item;
  const images = detail.images?.length ? detail.images : item.preview_url ? [item.preview_url] : [];
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
    element(document, "span", `tyis-dialog-source is-${item.provider}`, sourceLabel(item.provider)),
    element(document, "h2", "", item.title || `素材 ${item.id}`),
  );
  const closeButton = createIconButton(document, "close", "关闭详情");
  header.append(heading, closeButton);

  const body = element(document, "div", "tyis-dialog-body");
  const stage = element(document, "div", "tyis-detail-stage");
  const imageFrame = element(document, "div", "tyis-detail-image-frame");
  const mainImage = element(document, "img", "tyis-detail-image");
  mainImage.alt = item.title || "素材大图";
  if (images[0]) mainImage.src = images[0];
  imageFrame.append(mainImage);
  const thumbs = element(document, "div", "tyis-thumbs");
  images.forEach((url, index) => {
    const button = element(document, "button", "tyis-thumb");
    button.type = "button";
    button.setAttribute("aria-label", `查看第 ${index + 1} 张图片`);
    button.setAttribute("aria-pressed", String(index === 0));
    const image = element(document, "img");
    image.src = url;
    image.alt = "";
    button.append(image);
    button.addEventListener("click", () => selectImage(index));
    thumbs.append(button);
  });
  stage.append(imageFrame, thumbs);

  const panel = element(document, "aside", "tyis-detail-panel");
  panel.append(renderFacts(document, item));
  if (item.provider === "civitai") panel.append(renderCivitai(document, item, detail, copyText));
  else if (item.provider === "wallhaven") panel.append(renderWallhaven(document, item));
  else if (item.provider === "xiaohongshu") panel.append(renderXiaohongshu(document, item, detail));
  else panel.append(renderLocal(document, detail));
  const actionBar = element(document, "div", "tyis-detail-actions");
  if (item.download_mode !== "none") {
    const download = element(
      document,
      "button",
      "tyis-primary-button",
      item.provider === "xiaohongshu" ? "下载整篇" : "下载图片",
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

  let closed = false;
  function selectImage(index) {
    if (!images[index]) return;
    mainImage.src = images[index];
    [...thumbs.children].forEach((button, position) => {
      button.setAttribute("aria-pressed", String(position === index));
    });
  }
  function close() {
    if (closed) return;
    closed = true;
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
    if (priorFocus?.isConnected) priorFocus.focus();
    onClose();
  }
  function onKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll("button,[href],[tabindex]")].filter(
      (node) => !node.disabled && node.tabIndex !== -1,
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
  return { overlay, dialog, mainImage, close, selectImage };
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

function sourceLabel(provider) {
  return (
    {
      civitai: "CIVITAI",
      wallhaven: "WALLHAVEN",
      xiaohongshu: "小红书",
      local: "本地历史",
    }[provider] || provider
  );
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
