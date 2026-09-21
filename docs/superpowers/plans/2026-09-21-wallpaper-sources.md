# 中国大陆壁纸来源与分组调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Wallhaven 移到独立“壁纸”分组，并新增可分页、可缓存、可详情查看和安全下载的彼岸图网与壁纸网 Provider。

**Architecture:** 每个站点由独立的 Provider 和 HTML 解析逻辑负责，遵循现有 `AssetProvider` 协议；公共层只复用 `JsonCache`、`CuratedDownloader`、`DownloadPolicy` 和 `ProviderRegistry`。来源通过 `ProviderPresentation` 声明 `wallpaper/壁纸` 分组，前端继续按描述符渲染，不增加来源 ID 映射表或集中式路由类。

**Tech Stack:** Python 3.10+、`urllib.request`、`html.parser.HTMLParser`、Pillow、pytest、Node.js、jsdom、Prettier。

**Spec:** `docs/superpowers/specs/2026-09-21-wallpaper-sources-design.md`

## Global Constraints

- 只读取公开 HTML 页面和图片地址，不使用登录、验证码绕过或浏览器自动化。
- 图片下载必须通过来源自己的 `DownloadPolicy`，校验 HTTPS、来源主机、图片格式、大小和安全 ID。
- 分页游标只接受来源定义的正整数页码；非法游标返回 `SpiderError`。
- 缓存分别写入 `cache/netbian/`、`cache/bizhi99/`，原图分别写入 `output/ty-node/ty-image-spider/netbian/`、`output/ty-node/ty-image-spider/bizhi99/`。
- Wallhaven 只修改展示分组，保留现有搜索参数、SFW 校验、榜单范围和下载流程。
- 小红书继续隐藏；现有其他 Provider 的接口和分组保持兼容。

## Review Focus

- 页面中的相对图片地址、懒加载属性和 HTML 实体必须解析成可验证的 HTTPS 原图地址；对应 Netbian/Bizhi99 解析测试。
- 详情页缺少尺寸或作者时必须返回空值，不把列表标题伪装成作者；对应详情测试。
- 站点返回跨域图片、非图片地址或重定向到未白名单主机时必须拒绝下载；对应下载策略测试。
- 空关键词、分类切换和上一页/下一页必须生成独立缓存键，不能复用另一分类结果；对应 Provider 搜索测试。
- HTML 结构变化或列表没有有效图片时必须返回可解释错误/空结果，不能让节点启动失败；对应客户端错误测试。

---

### Task 1: 为彼岸图网建立独立 Provider

**Files:**
- Create: `src/ty_image_spider/providers/netbian.py`
- Create: `tests/fixtures/netbian_list.html`
- Create: `tests/fixtures/netbian_detail.html`
- Create: `tests/test_netbian_provider.py`
- Modify: `src/ty_image_spider/bootstrap.py`

**Interfaces:**
- Produces `NetbianProvider`, `NetbianClient`, `NetbianPage` and `_parse_list(markup, base_url)` / `_parse_detail(markup, source_url)` helpers.
- `NetbianProvider.search(SearchRequest) -> SearchPage` uses numeric page cursors and source category paths.
- `NetbianProvider.detail(AssetItem) -> AssetDetail` verifies the item ID and reads the detail page.
- `NetbianProvider.download(AssetItem, Path) -> DownloadResult` delegates to `CuratedDownloader(IMAGE_POLICY)` after validating the source URL.

- [ ] **Step 1: Write failing parser and descriptor tests**

```python
def test_netbian_descriptor_lists_wallpaper_categories(tmp_path):
    descriptor = make_provider(tmp_path).descriptor()
    assert descriptor.id == "netbian"
    assert descriptor.presentation.group_id == "wallpaper"
    assert {field.name for field in descriptor.filters} == {"category"}
    assert {option.value for option in descriptor.filters[0].options} >= {
        "latest", "landscape", "anime", "movie", "mobile"
    }

def test_netbian_search_parses_lazy_image_and_page_cursor(tmp_path):
    provider = make_provider(tmp_path)
    page = provider.search(SearchRequest("netbian", filters={"category": "landscape"}))
    assert page.items[0].preview_url.startswith("https://")
    assert page.items[0].source_url.startswith("https://pic.netbian.com/tupian/")
    assert page.next_cursor == "2"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_netbian_provider.py -q`

Expected: FAIL because `ty_image_spider.providers.netbian` does not exist.

