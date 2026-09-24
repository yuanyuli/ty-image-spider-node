import { element } from "../../core/dom.js";
import { normalizePresentation, sourceGroups } from "../../core/presentation.js";

export function createSourceNavigation({ document, visible, current, onSourceChange }) {
  const sourceBar = element(document, "div", "tyis-source-bar");
  const sourceHead = element(document, "div", "tyis-source-head");
  const groups = element(document, "div", "tyis-source-groups");
  groups.setAttribute("role", "tablist");
  groups.setAttribute("aria-label", "素材来源类别");
  const segments = element(document, "div", "tyis-source-segments");
  segments.setAttribute("role", "tablist");
  segments.setAttribute("aria-label", "素材来源");
  const status = element(
    document,
    "span",
    `tyis-source-status${current?.status?.available === false ? " is-unavailable" : ""}`,
    current?.status?.message || (current?.status?.available === false ? "不可用" : "就绪"),
  );
  const grouped = sourceGroups(visible);
  let activeGroup = normalizePresentation(current?.provider).groupId;
  if (!grouped.some((entry) => entry.id === activeGroup)) activeGroup = grouped[0]?.id || "other";

  function renderSources() {
    segments.replaceChildren();
    for (const entry of visible.filter(
      (entry) => normalizePresentation(entry.provider).groupId === activeGroup,
    )) {
      const button = element(document, "button", "tyis-source-tab", entry.provider.label);
      button.type = "button";
      button.dataset.provider = entry.provider.id;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(entry.provider.id === current?.provider.id));
      button.dataset.available = String(entry.status?.available !== false);
      button.addEventListener("click", () => onSourceChange(entry.provider.id));
      segments.append(button);
    }
  }

  for (const group of grouped) {
    const button = element(document, "button", "tyis-source-group", group.label);
    button.type = "button";
    button.dataset.sourceGroup = group.id;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(group.id === activeGroup));
    button.addEventListener("click", () => {
      activeGroup = group.id;
      for (const peer of groups.children) {
        peer.setAttribute("aria-selected", String(peer === button));
      }
      renderSources();
    });
    groups.append(button);
  }
  renderSources();
  sourceHead.append(groups, status);
  sourceBar.append(sourceHead, segments);
  return { sourceBar, status };
}
