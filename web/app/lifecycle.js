import {
  clearComfyPreview,
  installPreviewIsolation,
} from "../features/preview/preview_isolation.js";
import { mountNode } from "./workspace.js";

export function installLifecycle(nodeType, dependencies) {
  const created = nodeType.prototype.onNodeCreated;
  const configured = nodeType.prototype.onConfigure;
  const removed = nodeType.prototype.onRemoved;
  installPreviewIsolation(nodeType);
  nodeType.prototype.onNodeCreated = function (...args) {
    const result = created?.apply(this, args);
    clearComfyPreview(this);
    mountNode(this, dependencies);
    return result;
  };
  nodeType.prototype.onConfigure = function (...args) {
    const result = configured?.apply(this, args);
    clearComfyPreview(this);
    mountNode(this, dependencies).restore();
    return result;
  };
  nodeType.prototype.onRemoved = function (...args) {
    this.tyImageSpider?.dispose();
    this.tyImageSpider = null;
    return removed?.apply(this, args);
  };
}
