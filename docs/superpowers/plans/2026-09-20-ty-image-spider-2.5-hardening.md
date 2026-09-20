# TY Image Spider 2.5 加固实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TY Image Spider 2.4.0 加固为具备清晰扩展边界、安全 HTTP 接口、隔离后台任务、开源治理、自动检查和可复现分发包的 2.5.0。

**Architecture:** 保留现有 Provider 注册表、单用例服务和组合根；展示信息通过 `ProviderPresentation` 随描述符下发，下载差异通过绑定来源的 `DownloadPolicy` 组合，缓存协调器与单任务 Runner 分离，JSON 正文由独立解析器限流。发布层使用明确运行时白名单和确定性 ZIP，不引入动态插件框架或新的运行依赖。

**Tech Stack:** Python 3.10+、dataclasses、typing Protocol、aiohttp、urllib、Pillow、SQLite、pytest、原生 ES modules、Node 20/22、jsdom、GitHub Actions、PowerShell、ComfyUI。

**Spec:** `docs/superpowers/specs/2026-09-20-ty-image-spider-2.5-hardening-design.md`

## Global Constraints

- 直接在当前 `main` 实施，不创建 worktree；每个任务独立提交。
- 节点继续保持 `TyImageSpider`、零输出端口和纯浏览下载行为。
- 下载根目录保持 `<ComfyUI>/output/ty-node/ty-image-spider/`，不写死盘符。
- 小红书后端兼容代码保留，`presentation.visible=false`，前端继续隐藏。
- 不读取、记录、归档或提交 `.local/tmdb.json` 及其他凭据。
- 不操作 8189；重启 8188 前必须确认 `/queue` 的 Running 与 Pending 均为 0。
- Python 运行依赖仍只有 `Pillow>=10`；不增加前端运行时依赖。
- JSON 请求体上限固定为 `1 * 1024 * 1024` 字节。
- 缓存任务默认最多并行 3 个，完成历史最多 64 个或 24 小时。
- 自动测试不得依赖实时素材站、TMDB、OpenCLI 或浏览器登录状态。
- 文档、用户文案和代码注释使用中文；公共标识符使用英文。
- 所有行为变更先写失败测试并确认失败原因，再实现最小代码。
- 不推送远端、不创建 GitHub Release；完成后只创建本地提交、`v2.5.0` 标签和分发包。

## Review Focus

- 描述符缺少 `presentation` 或两个来源声明同一分组却使用不同名称时，应在契约测试中失败，前端对旧缓存描述符仍应显示“其他”和来源原名。
- 相同筛选字典采用不同键顺序时必须得到同一缓存任务指纹并拒绝重复，不同查询不得互相取消或覆盖。
- 没有 `Content-Length` 的 chunked 请求必须在累计超过 1 MiB 时返回统一 413，不能依赖 aiohttp 全局设置。
- 下载发生跨站重定向、Provider 使用错误策略或资产 ID 含路径字符时，必须在写文件前拒绝。
- 发布包即使遇到误跟踪的 `.local/tmdb.json`、绝对本机路径或旧版本号，也必须拒绝构建且不留下半成品 ZIP。

---

## File Map

### 领域契约与展示

- `src/ty_image_spider/version.py`：运行时版本与统一 User-Agent。
- `src/ty_image_spider/models.py`：新增不可变 `ProviderPresentation`，扩展 `ProviderDescriptor` 和 `SpiderError.details`。
- `src/ty_image_spider/providers/*.py`：每个 Provider 声明自身展示元数据。
- `web/source_controls.js`：按描述符分组、排序和隐藏来源。
- `web/gallery.js`：从描述符读取缩略图标记和缓存说明。
- `web/dialog.js`：从描述符读取详情来源名。
- `web/ty_image_spider.js`：把当前描述符传给画廊和详情。

### 下载与缓存

- `src/ty_image_spider/providers/download_policy.py`：下载策略协议、通用规则对象和策略构造函数。
- `src/ty_image_spider/providers/curated_download.py`：只执行绑定策略后的通用图片读取和落盘。
- `src/ty_image_spider/providers/image_readers.py`：按 Provider ID 查找已绑定读取器。
- `src/ty_image_spider/services/cache_runner.py`：单个缓存任务的翻页、详情、读取和索引流程。
- `src/ty_image_spider/services/cache_job.py`：任务去重、并发、取消、状态和历史清理。
- `src/ty_image_spider/bootstrap.py`：唯一依赖组合位置。

### HTTP、安全与发布

- `src/ty_image_spider/http_json.py`：1 MiB JSON 正文读取和解析。
- `src/ty_image_spider/routes.py`：使用 `JsonBodyReader` 并序列化结构化错误详情。
- `.github/workflows/ci.yml`：Python 与前端兼容矩阵。
- `scripts/build_release.py`：版本校验、运行时文件选择、敏感内容检查和确定性 ZIP。
- `scripts/check_quality.py`：本地完整质量门禁。
- `LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`：开源治理。
- `docs/compatibility.md`、`docs/source-rights.md`：兼容范围与素材权利。
- `README.md`、`CHANGELOG.md`：2.5.0 用户说明与验收记录。

