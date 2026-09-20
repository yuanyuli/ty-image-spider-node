"""只提取正文中可信的静态图片；选择 srcset 高清项并去重。"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlsplit

from .museum_assets import image_url
from .download_policy import DownloadPolicy


def article_images(
    markup: str, source: DownloadPolicy, *, max_width: int | None = None
) -> tuple[str, ...]:
    class Images(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.urls: list[str] = []
            self.ignored = 0

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            if tag in {"script", "style", "noscript"}:
                self.ignored += 1
            if tag != "img" or self.ignored:
                return
            fields = dict(attrs)
            for key in ("width", "height"):
                value = fields.get(key) or ""
                if value.isdigit() and int(value) < 100:
                    return
            candidates: list[tuple[int, str]] = []
            for value in (fields.get("srcset") or "").split(","):
                parts = value.strip().rsplit(None, 1)
                if (
                    len(parts) == 2
                    and parts[1].endswith("w")
                    and parts[1][:-1].isdigit()
                ):
                    candidates.append((int(parts[1][:-1]), parts[0]))
            candidates.extend((0, fields.get(key) or "") for key in ("data-src", "src"))
            if max_width is not None:
                bounded = [
                    candidate
                    for candidate in candidates
                    if candidate[0] == 0 or candidate[0] <= max_width
                ]
                if bounded:
                    candidates = bounded
            for _, value in sorted(candidates, reverse=True):
                url = image_url(value, source)
                if url and urlsplit(url).path.lower().endswith(
                    (".jpg", ".jpeg", ".png", ".webp", ".gif")
                ):
                    if url not in self.urls:
                        self.urls.append(url)
                    break

        def handle_endtag(self, tag: str) -> None:
            if tag in {"script", "style", "noscript"} and self.ignored:
                self.ignored -= 1

    parser = Images()
    parser.feed(markup)
    return tuple(parser.urls[:60])
