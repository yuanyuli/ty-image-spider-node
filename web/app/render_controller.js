import { element } from "../core/dom.js";
import { createGallery } from "../ui/gallery/index.js";
import { renderSourceControls } from "../ui/source_controls/index.js";

export function createRenderController({ document, controlsHost, galleryHost }) {
  function initial() {
    const controls = element(document, "section", "tyis-controls tyis-controls-loading");
    const sourceBar = element(document, "div", "tyis-source-bar");
    sourceBar.append(
      element(document, "strong", "", "正在加载素材源"),
      element(document, "span", "tyis-source-status", "连接中"),
    );
    controls.append(sourceBar, element(document, "div", "tyis-search-placeholder"));
    controlsHost.replaceChildren(controls);
    const gallery = createGallery({ document });
    galleryHost.replaceChildren(gallery.root);
    gallery.setLoading();
    return gallery;
  }

  function providerError(error, onRetry) {
    const controls = element(document, "section", "tyis-controls tyis-controls-error");
    const message = element(
      document,
      "strong",
      "tyis-provider-error-message",
      error.message || "素材源读取失败",
    );
    const retry = element(document, "button", "tyis-subtle-button", "重新加载");
    retry.type = "button";
    retry.dataset.action = "retry-providers";
    retry.addEventListener("click", onRetry);
    controls.append(message, retry);
    controlsHost.replaceChildren(controls);
    const gallery = createGallery({ document });
    galleryHost.replaceChildren(gallery.root);
    gallery.setError(error.message || "素材源读取失败");
    return gallery;
  }

  function controls(context) {
    const view = renderSourceControls({ document, ...context });
    controlsHost.replaceChildren(view.root);
    return view;
  }

  function gallery(context) {
    const view = createGallery({ document, ...context });
    galleryHost.replaceChildren(view.root);
    return view;
  }

  return { initial, providerError, controls, gallery };
}
