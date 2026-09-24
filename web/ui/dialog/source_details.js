import { element } from "../../core/dom.js";
import { codeSection, sectionWithTitle, textSection } from "./actions.js";

export function renderCivitai(document, item, detail, copyText) {
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

export function renderXiaohongshu(document, item, detail) {
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

export function renderWallhaven(document, item) {
  const root = document.createDocumentFragment();
  const stats = element(document, "div", "tyis-stat-row");
  if (item.stats?.views !== undefined)
    stats.append(element(document, "span", "", `${item.stats.views} 浏览`));
  if (item.stats?.favorites !== undefined)
    stats.append(element(document, "span", "", `${item.stats.favorites} 收藏`));
  if (item.metadata?.category) stats.append(element(document, "span", "", item.metadata.category));
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

export function renderLocal(document, detail) {
  return codeSection(document, "图片 Metadata", detail.metadata || {});
}
