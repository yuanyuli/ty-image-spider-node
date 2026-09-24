import { formatDuration } from "./resources.js";

export function decorateVideoCard(document, media, item) {
  media.classList.add("is-video");
  const play = document.createElement("span");
  play.className = "tyis-video-play-mark";
  play.textContent = "播放";
  media.append(play);
  const duration = formatDuration(item.duration_seconds);
  if (duration) {
    const badge = document.createElement("span");
    badge.className = "tyis-video-duration";
    badge.textContent = duration;
    media.append(badge);
  }
}