---

### Task 1: 统一版本标识与 Provider 展示契约

**Files:**
- Create: `src/ty_image_spider/version.py`
- Modify: `src/ty_image_spider/models.py`
- Modify: `src/ty_image_spider/providers/civitai.py`
- Modify: `src/ty_image_spider/providers/wallhaven.py`
- Modify: `src/ty_image_spider/providers/behance.py`
- Modify: `src/ty_image_spider/providers/editorial.py`
- Modify: `src/ty_image_spider/providers/arena.py`
- Modify: `src/ty_image_spider/providers/loc.py`
- Modify: `src/ty_image_spider/providers/nasa.py`
- Modify: `src/ty_image_spider/providers/filmgrab.py`
- Modify: `src/ty_image_spider/providers/vam.py`
- Modify: `src/ty_image_spider/providers/artic.py`
- Modify: `src/ty_image_spider/providers/cleveland.py`
- Modify: `src/ty_image_spider/providers/xiaohongshu.py`
- Modify: `src/ty_image_spider/providers/local.py`
- Modify: `src/ty_image_spider/providers/editorial_sources.py`
- Modify: `src/ty_image_spider/downloads.py`
- Modify: `src/ty_image_spider/movies/tmdb.py`
- Modify: `src/ty_image_spider/providers/civitai_client.py`
- Modify: `src/ty_image_spider/providers/curated_client.py`
- Modify: `src/ty_image_spider/providers/curated_download.py`
- Modify: `src/ty_image_spider/providers/museum_client.py`
- Modify: `src/ty_image_spider/providers/public_json_client.py`
- Modify: `src/ty_image_spider/providers/wallhaven_client.py`
- Modify: `src/ty_image_spider/providers/wallhaven_download.py`
- Modify: `pyproject.toml`, `package.json`, `package-lock.json`
- Test: `tests/test_models.py`, `tests/test_provider_registry.py`, `tests/test_bootstrap.py`, `tests/test_version.py`

**Interfaces:**
- Produces: `ProviderPresentation(group_id, group_label, short_label, detail_label, group_order, source_order, cache_description="", visible=True)`。
- Produces: required `ProviderDescriptor.presentation: ProviderPresentation` and serialized `presentation` object.
- Produces: `__version__ = "2.5.0"` and `USER_AGENT = "TY-Image-Spider/2.5.0"`.
- Produces: `SpiderError.details: Mapping[str, JsonValue]` for later structured duplicate-task responses.

- [ ] **Step 1: Write failing model, descriptor and version tests**

```python
def test_provider_descriptor_serializes_presentation():
    presentation = ProviderPresentation(
        "collections", "艺术馆藏", "AIC", "芝加哥艺术博物馆", 30, 40,
        "新增最多100件馆藏素材", True,
    )
    value = ProviderDescriptor("artic", "芝加哥艺术", presentation).to_dict()
    assert value["presentation"] == {
        "group_id": "collections", "group_label": "艺术馆藏",
        "short_label": "AIC", "detail_label": "芝加哥艺术博物馆",
        "group_order": 30, "source_order": 40,
        "cache_description": "新增最多100件馆藏素材", "visible": True,
    }

def test_all_registered_providers_have_consistent_presentation(tmp_path):
    descriptors = build_services(tmp_path / "out", tmp_path / "cache").providers.descriptors()
    assert next(item for item in descriptors if item.id == "xiaohongshu").presentation.visible is False
    names = {}
    for descriptor in descriptors:
        key = descriptor.presentation.group_id
        names.setdefault(key, descriptor.presentation.group_label)
        assert names[key] == descriptor.presentation.group_label
        assert descriptor.presentation.short_label
        assert descriptor.presentation.detail_label

def test_runtime_and_manifest_versions_match():
    assert __version__ == "2.5.0"
    assert USER_AGENT == "TY-Image-Spider/2.5.0"
    assert tomllib.loads(Path("pyproject.toml").read_text("utf-8"))["project"]["version"] == __version__
    assert json.loads(Path("package.json").read_text("utf-8"))["version"] == __version__
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_models.py tests/test_provider_registry.py tests/test_bootstrap.py tests/test_version.py -q`

Expected: FAIL because `ProviderPresentation`, runtime version module and descriptor fields do not exist.

- [ ] **Step 3: Implement the immutable presentation model and migrate every Provider**

```python
@dataclass(frozen=True, slots=True)
class ProviderPresentation:
    group_id: str
    group_label: str
    short_label: str
    detail_label: str
    group_order: int
    source_order: int
    cache_description: str = ""
    visible: bool = True

@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    id: str
    label: str
    presentation: ProviderPresentation
    description: str = ""
    # existing fields unchanged
```

Use these stable group orders: AI 与壁纸 `10`、摄影与设计 `20`、艺术馆藏 `30`、电影 `40`、本地 `50`。Preserve the current within-group order with increments of 10. Put editorial presentation values in each `EditorialSource` config so `EditorialProvider` has no source-ID branches.

- [ ] **Step 4: Replace every literal User-Agent with the shared constant and update manifests**

```python
from .version import USER_AGENT

request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
```

