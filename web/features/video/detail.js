import { createVideoPlayer } from "./player.js";
import { selectDownloadResource } from "./resources.js";

export function renderVideoDetail(document, detail, context = {}) {
  const root = document.createElement("section");
  root.className = "tyis-video-detail";
  const player = createVideoPlayer({ document, detail, onError: context.onError });
  let facts = renderMediaFacts(document, detail);
  root.append(player.root, facts);
  let downloadResource = selectDownloadResource(detail);

  function update(nextDetail) {
    player.update(nextDetail);
    downloadResource = selectDownloadResource(nextDetail);
    const nextFacts = renderMediaFacts(document, nextDetail);
    facts.replaceWith(nextFacts);
    facts = nextFacts;
  }

  return {
    root,
    update,
    destroy: player.destroy,
    get downloadResource() {
      return downloadResource;
    },
  };
}

function renderMediaFacts(document, detail) {
  const list = document.createElement("dl");
  list.className = "tyis-video-facts";
  const playback = detail?.media?.find((resource) => resource.role === "playback");
  const download = selectDownloadResource(detail);
  appendFact(document, list, "播放规格", playback?.label || "暂不可播放");
  if (download) appendFact(document, list, "下载规格", download.label || download.mime_type);
  const resource = playback || download;
  const width = resource?.width || detail?.item?.width;
  const height = resource?.height || detail?.item?.height;
  if (width && height) appendFact(document, list, "画面尺寸", `${width} × ${height}`);
  if (download?.size_bytes)
    appendFact(document, list, "文件大小", formatBytes(download.size_bytes));
  return list;
}

function appendFact(document, list, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value;
  list.append(term, description);
}

function formatBytes(value) {
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${Number(amount.toFixed(amount >= 10 || index === 0 ? 0 : 1))} ${units[index]}`;
}
