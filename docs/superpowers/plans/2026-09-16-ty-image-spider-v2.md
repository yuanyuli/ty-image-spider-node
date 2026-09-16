# TY Image Spider 2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个零输出的 ComfyUI 素材浏览节点，以可插拔 Provider 支持 Civitai、小红书和本地历史，并提供来源感知的搜索、详情与安全下载界面。

**Architecture:** 使用策略模式实现独立 Provider，轻量注册表承担工厂职责，搜索、详情、下载和状态检测分别由小型应用服务编排。ComfyUI HTTP 路由只做输入输出适配，前端入口只组合状态、控件、画廊和弹窗模块；小红书通过可选 OpenCLI 持久浏览器会话接入。

**Tech Stack:** Python 3.10+、dataclasses、typing Protocol、urllib、Pillow、aiohttp/ComfyUI PromptServer、pytest、原生 ES modules、Node.js 内置测试运行器、Prettier。

**Spec:** `docs/superpowers/specs/2026-09-16-ty-image-spider-v2-design.md`

## Global Constraints

- 注册名固定为 `TyImageSpider`，显示名固定为 `TY Image Spider · 素材浏览`，分类固定为 `TY Utils/素材浏览`。
- 节点没有输出端口，不注册旧节点 ID，不修改或导入 `civitai-inspiration` 运行时代码。
- 每个来源独立实现 `AssetProvider`；注册表只注册、创建和查找，不执行业务。
- 搜索、详情、下载、状态检测保持独立服务；`bootstrap.py` 只组合依赖。
- 小红书依赖 OpenCLI `>=1.8.8`，但 OpenCLI 缺失时 Civitai 和本地来源必须正常工作。
- 小红书签名 URL 不写入工作流、节点 properties 或 `localStorage`。
- 所有网络测试使用固定 fixture 或 fake server；自动测试不依赖实时站点或真实浏览器。
- 下载目标只能位于 ComfyUI output 目录，远程资源必须通过来源域名白名单、大小和图片格式校验。
- 文档、UI 文案和代码注释使用中文；公共代码字段和 API 名使用英文。
- 新代码先写失败测试并确认失败原因，再写最小实现。

---

## File Map

### Python domain and composition

- `src/ty_image_spider/models.py`：不可变请求、结果、素材和错误数据模型。
- `src/ty_image_spider/providers/base.py`：`AssetProvider` 协议。
- `src/ty_image_spider/providers/registry.py`：Provider 注册与工厂查找。
- `src/ty_image_spider/bootstrap.py`：生产依赖组合根。
- `src/ty_image_spider/nodes.py`：零输出 ComfyUI 节点适配。
- `src/ty_image_spider/routes.py`：aiohttp 请求和响应适配。

### Python capabilities

- `src/ty_image_spider/cache.py`：原子 JSON 缓存。
- `src/ty_image_spider/security.py`：URL、路径、大小和脱敏工具。
- `src/ty_image_spider/metadata.py`：图片 metadata 与提示词解析。
- `src/ty_image_spider/downloads.py`：Civitai 安全图片下载。
- `src/ty_image_spider/opencli.py`：OpenCLI 子进程 Runner。
- `src/ty_image_spider/providers/civitai_client.py`：Civitai HTTP 与重试。
- `src/ty_image_spider/providers/civitai.py`：Civitai 策略。
- `src/ty_image_spider/providers/local.py`：本地历史策略。
- `src/ty_image_spider/providers/xiaohongshu_extract.py`：小红书只读浏览器提取脚本和结果解析。
- `src/ty_image_spider/providers/xiaohongshu.py`：小红书策略。
- `src/ty_image_spider/services/search.py`、`detail.py`、`download.py`、`status.py`：单用例服务。

### Frontend

- `web/ty_image_spider.js`：ComfyUI 扩展安装与模块组合。
- `web/ty_image_spider.css`：节点、画廊和弹窗样式。
- `web/api.js`：HTTP 客户端。
- `web/state.js`：可序列化状态、Provider 特定持久化策略和竞态保护。
- `web/source_controls.js`：来源分段控件、动态筛选和状态区。
- `web/gallery.js`：稳定网格、卡片和分页工具栏。
- `web/dialog.js`：详情弹窗、图集、复制和下载动作。
- `web/icons.js`：项目使用的少量内联图标函数，集中维护并提供可访问标签。

### Project and tests

- `__init__.py`：ComfyUI 扫描入口。
- `pyproject.toml`、`requirements.txt`、`package.json`、`package-lock.json`、`.prettierrc.json`：项目和开发工具配置。
- `tests/`：Python 行为测试、固定 fixture、前端 `.test.mjs`。
- `scripts/check_quality.py`：单一质量检查入口。
- `README.md`：中文安装、使用、OpenCLI 配置和故障排查。

---

### Task 1: Domain Models and Provider Factory

**Files:**
- Create: `src/ty_image_spider/models.py`
- Create: `src/ty_image_spider/providers/__init__.py`
- Create: `src/ty_image_spider/providers/base.py`
- Create: `src/ty_image_spider/providers/registry.py`
- Create: `tests/test_models.py`
- Create: `tests/test_provider_registry.py`

