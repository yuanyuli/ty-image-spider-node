import { createIcon, createIconButton } from "./icons.js";

export function renderSourceControls(context) {
  const {
    document,
    providers = [],
    provider,
    filters = {},
    onSourceChange = () => {},
    onSearch = () => {},
    onRefresh = () => {},
    onCheck = () => {},
    onFilterChange = () => {},
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

  const searchRow = element(document, "div", "tyis-search-row");
  const searchBox = element(document, "label", "tyis-search-box");
  searchBox.append(createIcon(document, "search"));
  const query = element(document, "input", "tyis-query");
  query.name = "query";
  query.type = "search";
  query.value = String(filters.query || "");
  query.placeholder =
    current?.provider.id === "xiaohongshu" ? "搜索关键词或粘贴笔记链接" : "搜索素材";
  query.setAttribute("aria-label", "搜索素材");
  query.disabled = unavailable;
  query.addEventListener("input", () => onFilterChange("query", query.value));
  query.addEventListener("keydown", (event) => {
    if (event.key === "Enter") onSearch(query.value.trim());
  });
  searchBox.append(query);
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
  searchRow.append(searchBox, searchButton, refresh);

  const filterRow = element(document, "div", "tyis-filter-row");
  for (const field of current?.provider.filters || []) {
    filterRow.append(renderField(document, field, filters[field.name], onFilterChange));
  }
  root.append(sourceBar, searchRow, filterRow);
  if (unavailable && current.status.action) {
    const action = element(document, "div", "tyis-source-action");
    action.append(element(document, "span", "", current.status.action));
    const check = element(document, "button", "tyis-subtle-button", "重新检查");
    check.type = "button";
    check.dataset.action = "check-provider";
    check.addEventListener("click", onCheck);
    action.append(check);
    root.append(action);
  }
  return { root, query, status, descriptor: current?.provider || null };
}

function renderField(document, field, supplied, onFilterChange) {
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