- [ ] **Step 3: Implement the source boundary**

Use a fixed category map such as:

```python
_CATEGORIES = {
    "latest": ("最新", "/new/"),
    "landscape": ("4K风景", "/4kfengjing/"),
    "anime": ("4K动漫", "/4kdongman/"),
    "movie": ("4K剧照", "/4kjuzhao/"),
    "car": ("4K汽车", "/4kqiche/"),
    "animal": ("4K动物", "/4kdongwu/"),
    "background": ("4K背景", "/4kbeijing/"),
    "mobile": ("4K手机", "/shoujibizhi/"),
    "ultrawide": ("5K带鱼屏", "/5120x2160/"),
}
```

`NetbianClient.read_page(category, page)` must construct only `https://pic.netbian.com` URLs, send the project User-Agent, cap response size, and map network/parse failures to `SpiderError("netbian_unavailable"|"netbian_invalid_response", ...)`. The parser must accept `src`, `data-src`, and `data-original`, normalize HTML entities, require an HTTPS `pic.netbian.com` host, derive a stable ID from the detail path, and keep at most 100 valid items. Details must parse the title, original image URL, width/height text when present, and source URL.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_netbian_provider.py -q`

Expected: all Netbian tests pass, including invalid cursor, stale cache, foreign item and unsafe download URL cases.

- [ ] **Step 5: Register the Provider and commit**

Register `NetbianProvider(NetbianClient(), JsonCache(cache / "netbian"), CuratedDownloader(NETBIAN_IMAGE_POLICY))` in `build_services`. Commit:

```bash
git add src/ty_image_spider/providers/netbian.py src/ty_image_spider/bootstrap.py tests/fixtures/netbian_*.html tests/test_netbian_provider.py
git commit -m "feat: add Netbian wallpaper provider"
```

### Task 2: 为壁纸网建立独立 Provider

**Files:**
- Create: `src/ty_image_spider/providers/bizhi99.py`
- Create: `tests/fixtures/bizhi99_list.html`
- Create: `tests/fixtures/bizhi99_detail.html`
- Create: `tests/test_bizhi99_provider.py`
- Modify: `src/ty_image_spider/bootstrap.py`

**Interfaces:**
- Produces `Bizhi99Provider`, `Bizhi99Client`, `Bizhi99Page` and isolated list/detail parsers.
- `Bizhi99Provider.search`, `detail`, and `download` match the `AssetProvider` protocol and never call Netbian code.

- [ ] **Step 1: Write failing tests for categories, pagination, detail and download policy**

```python
def test_bizhi99_search_maps_category_and_page(tmp_path):
    client = FakeClient()
    page = make_provider(tmp_path, client).search(
        SearchRequest("bizhi99", "", {"category": "stars"}, cursor="2")
    )
    assert client.calls == [("/c18/", 2)]
    assert page.items[0].metadata["category"] == "星空壁纸"
    assert page.items[0].source_url.startswith("https://www.bizhi99.com/")
```

- [ ] **Step 2: Run the focused tests and verify the expected import failure**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_bizhi99_provider.py -q`

Expected: FAIL because the Provider module is absent.

- [ ] **Step 3: Implement the source boundary**

Use the fixed map `latest=/zuixin/`, `landscape=/c2/`, `stars=/c18/`, `anime=/c3/`, `background=/c21/`, `pets=/c4/`, `car=/c5/`, `games=/s/470/`, `movie=/s/1842/`, `fresh=/c14/`. `Bizhi99Client` must only request `https://www.bizhi99.com`, reject query-string pagination, parse source-hosted list/detail links, and normalize the static image host only after validating it against the observed allowlist. A page without an accepted image must return a typed invalid-response error. Use `CuratedDownloader(BIZHI99_IMAGE_POLICY)` for the actual file write.

