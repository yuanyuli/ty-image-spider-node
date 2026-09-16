"""小红书页面只读提取脚本与结果归一化。"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse


_NOTE_PATH = re.compile(r"^/(?:explore|search_result|note)/([0-9a-zA-Z_-]+)/*$")


def build_card_extract_js() -> str:
    return r"""
(() => {
  const clean = (value) => (value || '').trim();
  const rows = [];
  const seen = new Set();
  const cards = document.querySelectorAll(
    'section.note-item, section:has(a[href*="/search_result/"]), section:has(a[href*="/explore/"])'
  );
  for (const card of cards) {
    const link = card.querySelector('a[href*="/search_result/"], a[href*="/explore/"]');
    if (!link) continue;
    let url = '';
    try {
      const parsed = new URL(link.getAttribute('href') || '', 'https://www.xiaohongshu.com/');
      if (parsed.protocol !== 'https:' || !parsed.hostname.endsWith('xiaohongshu.com')) continue;
      url = parsed.href;
    } catch (_) { continue; }
    const matched = new URL(url).pathname.match(/\/(?:explore|search_result|note)\/([0-9a-zA-Z_-]+)/);
    if (!matched || seen.has(matched[1])) continue;
    seen.add(matched[1]);
    const image = card.querySelector('img');
    const previewUrl = clean(image?.currentSrc || image?.src || image?.getAttribute('data-src'));
    const countText = clean(card.querySelector('[class*="image-count"], [class*="count-badge"]')?.textContent);
    const count = Number.parseInt(countText, 10);
    rows.push({ id: matched[1], url, preview_url: previewUrl, image_count: Number.isFinite(count) ? count : 1 });
  }
  return rows;
})()
""".strip()


def build_detail_extract_js(note_id: str) -> str:
    encoded_id = json.dumps(note_id)
    return rf"""
(() => {{
  const requestedId = {encoded_id};
  const matched = (location.pathname || '').match(/\/(?:explore|search_result|note)\/([0-9a-zA-Z_-]+)/);
  const id = matched?.[1] || requestedId;
  const images = [];
  const seen = new Set();
  const push = (raw) => {{
    if (!raw || typeof raw !== 'string') return;
    try {{
      const value = new URL(raw, location.origin).href;
      if (!seen.has(value)) {{ seen.add(value); images.push(value); }}
    }} catch (_) {{}}
  }};
  try {{
    const map = window.__INITIAL_STATE__?.note?.noteDetailMap || {{}};
    const entry = map[id];
    const list = entry?.note?.imageList || entry?.imageList || [];
    for (const image of list) {{
      push(image?.urlDefault || image?.urlPre || image?.url || image?.infoList?.[0]?.url);
    }}
  }} catch (_) {{}}
  if (images.length === 0) {{
    for (const image of document.querySelectorAll('#noteContainer img')) {{
      push(image.currentSrc || image.src || image.getAttribute('data-src'));
    }}
  }}
  return {{ id, images }};
}})()
""".strip()


def merge_search_rows(rows: object, cards: object) -> list[dict[str, Any]]:
    row_values = _as_rows(rows)
    card_values = _as_rows(cards)
    cards_by_id: dict[str, Mapping[str, Any]] = {}
    for card in card_values:
        card_id = str(card.get("id") or "")
        if card_id:
            cards_by_id[card_id] = card

    merged: list[dict[str, Any]] = []
    for row in row_values:
        source_url = _trusted_note_url(row.get("url"))
        if not source_url:
            continue
        note_id = _note_id(source_url)
        card = cards_by_id.get(note_id, {})
        card_url = _trusted_note_url(card.get("url"))
        if card_url and "xsec_token=" in card_url:
            source_url = card_url
        preview = _trusted_image_url(card.get("preview_url"))
        image_count = card.get("image_count", 1)
        if (
            not isinstance(image_count, int)
            or isinstance(image_count, bool)
            or image_count < 1
        ):
            image_count = 1
        merged.append(
            {
                "id": note_id,
                "title": _text(row.get("title")),
                "author": _text(row.get("author")),
                "likes": _text(row.get("likes")) or "0",
                "created_at": _text(row.get("published_at")) or None,
                "source_url": source_url,
                "preview_url": preview,
                "image_count": image_count,
            }
        )
    return merged


def trusted_images(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping) and "data" in value:
        value = value["data"]
    if not isinstance(value, Mapping):
        return ()
    raw_images = value.get("images")
    if not isinstance(raw_images, Sequence) or isinstance(raw_images, (str, bytes)):
        return ()
    result: list[str] = []
    for raw in raw_images:
        url = _trusted_image_url(raw)
        if url and url not in result:
            result.append(url)
    return tuple(result)


def detail_note_id(value: object, fallback: str) -> str:
    if isinstance(value, Mapping) and "data" in value:
        value = value["data"]
    if isinstance(value, Mapping):
        candidate = value.get("id")
        if isinstance(candidate, str) and re.fullmatch(
            r"[0-9a-zA-Z_-]{1,64}", candidate
        ):
            return candidate
    return fallback


def _as_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping) and "data" in value:
        value = value["data"]
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _trusted_note_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")
    ):
        return None
    return value if _NOTE_PATH.fullmatch(parsed.path) else None


def _trusted_image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    trusted = (
        host == "xhscdn.com"
        or host.endswith(".xhscdn.com")
        or host == "xiaohongshu.com"
        or host.endswith(".xiaohongshu.com")
    )
    return value if parsed.scheme == "https" and trusted else None


def _note_id(url: str) -> str:
    matched = _NOTE_PATH.fullmatch(urlparse(url).path)
    return matched.group(1) if matched else ""


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
