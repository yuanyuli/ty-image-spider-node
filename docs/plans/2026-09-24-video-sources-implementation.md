# 视频素材源实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 TY Image Spider 中加入可搜索、预览、缓存封面并按需下载的 Prelinger、Wikimedia Commons 视频和 NASA 视频来源。

**Architecture:** 领域层新增与来源无关的媒体资源契约；视频下载基础设施独立处理策略、签名与流式文件写入；每个来源以 Client、Normalizer、Provider 三层实现；前端视频功能位于独立 feature 目录并由现有画廊和详情组件组合。缓存继续只读取静态 `preview_url`，视频文件只能由用户明确下载。

**Tech Stack:** Python 3.10+、dataclasses、urllib、SQLite、Pillow 封面校验、原生 ES modules、原生 `<video>`、Node test、jsdom、pytest、Ruff、Mypy、Prettier。

**Spec:** `docs/specs/2026-09-24-video-sources-design.md`

## Global Constraints

- 节点保持零输出端口，视频不传给下游 ComfyUI 节点。
- 首批来源固定为 `prelinger`、`commons-video`、`nasa-video`，均不要求账号或 API Key。
- 列表只加载静态封面；详情打开后才设置视频地址；关闭详情必须释放播放器资源。
- 后台缓存只保存封面、详情和索引，不下载视频文件。
- 视频只支持单项下载，不提供整页批量下载；默认单文件上限为 `2 * 1024 * 1024 * 1024` 字节。
- 只接受 HTTPS、标准443端口、无凭据 URL 和来源策略允许的主机；重定向终点必须再次校验。
- 保持现有图片 Provider、工作流字段、路由成功包络和旧 SQLite 索引兼容。
- 执行单一职责、开闭、里氏替换、接口隔离、依赖倒置和迪米特法则；不得新增跨来源或跨层大管家类。
- 新增目录必须声明允许职责和禁止依赖，结构测试必须阻止越界导入。
- Python、代码注释、测试名称、README 和用户文档使用中文；公开字段和 API 标识使用稳定英文名称。

## Review Focus

- 上游把 HTML 错误页标成 `video/mp4` 时，下载器必须通过文件签名拒绝并清理临时文件；由任务3测试覆盖。
- `Content-Length` 缺失、伪造或超过2 GiB时，流式计数必须保持硬上限且不把响应读入内存；由任务3测试覆盖。
- 旧缓存详情没有 `media` 字段时必须继续恢复图片详情；视频缓存恢复后播放地址不能被本地封面 URL 覆盖；由任务1和任务7测试覆盖。
- 详情快速切换或关闭时，旧播放器必须暂停、移除 `src` 并执行 `load()`，迟到详情不能复活已关闭播放器；由任务8测试覆盖。
- 来源返回没有可播放派生文件但有可下载原文件时，详情必须保留封面、许可和下载能力并显示不可播放状态；由任务4至任务6及任务8测试覆盖。

---

### Task 1: 领域媒体契约与索引兼容

**Files:**
- Modify: `src/ty_image_spider/domain/assets.py`
- Modify: `src/ty_image_spider/domain/__init__.py`
- Modify: `src/ty_image_spider/infrastructure/asset_index.py`
- Modify: `tests/backend/domain/test_models.py`
- Modify: `tests/backend/infrastructure/test_asset_index.py`

**Interfaces:**
- Produces: `MediaResource.from_untrusted(value) -> MediaResource`
- Produces: `AssetItem.duration_seconds: int | None`
- Produces: `AssetDetail.media`，值为不可变的 `MediaResource` 元组。
- Preserves: `AssetDetail.images` and all existing serialized fields.

- [ ] **Step 1: Write the failing domain tests**

Add tests equivalent to:

```python
def test_video_media_resource_round_trips():
    resource = MediaResource(
        kind="video",
        url="https://archive.org/download/item/video.mp4",
        mime_type="video/mp4",
        role="playback",
        width=1280,
        height=720,
        duration_seconds=42,
        size_bytes=1024,
        label="720p MP4",
    )
    item = AssetItem("prelinger", "item", kind="video", duration_seconds=42)
    detail = AssetDetail(item, media=(resource,))
    assert MediaResource.from_untrusted(resource.to_dict()) == resource
    assert detail.to_dict()["media"] == [resource.to_dict()]


def test_media_resource_rejects_invalid_role_and_url_shape():
    with pytest.raises(SpiderError, match="媒体资源"):
        MediaResource.from_untrusted({"kind": "video", "url": [], "role": "other"})
```