**Interfaces:**
- Produces: `FilterOption`, `FilterField`, `ProviderCapabilities`, `ProviderDescriptor`, `ProviderStatus`, `SearchRequest`, `AssetItem`, `AssetDetail`, `SearchPage`, `DownloadResult`, `SpiderError`。
- Produces: `AssetItem.to_dict()` and `AssetItem.from_untrusted(value)` for the only accepted HTTP item representation.
- Produces: `AssetProvider` Protocol and `ProviderRegistry.register(provider)`, `get(provider_id)`, `descriptors()`。

- [ ] **Step 1: Write failing immutable-model and registry tests**

```python
def test_asset_item_serializes_without_none_values():
    item = AssetItem(provider="civitai", id="42", preview_url="https://image.civitai.com/a.jpg")
    assert item.to_dict() == {
        "provider": "civitai", "id": "42", "kind": "image",
        "preview_url": "https://image.civitai.com/a.jpg", "download_mode": "single",
        "has_prompt": False, "image_count": 1, "stats": {}, "tags": [], "metadata": {},
    }
    assert AssetItem.from_untrusted(item.to_dict()) == item

def test_registry_rejects_duplicate_provider_ids():
    registry = ProviderRegistry()
    registry.register(FakeProvider("civitai"))
    with pytest.raises(ValueError, match="重复"):
        registry.register(FakeProvider("civitai"))
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_models.py tests/test_provider_registry.py -q`

Expected: collection fails because `ty_image_spider.models` and registry do not exist.

- [ ] **Step 3: Implement focused dataclasses, protocol, and registry**

```python
@dataclass(frozen=True, slots=True)
class SearchRequest:
    provider: str
    query: str = ""
    filters: Mapping[str, JsonValue] = field(default_factory=dict)
    cursor: str | None = None
    refresh: bool = False

class AssetProvider(Protocol):
    id: str
    def descriptor(self) -> ProviderDescriptor: ...
    def status(self) -> ProviderStatus: ...
    def search(self, request: SearchRequest) -> SearchPage: ...
    def detail(self, item: AssetItem) -> AssetDetail: ...
    def download(self, item: AssetItem, output_root: Path) -> DownloadResult: ...
```

Implement explicit `to_dict()` methods so API serialization never depends on `dataclasses.asdict()` recursively exposing future private fields. `ProviderRegistry.get()` raises `SpiderError("provider_not_found", ...)` for unknown IDs.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_models.py tests/test_provider_registry.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/models.py src/ty_image_spider/providers tests/test_models.py tests/test_provider_registry.py
git commit -m "feat: define provider domain contracts"
```

### Task 2: Package Entry and Zero-Output Node

**Files:**
- Create: `__init__.py`
- Create: `src/ty_image_spider/__init__.py`
- Create: `src/ty_image_spider/nodes.py`
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `tests/test_package.py`
- Create: `tests/test_node_contract.py`

**Interfaces:**
- Consumes: domain package from Task 1.
- Produces: `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`, `WEB_DIRECTORY` and `TyImageSpider.browse(state_json="{}")`.

- [ ] **Step 1: Write failing ComfyUI registration tests**

```python
def test_package_registers_only_new_node_id():
    package = load_root_package()
    assert set(package.NODE_CLASS_MAPPINGS) == {"TyImageSpider"}
    assert package.NODE_DISPLAY_NAME_MAPPINGS == {"TyImageSpider": "TY Image Spider · 素材浏览"}
    assert package.WEB_DIRECTORY == "./web"

def test_node_is_zero_output_and_serializes_only_state():
    assert TyImageSpider.RETURN_TYPES == ()
    assert TyImageSpider.OUTPUT_NODE is True
    assert set(TyImageSpider.INPUT_TYPES()["required"]) == {"state_json"}
    assert TyImageSpider().browse('{"provider":"local"}') == {"ui": {"state": ['{"provider":"local"}']}}
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_package.py tests/test_node_contract.py -q`

Expected: imports fail because package entry and node do not exist.

- [ ] **Step 3: Implement minimal package and node adapter**

```python
class TyImageSpider:
    OUTPUT_NODE = True
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "browse"
    CATEGORY = "TY Utils/素材浏览"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"state_json": ("STRING", {"default": "{}", "hidden": True})}}

    def browse(self, state_json: str = "{}"):
        return {"ui": {"state": [state_json if isinstance(state_json, str) else "{}"]}}
```

Root `__init__.py` adds only this repository's `src` directory to `sys.path`, imports the three ComfyUI exports, and never catches broad import errors.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_package.py tests/test_node_contract.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add __init__.py pyproject.toml requirements.txt src/ty_image_spider tests/test_package.py tests/test_node_contract.py
git commit -m "feat: register zero-output image spider node"
```

### Task 3: Cache, Security, and Metadata Utilities

