import { element } from "../../core/dom.js";
import { normalizePresentation } from "../../core/presentation.js";
import { createIcon } from "../icons.js";

export function createGalleryToolbar({ document, capabilities, descriptor }) {
  const toolbar = element(document, "div", "tyis-gallery-toolbar");
  const count = element(document, "span", "tyis-result-count", "0 项素材");
  const actions = element(document, "div", "tyis-gallery-actions");
  const bulkDownloadButton = element(document, "button", "tyis-subtle-button", "下载本页");
  bulkDownloadButton.type = "button";
  bulkDownloadButton.prepend(createIcon(document, "download", 15));
  bulkDownloadButton.hidden = capabilities.bulk_download !== true;
  const cacheButton = element(document, "button", "tyis-subtle-button", "新增缓存100张");
  cacheButton.title = normalizePresentation(descriptor).cacheDescription;
  cacheButton.type = "button";
  cacheButton.dataset.action = "cache-100";
  cacheButton.hidden = capabilities.cache !== true;
  const cancelCacheButton = element(document, "button", "tyis-subtle-button", "取消缓存");
  cancelCacheButton.type = "button";
  cancelCacheButton.dataset.action = "cancel-cache";
  cancelCacheButton.hidden = true;
  const previousButton = element(document, "button", "tyis-subtle-button", "上一页");
  previousButton.type = "button";
  previousButton.setAttribute("aria-label", "上一页");
  previousButton.append(createIcon(document, "previous", 15));
  previousButton.hidden = true;
  const nextButton = element(document, "button", "tyis-subtle-button", "下一页");
  nextButton.type = "button";
  nextButton.setAttribute("aria-label", "下一页");
  nextButton.append(createIcon(document, "next", 15));
  nextButton.hidden = true;
  actions.append(cacheButton, cancelCacheButton, bulkDownloadButton, previousButton, nextButton);
  toolbar.append(count, actions);
  return {
    toolbar,
    count,
    bulkDownloadButton,
    cacheButton,
    cancelCacheButton,
    previousButton,
    nextButton,
  };
}
