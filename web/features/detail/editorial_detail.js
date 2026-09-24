export function renderEditorialDetails(document, detail) {
  const root = document.createElement("section");
  root.className = "tyis-detail-section tyis-editorial-info";
  const heading = document.createElement("h3");
  heading.textContent = "作品说明";
  const description = document.createElement("p");
  description.className = "tyis-detail-copy";
  description.textContent =
    detail.content || detail.item?.metadata?.description || "完整介绍与图片署名见来源页面。";
  root.append(heading, description);
  return root;
}