**Files:**
- Create: `src/ty_image_spider/cache.py`
- Create: `src/ty_image_spider/security.py`
- Create: `src/ty_image_spider/metadata.py`
- Create: `tests/test_cache.py`
- Create: `tests/test_security.py`
- Create: `tests/test_metadata.py`

**Interfaces:**
- Produces: `JsonCache.get(key, max_age_seconds)`, `put(key, value)`, `clear(key)`.
- Produces: `require_https_host(url, allowed)`, `resolve_inside(root, relative)`, `read_limited(response, max_bytes)`, `redact_secrets(value)`.
- Produces: `read_image_metadata(path)` and `extract_prompts(metadata)`.

- [ ] **Step 1: Write failing utility behavior tests**

```python
def test_cache_uses_atomic_hashed_paths_and_expires(tmp_path, monkeypatch):
    cache = JsonCache(tmp_path, max_entries=2)
    cache.put("secret?xsec_token=abc", {"value": 1})
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1 and "secret" not in files[0].name
    monkeypatch.setattr(cache, "_now", lambda: files[0].stat().st_mtime + 11)
    assert cache.get("secret?xsec_token=abc", max_age_seconds=10) is None

def test_redaction_is_recursive():
    assert redact_secrets({"cookie": "a", "nested": [{"xsec_token": "b"}]}) == {
        "cookie": "[已隐藏]", "nested": [{"xsec_token": "[已隐藏]"}]
    }

def test_workflow_json_is_not_treated_as_prompt():
    prompt, negative = extract_prompts({"prompt": '{"nodes":[{"id":1}]}'})
    assert prompt == "" and negative == ""
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_cache.py tests/test_security.py tests/test_metadata.py -q`

Expected: imports fail for the three new modules.

- [ ] **Step 3: Implement one-purpose utilities**

Use SHA-256 cache filenames, `tempfile.mkstemp()` plus `os.replace()` for atomic writes, `Path.resolve()` plus `relative_to()` for containment, and Pillow with decompression-bomb warnings promoted to errors. Secret-key matching includes `key`, `token`, `secret`, `cookie`, and `authorization` case-insensitively.

```python
def require_https_host(url: str, allowed: Callable[[str], bool]) -> ParseResult:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not allowed(host):
        raise SpiderError("unsafe_url", "图片地址不属于当前素材源")
    return parsed
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_cache.py tests/test_security.py tests/test_metadata.py -q`

Expected: all tests pass, including corrupt-cache cleanup and path traversal cases.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/cache.py src/ty_image_spider/security.py src/ty_image_spider/metadata.py tests/test_cache.py tests/test_security.py tests/test_metadata.py
git commit -m "feat: add cache and asset safety utilities"
```

### Task 4: Civitai Client and Provider Strategy

**Files:**
- Create: `src/ty_image_spider/providers/civitai_client.py`
- Create: `src/ty_image_spider/providers/civitai.py`
- Create: `src/ty_image_spider/downloads.py`
- Create: `tests/fixtures/civitai_images.json`
- Create: `tests/test_civitai_client.py`
- Create: `tests/test_civitai_provider.py`
- Create: `tests/test_downloads.py`

**Interfaces:**
- Consumes: domain models, `JsonCache`, security and metadata utilities.
- Produces: `CivitaiClient.search(site, params) -> CivitaiPage`, `page_metadata(site, image_id) -> dict`.
- Produces: `CivitaiProvider(client, cache, downloader)` implementing `AssetProvider`.
- Produces: `ImageDownloader.download(url, item_id, output_root) -> DownloadResult`.

- [ ] **Step 1: Write failing fake-server and normalization tests**

```python
def test_civitai_provider_maps_filters_and_normalizes_prompt(fake_civitai_server, tmp_path):
    provider = make_provider(fake_civitai_server, tmp_path)
    page = provider.search(SearchRequest("civitai", "portrait", {
        "site": "civitai.com", "period": "Week", "sort": "Most Reactions",
        "sfw": True, "tag": "Portrait", "only_with_prompt": True, "count": 6,
    }))
    assert page.items[0].provider == "civitai"
    assert page.items[0].has_prompt is True
    assert page.items[0].download_mode == "single"
    assert page.next_cursor == "cursor-2"

def test_civitai_timeout_returns_marked_stale_cache(tmp_path):
    provider = make_timeout_provider_with_cache(tmp_path)
    page = provider.search(SearchRequest("civitai", "cat"))
    assert page.stale is True and page.items[0].id == "cached"
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_civitai_client.py tests/test_civitai_provider.py tests/test_downloads.py -q`

Expected: imports fail because the client and provider are absent.

- [ ] **Step 3: Implement the client, strategy, and downloader**

Migrate verified behavior from the old repository by rewriting it behind the new interfaces: finite retry for 429/5xx, `Retry-After`, cursor loop protection, prompt fallback from page metadata, source-specific cache keys, official-domain redirect validation, temporary files, Pillow verification, and non-overwriting safe filenames.

```python
class CivitaiProvider:
    id = "civitai"
    def __init__(self, client: CivitaiClient, cache: JsonCache, downloader: ImageDownloader): ...
    def descriptor(self) -> ProviderDescriptor: ...
    def search(self, request: SearchRequest) -> SearchPage: ...
    def detail(self, item: AssetItem) -> AssetDetail: ...
    def download(self, item: AssetItem, output_root: Path) -> DownloadResult: ...
