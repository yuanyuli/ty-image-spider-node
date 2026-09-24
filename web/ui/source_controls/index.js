import { element } from "../../core/dom.js";
import { renderTmdbHelp } from "../../features/movie/tmdb_help.js";
import { visibleSources } from "../../core/presentation.js";
import { renderField } from "./filters.js";
import { createSourceNavigation } from "./navigation.js";
import { createSearchControls } from "./search.js";

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
  const visible = visibleSources(providers);
  const current = visible.find((entry) => entry.provider.id === provider) || visible[0];
  const unavailable = current?.status?.available === false;
  const root = element(document, "section", "tyis-controls");

  const { sourceBar, status } = createSourceNavigation({
    document,
    visible,
    current,
    onSourceChange,
  });

  if (current?.provider.id === "xiaohongshu") {
    const connect = element(document, "button", "tyis-subtle-button", "一键连接 OpenCLI");
    connect.type = "button";
    connect.dataset.action = "connect-opencli";
    connect.addEventListener("click", onConnect);
    sourceBar.append(connect);
  }

  const { searchRow, query, historyMenu } = createSearchControls({
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
  });

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
