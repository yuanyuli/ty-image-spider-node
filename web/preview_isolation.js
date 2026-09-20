// ComfyUI 1.51 的默认背景回调会按节点 ID 读取执行结果和采样预览，
// 异步加载后写入 imgs，并在下一帧创建预览 widget。纯浏览节点不参与此流程。
const PREVIEW_WIDGETS = new Set([
  "$$canvas-image-preview",
  "$$comfy_animation_preview",
  "video-preview",
]);

export function clearComfyPreview(node) {
  // Vue 输出预览使用此开关；Canvas 预览必须另外截断背景回调。
  node.hideOutputImages = true;
  for (const key of [
    "imgs",
    "images",
    "preview",
    "imageIndex",
    "overIndex",
    "animatedImages",
    "previewMediaType",
    "videoContainer",
  ]) {
    delete node[key];
  }
  for (let index = (node.widgets?.length || 0) - 1; index >= 0; index--) {
    const widget = node.widgets[index];
    if (!PREVIEW_WIDGETS.has(widget.name)) continue;
    widget.onRemove?.();
    node.widgets.splice(index, 1);
  }
}

export function installPreviewIsolation(nodeType) {
  // 不调用原回调：清理之后再绘制、或先绘制再清理，都无法阻止异步回写。
  // 只修改 TyImageSpider 的原型，不改共享输出缓存或其他节点。
  nodeType.prototype.onDrawBackground = function () {
    clearComfyPreview(this);
  };
  nodeType.prototype.onExecuted = function () {
    clearComfyPreview(this);
    this.setDirtyCanvas?.(true, true);
  };
}