```

The descriptor declares `bulk_download=True` and fields `site`, `period`, `sort`, `sfw`, `tag`, `only_with_prompt`, and `count` with fixed defaults and limits.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_civitai_client.py tests/test_civitai_provider.py tests/test_downloads.py -q`

Expected: all tests pass without reaching the public internet.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/civitai_client.py src/ty_image_spider/providers/civitai.py src/ty_image_spider/downloads.py tests/fixtures tests/test_civitai_client.py tests/test_civitai_provider.py tests/test_downloads.py
git commit -m "feat: add Civitai provider"
```

### Task 5: Local History Provider

**Files:**
- Create: `src/ty_image_spider/providers/local.py`
- Create: `tests/test_local_provider.py`

**Interfaces:**
- Consumes: `AssetItem`, `AssetDetail`, `SearchPage`, metadata utilities.
- Produces: `LocalProvider(output_root)` implementing `AssetProvider` over `ty-image-spider/` and legacy `ty-node/`.

- [ ] **Step 1: Write failing local indexing tests**

```python
def test_local_provider_reads_new_and_legacy_directories_in_mtime_order(tmp_path):
    write_png(tmp_path / "ty-node" / "old.png", prompt="old", mtime=10)
    write_png(tmp_path / "ty-image-spider" / "new.png", prompt="new", mtime=20)
    page = LocalProvider(tmp_path).search(SearchRequest("local", "", {"count": 10}))
    assert [item.title for item in page.items] == ["new.png", "old.png"]
    assert all(item.download_mode == "none" for item in page.items)

def test_local_provider_does_not_follow_external_symlink(tmp_path):
    outside = tmp_path.parent / "outside.png"
    write_png(outside)
    create_supported_link(tmp_path / "ty-image-spider" / "link.png", outside)
    assert LocalProvider(tmp_path).search(SearchRequest("local")).items == ()
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_local_provider.py -q`

Expected: import fails for `LocalProvider`.

- [ ] **Step 3: Implement bounded indexing and `/view` URLs**

Use one scan helper per root, reject resolved paths outside the root, accept PNG/JPEG/WEBP, parse page cursors as integer offsets, and generate `/view` query parameters with `urllib.parse.urlencode()`.

```python
def _view_url(path: Path, output_root: Path) -> str:
    relative = path.relative_to(output_root)
    return "/view?" + urlencode({
        "filename": relative.name,
        "subfolder": relative.parent.as_posix() if relative.parent != Path(".") else "",
        "type": "output",
    })
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_local_provider.py -q`

Expected: all tests pass on Windows; symlink test skips only if link creation is unavailable.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/local.py tests/test_local_provider.py
git commit -m "feat: add bounded local history provider"
```

### Task 6: OpenCLI Runner

**Files:**
- Create: `src/ty_image_spider/opencli.py`
- Create: `tests/test_opencli.py`

**Interfaces:**
- Produces: `CommandResult`, `OpenCliRunner.version()`, `doctor()`, `run_json(args, timeout_seconds)`, and exit-code-to-`SpiderError` mapping.
- Does not import or reference Xiaohongshu domain models.

- [ ] **Step 1: Write failing subprocess boundary tests**

```python
def test_runner_passes_arguments_without_shell_and_parses_json(fake_run):
    fake_run.return_value = completed(0, '[{"title":"穿搭"}]')
    rows = OpenCliRunner(executable="opencli", run=fake_run).run_json(
        ["xiaohongshu", "search", "穿搭", "--format", "json"], 30
    )
    assert rows == [{"title": "穿搭"}]
    assert fake_run.call_args.kwargs["shell"] is False

@pytest.mark.parametrize((code, expected), [(69, "opencli_bridge_unavailable"), (75, "opencli_timeout"), (77, "opencli_auth_required"), (78, "opencli_config_error")])
def test_runner_maps_documented_exit_codes(fake_run, code, expected):
    fake_run.return_value = completed(code, '{"error":{"message":"failed"}}')
    with pytest.raises(SpiderError) as caught:
        OpenCliRunner(run=fake_run).run_json(["doctor"], 5)
    assert caught.value.code == expected
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_opencli.py -q`

Expected: import fails for `OpenCliRunner`.

- [ ] **Step 3: Implement the process runner**

Resolve the executable with `shutil.which`, use `subprocess.run([...], shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace")`, set `CREATE_NO_WINDOW` on Windows, reject stdout over 4 MiB, and convert `TimeoutExpired` into `SpiderError("opencli_timeout", ...)`. Parse semantic versions and reject versions lower than `1.8.8`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_opencli.py -q`

Expected: all tests pass, including missing executable, malformed JSON, output limit, timeout, and version cases.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/opencli.py tests/test_opencli.py
git commit -m "feat: add safe OpenCLI process runner"
```