Update `pyproject.toml`, `package.json`, and both version fields in `package-lock.json` to `2.5.0`. Extend `tests/test_version.py` to scan `src/**/*.py` and assert no `TY-Image-Spider/2.0`, `/2.1`, or `/2.4` remains.

- [ ] **Step 5: Run focused and regression tests**

Run: `python -m pytest tests/test_models.py tests/test_provider_registry.py tests/test_bootstrap.py tests/test_version.py tests/test_civitai_client.py tests/test_wallhaven_client.py tests/test_museum_client.py -q`

Expected: PASS; 18 descriptors serialize complete presentation metadata and all clients use the 2.5.0 identifier.

- [ ] **Step 6: Commit**

```powershell
git add src tests/test_models.py tests/test_provider_registry.py tests/test_bootstrap.py tests/test_version.py pyproject.toml package.json package-lock.json
git commit -m "refactor: centralize provider presentation and version identity"
```

### Task 2: 让前端完全由 Provider 描述符驱动

**Files:**
- Modify: `web/source_controls.js`
- Modify: `web/gallery.js`
- Modify: `web/dialog.js`
- Modify: `web/ty_image_spider.js`
- Modify: `tests/source_controls.test.mjs`
- Modify: `tests/gallery.test.mjs`
- Modify: `tests/dialog.test.mjs`
- Modify: `tests/frontend_integration.test.mjs`

**Interfaces:**
- Consumes: Task 1 serialized `provider.presentation`.
- Produces: `normalizePresentation(descriptor)` compatibility fallback.
- Changes: `createGallery({ descriptor, ... })` and `openAssetDialog({ descriptor, ... })` use one current descriptor instead of source-name maps.

- [ ] **Step 1: Write failing metadata-driven frontend tests**

```javascript
test("来源分组、排序和隐藏完全来自描述符", () => {
  const providers = [
    provider("hidden", { visible: false, group_id: "x", group_label: "隐藏", group_order: 1 }),
    provider("second", { group_id: "g", group_label: "设计", group_order: 20, source_order: 20 }),
    provider("first", { group_id: "g", group_label: "设计", group_order: 20, source_order: 10 }),
  ];
  const view = renderSourceControls({ document, providers, provider: "first" });
  assert.deepEqual([...view.root.querySelectorAll(".tyis-source-tab")].map((node) => node.dataset.provider), ["first", "second"]);
  assert.equal(view.root.textContent.includes("hidden"), false);
});

test("缩略图和详情使用描述符标签", () => {
  const descriptor = providerDescriptor({ short_label: "TEST", detail_label: "测试来源" });
  const gallery = createGallery({ document, descriptor });
  gallery.render([item({ provider: descriptor.id })]);
  assert.equal(gallery.root.querySelector(".tyis-source-mark").textContent, "TEST");
  const dialog = openAssetDialog({ document, descriptor, detail: detail(descriptor.id) });
  assert.equal(dialog.overlay.querySelector(".tyis-dialog-source").textContent, "测试来源");
});
```

Add a compatibility test where `presentation` is absent: group is “其他”, labels fall back to descriptor `label`, and the UI does not throw.

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `node --test tests/source_controls.test.mjs tests/gallery.test.mjs tests/dialog.test.mjs tests/frontend_integration.test.mjs`

Expected: FAIL because grouping, source marks, detail labels and editorial cache text are hard-coded.

- [ ] **Step 3: Implement descriptor normalization and remove all source display maps**

```javascript
export function normalizePresentation(descriptor = {}) {
  const value = descriptor.presentation || {};
  return {
    groupId: value.group_id || "other",
    groupLabel: value.group_label || "其他",
    shortLabel: value.short_label || descriptor.label || descriptor.id || "来源",
    detailLabel: value.detail_label || descriptor.label || descriptor.id || "来源",
    groupOrder: Number.isFinite(value.group_order) ? value.group_order : 999,
    sourceOrder: Number.isFinite(value.source_order) ? value.source_order : 999,
    cacheDescription: value.cache_description || "按当前条件新增最多100张素材，已有缓存将跳过",
    visible: value.visible !== false,
  };
}
```

Build groups from visible providers, stable-sort groups and sources, and remove `SOURCE_GROUPS`, `sourceMark()` label objects, `sourceLabel()` maps, and editorial provider arrays used only for cache tooltips. Keep source-specific content renderers for Civitai, Wallhaven, collections and editorials because those are behavior, not display metadata.

- [ ] **Step 4: Pass descriptors through the integration controller**

When creating or refreshing a source view, resolve the descriptor once from `providers` and pass it to source controls, gallery and detail. If a restored workflow names hidden Xiaohongshu, keep the existing fallback to the first visible Provider.

- [ ] **Step 5: Run all frontend tests and scan for stale mappings**

Run: `npm test`

Run: `rg -n "SOURCE_GROUPS|function sourceLabel|const labels =|featureshoot.*mymodernmet" web`

Expected: all tests PASS; search returns no display-name map.

- [ ] **Step 6: Commit**

```powershell
git add web tests/*.test.mjs
git commit -m "refactor: render source UI from provider metadata"
```

### Task 3: 将下载限制拆成可组合策略

