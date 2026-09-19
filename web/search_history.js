const STORAGE_KEY = "ty-image-spider:search-history";
const MAX_QUERIES = 8;

export function createSearchHistory(storage) {
  function read() {
    try {
      const value = JSON.parse(storage?.getItem(STORAGE_KEY) || "{}");
      return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch (_) {
      return {};
    }
  }

  function list(provider) {
    const values = read()[provider];
    return Array.isArray(values) ? values.filter(isKeyword).slice(0, MAX_QUERIES) : [];
  }

  function add(provider, value) {
    const query = typeof value === "string" ? value.trim() : "";
    if (!isKeyword(query)) return;
    const data = read();
    data[provider] = [query, ...list(provider).filter((item) => item !== query)].slice(
      0,
      MAX_QUERIES,
    );
    try {
      storage?.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (_) {
      // 浏览器禁用本地存储时，搜索本身仍可使用。
    }
  }

  return { list, add };
}

function isKeyword(value) {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= 120 &&
    !/^https?:\/\//i.test(value) &&
    !/(?:xsec_token|authorization|cookie)=/i.test(value)
  );
}