### Task 7: Xiaohongshu Extraction and Provider Strategy

**Files:**
- Create: `src/ty_image_spider/providers/xiaohongshu_extract.py`
- Create: `src/ty_image_spider/providers/xiaohongshu.py`
- Create: `tests/fixtures/xiaohongshu_search.json`
- Create: `tests/fixtures/xiaohongshu_cards.json`
- Create: `tests/fixtures/xiaohongshu_detail.json`
- Create: `tests/test_xiaohongshu_extract.py`
- Create: `tests/test_xiaohongshu_provider.py`

**Interfaces:**
- Consumes: `OpenCliRunner`, domain models.
- Produces: `build_card_extract_js()`, `build_detail_extract_js(note_id)`, `merge_search_rows(rows, cards)`.
- Produces: `XiaohongshuProvider(runner, cache, session_lock)` implementing `AssetProvider`.

- [ ] **Step 1: Write failing merge, command, and persistence-boundary tests**

```python
def test_search_uses_official_adapter_then_persistent_read_only_eval(fake_runner):
    provider = XiaohongshuProvider(fake_runner, JsonCache(tmp_path), threading.Lock())
    page = provider.search(SearchRequest("xiaohongshu", "秋季穿搭", {
        "sort": "most-liked", "note_type": "image", "publish_time": "week", "count": 12,
    }))
    assert fake_runner.calls[0].args[:3] == ["xiaohongshu", "search", "秋季穿搭"]
    assert "--site-session" in fake_runner.calls[0].args
    assert fake_runner.calls[1].args[:4] == ["browser", "site:xiaohongshu", "eval", build_card_extract_js()]
    assert page.items[0].preview_url.startswith("https://sns-img")

def test_signed_note_url_uses_note_flow_instead_of_keyword_search(fake_runner):
    url = "https://www.xiaohongshu.com/explore/abc123?xsec_token=signed"
    page = make_xhs_provider(fake_runner).search(SearchRequest("xiaohongshu", url))
    assert fake_runner.calls[0].args[:3] == ["xiaohongshu", "note", url]
    assert page.items[0].source_url == url

def test_detail_rejects_unsigned_note_url(fake_runner):
    item = xhs_item("https://www.xiaohongshu.com/explore/abc123")
    with pytest.raises(SpiderError, match="完整签名链接"):
        make_xhs_provider(fake_runner).detail(item)
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_xiaohongshu_extract.py tests/test_xiaohongshu_provider.py -q`

Expected: imports fail for extraction and provider modules.

- [ ] **Step 3: Implement extraction helpers and strategy**

The search adapter command includes explicit `--limit`, `--sort`, `--note-type`, `--publish-time`, `--format json`, `--site-session persistent`, and `--window background`. The browser eval script reads visible note cards and returns only `{id, url, preview_url, image_count}`. It performs no clicks, fetches, form submission, or navigation.

Before keyword search, classify the trimmed query. A trusted full Xiaohongshu note URL with `xsec_token`, or an `xhslink.com` short URL, enters single-note mode: call the official `xiaohongshu note` adapter, reuse the persistent session for detail extraction, and return one `AssetItem`. Other HTTP URLs fail with `SpiderError("invalid_note_url", ...)`; ordinary text enters keyword search.

The detail script first reads `window.__INITIAL_STATE__.note.noteDetailMap[noteId].note.imageList` in order, then falls back to scoped `#noteContainer` image selectors. Accept only HTTPS hosts matching `xiaohongshu.com`, `xhscdn.com`, or subdomains.

```python
def download(self, item: AssetItem, output_root: Path) -> DownloadResult:
    target = resolve_inside(output_root, Path("ty-image-spider/xiaohongshu") / item.id)
    before = _snapshot_images(target)
    self._runner.run_json([
        "xiaohongshu", "download", item.source_url,
        "--output", str(target.parent), "--format", "json",
        "--site-session", "persistent", "--window", "background",
    ], timeout_seconds=180)
    return _verified_new_images(target, before, output_root)
```

Wrap the complete adapter-plus-eval or detail-plus-eval sequence in the injected lock so two requests never operate on `site:xiaohongshu` concurrently.

Implement private `_snapshot_images(directory) -> set[Path]` and `_verified_new_images(directory, before, output_root) -> DownloadResult` helpers in `xiaohongshu.py`. They resolve every candidate under `output_root`, accept only files that Pillow can verify as images, and return output-relative paths.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_xiaohongshu_extract.py tests/test_xiaohongshu_provider.py -q`

Expected: all fixture-driven tests pass; command arguments contain no shell string and persistent serialization excludes signed URLs.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/providers/xiaohongshu_extract.py src/ty_image_spider/providers/xiaohongshu.py tests/fixtures/xiaohongshu_* tests/test_xiaohongshu_extract.py tests/test_xiaohongshu_provider.py
git commit -m "feat: add optional Xiaohongshu provider"
```