**Files:**
- Create: `src/ty_image_spider/providers/download_policy.py`
- Create: `src/ty_image_spider/providers/image_readers.py`
- Modify: `src/ty_image_spider/providers/curated_download.py`
- Modify: `src/ty_image_spider/providers/artic.py`
- Modify: `src/ty_image_spider/providers/arena.py`
- Modify: `src/ty_image_spider/providers/behance.py`
- Modify: `src/ty_image_spider/providers/cleveland.py`
- Modify: `src/ty_image_spider/providers/editorial.py`
- Modify: `src/ty_image_spider/providers/filmgrab.py`
- Modify: `src/ty_image_spider/providers/loc.py`
- Modify: `src/ty_image_spider/providers/nasa.py`
- Modify: `src/ty_image_spider/providers/vam.py`
- Modify: `src/ty_image_spider/bootstrap.py`
- Create: `tests/test_download_policy.py`
- Create: `tests/test_image_readers.py`
- Modify: `tests/test_curated_download.py`
- Modify: Provider download tests

**Interfaces:**
- Produces: `DownloadPolicy` Protocol with `provider_id`, `validate_asset_id()`, `validate_url()`, `normalize_url()`.
- Produces: `HostDownloadPolicy(provider_id, host_rule, id_pattern, safe_path_chars="/%")`.
- Changes: `CuratedDownloader(policy, open_url=urlopen).read(url)` and `.download(url, item_id, output_root)`.
- Produces: `ImageReaderRegistry.register(provider_id, reader)` and `.read(url, provider_id)`.

- [ ] **Step 1: Write failing policy and registry tests**

```python
def test_policy_rejects_foreign_url_and_path_asset_id():
    policy = curated_policies()["artic"]
    with pytest.raises(SpiderError, match="素材 ID"):
        policy.validate_asset_id("../../secret")
    with pytest.raises(SpiderError):
        policy.validate_url("https://evil.example/image.jpg")
    assert policy.normalize_url("https://www.artic.edu/iiif/2/a/full/843,/0/default.jpg").endswith("/full/843,/0/default.jpg")

def test_image_reader_registry_routes_to_bound_strategy():
    registry = ImageReaderRegistry()
    registry.register("artic", ReaderStub(b"a"))
    assert registry.read("https://www.artic.edu/image.jpg", "artic") == (b"a", ".jpg")
    with pytest.raises(SpiderError, match="不支持"):
        registry.read("https://example.com/a.jpg", "unknown")
```

Cover every curated Provider ID in a parameterized test, including redirect revalidation and IIIF comma preservation.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest tests/test_download_policy.py tests/test_image_readers.py tests/test_curated_download.py -q`

Expected: FAIL because policy and reader registry modules do not exist and `CuratedDownloader` still branches on Provider ID.

- [ ] **Step 3: Implement policies and make the downloader provider-agnostic**

```python
class CuratedDownloader:
    def __init__(self, policy: DownloadPolicy, open_url: Callable[..., Any] = urlopen):
        self._policy = policy
        self._open_url = open_url

    def read(self, url: str) -> tuple[bytes, str]:
        self._policy.validate_url(url)
        normalized = self._policy.normalize_url(url)
        # existing limited read and Pillow verification

    def download(self, url: str, item_id: str, output_root: Path) -> DownloadResult:
        self._policy.validate_asset_id(item_id)
        # use self._policy.provider_id for destination
```

Place each source rule in a small named policy constant or factory. Do not leave `_HOSTS`, `if provider in {...}` or asset-ID branching in `curated_download.py`.

- [ ] **Step 4: Inject bound downloaders and readers in the composition root**

Construct one downloader per policy, pass it to the corresponding Provider, and register cache-capable readers in `ImageReaderRegistry`. Editorial configs expose their policy key so the bootstrap loop remains data-driven.

- [ ] **Step 5: Run all download, Provider and bootstrap tests**

Run: `python -m pytest tests/test_download_policy.py tests/test_image_readers.py tests/test_curated_download.py tests/test_curated_providers.py tests/test_editorial_sources.py tests/test_museum_providers.py tests/test_loc_provider.py tests/test_nasa_provider.py tests/test_bootstrap.py -q`

Expected: PASS; foreign URL and redirection tests fail closed before writing output.

- [ ] **Step 6: Commit**

```powershell
git add src/ty_image_spider/providers src/ty_image_spider/bootstrap.py tests
git commit -m "refactor: isolate provider download policies"
```

### Task 4: 用独立 Runner 支持隔离的多缓存任务

**Files:**
- Create: `src/ty_image_spider/services/cache_runner.py`
- Modify: `src/ty_image_spider/services/cache_job.py`
- Modify: `src/ty_image_spider/bootstrap.py`
- Modify: `src/ty_image_spider/routes.py`
- Create: `tests/test_cache_runner.py`
- Modify: `tests/test_cache_job.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Produces: immutable `CacheRequest.from_payload(payload)` and `.fingerprint()` using canonical JSON.
- Produces: `CacheJobRunner.run(request, cancel, update) -> None` containing the existing 100-item traversal.
- Changes: `CacheJobService(..., max_concurrency=3, max_history=64, retention_seconds=86400, clock=time.time)`.
- Produces: duplicate errors as `SpiderError("cache_duplicate", ..., status=409, details={"job_id": existing_id})`.

