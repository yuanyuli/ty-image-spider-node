import { installLifecycle } from "./lifecycle.js";

const INSTALLED = Symbol("tyImageSpiderInstalled");

export function createImageSpiderExtension({ app, api, document }) {
  return {
    name: "ty.image.spider",
    async beforeRegisterNodeDef(nodeType, nodeData) {
      if (nodeData.name !== "TyImageSpider" || nodeType.prototype[INSTALLED]) return;
      nodeType.prototype[INSTALLED] = true;
      installLifecycle(nodeType, { app, api, document });
    },
  };
}