### Task 8: Single-Use-Case Application Services

**Files:**
- Create: `src/ty_image_spider/services/__init__.py`
- Create: `src/ty_image_spider/services/search.py`
- Create: `src/ty_image_spider/services/detail.py`
- Create: `src/ty_image_spider/services/download.py`
- Create: `src/ty_image_spider/services/status.py`
- Create: `tests/test_services.py`

**Interfaces:**
- Consumes: `ProviderRegistry` and domain models.
- Produces: `SearchService.execute(payload)`, `DetailService.execute(payload)`, `DownloadService.execute(payload)`, `StatusService.list()` and `check(provider_id)`.

- [ ] **Step 1: Write failing service isolation tests**

```python
def test_search_service_calls_only_selected_provider(registry):
    civitai, local = recording_providers()
    registry.register(civitai); registry.register(local)
    result = SearchService(registry).execute({"provider": "local", "query": "cat", "filters": {}})
    assert result.items[0].provider == "local"
    assert local.search_calls == 1 and civitai.search_calls == 0

def test_download_page_requires_provider_capability(registry):
    registry.register(provider_with_bulk_download(False))
    with pytest.raises(SpiderError, match="不支持整页下载"):
        DownloadService(registry, tmp_path).download_page("xiaohongshu", [item_dict])
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_services.py -q`

Expected: service modules do not exist.

- [ ] **Step 3: Implement four narrow services**

Each service validates only fields needed by its use case and delegates to one Provider method. `DownloadService.download_page()` caps the list at 20 items and rejects providers without `bulk_download`. `StatusService.list()` catches an unavailable optional provider and returns its unavailable status without failing the list.

```python
class DetailService:
    def __init__(self, providers: ProviderRegistry):
        self._providers = providers

    def execute(self, payload: Mapping[str, object]) -> AssetDetail:
        item = AssetItem.from_untrusted(payload.get("item"))
        return self._providers.get(item.provider).detail(item)
```

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_services.py -q`

Expected: all tests pass and no service imports aiohttp, ComfyUI, urllib, subprocess, or Pillow.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/services tests/test_services.py
git commit -m "feat: add isolated image spider use cases"
```

### Task 9: HTTP Routes and Composition Root

**Files:**
- Create: `src/ty_image_spider/bootstrap.py`
- Create: `src/ty_image_spider/routes.py`
- Modify: `src/ty_image_spider/__init__.py`
- Create: `tests/test_bootstrap.py`
- Create: `tests/test_routes.py`

**Interfaces:**
- Consumes: all Providers and services.
- Produces: `ApplicationServices` frozen dataclass, `build_services(output_root, cache_root)`, route handler functions, and idempotent `register_routes()`.

- [ ] **Step 1: Write failing route contract tests with fake services**

```python
@pytest.mark.asyncio
async def test_search_route_returns_uniform_envelope(fake_request, fake_services):
    response = await post_search(fake_request({"provider": "local"}), fake_services)
    assert response.status == 200
    assert await response.json() == {"ok": True, "data": fake_services.page.to_dict()}

@pytest.mark.asyncio
async def test_route_maps_spider_error_without_secret(fake_request, fake_services):
    fake_services.search.error = SpiderError("opencli_auth_required", "cookie=secret", "请重新登录")
    response = await post_search(fake_request({"provider": "xiaohongshu"}), fake_services)
    body = await response.json()
    assert response.status == 401
    assert "secret" not in json.dumps(body)
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_bootstrap.py tests/test_routes.py -q`

Expected: imports fail for bootstrap and routes.

- [ ] **Step 3: Implement composition and thin route adapters**

`build_services()` constructs one registry, one shared OpenCLI lock, three Providers, and four services. It obtains output root lazily from `folder_paths` only in production composition. Route functions accept an optional services argument for tests; registered wrappers call `get_services()`.

```python
ROUTES = (
    ("GET", "/ty-image-spider/providers", get_providers),
    ("POST", "/ty-image-spider/search", post_search),
    ("POST", "/ty-image-spider/detail", post_detail),
    ("POST", "/ty-image-spider/download", post_download),
    ("POST", "/ty-image-spider/download-page", post_download_page),
    ("POST", "/ty-image-spider/providers/xiaohongshu/check", post_provider_check),
)
```

Use `asyncio.to_thread(service.execute, payload)` for blocking calls. Register once via a module-level boolean owned by this package; do not attach arbitrary attributes to aiohttp route tables.

- [ ] **Step 4: Verify GREEN**

Run: `uv run --project ..\.. pytest tests/test_bootstrap.py tests/test_routes.py -q`

