import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { renderVideoDetail } from "../../web/features/video/detail.js";
import { createVideoPlayer } from "../../web/features/video/player.js";
import {
  selectDownloadResource,
  selectPlaybackResource,
} from "../../web/features/video/resources.js";

function detail(media = []) {
  return {
    item: {
      provider: "commons-video",
      id: "123",
      kind: "video",
      title: "Portrait film",
      preview_url: "https://upload.wikimedia.org/poster.jpg",
      width: 720,
      height: 1280,
      duration_seconds: 95,
      metadata: { rights: "CC BY-SA 4.0" },
    },
    images: ["https://upload.wikimedia.org/poster.jpg"],
    media,
  };
}

const playback = {
  kind: "video",
  url: "https://upload.wikimedia.org/play.mp4",
  mime_type: "video/mp4",
  role: "playback",
  width: 720,
  height: 1280,
  duration_seconds: 95,
  label: "720p MP4",
};
const download = {
  ...playback,
  url: "https://upload.wikimedia.org/original.webm",
  mime_type: "video/webm",
  role: "download",
  label: "原始文件",
  size_bytes: 10485760,
};

test("播放和下载资源选择稳定且支持下载回退", () => {
  const value = detail([download, playback]);
  assert.equal(selectPlaybackResource(value), playback);
  assert.equal(selectDownloadResource(value), download);
  assert.equal(selectPlaybackResource(detail([download])), null);
  assert.equal(selectDownloadResource(detail([playback])), playback);
});

test("详情按需创建一个原生播放器且不会自动播放", () => {
  const document = new JSDOM("<body></body>").window.document;
  const view = createVideoPlayer({ document, detail: detail([download, playback]) });
  const video = view.root.querySelector("video");

  assert.equal(view.root.querySelectorAll("video").length, 1);
  assert.equal(video.controls, true);
  assert.equal(video.playsInline, true);
  assert.equal(video.preload, "metadata");
  assert.equal(video.hasAttribute("autoplay"), false);
  assert.equal(video.getAttribute("src"), playback.url);
  assert.equal(video.style.objectFit, "contain");
});

test("没有播放资源时保留不可播放状态和下载资源", () => {
  const document = new JSDOM("<body></body>").window.document;
  const view = renderVideoDetail(document, detail([download]), {});

  assert.equal(view.root.querySelector("video"), null);
  assert.match(view.root.textContent, /暂不可播放/);
  assert.equal(view.downloadResource, download);
});

test("视频详情显示归一化媒体规格而不读取来源私有字段", () => {
  const document = new JSDOM("<body></body>").window.document;
  const view = renderVideoDetail(document, detail([playback, download]), {});

  assert.match(view.root.textContent, /720p MP4/);
  assert.match(view.root.textContent, /原始文件/);
  assert.match(view.root.textContent, /720 × 1280/);
  assert.match(view.root.textContent, /10 MB/);
});

test("销毁播放器会暂停、移除地址并刷新且可以重复调用", () => {
  const document = new JSDOM("<body></body>").window.document;
  const calls = [];
  const view = createVideoPlayer({ document, detail: detail([playback]) });
  const video = view.root.querySelector("video");
  video.pause = () => calls.push("pause");
  video.load = () => calls.push("load");

  view.destroy();
  view.destroy();

  assert.deepEqual(calls, ["pause", "load"]);
  assert.equal(video.hasAttribute("src"), false);
});