- [ ] **Step 1: Move current single-task behavior behind failing Runner tests**

```python
def test_runner_adds_100_new_items_and_preserves_progress(tmp_path):
    updates = []
    runner = make_runner(tmp_path, pages=three_pages_of_60())
    runner.run(CacheRequest("filmgrab", "film", {}), Event(), updates.append)
    assert updates[-1]["state"] == "complete"
    assert updates[-1]["cached"] == 100
    assert progress_cursor(tmp_path) == "2"
```

Also port the empty-page, failure-count, cancellation and “skip existing then continue” cases from `test_cache_job.py` so the coordinator tests no longer depend on traversal internals.

- [ ] **Step 2: Run Runner tests and verify RED**

Run: `python -m pytest tests/test_cache_runner.py -q`

Expected: FAIL because `CacheJobRunner` and `CacheRequest` do not exist.

- [ ] **Step 3: Implement the single-task Runner without locks or thread creation**

The Runner receives search, detail, index, image reader and progress dependencies. `update(values: Mapping[str, object])` is the only way it reports state. Preserve limits of 100 new items, 500 distinct candidates and 50 cursors.

- [ ] **Step 4: Write failing coordinator concurrency tests**

```python
def test_different_jobs_run_concurrently_and_cancel_independently(service, blocking_runner):
    one = service.start({"provider": "filmgrab", "query": "one", "filters": {}})
    two = service.start({"provider": "filmgrab", "query": "two", "filters": {}})
    assert blocking_runner.wait_for_entries(2)
    service.cancel(one["id"])
    assert service.status(one["id"])["state"] in {"running", "cancelled"}
    assert service.status(two["id"])["state"] == "running"

def test_equivalent_filter_order_is_duplicate(service):
    service.start({"provider": "filmgrab", "filters": {"a": 1, "b": 2}})
    with pytest.raises(SpiderError) as caught:
        service.start({"provider": "filmgrab", "filters": {"b": 2, "a": 1}})
    assert caught.value.code == "cache_duplicate"
    assert caught.value.details["job_id"]
```

Add tests for fourth-task capacity rejection, 64-history pruning, 24-hour pruning, running-job retention and thread-start failure releasing capacity.

Add a route test with `SpiderError(details={"job_id": "safe", "token": "secret"})`; the response must retain `job_id` and replace the token value with `[已隐藏]`.

- [ ] **Step 5: Implement the coordinator and structured route error**

Under one lock, prune terminal history, check `active_keys`, acquire a `BoundedSemaphore` without blocking, create `CacheJobContext`, then start one daemon thread. The worker calls the Runner, removes its fingerprint from `active_keys`, releases the semaphore in `finally`, and never holds the service lock during network or disk work.

```python
def _error(error: SpiderError) -> web.Response:
    body = {"code": error.code, "message": _safe_text(error.message), "action": _safe_text(error.action)}
    if error.details:
        body["details"] = _safe_json(error.details)
    return web.json_response({"ok": False, "error": body}, status=error.status)
```

`_safe_json` recursively copies mappings and lists, replaces values whose key matches `key|token|secret|cookie|authorization`, and applies `_safe_text` to strings. It never mutates the original details object.

- [ ] **Step 6: Run cache and route tests**

Run: `python -m pytest tests/test_cache_runner.py tests/test_cache_job.py tests/test_routes.py tests/test_bootstrap.py -q`

Expected: PASS; three distinct tasks run, the fourth gets `cache_capacity`, duplicates include the existing `job_id`, and cancellation is isolated.

- [ ] **Step 7: Commit**

```powershell
git add src/ty_image_spider/services/cache_runner.py src/ty_image_spider/services/cache_job.py src/ty_image_spider/bootstrap.py src/ty_image_spider/routes.py tests/test_cache_runner.py tests/test_cache_job.py tests/test_routes.py tests/test_bootstrap.py
git commit -m "feat: isolate concurrent cache jobs"
```

### Task 5: 对所有 JSON 路由执行 1 MiB 正文限制

**Files:**
- Create: `src/ty_image_spider/http_json.py`
- Modify: `src/ty_image_spider/routes.py`
- Create: `tests/test_http_json.py`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Produces: `JsonBodyReader(max_bytes=1 * 1024 * 1024, chunk_bytes=64 * 1024).read(request) -> Mapping[str, object]`.
- Consumes: aiohttp `Request.content_length` and `Request.content.iter_chunked()`.
- Produces: `request_too_large` with HTTP 413, and `invalid_json` with HTTP 400.

- [ ] **Step 1: Write failing real-aiohttp boundary tests**

```python
async def test_json_reader_rejects_declared_and_chunked_oversize(aiohttp_client):
    client = await reader_client(client_max_size=2 * 1024 * 1024)
    declared = await client.post("/read", data=b"x" * (MAX_JSON_BYTES + 1), headers={"Content-Type": "application/json"})
    assert declared.status == 413
    chunked = await client.post("/read", data=chunk_stream(MAX_JSON_BYTES + 1))
    assert chunked.status == 413

async def test_json_reader_accepts_exact_limit_and_rejects_bad_utf8():
    assert (await post_exact_json(MAX_JSON_BYTES)).status == 200
    response = await post_raw(b'\xff', content_type="application/json")
    assert response.status == 400
```