Expected: success, malformed JSON, missing provider, optional-source unavailable, and route idempotency tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/bootstrap.py src/ty_image_spider/routes.py src/ty_image_spider/__init__.py tests/test_bootstrap.py tests/test_routes.py
git commit -m "feat: expose image spider HTTP API"
```

### Task 10: Frontend API, State, and Dynamic Source Controls

**Files:**
- Create: `web/api.js`
- Create: `web/state.js`
- Create: `web/source_controls.js`
- Create: `web/icons.js`
- Create: `tests/api.test.mjs`
- Create: `tests/state.test.mjs`
- Create: `tests/source_controls.test.mjs`
- Create: `package.json`
- Create: `package-lock.json`
- Create: `.prettierrc.json`

**Interfaces:**
- Produces: `createApiClient(fetchApi).requestJson(path, options)`, `createSpiderState(initial)`, `serializeWorkflowState(state)`, `createRequestGuard()`, `renderSourceControls(context)`.
- Source controls emit `sourcechange`, `search`, `refresh`, and `filterchange` callbacks; they do not call HTTP directly.

- [ ] **Step 1: Write failing pure-state and control tests**

```javascript
test("小红书持久状态移除结果和签名链接", () => {
  const saved = serializeWorkflowState({
    provider: "xiaohongshu",
    filters: { query: "穿搭" },
    items: [{ source_url: "https://www.xiaohongshu.com/explore/a?xsec_token=secret" }],
  });
  assert.deepEqual(JSON.parse(saved), { provider: "xiaohongshu", filters: { query: "穿搭" } });
  assert.equal(saved.includes("xsec_token"), false);
});