- [ ] **Step 4: Run focused tests, then register the Provider**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_bizhi99_provider.py -q`

Register `Bizhi99Provider(Bizhi99Client(), JsonCache(cache / "bizhi99"), CuratedDownloader(BIZHI99_IMAGE_POLICY))` in `build_services`, then commit:

```bash
git add src/ty_image_spider/providers/bizhi99.py src/ty_image_spider/bootstrap.py tests/fixtures/bizhi99_*.html tests/test_bizhi99_provider.py
git commit -m "feat: add Bizhi99 wallpaper provider"
```

### Task 3: 调整 Wallhaven 分组并锁定来源描述符

**Files:**
- Modify: `src/ty_image_spider/providers/wallhaven.py`
- Modify: `tests/test_wallhaven_provider.py`
- Modify: `tests/fixtures/provider_descriptors.json`
- Modify: `tests/frontend_integration.test.mjs`

**Interfaces:**
- `WallhavenProvider.descriptor().presentation` becomes `ProviderPresentation("wallpaper", "壁纸", "W", "WALLHAVEN", 15, 10, ...)`.
- Existing `_search_parameters`, Wallhaven client, downloader and cache key behavior remain unchanged.

- [ ] **Step 1: Add the failing descriptor assertion**

```python
def test_wallhaven_is_in_wallpaper_group(tmp_path):
    presentation = make_provider(tmp_path).descriptor().presentation
    assert presentation.group_id == "wallpaper"
    assert presentation.group_label == "壁纸"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_wallhaven_provider.py::test_wallhaven_is_in_wallpaper_group -q`

Expected: FAIL because the current group is `inspiration` / `AI 与壁纸`.

- [ ] **Step 3: Change only the presentation values and refresh the descriptor fixture**

Do not change Wallhaven request parameters or download policy. Update the backend fixture and any frontend provider fixture that asserts group labels.

- [ ] **Step 4: Run Wallhaven and descriptor tests**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests/test_wallhaven_provider.py tests/test_provider_presentation.py -q`

Expected: all tests pass and the existing toplist range regression remains green.

### Task 4: 完成来源注册、导航和前端会话回归

**Files:**
- Modify: `tests/fixtures/provider_descriptors.json`
- Modify: `tests/presentation.test.mjs`
- Modify: `tests/frontend_integration.test.mjs`
- Modify: `tests/provider-fixtures.mjs`
- Modify: `README.md`
- Create: `docs/wallpaper-sources.md`

**Interfaces:**
- Backend descriptors for `wallhaven`, `netbian`, and `bizhi99` share `group_id="wallpaper"`, `group_label="壁纸"`, and unique `source_order` values.
- Frontend `sourceGroups` receives the group entirely from descriptors; no provider-specific branch is added.

- [ ] **Step 1: Add failing frontend grouping and session tests**

Add assertions that the rendered group order contains `壁纸`, the group contains `wallhaven`, `netbian`, and `bizhi99`, and switching between the three restores each source's filters, items, and page cursor.

- [ ] **Step 2: Run the focused frontend tests and verify failure**

Run: `npm.cmd test -- --test-name-pattern="壁纸|来源分组|切换素材源"`

Expected: FAIL because the backend fixture does not yet expose the new sources/group.

- [ ] **Step 3: Update fixtures and user documentation**

Regenerate the static descriptor fixture from the backend output, document the two public source URLs, supported categories, download directory, caching behavior, source-page attribution, and that users must confirm image reuse rights.

- [ ] **Step 4: Run frontend tests and formatting**

Run: `npm.cmd test` and `npm.cmd run format:check`.

Expected: all tests pass and Prettier reports every file formatted.

### Task 5: 全量验证、真实只读探测与发布检查

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/compatibility.md` only if the new Provider registration changes installation requirements.
- Modify: `docs/wallpaper-sources.md` with the final observed host allowlists.

- [ ] **Step 1: Run the complete verification suite**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest -q
npm.cmd test
npm.cmd run format:check
git diff --check
```

Expected: 0 failures, 0 formatting errors, and no whitespace errors.

- [ ] **Step 2: Run real read-only probes**

Request only the first list page and one detail page from `https://pic.netbian.com` and `https://www.bizhi99.com`; record status, number of accepted images, page cursor and accepted hostnames. Do not download an image during this probe.

- [ ] **Step 3: Run the release security checks**

Run the existing release/security tests and scan tracked files for API keys, tokens, cookies, private keys and local absolute paths. Confirm the new docs contain source URLs but no local machine paths or credentials.

- [ ] **Step 4: Update changelog and commit the integration**

```bash
git add CHANGELOG.md docs/wallpaper-sources.md docs/compatibility.md tests src web
git commit -m "feat: add mainland wallpaper sources"
```

- [ ] **Step 5: Push only after all evidence is captured**

Run `git status --short --branch` and `git log -1 --oneline`, then push `main`. Report exact test counts, source probe results, and the new commit hash.