Add index tests proving a video detail round-trips through SQLite and an old image detail without `media` still restores.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/domain/test_models.py tests/backend/infrastructure/test_asset_index.py
```

Expected: import or constructor failures because `MediaResource`, `duration_seconds` and `AssetDetail.media` do not exist.

- [ ] **Step 3: Implement the immutable contracts**

Implement:

```python
@dataclass(frozen=True, slots=True)
class MediaResource:
    kind: str
    url: str
    mime_type: str
    role: str
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    size_bytes: int | None = None
    label: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "kind": self.kind,
            "url": self.url,
            "mime_type": self.mime_type,
            "role": self.role,
            "label": self.label,
        }
        for name in ("width", "height", "duration_seconds", "size_bytes"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result

    @classmethod
    def from_untrusted(cls, value: object) -> "MediaResource":
        if not isinstance(value, Mapping):
            raise SpiderError("invalid_media", "媒体资源必须是对象")
        kind, url = value.get("kind"), value.get("url")
        mime_type, role = value.get("mime_type"), value.get("role")
        if (
            kind != "video"
            or not isinstance(url, str)
            or not url
            or not isinstance(mime_type, str)
            or not mime_type.startswith("video/")
            or role not in {"playback", "download"}
        ):
            raise SpiderError("invalid_media", "媒体资源字段无效")
        integers: dict[str, int | None] = {}
        for name in ("width", "height", "duration_seconds", "size_bytes"):
            raw = value.get(name)
            if raw is not None and (
                not isinstance(raw, int) or isinstance(raw, bool) or raw < 0
            ):
                raise SpiderError("invalid_media", f"媒体资源字段 {name} 无效")
            integers[name] = raw
        label = value.get("label", "")
        if not isinstance(label, str):
            raise SpiderError("invalid_media", "媒体资源标签必须是字符串")
        return cls(kind, url, mime_type, role, label=label, **integers)
```

Validation accepts only `kind == "video"`, roles `playback` and `download`, non-empty string URL/MIME, and non-negative integer optional metrics. Extend `AssetItem` serialization for `duration_seconds`, extend `AssetDetail.to_dict()`, and parse cached media in `AssetIndex.detail()` without changing old image behavior.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/domain src/ty_image_spider/infrastructure/asset_index.py tests/backend/domain/test_models.py tests/backend/infrastructure/test_asset_index.py
git commit -m "feat: add video media domain contracts"
```

### Task 2: 目录边界与依赖规则

**Files:**
- Create: `docs/architecture/module-boundaries.md`
- Create: `src/ty_image_spider/infrastructure/video/__init__.py`
- Create: `src/ty_image_spider/providers/videos/__init__.py`
- Create: `src/ty_image_spider/providers/videos/shared/__init__.py`
- Create: `web/features/video/BOUNDARY.md`
- Create: `tests/backend/app/test_video_module_boundaries.py`
- Modify: `tests/frontend/module_boundaries.test.mjs`

**Interfaces:**
- Produces: machine-checked dependency direction for every new video directory.
- Preserves: no runtime import side effects from boundary declarations.

- [ ] **Step 1: Write failing structure tests**

The Python test must parse imports with `ast` and assert:

```python
FORBIDDEN_BY_ROOT = {
    "src/ty_image_spider/domain": ("ty_image_spider.infrastructure", "ty_image_spider.providers", "folder_paths", "server"),
    "src/ty_image_spider/infrastructure/video": ("ty_image_spider.providers", "ty_image_spider.api", "ty_image_spider.app"),
    "src/ty_image_spider/providers/videos": ("ty_image_spider.api", "ty_image_spider.app", "folder_paths", "server"),
}
```

It must also reject imports from one concrete video source package into another. The frontend test must reject imports from `web/features/video/` into `web/app/` and reject literal checks for `prelinger`, `commons-video` or `nasa-video` inside `web/ui/`.

- [ ] **Step 2: Run boundary tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/app/test_video_module_boundaries.py
node --test tests/frontend/module_boundaries.test.mjs
```

Expected: missing directory/boundary declarations fail.

- [ ] **Step 3: Add boundary declarations**

Document for each directory: owned responsibilities, permitted dependencies, forbidden dependencies and extension point. Python `__init__.py` files contain only package docstrings and explicit public exports; they do not construct clients or register providers.

- [ ] **Step 4: Run boundary tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add docs/architecture src/ty_image_spider/infrastructure/video src/ty_image_spider/providers/videos web/features/video/BOUNDARY.md tests/backend/app/test_video_module_boundaries.py tests/frontend/module_boundaries.test.mjs
git commit -m "test: enforce video module boundaries"
```

### Task 3: 受限流式视频下载基础设施

**Files:**
- Create: `src/ty_image_spider/infrastructure/video/policy.py`
- Create: `src/ty_image_spider/infrastructure/video/signatures.py`
- Create: `src/ty_image_spider/infrastructure/video/files.py`
- Create: `src/ty_image_spider/infrastructure/video/downloader.py`
- Modify: `src/ty_image_spider/infrastructure/video/__init__.py`
- Create: `tests/backend/infrastructure/test_video_downloader.py`

**Interfaces:**
- Produces: `VideoDownloadPolicy(provider_id, host_rule, id_pattern, max_bytes=2 * 1024**3)`.
- Produces: `detect_video_extension(header: bytes) -> str | None` for `.mp4`, `.webm`, `.ogv`.
- Produces: `find_valid_video(directory: Path, item_id: str) -> Path | None`.
- Produces: `VideoDownloader.download(resource: MediaResource, item_id: str, output_root: Path) -> DownloadResult`.

- [ ] **Step 1: Write failing downloader tests**

Tests must cover valid MP4/WebM/Ogg signatures, unsafe URL, unsafe redirect, invalid ID, declared oversize, streamed oversize without `Content-Length`, interrupted reads, HTML disguised as video, atomic replacement of a damaged canonical file and reuse of an existing valid file without opening the network.

Use small fake byte streams such as:

```python
MP4 = b"\x00\x00\x00\x18ftypisom" + b"x" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"x" * 32
OGG = b"OggS" + b"x" * 32
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/infrastructure/test_video_downloader.py
```

Expected: module imports fail.

- [ ] **Step 3: Implement policy, signature and file units**

`policy.py` validates ID and normalized URL. `signatures.py` contains no file system or HTTP code. `files.py` only validates existing canonical video files. `downloader.py` streams 1 MiB chunks into a same-directory temporary file, counts bytes, flushes and `fsync`s, detects the extension from the first bytes, then uses `os.replace`. Any failure unlinks the temporary file.

- [ ] **Step 4: Run downloader tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/infrastructure/video tests/backend/infrastructure/test_video_downloader.py
git commit -m "feat: add secure streaming video downloader"
```

### Task 4: Prelinger Archives Provider

**Files:**
- Create: `src/ty_image_spider/providers/videos/prelinger/__init__.py`
- Create: `src/ty_image_spider/providers/videos/prelinger/client.py`
- Create: `src/ty_image_spider/providers/videos/prelinger/normalizer.py`
- Create: `src/ty_image_spider/providers/videos/prelinger/provider.py`
- Create: `tests/fixtures/prelinger_search.json`
- Create: `tests/fixtures/prelinger_metadata.json`
- Create: `tests/backend/providers/test_prelinger_provider.py`

**Interfaces:**
- Produces: `PrelingerClient.search(query, page, sort, refresh=False) -> Mapping[str, object]`.
- Produces: `PrelingerClient.metadata(identifier, refresh=False) -> Mapping[str, object]`.
- Produces: pure `normalize_search_item(raw) -> AssetItem | None` and `normalize_detail(item, raw) -> AssetDetail`.
- Produces: `PrelingerProvider` implementing the complete `AssetProvider` contract.

- [ ] **Step 1: Write failing provider tests from fixtures**

Tests assert a24-item page, numeric next cursor, `kind="video"`, stable identifier, static poster, source page, author/date, duration, license, playback/download resource selection, `bulk_download=False`, cache capability, unsafe metadata filenames ignored, no playable derivative fallback and downloader delegation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/providers/test_prelinger_provider.py
```

Expected: package import fails.

- [ ] **Step 3: Implement source-owned units**

Client endpoints are fixed to `https://archive.org/advancedsearch.php` and `https://archive.org/metadata/<id>`, with JSON size limits and `JsonCache`. Normalizer accepts safe identifiers matching `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` and chooses medium H.264/MPEG-4 for playback plus the best supported MPEG-4 for download. Provider owns descriptor, filters, page mapping, detail orchestration and injected `VideoDownloader`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/videos/prelinger tests/fixtures/prelinger_search.json tests/fixtures/prelinger_metadata.json tests/backend/providers/test_prelinger_provider.py
git commit -m "feat: add Prelinger video source"
```

### Task 5: Wikimedia Commons 视频 Provider

**Files:**
- Create: `src/ty_image_spider/providers/videos/commons/__init__.py`
- Create: `src/ty_image_spider/providers/videos/commons/client.py`
- Create: `src/ty_image_spider/providers/videos/commons/normalizer.py`
- Create: `src/ty_image_spider/providers/videos/commons/provider.py`
- Create: `tests/fixtures/commons_video_search.json`
- Create: `tests/fixtures/commons_video_detail.json`
- Create: `tests/backend/providers/test_commons_video_provider.py`

**Interfaces:**
- Produces: `CommonsVideoClient.search(query, category, cursor, refresh=False) -> Mapping[str, object]`.
- Produces: `CommonsVideoClient.detail(title, refresh=False) -> Mapping[str, object]`.
- Produces: `CommonsVideoProvider` with cursor pagination and normalized license metadata.

- [ ] **Step 1: Write failing Commons video tests**

Tests assert File namespace and `filetype:video` query constraints, continuation cursor round-trip, MP4-before-WebM playback preference, original-file download role, author/license/attribution preservation, missing derivatives behavior, unsafe upload host rejection and downloader delegation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/providers/test_commons_video_provider.py
```

Expected: package import fails.

- [ ] **Step 3: Implement Commons video modules**

Keep the existing image `CommonsProvider` untouched. The new Client requests `videoinfo` fields needed for original URL, derivatives, dimensions, duration, size and `extmetadata`. Normalizer strips HTML from source metadata, emits typed `MediaResource` entries and never exposes raw API structures to the frontend.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/videos/commons tests/fixtures/commons_video_search.json tests/fixtures/commons_video_detail.json tests/backend/providers/test_commons_video_provider.py
git commit -m "feat: add Wikimedia Commons video source"
```

### Task 6: NASA 视频 Provider

**Files:**
- Create: `src/ty_image_spider/providers/videos/nasa/__init__.py`
- Create: `src/ty_image_spider/providers/videos/nasa/client.py`
- Create: `src/ty_image_spider/providers/videos/nasa/normalizer.py`
- Create: `src/ty_image_spider/providers/videos/nasa/provider.py`
- Create: `tests/fixtures/nasa_video_search.json`
- Create: `tests/fixtures/nasa_video_manifest.json`
- Create: `tests/backend/providers/test_nasa_video_provider.py`

**Interfaces:**
- Produces: `NasaVideoClient.search(query, page, refresh=False) -> Mapping[str, object]`.
- Produces: `NasaVideoClient.manifest(url, refresh=False) -> list[str]`.
- Produces: `NasaVideoProvider` with page pagination and existing NASA category vocabulary.

- [ ] **Step 1: Write failing NASA video tests**

Tests assert `media_type=video`, category/query composition, page cursor, stable NASA ID, static poster, manifest host validation, medium MP4 playback choice, highest supported MP4 download choice, missing manifest fallback, unsafe asset host rejection and downloader delegation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/providers/test_nasa_video_provider.py
```

Expected: package import fails.

- [ ] **Step 3: Implement NASA video modules**

Share only immutable category values or small pure helpers with the image NASA implementation; do not make one Provider branch on media type. The video Client owns the search and manifest requests, Normalizer owns file selection, and Provider owns orchestration and download.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/videos/nasa tests/fixtures/nasa_video_search.json tests/fixtures/nasa_video_manifest.json tests/backend/providers/test_nasa_video_provider.py
git commit -m "feat: add NASA video source"
```

### Task 7: Provider 注册与封面缓存集成

**Files:**
- Modify: `src/ty_image_spider/providers/videos/__init__.py`
- Modify: `src/ty_image_spider/app/provider_factories.py`
- Modify: `src/ty_image_spider/app/bootstrap.py`
- Modify: `tests/backend/app/test_bootstrap.py`
- Modify: `tests/backend/app/test_provider_presentation.py`
- Modify: `tests/backend/providers/test_provider_registry.py`
- Modify: `tests/backend/services/test_cache_runner.py`
- Modify: `tests/fixtures/provider_descriptors.json`

**Interfaces:**
- Produces: `register_video_providers(registry, cache_root) -> None`.
- Consumes: each video Provider's static `image_policy` only for poster caching.
- Preserves: generic cache runner never imports video downloader or source IDs.

- [ ] **Step 1: Write failing registration and cache tests**

Assert 27 registered Providers, 26 visible sources, one `video` group ordered between collections and cinema, distinct source ordering, `bulk_download=False`, `cache=True`, and cache descriptions mentioning cover metadata. Add a cache runner test where a `kind="video"` item causes exactly one `ImageReaderRegistry.read(preview_url, provider)` call and zero `VideoDownloader.download` calls.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/app/test_bootstrap.py tests/backend/app/test_provider_presentation.py tests/backend/providers/test_provider_registry.py tests/backend/services/test_cache_runner.py
```

Expected: source count and descriptors fail.

- [ ] **Step 3: Register video Providers through one factory**

`register_video_providers` constructs source-owned clients and downloaders, then registers Providers. `bootstrap.py` invokes the factory and continues registering static preview readers through the existing policy-driven loop. Do not add provider-ID branches to search, detail, download or cache services.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/app src/ty_image_spider/providers/videos tests/backend/app tests/backend/providers/test_provider_registry.py tests/backend/services/test_cache_runner.py tests/fixtures/provider_descriptors.json
git commit -m "feat: register video providers and poster caching"
```

### Task 8: 视频卡片、播放器与详情生命周期

**Files:**
- Create: `web/features/video/resources.js`
- Create: `web/features/video/card.js`
- Create: `web/features/video/player.js`
- Create: `web/features/video/detail.js`
- Modify: `web/ui/gallery/card.js`
- Modify: `web/ui/dialog/index.js`
- Modify: `web/ui/dialog/facts.js`
- Create: `web/styles/video.css`
- Modify: `web/ty_image_spider.css`
- Create: `tests/frontend/video_card.test.mjs`
- Create: `tests/frontend/video_player.test.mjs`
- Modify: `tests/frontend/dialog.test.mjs`
- Modify: `tests/frontend/styles.test.mjs`

**Interfaces:**
- Produces: `selectPlaybackResource(detail) -> object | null`.
- Produces: `selectDownloadResource(detail) -> object | null`.
- Produces: `decorateVideoCard(document, media, item) -> void`.
- Produces: `createVideoPlayer({document, detail, onError}) -> {root, update, destroy}`.
- Produces: `renderVideoDetail(document, detail, context) -> {root, update, destroy}`.

- [ ] **Step 1: Write failing frontend tests**

Tests assert cards contain one `<img>` and zero `<video>`, play icon and formatted duration; detail creates exactly one `<video controls playsinline preload="metadata">` without `autoplay`; playback/download role selection is deterministic; missing playback displays a message while preserving download; portrait dimensions keep `object-fit: contain`; `destroy()` calls `pause()`, removes `src`, invokes `load()` and is idempotent; existing image dialog behavior remains unchanged.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/frontend/video_card.test.mjs tests/frontend/video_player.test.mjs tests/frontend/dialog.test.mjs tests/frontend/styles.test.mjs
```

Expected: new module imports fail.

- [ ] **Step 3: Implement small video feature modules**

`resources.js` contains only pure selection/format helpers. `card.js` only decorates an existing card media area. `player.js` owns the native video element lifecycle. `detail.js` composes player and media facts. Generic UI branches once on `item.kind === "video"`; it must not inspect provider IDs or raw provider metadata.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add web/features/video web/ui/gallery/card.js web/ui/dialog web/styles/video.css web/ty_image_spider.css tests/frontend/video_card.test.mjs tests/frontend/video_player.test.mjs tests/frontend/dialog.test.mjs tests/frontend/styles.test.mjs
git commit -m "feat: add video cards and detail player"
```

### Task 9: 视频下载操作与键盘行为

**Files:**
- Modify: `web/features/preview/preview_actions.js`
- Modify: `web/app/download_controller.js`
- Modify: `web/ui/dialog/index.js`
- Modify: `tests/frontend/frontend_integration.test.mjs`
- Modify: `tests/frontend/dialog.test.mjs`
- Modify: `tests/backend/services/test_selected_download.py`

**Interfaces:**
- Consumes: existing provider-level `download(item)` path for videos.
- Preserves: indexed single-image download for image galleries.
- Produces: ArrowDown dispatches provider-level video download for `kind="video"`; ArrowLeft/ArrowRight continue adjacent-item navigation.

- [ ] **Step 1: Write failing interaction tests**

Assert video detail download button and ArrowDown call `onDownload(item)` once, key repeat is ignored, in-flight download suppresses duplicates, errors permit retry, inputs do not capture shortcuts, image details still call `onDownloadImage(item, index)`, and backend selected-image service rejects video index payloads rather than guessing.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
node --test tests/frontend/dialog.test.mjs tests/frontend/frontend_integration.test.mjs
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/services/test_selected_download.py
```

Expected: video ArrowDown follows the image path or does nothing.

- [ ] **Step 3: Route commands by media kind**

Keep command selection in the reusable preview action layer. Video uses provider download; images retain indexed download. Reuse existing visible output-path message and activity state. Do not create a source-specific download controller.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add web/features/preview/preview_actions.js web/app/download_controller.js web/ui/dialog/index.js tests/frontend/frontend_integration.test.mjs tests/frontend/dialog.test.mjs tests/backend/services/test_selected_download.py
git commit -m "feat: support video download actions"
```

### Task 10: 用户文档、版本与完整验收

**Files:**
- Create: `docs/sources/video.md`
- Modify: `README.md`
- Modify: `docs/source-rights.md`
- Modify: `docs/guides/cache.md`
- Modify: `docs/guides/compatibility.md`
- Modify: `CHANGELOG.md`
- Modify: `src/ty_image_spider/version.py`
- Modify: `pyproject.toml`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `tests/backend/app/test_version.py`
- Modify: `tests/backend/app/test_readme.py`
- Modify: `scripts/release/build.py`
- Modify: `tests/release/test_build_release.py`

**Interfaces:**
- Produces: version `2.7.0` across Python and npm manifests.
- Produces: released documentation for three video sources, cache behavior, output paths, rights and limitations.
- Preserves: release archive excludes tests, fixtures, local credentials and development plans.

- [ ] **Step 1: Write failing release/documentation tests**

Update version assertions to `2.7.0`, require all three source names and the phrase “视频缓存只保存封面和资料” in README/user docs, and require `docs/sources/video.md` in the release whitelist.

- [ ] **Step 2: Run release tests and verify RED**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe -m pytest -q tests/backend/app/test_version.py tests/backend/app/test_readme.py tests/release
```

Expected: version and required-document assertions fail.

- [ ] **Step 3: Update product documentation and manifests**

Document source behavior, supported formats, no-key setup, per-item licensing, output directories, 2 GiB limit, no bulk video download, cover-only caching and browser playback limitations. Add a `2.7.0 — 2026-09-24` changelog section and keep historical release entries intact.

- [ ] **Step 4: Run full automated quality gate**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe scripts/quality/check.py
```

Expected: Ruff, Ruff format, Mypy, all Python tests, all frontend tests, Prettier, JS syntax, Python compile and Git diff checks pass.

- [ ] **Step 5: Commit the release metadata**

```powershell
git add README.md CHANGELOG.md docs src/ty_image_spider/version.py pyproject.toml package.json package-lock.json scripts/release/build.py tests/backend/app/test_version.py tests/backend/app/test_readme.py tests/release
git commit -m "docs: release video sources in 2.7.0"
```

- [ ] **Step 6: Validate committed release snapshot**

Run:

```powershell
D:\work_station\ty-comfyui-node\.venv\Scripts\python.exe scripts/release/build.py --check
```

Expected: `发布快照检查通过`.

- [ ] **Step 7: Perform real-source smoke tests**

With no credentials, query one page from each source, open one detail, verify the selected playback URL with an HTTP range request, download one small sample per source, repeat the download to confirm reuse, and verify a cache job creates only poster files. Record item IDs, formats and results in `docs/guides/compatibility.md`; do not commit downloaded media.

- [ ] **Step 8: Restart and verify ComfyUI UI**

Confirm the 8188 queue is empty, restart ComfyUI, force-refresh the browser, then verify: the “视频素材” group contains three sources; cards load only images; details play video on demand; native fullscreen works; ArrowLeft/ArrowRight navigate; ArrowDown downloads once; output path is visible; closing stops network/decoding; existing image sources still browse and preview normally.

- [ ] **Step 9: Final cleanup and tag**

Delete generated test caches and smoke-test video files, confirm `.local/tmdb.json` remains untouched, confirm the worktree is clean, and create annotated tag `v2.7.0` only after all checks pass.
