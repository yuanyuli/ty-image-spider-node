import { element } from "../../core/dom.js";
import { normalizePresentation } from "../../core/presentation.js";
import { createIconButton } from "../icons.js";

export function renderCard(document, item, provider, onOpen, onDownload, descriptor) {
  const card = element(document, "article", `tyis-card is-${provider}`);
  const media = element(document, "div", "tyis-card-media");
  media.setAttribute("role", "button");
  media.tabIndex = 0;
  media.setAttribute("aria-label", `查看 ${item.title || "素材"}`);
  const image = element(document, "img", "tyis-card-image");
  image.alt = item.title || "素材预览";
  image.loading = "lazy";
  if (item.preview_url) image.src = item.preview_url;
  else image.classList.add("is-empty");
  image.addEventListener("error", () => image.classList.add("is-error"));
  const top = element(document, "div", "tyis-card-topline");
  top.append(
    element(
      document,
      "span",
      `tyis-source-mark is-${provider}`,
      normalizePresentation(descriptor).shortLabel,
    ),
  );
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
      provider === "xiaohongshu"
        ? "下载整篇"
        : item.download_mode === "gallery"
          ? "下载图集"
          : "下载图片",
    );
    download.dataset.action = "download";
    download.addEventListener("click", (event) => {
      event.stopPropagation();
      onDownload(item);
    });
    hoverActions.append(download);
  }
  media.addEventListener("click", () => onOpen(item));
  media.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onOpen(item);
  });
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