Include empty input, valid array top-level rejection, malformed JSON and payload just below the limit.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_http_json.py tests/test_routes.py -q`

Expected: FAIL because routes call `request.json()` and chunked requests are not explicitly bounded.

- [ ] **Step 3: Implement bounded streaming parse and inject it into every JSON route**

```python
async def read(self, request: web.Request) -> Mapping[str, object]:
    if request.content_length is not None and request.content_length > self._max_bytes:
        raise SpiderError("request_too_large", "请求正文不能超过 1 MiB", status=413)
    payload = bytearray()
    async for chunk in request.content.iter_chunked(self._chunk_bytes):
        payload.extend(chunk)
        if len(payload) > self._max_bytes:
            raise SpiderError("request_too_large", "请求正文不能超过 1 MiB", status=413)
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpiderError("invalid_json", "请求正文不是有效 JSON") from exc
    if not isinstance(value, Mapping):
        raise SpiderError("invalid_json", "请求正文必须是 JSON 对象")
    return value
```

Convert aiohttp `HTTPRequestEntityTooLarge` into the same error. Do not log or echo raw request bytes.

- [ ] **Step 4: Run route and security tests**

Run: `python -m pytest tests/test_http_json.py tests/test_routes.py tests/test_security.py -q`

Expected: PASS; all POST JSON endpoints use the reader, including page download and cache start.

- [ ] **Step 5: Commit**

```powershell
git add src/ty_image_spider/http_json.py src/ty_image_spider/routes.py tests/test_http_json.py tests/test_routes.py
git commit -m "security: bound JSON request bodies"
```

### Task 6: 补齐开源治理、素材权利和兼容文档

**Files:**
- Create: `LICENSE`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `docs/compatibility.md`
- Create: `docs/source-rights.md`
- Modify: `README.md`
- Modify: `tests/test_readme.py`
- Create: `tests/test_governance_docs.py`

**Interfaces:**
- Produces: MIT 许可、Contributor Covenant 2.1、私密漏洞报告流程、Provider 贡献清单和验证矩阵。
- Documents: all 18 registered Provider IDs, with Xiaohongshu explicitly hidden/experimental.

- [ ] **Step 1: Write failing documentation contract tests**

```python
def test_governance_documents_have_required_boundaries():
    assert "MIT License" in Path("LICENSE").read_text("utf-8")
    assert "TY Image Spider contributors" in Path("LICENSE").read_text("utf-8")
    security = Path("SECURITY.md").read_text("utf-8")
    assert "Report a vulnerability" in security
    assert "不要在公开 Issue" in security
    rights = Path("docs/source-rights.md").read_text("utf-8")
    for provider_id in registered_provider_ids():
        assert f"`{provider_id}`" in rights

def test_compatibility_matrix_names_ci_and_real_machine_scope():
    text = Path("docs/compatibility.md").read_text("utf-8")
    for required in ("Python 3.10", "Python 3.13", "Node.js 20", "Node.js 22", "Windows", "Ubuntu", "ComfyUI"):
        assert required in text
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_readme.py tests/test_governance_docs.py -q`

Expected: FAIL because governance and compatibility files are absent and README still contains outdated output paths.

- [ ] **Step 3: Write exact governance documents**

Use the unmodified MIT text with `Copyright (c) 2026 TY Image Spider contributors`. Use Contributor Covenant 2.1 text and its standard enforcement ladder；行为准则的举报入口明确引用 `SECURITY.md` 中的私密渠道，不保留 `[INSERT CONTACT METHOD]` 等模板占位符。`SECURITY.md` supports only the latest 2.x release, directs private reports to GitHub Security Advisories, and says a public Issue may request private contact but must not contain vulnerability details or credentials.

`CONTRIBUTING.md` includes setup, `python scripts/check_quality.py`, Provider responsibilities, required presentation and download policy fields, fixture-only tests, Chinese docs, output-path invariant and PR checklist.

- [ ] **Step 4: Write source rights, compatibility and README links**

For every Provider, document source API/page, typical rights owner, fields preserved by the node and user responsibility. State that caching and downloading never grant a new license. Fix README paths to `output/ty-node/ty-image-spider/` and link all governance documents.

- [ ] **Step 5: Run documentation tests**

Run: `python -m pytest tests/test_readme.py tests/test_governance_docs.py -q`

Expected: PASS; no test expects hidden Xiaohongshu to appear in the UI.

- [ ] **Step 6: Commit**

```powershell
git add LICENSE CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md docs/compatibility.md docs/source-rights.md README.md tests/test_readme.py tests/test_governance_docs.py
git commit -m "docs: add open source governance and rights guidance"
```

### Task 7: 建立 Python、前端 GitHub CI 与本地质量矩阵

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `scripts/check_quality.py`
- Create: `tests/test_ci_config.py`

**Interfaces:**
- Produces: Python matrix `{windows-latest, ubuntu-latest} x {3.10, 3.13}`.
- Produces: Frontend matrix `ubuntu-latest x {20, 22}`.

- [ ] **Step 1: Write failing CI contract tests**

```python
def test_ci_has_required_matrices_and_minimal_permissions():
    text = Path(".github/workflows/ci.yml").read_text("utf-8")
    for required in ("windows-latest", "ubuntu-latest", '"3.10"', '"3.13"', '"20"', '"22"'):
        assert required in text
    assert "contents: read" in text
    assert "npm ci" in text
