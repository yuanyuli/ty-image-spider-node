import { selectPlaybackResource } from "./resources.js";

export function createVideoPlayer({ document, detail, onError = () => {} }) {
  const root = document.createElement("div");
  root.className = "tyis-video-player";
  let video = null;
  let destroyed = false;

  function release() {
    if (!video) return;
    video.pause();
    video.removeAttribute("src");
    video.load();
    video.remove();
    video = null;
  }

  function renderUnavailable() {
    const empty = document.createElement("p");
    empty.className = "tyis-video-unavailable";
    empty.textContent = "当前视频暂不可播放";
    root.append(empty);
  }

  function update(nextDetail) {
    if (destroyed) return;
    release();
    root.replaceChildren();
    const resource = selectPlaybackResource(nextDetail);
    if (!resource) {
      renderUnavailable();
      return;
    }
    video = document.createElement("video");
    const currentVideo = video;
    video.controls = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.poster = nextDetail?.item?.preview_url || "";
    video.style.objectFit = "contain";
    video.setAttribute("src", resource.url);
    video.addEventListener("error", () => {
      if (destroyed || video !== currentVideo) return;
      release();
      root.replaceChildren();
      renderUnavailable();
      onError("当前视频加载失败");
    });
    root.append(video);
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    release();
  }

  update(detail);
  return { root, update, destroy };
}
