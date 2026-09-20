export function renderTmdbHelp(document) {
  const details = document.createElement("details");
  details.className = "tyis-tmdb-help";
  const summary = document.createElement("summary");
  summary.textContent = "TMDB 配置与鸣谢";
  const logo = document.createElement("img");
  logo.src = new URL("./tmdb-logo.svg", import.meta.url).href;
  logo.alt = "TMDB";
  logo.width = 72;
  const instructions = document.createElement("p");
  instructions.textContent =
    "扩展中文片名查询需 TMDB API 读取访问令牌。在节点目录 .local/tmdb.json 中填写 read_access_token，保存后即可重试，无需重启。未配置时仍可使用内置片单。";
  const links = document.createElement("p");
  for (const [name, url] of [
    ["申请 API 凭据", "https://www.themoviedb.org/settings/api"],
    ["使用与署名要求", "https://developer.themoviedb.org/docs/faq"],
  ]) {
    const link = document.createElement("a");
    link.textContent = name;
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    links.append(link);
  }
  const credit = document.createElement("p");
  credit.textContent = "This product uses the TMDB API but is not endorsed or certified by TMDB.";
  details.append(summary, logo, instructions, links, credit);
  return details;
}