```

Also assert Python jobs run pytest, Ruff, Mypy and compileall, while frontend jobs run Node tests, Prettier and syntax checks.

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest tests/test_ci_config.py -q`

Expected: FAIL because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Add separate Python, frontend and release-check jobs**

```yaml
permissions:
  contents: read
jobs:
  python:
    strategy:
      matrix:
        os: [windows-latest, ubuntu-latest]
        python: ["3.10", "3.13"]
  frontend:
    strategy:
      matrix:
        node: ["20", "22"]
```

Use `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`. Python installs `requirements-dev.txt`; frontend uses `npm ci`. Do not place live-site, TMDB, OpenCLI or ComfyUI UI tests in CI. The release-check job is added in Task 8 after its executable script exists, so every intermediate commit remains green.

- [ ] **Step 4: Align the local quality runner with CI commands**

Keep `scripts/check_quality.py` as the complete local entry point. Add governance, CI and release-script tests to pytest discovery automatically; add version and stale User-Agent checks through tests, not shell-only assertions.

- [ ] **Step 5: Run local static verification**

Run: `python -m pytest tests/test_ci_config.py -q`

Run: `python scripts/check_quality.py`

Expected: CI contract passes and the complete local gate passes without skipped tools.

- [ ] **Step 6: Commit**

```powershell
git add .github/workflows/ci.yml scripts/check_quality.py tests/test_ci_config.py
git commit -m "ci: add supported runtime matrix"
```

### Task 8: 构建可复现且不泄密的运行时分发包

**Files:**
- Create: `scripts/build_release.py`
- Create: `tests/test_release.py`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ci_config.py`

**Interfaces:**
- Produces: `read_versions(root) -> Mapping[str, str]` and `validate_versions(root) -> str`.
- Produces: `select_runtime_files(tracked: Iterable[PurePosixPath]) -> tuple[PurePosixPath, ...]`.
- Produces: `scan_release_files(root, files) -> None`.
- Produces: `build_archive(root, target, files, epoch) -> str` returning uppercase SHA256.
- CLI: `python scripts/build_release.py [--check] [--output-dir dist]`.

- [ ] **Step 1: Write failing pure release-policy tests**

```python
def test_runtime_allowlist_excludes_development_and_secrets():
    selected = select_runtime_files(map(PurePosixPath, [
        "__init__.py", "src/ty_image_spider/models.py", "web/api.js", "LICENSE",
        "docs/source-rights.md", "tests/test_models.py", "docs/superpowers/specs/x.md",
        ".local/tmdb.json", "scripts/check_quality.py", "package-lock.json",
    ]))
    assert PurePosixPath("src/ty_image_spider/models.py") in selected
    assert PurePosixPath("docs/source-rights.md") in selected
    assert all("tests" not in path.parts and ".local" not in path.parts for path in selected)

def test_two_archives_are_byte_identical(tmp_path):
    one = build_archive(FIXTURE_ROOT, tmp_path / "one.zip", FILES, 1_600_000_000)
    two = build_archive(FIXTURE_ROOT, tmp_path / "two.zip", FILES, 1_600_000_000)
    assert one == two
    assert (tmp_path / "one.zip").read_bytes() == (tmp_path / "two.zip").read_bytes()
```

Add version mismatch, forbidden filename, `C:\Users\...`, `E:\ComfyUI...`, token-like text, stable path order, fixed top-level directory and failed-build cleanup tests.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_release.py -q`

Expected: FAIL because release builder functions do not exist.

- [ ] **Step 3: Implement the strict runtime allowlist and sensitive scan**

Allow only root runtime/install docs, `src/**`, `web/**`, and user-facing `docs/*.md`. Explicitly reject any path segment named `.local`, `.git`, `tests`, `scripts`, `dist`, `node_modules`, `__pycache__`, or `superpowers`. Obtain production candidates from `git ls-files -z`; an untracked file is never archived.

Scan UTF-8 text files for the two known local workspace prefixes, private key headers, bearer tokens and credential filenames. False-positive-prone generic words such as `token` in documentation are not forbidden by themselves.

- [ ] **Step 4: Implement deterministic ZIP metadata and atomic output**

Sort POSIX paths, prefix each with `ty-image-spider-node/`, use fixed compression level and permissions, and derive the DOS-safe timestamp from `SOURCE_DATE_EPOCH` or the target Git commit time. Write to a temporary file, verify it, then `os.replace()` the final ZIP and atomically write `<zip>.sha256`.

- [ ] **Step 5: Verify check mode and reproducibility in the real repository**

