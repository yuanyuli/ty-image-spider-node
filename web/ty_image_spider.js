export { createImageSpiderExtension } from "./app/extension.js";

import { createImageSpiderExtension } from "./app/extension.js";

if (typeof window !== "undefined" && !window.__TY_IMAGE_SPIDER_DISABLE_AUTO_REGISTER__) {
  Promise.all([import("../../scripts/app.js"), import("../../scripts/api.js")]).then(
    ([{ app }, { api }]) =>
      app.registerExtension(createImageSpiderExtension({ app, api, document })),
  );
}