test("过期请求不能覆盖新搜索", () => {
  const guard = createRequestGuard();
  const old = guard.begin();
  const current = guard.begin();
  assert.equal(guard.isCurrent(old), false);
  assert.equal(guard.isCurrent(current), true);
});
```

- [ ] **Step 2: Verify RED**

Run: `node --test tests/api.test.mjs tests/state.test.mjs tests/source_controls.test.mjs`

Expected: module-not-found failures for frontend modules.

- [ ] **Step 3: Implement framework-free modules**

`createApiClient(fetchApi)` closes over the `api.fetchApi` function supplied through dependency injection. Its `requestJson` method parses uniform envelopes and throws an `ApiError` containing `code`, `message`, and `action`. `source_controls.js` renders field kinds from Provider descriptors and keeps stable element heights. `icons.js` returns DOM nodes for search, refresh, next, download, copy, external-link, close, and chevron icons with `aria-hidden` and button tooltips.

```javascript
export function serializeWorkflowState(state) {
  const value = { provider: state.provider, filters: state.filters, summary: state.summary };
  if (state.provider !== "xiaohongshu") value.items = state.items;
  return JSON.stringify(removeUndefined(value));
}
```

- [ ] **Step 4: Verify GREEN**

Run: `node --test tests/api.test.mjs tests/state.test.mjs tests/source_controls.test.mjs`

Expected: all tests pass with lightweight fake DOM objects; no browser or ComfyUI process is required.

- [ ] **Step 5: Commit**

```powershell
git add web/api.js web/state.js web/source_controls.js web/icons.js tests/*.test.mjs package.json package-lock.json .prettierrc.json
git commit -m "feat: add source-aware frontend state"
```

### Task 11: Gallery, Detail Dialog, and ComfyUI Frontend Integration

**Files:**
- Create: `web/gallery.js`
- Create: `web/dialog.js`
- Create: `web/ty_image_spider.js`
- Create: `web/ty_image_spider.css`
- Create: `tests/gallery.test.mjs`
- Create: `tests/dialog.test.mjs`
- Create: `tests/frontend_integration.test.mjs`

**Interfaces:**
- Consumes: API, state, controls, icons and Provider descriptors.
- Produces: `createGallery(context)`, `openAssetDialog(context, item)`, and ComfyUI extension `ty.image.spider`.

- [ ] **Step 1: Write failing gallery and lifecycle tests**

```javascript
test("小红书画廊隐藏整页下载并显示多图数量", () => {
  const view = createGallery(fakeContext({ provider: "xiaohongshu", bulk_download: false }));
  view.render([xhsItem({ image_count: 6 })], pageInfo());
  assert.equal(view.bulkDownloadButton.hidden, true);
  assert.match(view.root.textContent, /6 张/);
});

test("重复 configure 不重复安装控件和监听器", async () => {
  const { extension, NodeType, node, document } = makeComfyHarness();
  await extension.beforeRegisterNodeDef(NodeType, { name: "TyImageSpider" });
  node.onNodeCreated();
  node.onConfigure({});
  node.onConfigure({});
  assert.equal(node.domWidgets.filter((entry) => entry.name === "ty_image_spider").length, 1);
  assert.equal(document.listenerCount("keydown"), 1);
});
```

- [ ] **Step 2: Verify RED**

Run: `node --test tests/gallery.test.mjs tests/dialog.test.mjs tests/frontend_integration.test.mjs`

Expected: imports fail for gallery, dialog and integration modules.

- [ ] **Step 3: Implement the visual workspace in focused modules**

Gallery cards use `aspect-ratio: 4 / 5`, fixed overlay rows, `object-fit: cover`, two columns below 520 px node width and three columns above it. Loading uses fixed skeleton blocks; image errors preserve card dimensions. Detail dialog uses a full viewport backdrop, main image with `object-fit: contain`, source-specific right panel, thumbnail strip, Escape close, Tab focus loop, and prior-focus restoration.

The integration module hides `state_json`, creates exactly one DOM widget, synchronizes workflow state, aborts obsolete fetches, restores only permitted snapshots, and removes listeners/dialogs in `onRemoved`. It never queues a ComfyUI workflow for browsing.

```javascript
app.registerExtension({
  name: "ty.image.spider",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "TyImageSpider") return;
    installLifecycle(nodeType);
  },
});
```

The CSS uses neutral charcoal surfaces, white/gray text, green operational accents, and a restrained red source marker for Xiaohongshu. Borders, spacing, focus rings, empty states and status colors remain legible under ComfyUI light and dark theme variables.

- [ ] **Step 4: Verify GREEN**

Run: `node --test tests/gallery.test.mjs tests/dialog.test.mjs tests/frontend_integration.test.mjs`

Expected: all tests pass, including keyboard dialog behavior, source-specific actions, cleanup, restore and stale-request cases.

- [ ] **Step 5: Commit**

```powershell
git add web/gallery.js web/dialog.js web/ty_image_spider.js web/ty_image_spider.css tests/gallery.test.mjs tests/dialog.test.mjs tests/frontend_integration.test.mjs
git commit -m "feat: build image spider gallery interface"
```

### Task 12: Documentation, Quality Gate, and Real ComfyUI Verification

**Files:**
- Create: `README.md`
- Create: `requirements-dev.txt`
- Create: `scripts/check_quality.py`
- Create: `tests/test_readme.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: complete implementation.
- Produces: reproducible install, development, OpenCLI setup and release verification workflow.

- [ ] **Step 1: Write failing documentation contract test**

```python
def test_readme_documents_required_install_and_privacy_boundaries():
    text = Path("README.md").read_text(encoding="utf-8")
    for required in (
        "TY Image Spider", "civitai.com", "civitai.red", "小红书",
        "OpenCLI >= 1.8.8", "Chrome 扩展", "output/ty-image-spider",
        "不会写入工作流", "uv run", "故障排查",
    ):
        assert required in text
```

- [ ] **Step 2: Verify RED**

Run: `uv run --project ..\.. pytest tests/test_readme.py -q`

Expected: fails because README is missing.

- [ ] **Step 3: Write docs and quality runner**

README sections: product boundary, supported sources matrix, installation, junction development setup, Civitai API key, OpenCLI/extension/login setup, source-specific controls, downloads and privacy, troubleshooting, tests, and third-party licenses.

`scripts/check_quality.py` runs, in order: Ruff check/format, Mypy on domain/provider/service packages, pytest, Node tests, Prettier check, `node --check` for every web JS module, `compileall`, `git diff --check`, and `git diff --cached --check`. It exits immediately on the first nonzero status and prints Chinese check labels.

- [ ] **Step 4: Run the complete automated gate**

Run: `uv run --project ..\.. python scripts/check_quality.py`

Expected: every check passes with no warning or skipped required tool.

- [ ] **Step 5: Install OpenCLI and validate optional-source diagnostics**

Run:

```powershell
npm install -g @jackwener/opencli@^1.8.8
opencli --version
opencli doctor
```

Expected: version is at least `1.8.8`; if the extension or login is not configured, record the real error and verify the node maps it to the corresponding Chinese status without blocking Civitai/local. Do not treat missing user login as an automated-test failure.

- [ ] **Step 6: Create or verify the ComfyUI junction**

Run:

```powershell
$link = "C:\path\to\ComfyUI\custom_nodes\ty-image-spider-node"
$target = "C:\path\to\ty-image-spider-node"
if (-not (Test-Path -LiteralPath $link)) { cmd /c mklink /J $link $target }
Get-Item -LiteralPath $link | Select-Object FullName,LinkType,Target
```

Expected: the custom node path is a junction targeting this repository.

- [ ] **Step 7: Restart ComfyUI and inspect the UI**

Start or restart the local ComfyUI backend, open its actual configured URL, add `TY Image Spider · 素材浏览`, and capture desktop and narrow-node screenshots. Verify:

- Node registration and no output ports.
- Civitai search, filters, pagination, detail, prompt copy, single download and page download.
- Local new and legacy history.
- Xiaohongshu unavailable, bridge error, login error, search, detail carousel and whole-note download states available in the current environment.
- No overlapping text, controls or modal content at desktop and narrow widths.
- Node removal and workflow reload leave no duplicate DOM widgets or listeners.

- [ ] **Step 8: Run final verification after any UI fixes**

Run:

```powershell
uv run --project ..\.. python scripts/check_quality.py
git status --short
git diff --check
```

Expected: quality gate passes, only intended files are modified, and no generated screenshot, cache, browser profile or credential file is tracked.

- [ ] **Step 9: Commit**

```powershell
git add README.md requirements-dev.txt scripts/check_quality.py tests/test_readme.py .gitignore
git commit -m "docs: complete image spider delivery guide"
```
