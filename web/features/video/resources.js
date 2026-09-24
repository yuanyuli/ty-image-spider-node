export function selectPlaybackResource(detail) {
  return validMedia(detail).find((resource) => resource.role === "playback") || null;
}

export function selectDownloadResource(detail) {
  const resources = validMedia(detail);
  return (
    resources.find((resource) => resource.role === "download") ||
    resources.find((resource) => resource.role === "playback") ||
    null
  );
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  const value = Math.round(seconds);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const remainder = value % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function validMedia(detail) {
  return Array.isArray(detail?.media)
    ? detail.media.filter(
        (resource) =>
          resource?.kind === "video" &&
          typeof resource.url === "string" &&
          resource.url.length > 0 &&
          typeof resource.mime_type === "string" &&
          resource.mime_type.startsWith("video/"),
      )
    : [];
}
