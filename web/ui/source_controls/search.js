import { element } from "../../core/dom.js";
import { createIcon, createIconButton } from "../icons.js";

export function createSearchControls(context) {
  const {
    document,
    root,
    current,
    filters,
    unavailable,
    getRecentQueries,
    onFilterChange,
    onSearch,
    onRefresh,
    onMovieLookup,
  } = context;
  const searchRow = element(document, "div", "tyis-search-row");
  const searchWrap = element(document, "div", "tyis-search-wrap");
  const searchBox = element(document, "label", "tyis-search-box");
  searchBox.append(createIcon(document, "search"));
  const query = element(document, "input", "tyis-query");
  query.name = "query";
  query.type = "text";
  query.autocomplete = "off";
  query.inputMode = "search";
  query.spellcheck = false;
  query.value = String(filters.query || "");
  query.placeholder =
    current?.provider.search_placeholder ||
    (current?.provider.id === "xiaohongshu" ? "搜索关键词或粘贴笔记链接" : "搜索素材");
  query.setAttribute("aria-label", "搜索素材");
  query.disabled = unavailable;
  const historyMenu = element(document, "div", "tyis-search-history");
  historyMenu.setAttribute("role", "listbox");
  historyMenu.hidden = true;

  function syncPreset() {
    const preset = root.querySelector('[name="search_preset"]');
    if (preset) {
      preset.value = current.provider.search_presets.some((entry) => entry.value === query.value)
        ? query.value
        : "";
    }
  }

  function updateHistory() {
    historyMenu.replaceChildren();
    if (query.disabled) return;
    const typed = query.value.trim().toLocaleLowerCase();
    const matches = getRecentQueries().filter((item) => item.toLocaleLowerCase().includes(typed));
    for (const item of matches) {
      const option = element(document, "button", "tyis-search-history-item", item);
      option.type = "button";
      option.dataset.recentQuery = item;
      option.setAttribute("role", "option");
      option.addEventListener("pointerdown", (event) => event.preventDefault());
      option.addEventListener("click", () => {
        query.value = item;
        syncPreset();
        onFilterChange("query", item);
        historyMenu.hidden = true;
        onSearch(item);
      });
      historyMenu.append(option);
    }
    historyMenu.hidden = matches.length === 0;
  }

  query.addEventListener("focus", updateHistory);
  query.addEventListener("input", () => {
    syncPreset();
    onFilterChange("query", query.value);
    updateHistory();
  });
  query.addEventListener("keydown", (event) => {
    if (event.key === "Escape") historyMenu.hidden = true;
    if (event.key === "Enter" && !event.isComposing) {
      historyMenu.hidden = true;
      onSearch(query.value.trim());
    }
  });
  searchBox.append(query);
  searchWrap.append(searchBox, historyMenu);
  searchWrap.addEventListener("focusout", (event) => {
    if (!searchWrap.contains(event.relatedTarget)) historyMenu.hidden = true;
  });
  const searchButton = element(document, "button", "tyis-search-button", "搜索");
  searchButton.type = "button";
  searchButton.dataset.action = "search";
  searchButton.disabled = unavailable;
  searchButton.prepend(createIcon(document, "search", 16));
  searchButton.addEventListener("click", () => onSearch(query.value.trim()));
  const refresh = createIconButton(document, "refresh", "刷新结果");
  refresh.dataset.action = "refresh";
  refresh.disabled = unavailable;
  refresh.addEventListener("click", onRefresh);
  searchRow.append(searchWrap, searchButton, refresh);
  if (current?.provider.capabilities?.movie_lookup) {
    const versions = element(document, "button", "tyis-subtle-button", "查找电影版本");
    versions.type = "button";
    versions.title = "通过 TMDB 按中文片名、年份选择电影，也可重新选择已记住的版本";
    versions.addEventListener("click", () => onMovieLookup(query.value.trim()));
    searchRow.append(versions);
  }
  return { searchRow, query, historyMenu };
}
