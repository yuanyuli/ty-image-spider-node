export function renderCollectionDetails(document, detail) {
  const root = document.createElement("section");
  root.className = "tyis-detail-section tyis-collection-info";
  const title = document.createElement("h3");
  title.textContent = "馆藏资料";
  const facts = document.createElement("dl");
  facts.className = "tyis-facts";
  const metadata = detail.item?.metadata || {};
  for (const [key, label] of [
    ["collection", "收藏机构"],
    ["category", "类别"],
    ["medium", "媒介"],
    ["dimensions", "作品尺寸"],
    ["place", "产地"],
    ["rights", "使用条件"],
    ["resolution_note", "图片规格"],
  ]) {
    if (!metadata[key]) continue;
    const term = document.createElement("dt");
    term.textContent = label;
    const value = document.createElement("dd");
    value.textContent = String(metadata[key]);
    facts.append(term, value);
  }
  root.append(title, facts);
  const content = detail.content || metadata.description;
  if (content) {
    const description = document.createElement("p");
    description.className = "tyis-detail-copy";
    description.textContent = String(content);
    root.append(description);
  }
  return root;
}
