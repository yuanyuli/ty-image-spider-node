import { createIcon, createIconButton } from "./icons.js";
import { renderTmdbHelp } from "./tmdb_help.js";

export function renderSourceControls(context) {
  const {
    document,
    providers = [],
    provider,
    filters = {},
    getRecentQueries = () => [],
    onSourceChange = () => {},
    onSearch = () => {},
    onRefresh = () => {},
    onCheck = () => {},
    onConnect = () => {},
    onFilterChange = () => {},
    onMovieLookup = () => {},
  } = context;
  const current = providers.find((entry) => entry.provider.id === provider) || providers[0];
  const unavailable = current?.status?.available === false;
  const root = element(document, "section", "tyis-controls");

  const sourceBar = element(document, "div", "tyis-source-bar");
  const segments = element(document, "div", "tyis-source-segments");
  segments.setAttribute("role", "tablist");
  for (const entry of providers) {
    const button = element(document, "button", "tyis-source-tab", entry.provider.label);
    button.type = "button";
    button.dataset.provider = entry.provider.id;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(entry.provider.id === current?.provider.id));
    button.dataset.available = String(entry.status?.available !== false);
    button.addEventListener("click", () => onSourceChange(entry.provider.id));
    segments.append(button);
  }
  const status = element(
    document,
    "span",
    `tyis-source-status${current?.status?.available === false ? " is-unavailable" : ""}`,
    current?.status?.message || (current?.status?.available === false ? "不可用" : "就绪"),
  );
  sourceBar.append(segments, status);

  if (current?.provider.id === "xiaohongshu") {
    const connect = element(document, "button", "tyis-subtle-button", "一键连接 OpenCLI");
    connect.type = "button";
    connect.dataset.action = "connect-opencli";
    connect.addEventListener("click", onConnect);
    sourceBar.append(connect);
  }

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

  const filterRow = element(document, "div", "tyis-filter-row");
  if (current?.provider.search_presets?.length) {
    filterRow.append(
      renderField(
        document,
        {
          name: "search_preset",
          label: "中文精选片单",
          kind: "select",
          default: "",
          options: [
            { value: "", label: "浏览全部 / 自行输入片名" },
            ...current.provider.search_presets,
          ],
        },
        current.provider.search_presets.some((entry) => entry.value === query.value)
          ? query.value
          : "",
        (_name, value) => {
          query.value = value;
          historyMenu.hidden = true;
          onFilterChange("query", value);
          onSearch(value);
        },
        { disabled: unavailable },
      ),
    );
  }
  for (const field of current?.provider.filters || []) {
    filterRow.append(
      renderField(document, field, filters[field.name], onFilterChange, {
        disabled:
          current?.provider.id === "wallhaven" &&
          field.name === "top_range" &&
          (filters.sorting ?? "relevance") !== "toplist",
      }),
    );
  }
  root.append(sourceBar, searchRow, filterRow);
  if (current?.provider.capabilities?.movie_lookup) root.append(renderTmdbHelp(document));
  if (unavailable) {
    const action = element(document, "div", "tyis-source-action");
    if (current.status.action) {
      action.append(element(document, "span", "", current.status.action));
    }
    const check = element(document, "button", "tyis-subtle-button", "重新检查");
    check.type = "button";
    check.dataset.action = "check-provider";
    check.addEventListener("click", onCheck);
    action.append(check);
    root.append(action);
  }
  return { root, query, status, descriptor: current?.provider || null };
}

function renderField(document, field, supplied, onFilterChange, options = {}) {
  const wrapper = element(document, "label", `tyis-filter tyis-filter-${field.kind}`);
  const label = element(document, "span", "tyis-filter-label", field.label);
  const value = supplied ?? field.default;
  let control;
  if (field.kind === "select") {
    control = element(document, "select", "tyis-field");
    for (const option of field.options || []) {
      const node = element(document, "option", "", option.label);
      node.value = option.value;
      control.append(node);
    }
    control.value = value ?? "";
  } else if (field.kind === "toggle") {
    wrapper.classList.add("tyis-toggle");
    control = element(document, "input", "tyis-toggle-input");
    control.type = "checkbox";
    control.checked = Boolean(value);
  } else {
    control = element(document, "input", "tyis-field");
    control.type = field.kind === "number" ? "number" : "text";
    control.value = value ?? "";
    if (field.minimum !== undefined) control.min = String(field.minimum);
    if (field.maximum !== undefined) control.max = String(field.maximum);
    if (field.placeholder) control.placeholder = field.placeholder;
  }
  control.name = field.name;
  control.disabled = Boolean(options.disabled);
  control.addEventListener("change", () => {
    const next =
      field.kind === "toggle"
        ? control.checked
        : field.kind === "number"
          ? Number(control.value)
          : control.value;
    onFilterChange(field.name, next);
  });
  if (field.kind === "toggle") wrapper.append(control, label);
  else wrapper.append(label, control);
  return wrapper;
}

function element(document, tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
