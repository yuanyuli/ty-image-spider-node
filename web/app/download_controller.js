export function createDownloadController({ client, state, downloadLocation, setActivity }) {
  function resultMessage(result) {
    const files = Array.isArray(result?.files) ? result.files.filter(Boolean) : [];
    if (!files.length) return result?.message || "下载完成";
    const outputRoot = typeof result?.output_root === "string" ? result.output_root.trim() : "";
    const paths = files.map((file) => {
      if (!outputRoot) return `output/ty-node/${file}`;
      const normalizedRoot = outputRoot.replace(/[\\/]+$/, "");
      const normalizedFile = String(file).replaceAll("/", "\\");
      return `${normalizedRoot}\\${normalizedFile}`;
    });
    return `${result?.message || "下载完成"}：${paths.join("、")}`;
  }

  function showResult(result) {
    setActivity(result?.message || "下载完成");
    downloadLocation.textContent = resultMessage(result);
    downloadLocation.title = downloadLocation.textContent;
    downloadLocation.hidden = false;
  }

  async function downloadItem(item) {
    downloadLocation.hidden = true;
    setActivity("下载中");
    try {
      showResult(
        await client.requestJson("/ty-image-spider/download", {
          method: "POST",
          body: { item },
        }),
      );
    } catch (error) {
      setActivity(error.message || "下载失败", true);
    }
  }

  async function downloadImage(item, imageIndex) {
    try {
      const result = await client.requestJson("/ty-image-spider/download-image", {
        method: "POST",
        body: { item, image_index: imageIndex },
      });
      showResult(result);
      return resultMessage(result);
    } catch (error) {
      if (error.code === "invalid_response" && (error.status === 404 || error.status === 405)) {
        throw new Error("请重启 ComfyUI 以启用保存当前图片功能");
      }
      throw error;
    }
  }

  async function downloadPage(items) {
    downloadLocation.hidden = true;
    setActivity("下载本页");
    try {
      showResult(
        await client.requestJson("/ty-image-spider/download-page", {
          method: "POST",
          body: { provider: state.get().provider, items },
        }),
      );
    } catch (error) {
      setActivity(error.message || "下载失败", true);
    }
  }

  return { downloadItem, downloadImage, downloadPage };
}