Run: `python scripts/build_release.py --check`

Run twice with a temporary output directory and compare hashes. Expected: identical hashes; archive excludes `.github`, tests, scripts, dev dependencies and `docs/superpowers`.

- [ ] **Step 6: Add the CI release validation job**

Add one Ubuntu/Python 3.13 job that depends on the Python job and runs `python scripts/build_release.py --check`. Extend `tests/test_ci_config.py` to assert the command and dependency are present, then run `python -m pytest tests/test_ci_config.py tests/test_release.py -q`.

- [ ] **Step 7: Commit**

```powershell
git add scripts/build_release.py tests/test_release.py .gitignore .github/workflows/ci.yml tests/test_ci_config.py
git commit -m "build: add reproducible release packaging"
```

### Task 9: 完整回归、8188 实机验收和 2.5.0 固化

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md` if real verification exposes a documentation correction
- Generate (ignored): `dist/ty-image-spider-node-v2.5.0.zip`
- Generate (ignored): `dist/ty-image-spider-node-v2.5.0.zip.sha256`

**Interfaces:**
- Consumes: Tasks 1-8 complete implementation.
- Produces: final quality evidence, real ComfyUI verification record, release commit and local `v2.5.0` tag.

- [ ] **Step 1: Run the complete automated quality gate**

Run: `python scripts/check_quality.py`

Expected: Ruff check/format, Mypy, all Python tests, all frontend tests, Prettier, JS syntax, Python compileall and Git whitespace checks pass.

- [ ] **Step 2: Verify both installed Python boundaries available on this machine**

Run: `py -0p`

For installed 3.10 and 3.13 interpreters, create disposable virtual environments, install `requirements-dev.txt`, and run pytest plus compileall. If either interpreter is absent locally, record that CI covers it and do not claim local execution for that version.

- [ ] **Step 3: Check the 8188 queue before any restart**

```powershell
$queue = Invoke-RestMethod -Uri "http://127.0.0.1:8188/queue"
$running = @($queue.queue_running).Count
$pending = @($queue.queue_pending).Count
if ($running -ne 0 -or $pending -ne 0) { throw "8188 仍有任务：Running=$running Pending=$pending" }
```

Do not inspect, stop or send requests to port 8189. Identify the process listening on 8188 and preserve its actual command line before restarting only that process.

- [ ] **Step 4: Restart 8188 and perform real browser verification**

Open `http://127.0.0.1:8188/`. Verify one existing `TY Image Spider 2.0` workflow and a newly added node:

- Node opens with controls immediately and has no output ports.
- Two-level source navigation comes entirely from descriptors; Xiaohongshu is absent.
- Civitai search, prompt badge/detail, previous/next page, fullscreen and download path work.
- One editorial source and one collection source search, detail and download work.
- Start two distinct cache tasks from two nodes or API calls; both report independent IDs and cancelling one leaves the other running.
- Oversize request made to a safe local route returns HTTP 413 without destabilizing ComfyUI.
- Other workflows' output does not appear in this node.

Capture screenshots and logs under ignored `.artifacts/2.5.0/`; do not commit output images, source downloads or credentials.

- [ ] **Step 5: Build and inspect the final release twice**

Run: `python scripts/build_release.py --output-dir dist`

Delete only the just-built ignored ZIP and checksum, rebuild, and assert the SHA256 is identical. List the archive and verify it contains `LICENSE`, `README.md`, `requirements.txt`, `src/`, `web/`, and user docs, while excluding `.local`, `.github`, `tests`, `scripts`, dev requirements and design plans.

- [ ] **Step 6: Write the 2.5.0 changelog from verified evidence**

Record behavior changes, exact automated test counts, platforms/interpreters actually run, 8188 scenarios actually observed, archive SHA256 and remaining external-site risks. Do not copy expected counts from this plan.

- [ ] **Step 7: Re-run final checks after documentation changes**

Run: `python scripts/check_quality.py`

Run: `python scripts/build_release.py --check`

Run: `git diff --check` and `git status --short`.

Expected: all checks pass; only intended changelog/readme changes are pending; `.local`, caches, outputs, screenshots, ZIP and checksum remain untracked/ignored.

- [ ] **Step 8: Commit and tag the verified release**

```powershell
git add CHANGELOG.md README.md
git commit -m "release: 固化 TY Image Spider 2.5.0"
git tag -a v2.5.0 -m "TY Image Spider 2.5.0"
git status --short --branch
git show --stat --oneline v2.5.0
```

Expected: clean `main`, annotated local tag points at the release commit, and no remote operation has occurred.

---

## Execution Order and Review Gates

Tasks 1-3 establish contracts used by later work and must run in order. Tasks 4 and 5 are independent after Task 3 but remain sequential in this current-session execution to keep TDD evidence and commits easy to audit. Tasks 6-8 depend on the final contract names and version, and Task 9 runs only after every earlier task is green.

After each task: inspect `git diff --check`, run the task's focused tests, review the staged diff, commit only that task, then continue. After Tasks 3、5、8 run the complete `scripts/check_quality.py` gate because they change broad boundaries. Any new failure is fixed in the task that introduced it rather than deferred to final verification.
