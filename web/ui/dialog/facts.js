import { element } from "../../core/dom.js";

export function renderFacts(document, item) {
  const section = element(document, "section", "tyis-detail-section");
  const list = element(document, "dl", "tyis-facts");
  fact(document, list, "作者", item.author || "未知");
  if (item.created_at) fact(document, list, "时间", item.created_at);
  if (item.width && item.height) fact(document, list, "尺寸", `${item.width} × ${item.height}`);
  if (item.image_count > 1) fact(document, list, "图集", `${item.image_count} 张`);
  section.append(list);
  return section;
}

function fact(document, list, key, value) {
  list.append(element(document, "dt", "", key), element(document, "dd", "", value));
}
