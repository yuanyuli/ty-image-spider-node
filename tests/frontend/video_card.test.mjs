import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

import { decorateVideoCard } from "../../web/features/video/card.js";
import { createGallery } from "../../web/ui/gallery/index.js";

function videoItem(overrides = {}) {
  return {
    provider: "prelinger",
    id: "movie-1",
    kind: "video",
    title: "Design for Dreaming",
    preview_url: "https://archive.org/services/img/movie-1",
    duration_seconds: 558,
    width: 1280,
    height: 720,
    download_mode: "single",
    ...overrides,
  };
}

test("视频卡片只加载静态封面并显示播放标识和时长", () => {
  const document = new JSDOM("<body></body>").window.document;
  const gallery = createGallery({
    document,
    provider: "prelinger",
    descriptor: {
      id: "prelinger",
      presentation: { short_label: "PRE" },
    },
  });

  gallery.render([videoItem()]);

  assert.equal(gallery.root.querySelectorAll("img").length, 1);
  assert.equal(gallery.root.querySelectorAll("video").length, 0);
  assert.equal(gallery.root.querySelector(".tyis-video-play-mark").textContent, "播放");
  assert.equal(gallery.root.querySelector(".tyis-video-duration").textContent, "09:18");
  assert.match(gallery.root.textContent, /1280 × 720/);
});

test("视频卡片装饰器只负责现有媒体区域", () => {
  const document = new JSDOM("<body></body>").window.document;
  const media = document.createElement("div");
  media.append(document.createElement("img"));

  decorateVideoCard(document, media, videoItem({ duration_seconds: 65 }));

  assert.equal(media.querySelectorAll("img").length, 1);
  assert.equal(media.querySelectorAll("video").length, 0);
  assert.match(media.textContent, /01:05/);
});
