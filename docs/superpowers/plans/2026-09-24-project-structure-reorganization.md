# TY Image Spider 项目结构重构实施计划

> **供自动化执行者使用：** 必须使用 `superpowers:executing-plans`，按任务顺序执行并逐项更新复选框。每个任务完成测试和审查后再进入下一项。

**目标：** 将后端、前端、脚本、测试和文档按职责与业务领域归组，拆分大型模块，清除无运行价值的生成物，同时保持所有产品契约与用户行为不变。

**架构：** 后端采用 `app / api / domain / infrastructure / providers / services` 边界，Provider 再按素材类别归组；前端保留一个 ComfyUI 自动注册入口，其余代码拆成 `app / core / ui / features / styles`。迁移先锁定外部契约，再按依赖方向从领域层向组合根、从基础组件向前端入口推进，最后重组开发资料和清理忽略目录。

**技术栈：** Python 3.10+、aiohttp、Pillow、SQLite、原生 ES Modules、ComfyUI DOM Widget API、Node.js 20.19+/22.12+、jsdom、pytest、Ruff、Mypy、Prettier。

**规格：** `docs/superpowers/specs/2026-09-22-project-structure-reorganization-design.md`

## 全局约束

- ComfyUI 节点类型固定为 `TyImageSpider`，显示名、零输出端口和 `WEB_DIRECTORY="./web"` 不变。
- 24 个 Provider ID、23 个可见来源的分组与顺序不变。
- `/ty-image-spider/*` 路由、JSON 请求响应、工作流状态字段、下载目录和缓存索引格式不变。
- CSS 类名、键盘操作、搜索、分页、详情、缓存与下载行为不变。
- Python 最低版本保持 3.10；Node 验证保持 20.19.0 和 22.12.0。
- 不新增依赖，不更新产品版本，不新增来源，不建立依赖注入框架或事件总线。
- 内部旧模块路径不保留兼容空壳；仓库内引用一次迁移到新路径。
- 每个阶段使用 `git mv` 保留文件历史，阶段提交前必须通过对应测试。
- `.local/tmdb.json` 原地保留，不读取、不移动、不输出、不提交。

## 审查重点

- 旧工作流恢复：保存了来源、筛选、卡片和游标的工作流加载后必须保持来源、分页与提示词状态。
- 模块加载副作用：只有根包与 `web/ty_image_spider.js` 可以注册运行时能力，普通模块导入不得重复注册路由或前端扩展。
- 递归发现：移动后的 Python、JS 和测试文件必须被 Ruff、Mypy、compileall、Node 测试、JS 语法和 Prettier 全部发现。
- 发布包边界：新目录下所有运行时文件必须进入 ZIP，测试、脚本、内部设计、凭据和本机路径必须继续排除。
- Windows 路径与 ComfyUI Junction：根入口必须继续从节点目录加载 `src` 与 `web`，下载位置仍跟随 `folder_paths.get_output_directory()`。

---

### Task 1：递归质量门禁与外部契约基线

**文件：**

- Create: `tests/test_structure_contract.py`
- Modify: `scripts/check_quality.py`
- Modify: `scripts/check_js.mjs`
- Modify: `scripts/test_frontend.mjs`
- Modify: `package.json`
- Modify: `.github/workflows/ci.yml`

**接口：**

- Consumes: 当前 `NODE_CLASS_MAPPINGS`、`ROUTES`、Provider 描述符和工作流序列化行为。
- Produces: `findFiles(root, suffix)` 递归 JS 文件发现；质量脚本递归扫描 `src`、`web`、`tests`、`scripts`；结构迁移期间持续生效的产品契约测试。

- [ ] **Step 1：写产品契约测试**

在 `tests/test_structure_contract.py` 固定节点、路由和来源契约：

```python
from pathlib import Path

from ty_image_spider.bootstrap import build_services
from ty_image_spider.routes import ROUTES


EXPECTED_ROUTES = (
    ("GET", "/ty-image-spider/providers"),
    ("POST", "/ty-image-spider/search"),
    ("POST", "/ty-image-spider/detail"),
    ("POST", "/ty-image-spider/download"),
    ("POST", "/ty-image-spider/download-image"),
    ("POST", "/ty-image-spider/download-page"),
    ("POST", "/ty-image-spider/providers/xiaohongshu/check"),
    ("POST", "/ty-image-spider/providers/xiaohongshu/connect"),
    ("POST", "/ty-image-spider/cache/start"),
    ("GET", "/ty-image-spider/cache/{job_id}"),
    ("POST", "/ty-image-spider/cache/{job_id}/cancel"),
)


def test_public_route_and_provider_contracts_are_stable(tmp_path):
    assert tuple((method, path) for method, path, _ in ROUTES) == EXPECTED_ROUTES
    services = build_services(tmp_path / "output", tmp_path / "cache")
    descriptors = services.providers.descriptors()
    assert len(descriptors) == 24
    assert sum(item.presentation.visible for item in descriptors) == 23
    assert [item.id for item in descriptors] == list(
        __import__("json").loads(
            Path("tests/fixtures/provider_descriptors.json").read_text("utf-8")
        )
    )
```

- [ ] **Step 2：运行基线契约测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_structure_contract.py tests\test_package.py tests\test_node_contract.py tests\test_routes.py tests\test_provider_presentation.py -q
```

Expected: PASS，证明重构前基线可复现。

- [ ] **Step 3：让 JS 启动器递归发现文件**

在 `scripts/test_frontend.mjs` 和 `scripts/check_js.mjs` 使用同一递归函数，跳过 `node_modules`：

```javascript
function findFiles(root, accept) {
  return readdirSync(root, { withFileTypes: true })
    .flatMap((entry) => {
      const path = `${root}/${entry.name}`;
      return entry.isDirectory() ? findFiles(path, accept) : accept(path) ? [path] : [];
    })
    .sort();
}
```

测试入口查找 `tests/**/*.test.mjs`，语法入口查找 `web/**/*.js`。

- [ ] **Step 4：让 Python 质量入口和 CI 覆盖新目录**

保持 Ruff/Mypy/compileall 目标为目录，Prettier 改为：

```text
prettier --check "web/**/*.{js,css,svg}" "tests/**/*.test.mjs"
```

CI 改为调用 `python scripts/check_quality.py` 和 `python scripts/build_release.py --check` 前的现有门禁；本任务暂不移动脚本。

- [ ] **Step 5：运行递归门禁**

Run:

```powershell
npm.cmd test
npm.cmd run format:check
node scripts/check_js.mjs
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_structure_contract.py -q
```

Expected: 全部 PASS。

- [ ] **Step 6：提交**

```powershell
git add .github package.json scripts tests/test_structure_contract.py
git commit -m "test: make quality gates recursive"
```

### Task 2：拆分领域模型与基础设施

**文件：**

- Create: `src/ty_image_spider/domain/__init__.py`
- Create: `src/ty_image_spider/domain/errors.py`
- Create: `src/ty_image_spider/domain/json_types.py`
- Create: `src/ty_image_spider/domain/providers.py`
- Create: `src/ty_image_spider/domain/assets.py`
- Create: `src/ty_image_spider/domain/operations.py`
- Move: `src/ty_image_spider/asset_index.py` -> `src/ty_image_spider/infrastructure/asset_index.py`
- Move: `src/ty_image_spider/cache.py` -> `src/ty_image_spider/infrastructure/cache.py`
- Move: `src/ty_image_spider/diagnostics.py` -> `src/ty_image_spider/infrastructure/diagnostics.py`
- Move: `src/ty_image_spider/downloads.py` -> `src/ty_image_spider/infrastructure/downloads.py`
- Move: `src/ty_image_spider/metadata.py` -> `src/ty_image_spider/infrastructure/metadata.py`
- Move: `src/ty_image_spider/network_retry.py` -> `src/ty_image_spider/infrastructure/network_retry.py`
- Move: `src/ty_image_spider/opencli.py` -> `src/ty_image_spider/infrastructure/opencli.py`
- Move: `src/ty_image_spider/security.py` -> `src/ty_image_spider/infrastructure/security.py`
- Delete: `src/ty_image_spider/models.py`
- Modify: all Python imports in `src/` and `tests/`

**接口：**

- Consumes: 当前模型字段、`to_dict()`、`AssetItem.from_untrusted()` 和 `SpiderError` 构造参数。
- Produces: `ty_image_spider.domain` 统一重导出原模型名；`ty_image_spider.infrastructure.*` 提供原基础设施行为。

- [ ] **Step 1：补领域模块独立性测试**

在 `tests/test_models.py` 增加：

```python
def test_domain_package_does_not_import_runtime_adapters():
    import sys
    import ty_image_spider.domain

    assert "folder_paths" not in sys.modules
    assert "server" not in sys.modules
    assert ty_image_spider.domain.AssetItem(provider="local", id="1").id == "1"
```

- [ ] **Step 2：运行测试确认缺少新包**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_models.py::test_domain_package_does_not_import_runtime_adapters -q`

Expected: FAIL with `ModuleNotFoundError: ty_image_spider.domain`。

- [ ] **Step 3：按类型拆分模型并由 `domain/__init__.py` 重导出**

拆分映射固定为：

```text
errors.py      -> SpiderError
json_types.py  -> JsonValue
providers.py   -> FilterOption, FilterField, ProviderCapabilities,
                  ProviderPresentation, ProviderDescriptor, ProviderStatus
assets.py      -> AssetItem, AssetDetail
operations.py  -> SearchRequest, SearchPage, DownloadResult
```

`domain/__init__.py` 显式导入并在 `__all__` 中列出上述名称。复制实现时保持字段顺序、默认值、验证和序列化字节语义不变。

- [ ] **Step 4：移动基础设施并更新相对导入**

使用 `git mv` 移动八个模块，创建 `infrastructure/__init__.py`。所有模块从 `..domain` 或具体领域文件导入；仓库内所有 `ty_image_spider.models`、`.cache`、`.security` 等导入更新为新路径。

- [ ] **Step 5：删除旧 `models.py` 并验证无旧导入**

Run:

```powershell
rg -n "ty_image_spider\.(models|asset_index|cache|diagnostics|downloads|metadata|network_retry|opencli|security)|from \.(models|asset_index|cache|diagnostics|downloads|metadata|network_retry|opencli|security)" src tests
```

Expected: 无匹配。

- [ ] **Step 6：运行领域与基础设施测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_models.py tests\test_asset_index.py tests\test_cache.py tests\test_cache_threads.py tests\test_downloads.py tests\test_metadata.py tests\test_network_retry.py tests\test_opencli.py tests\test_security.py -q
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m compileall -q src
```

Expected: PASS。

- [ ] **Step 7：提交**

```powershell
git add src tests
git commit -m "refactor: separate domain and infrastructure"
```

### Task 3：拆分应用组合根与 API 路由

**文件：**

- Move: `src/ty_image_spider/nodes.py` -> `src/ty_image_spider/app/node.py`
- Create: `src/ty_image_spider/app/services.py`
- Create: `src/ty_image_spider/app/provider_factories.py`
- Create: `src/ty_image_spider/app/bootstrap.py`
- Delete: `src/ty_image_spider/bootstrap.py`
- Move: `src/ty_image_spider/http_json.py` -> `src/ty_image_spider/api/json_body.py`
- Create: `src/ty_image_spider/api/responses.py`
- Create: `src/ty_image_spider/api/service_locator.py`
- Create: `src/ty_image_spider/api/handlers.py`
- Create: `src/ty_image_spider/api/registration.py`
- Delete: `src/ty_image_spider/routes.py`
- Modify: `src/ty_image_spider/__init__.py`
- Modify: route, bootstrap, package and node tests

**接口：**

- Consumes: `ApplicationServices`, `build_services(output_root, cache_root)`, route handler call signatures and `ROUTES` tuple。
- Produces: 相同名称从 `ty_image_spider.app` 与 `ty_image_spider.api` 导出；根包继续只导出 ComfyUI 三个常量并执行一次 `register_routes()`。

- [ ] **Step 1：补重复导入与组合根测试**

在 `tests/test_structure_contract.py` 增加：

```python
def test_runtime_entrypoints_are_idempotent():
    from ty_image_spider.api import ROUTES, register_routes
    from ty_image_spider.app import TyImageSpider, build_services

    assert len(ROUTES) == 11
    assert register_routes() in {True, False}
    assert TyImageSpider.FUNCTION == "browse"
    assert callable(build_services)
```

- [ ] **Step 2：运行测试确认新入口不存在**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_structure_contract.py::test_runtime_entrypoints_are_idempotent -q`

Expected: FAIL with missing `ty_image_spider.api` or `app` export。

- [ ] **Step 3：拆分应用层**

`app/services.py` 只保留 `ApplicationServices`；`app/provider_factories.py` 提供以下纯构造函数：

```python
def register_wallpaper_providers(registry, cache_root): ...
def register_editorial_providers(registry, cache_root): ...
def register_movie_providers(registry, cache_root): ...
def register_collection_providers(registry, cache_root): ...
def register_optional_providers(registry, cache_root, browser_lock): ...
```

`app/bootstrap.py` 创建共享索引、注册表和服务，再调用这些函数；任何工厂不持有状态或调用搜索业务。

- [ ] **Step 4：拆分 API 层**

职责固定为：

```text
json_body.py       -> JsonBodyReader
responses.py       -> success, error, unexpected_error, safe_text, safe_json
service_locator.py -> get_services 及线程安全惰性单例
handlers.py        -> 11 个 aiohttp handler 与 execute_payload/respond
registration.py    -> ROUTES 与 register_routes
```

`api/__init__.py` 重导出测试和根入口需要的稳定名称。

- [ ] **Step 5：更新根入口和仓库内引用**

根包改为：

```python
from .api import register_routes
from .app import TyImageSpider

NODE_CLASS_MAPPINGS = {"TyImageSpider": TyImageSpider}
NODE_DISPLAY_NAME_MAPPINGS = {"TyImageSpider": "TY Image Spider · 素材浏览"}
WEB_DIRECTORY = "./web"
register_routes()
```

删除旧 `bootstrap.py`、`nodes.py`、`routes.py` 和 `http_json.py`，更新测试导入。

- [ ] **Step 6：运行应用与 API 测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_bootstrap.py tests\test_http_json.py tests\test_node_contract.py tests\test_package.py tests\test_routes.py tests\test_structure_contract.py -q
```

Expected: PASS，路由与 Provider 顺序不变。

- [ ] **Step 7：提交**

```powershell
git add src tests
git commit -m "refactor: separate app and api adapters"
```

### Task 4：归组共享、编辑、电影、本地与小型馆藏 Provider

**文件：**

- Create package directories under `src/ty_image_spider/providers/{shared,editorial,collections,movies,local}/`
- Move shared modules: `base.py`, `registry.py`, `download_policy.py`, `image_readers.py`, `public_json_client.py`, `curated_client.py`, `curated_download.py`
- Move editorial modules: `arena.py`, `behance.py`, `behance_projects.py`, `editorial.py`, `editorial_images.py`, `editorial_sources.py`
- Move collection modules: `artic.py`, `cleveland.py`, `loc.py`, `museum_assets.py`, `museum_client.py`, `nasa.py`, `vam.py`
- Move movie modules: `film_catalog.py`, `filmgrab.py`, `filmgrab_articles.py`, `tmdb_images.py`
- Move local module: `local.py` -> `local/provider.py`
- Modify: imports in `src/` and `tests/`

**接口：**

- Consumes: 当前类名、Provider ID 和模块行为。
- Produces: 类名从类别包显式导出；组合根只依赖类别包公开名称，不穿透解析器私有模块。

- [ ] **Step 1：添加类别包公开接口测试**

在 `tests/test_structure_contract.py` 增加对以下导出的导入断言：

```python
from ty_image_spider.providers.collections import ArticProvider, NasaProvider
from ty_image_spider.providers.editorial import ArenaProvider, BehanceProvider
from ty_image_spider.providers.local import LocalProvider
from ty_image_spider.providers.movies import FilmGrabProvider, TmdbImageProvider
from ty_image_spider.providers.shared import ProviderRegistry, PublicJsonClient
```

- [ ] **Step 2：运行测试确认类别包不存在**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_structure_contract.py -q`

Expected: FAIL with missing category package exports。

- [ ] **Step 3：使用 `git mv` 归组模块并创建显式 `__init__.py`**

每个 `__init__.py` 只重导出组合根和测试需要的公共类；解析函数不从类别包根导出。更新包内相对导入，禁止类别间反向依赖。

- [ ] **Step 4：更新组合工厂和测试导入**

Run:

```powershell
rg -n "providers\.(arena|artic|base|behance|cleveland|curated_|download_policy|editorial|film|image_readers|loc|local|museum|nasa|public_json_client|registry|tmdb_images|vam)" src tests
```

Expected: 只允许新类别路径，不再匹配旧平铺模块。

- [ ] **Step 5：运行相关测试与完整 Provider 注册测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_behance_projects.py tests\test_curated_download.py tests\test_curated_providers.py tests\test_editorial_sources.py tests\test_loc_provider.py tests\test_local_provider.py tests\test_museum_client.py tests\test_museum_providers.py tests\test_nasa_provider.py tests\test_tmdb_images_provider.py tests\test_bootstrap.py tests\test_structure_contract.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add src tests
git commit -m "refactor: group providers by source domain"
```

### Task 5：拆分 AI 与壁纸 Provider

**文件：**

- Create: `src/ty_image_spider/providers/ai/civitai/{__init__,provider,client,normalizer}.py`
- Create: `src/ty_image_spider/providers/ai/xiaohongshu/{__init__,provider,extract,cache_codec}.py`
- Create: `src/ty_image_spider/providers/wallpapers/wallhaven/{__init__,provider,client,normalizer,download}.py`
- Create: `src/ty_image_spider/providers/wallpapers/netbian/{__init__,provider,client,parser}.py`
- Create: `src/ty_image_spider/providers/wallpapers/bizhi99/{__init__,provider,client,parser}.py`
- Create: `src/ty_image_spider/providers/wallpapers/wallpaperscraft/{__init__,provider,client,parser}.py`
- Delete: original flat AI and wallpaper modules after migration
- Modify: composition imports and related tests

**接口：**

- Consumes: existing Provider constructors, client classes, download policies, parsers and normalizers。
- Produces: each source package exports only its Provider, injected client and image policy needed by composition/tests。

- [ ] **Step 1：添加静态职责边界测试**

在 `tests/test_structure_contract.py` 增加：

```python
def test_large_provider_packages_have_separate_adapters():
    root = Path("src/ty_image_spider/providers")
    for relative in (
        "ai/civitai/client.py",
        "ai/civitai/normalizer.py",
        "ai/xiaohongshu/extract.py",
        "wallpapers/wallhaven/client.py",
        "wallpapers/netbian/parser.py",
        "wallpapers/bizhi99/parser.py",
        "wallpapers/wallpaperscraft/parser.py",
    ):
        assert (root / relative).is_file(), relative
```

- [ ] **Step 2：运行测试确认目标文件不存在**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_structure_contract.py::test_large_provider_packages_have_separate_adapters -q`

Expected: FAIL on first missing path。

- [ ] **Step 3：拆 Civitai 与小红书**

固定职责：Civitai 的请求和页面元数据读取放 `client.py`，字段转换和提示词分类放 `normalizer.py`，筛选/缓存/用例编排放 `provider.py`；小红书的 OpenCLI 交互编排放 `provider.py`，浏览器数据提取放 `extract.py`，持久页编码与缓存 key 放 `cache_codec.py`。

- [ ] **Step 4：拆四个壁纸来源**

HTML 来源的网络请求只放 `client.py`，HTMLParser 与纯解析函数只放 `parser.py`；Wallhaven JSON 转换放 `normalizer.py`，原图读取放 `download.py`。每个 `provider.py` 保留描述符、请求参数和搜索/详情/下载编排。

- [ ] **Step 5：验证文件边界与旧模块清除**

Run:

```powershell
rg -n "urlopen|HTTPParser|HTMLParser" src\ty_image_spider\providers\ai\*\provider.py src\ty_image_spider\providers\wallpapers\*\provider.py
rg -n "providers\.(civitai|xiaohongshu|wallhaven|netbian|bizhi99|wallpaperscraft)" src tests
```

Expected: Provider 中无直接 HTML 解析器或 `urlopen`；旧平铺导入无匹配。

- [ ] **Step 6：运行 AI 与壁纸专项测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_civitai_client.py tests\test_civitai_provider.py tests\test_opencli.py tests\test_opencli_connect.py tests\test_xiaohongshu_extract.py tests\test_xiaohongshu_provider.py tests\test_wallhaven_client.py tests\test_wallhaven_download.py tests\test_wallhaven_provider.py tests\test_netbian_provider.py tests\test_bizhi99_provider.py tests\test_wallpaperscraft_provider.py tests\test_bootstrap.py tests\test_structure_contract.py -q
```

Expected: PASS。

- [ ] **Step 7：提交**

```powershell
git add src tests
git commit -m "refactor: split ai and wallpaper providers"
```

### Task 6：拆分 Commons、The Met 与电影解析模块

**文件：**

- Create: `src/ty_image_spider/providers/collections/commons/{__init__,provider,client,normalizer}.py`
- Create: `src/ty_image_spider/providers/collections/met/{__init__,provider,client,normalizer}.py`
- Create: `src/ty_image_spider/providers/movies/filmgrab/{__init__,provider,catalog,articles}.py`
- Create: `src/ty_image_spider/providers/movies/tmdb_images/{__init__,provider,normalizer}.py`
- Delete: superseded flat modules
- Modify: composition imports and related tests

**接口：**

- Consumes: current `CommonsClient`, `CommonsProvider`, `MetClient`, `MetProvider`, `FilmGrabProvider`, `TmdbImageProvider` signatures。
- Produces: unchanged public class names from source package roots; network clients and pure normalizers separately testable。

- [ ] **Step 1：补纯标准化模块测试入口**

将 Commons 与 The Met fixture 转换断言分别改为直接导入：

```python
from ty_image_spider.providers.collections.commons.normalizer import normalize_file
from ty_image_spider.providers.collections.met.normalizer import normalize_artwork
```

断言原有 `ROW`、`OBJECT` 转换出的 ID、作者、许可和原图完全一致。

- [ ] **Step 2：运行测试确认新模块不存在**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_commons_provider.py tests\test_met_provider.py -q`

Expected: collection errors for missing modules。

- [ ] **Step 3：拆分两个馆藏来源**

Commons `client.py` 只负责 MediaWiki 参数、游标和 HTTP；`normalizer.py` 负责格式白名单、许可和素材字段。The Met `client.py` 保留搜索、单件和 6 路有序批量读取；`normalizer.py` 负责公共领域与图片域名过滤。

- [ ] **Step 4：归并电影 Provider 的相邻文件**

FilmGrab 现有 catalog/articles 文件移入其来源子包；TMDB 图片的响应转换抽到 `normalizer.py`。中文电影身份解析继续保留在顶层 `movies/`，因为 FilmGrab 与 TMDB 图片共同使用它。

- [ ] **Step 5：运行专项与组合测试**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\test_commons_provider.py tests\test_met_provider.py tests\test_filmgrab_client.py tests\test_curated_providers.py tests\test_tmdb_images_provider.py tests\test_movie_matching.py tests\test_movie_resolution.py tests\test_bootstrap.py -q
```

Expected: PASS；The Met 并发顺序测试仍通过。

- [ ] **Step 6：提交**

```powershell
git add src tests
git commit -m "refactor: split collection and movie providers"
```

### Task 7：重组前端基础模块与独立功能

**文件：**

- Move: `web/api.js` -> `web/core/api.js`
- Move: `web/state.js` -> `web/core/state.js`
- Move: `web/presentation.js` -> `web/core/presentation.js`
- Create: `web/core/dom.js`
- Move: `web/cache_tasks.js` -> `web/features/cache/tasks.js`
- Move: `web/movie_picker.js`, `movie_search.js`, `tmdb_help.js` -> `web/features/movie/`
- Move: `web/preview_actions.js`, `preview_isolation.js` -> `web/features/preview/`
- Move: `web/collection_detail.js`, `editorial_detail.js` -> `web/features/detail/`
- Move: `web/icons.js` -> `web/ui/icons.js`
- Move: `web/image_viewer.js` -> `web/ui/image_viewer.js`
- Move: `web/tmdb-logo.svg` -> `web/assets/tmdb-logo.svg`
- Modify: JS imports and frontend tests

**接口：**

- Consumes: existing named exports and DOM behavior。
- Produces: identical named exports at new paths; shared `element(document, tag, className, text)` from `core/dom.js`。

- [ ] **Step 1：增加无副作用模块导入测试**

创建 `tests/frontend/module_boundaries.test.mjs`：

```javascript
import test from "node:test";
import assert from "node:assert/strict";

test("前端子模块导入不会自动注册 ComfyUI 扩展", async () => {
  globalThis.window = {};
  await import("../../web/core/state.js");
  await import("../../web/features/cache/tasks.js");
  assert.equal(window.__TY_IMAGE_SPIDER_REGISTERED__, undefined);
  delete globalThis.window;
});
```

- [ ] **Step 2：运行测试确认新路径不存在**

Run: `node --test tests/frontend/module_boundaries.test.mjs`

Expected: FAIL with module not found。

- [ ] **Step 3：移动内聚模块并统一 DOM 小工具**

使用 `git mv` 保留历史。将重复的 `element()` 小工具逐步替换为 `core/dom.js` 导入；保留需要特殊行为的局部构造函数，不建立通用组件框架。

- [ ] **Step 4：更新所有前端与测试相对导入**

Run:

```powershell
rg -n 'from "\.\/(api|state|presentation|cache_tasks|movie_|tmdb_help|preview_|collection_detail|editorial_detail|icons|image_viewer)' web tests
```

Expected: 无旧根级导入。

- [ ] **Step 5：运行前端测试和递归语法检查**

Run:

```powershell
npm.cmd test
node scripts/check_js.mjs
```

Expected: 现有 83 项及新增边界测试全部 PASS。

- [ ] **Step 6：提交**

```powershell
git add web tests
git commit -m "refactor: group frontend modules by responsibility"
```

### Task 8：拆分前端控制器、控件和详情弹窗

**文件：**

- Create: `web/app/extension.js`
- Create: `web/app/lifecycle.js`
- Create: `web/app/workspace.js`
- Create: `web/app/search_controller.js`
- Create: `web/app/download_controller.js`
- Create: `web/app/render_controller.js`
- Modify: `web/ty_image_spider.js`
- Create: `web/ui/source_controls/{index,navigation,search,filters}.js`
- Create: `web/ui/gallery/{index,toolbar,card,states}.js`
- Create: `web/ui/dialog/{index,shell,facts,source_details,actions}.js`
- Delete: old `web/source_controls.js`, `web/gallery.js`, `web/dialog.js`
- Modify: frontend tests

**接口：**

- Consumes: `createImageSpiderExtension`, `renderSourceControls`, `createGallery`, `openAssetDialog` public functions。
- Produces: same public functions from new package `index.js` files; root `ty_image_spider.js` only imports and auto-registers extension。

- [ ] **Step 1：添加入口职责测试**

在 `tests/frontend/module_boundaries.test.mjs` 增加：

```javascript
test("根前端入口只组合扩展并保留导出", async () => {
  globalThis.window = { __TY_IMAGE_SPIDER_DISABLE_AUTO_REGISTER__: true };
  const entry = await import("../../web/ty_image_spider.js");
  assert.equal(typeof entry.createImageSpiderExtension, "function");
  delete globalThis.window;
});
```

并在 Python 结构测试断言 `web/ty_image_spider.js` 不超过 40 行。

- [ ] **Step 2：拆分节点生命周期和用例控制器**

`extension.js` 只定义扩展对象；`lifecycle.js` 只包装 `onNodeCreated/onConfigure/onRemoved`；`workspace.js` 创建 DOM 与控制器依赖；搜索、下载和渲染行为分别移入对应控制器。控制器通过回调协作，不使用全局事件总线。

- [ ] **Step 3：拆分来源控件、画廊和弹窗**

每个 `index.js` 保留旧公共工厂签名。导航/搜索/筛选、工具栏/卡片/状态、弹窗外壳/事实/来源详情/动作分别独立；现有测试只更新导入路径，断言和 DOM 选择器保持不变。

- [ ] **Step 4：运行前端集成与专项测试**

Run:

```powershell
node --test tests\frontend\module_boundaries.test.mjs tests\frontend_integration.test.mjs tests\source_controls.test.mjs tests\gallery.test.mjs tests\dialog.test.mjs tests\image_viewer.test.mjs
npm.cmd test
```

Expected: PASS，首次加载、竞态、恢复、分页、提示词、详情、下载和键盘操作全部保持。

- [ ] **Step 5：提交**

```powershell
git add web tests
git commit -m "refactor: split frontend workspace controllers"
```

### Task 9：拆分 CSS 并保持视觉契约

**文件：**

- Create: `web/styles/tokens.css`
- Create: `web/styles/workspace.css`
- Create: `web/styles/controls.css`
- Create: `web/styles/gallery.css`
- Create: `web/styles/dialog.css`
- Create: `web/styles/viewer.css`
- Modify: `web/ty_image_spider.css`
- Create: `tests/frontend/styles.test.mjs`

**接口：**

- Consumes: all current `.tyis-*` selectors and one stylesheet URL loaded by `ensureStyles()`。
- Produces: `ty_image_spider.css` as import-only entry; unchanged selector set across six responsibility files。

- [ ] **Step 1：写 CSS 选择器保留测试**

测试递归读取新 CSS，并确认关键选择器至少保留一处定义：

```javascript
for (const selector of [
  ".tyis-workspace",
  ".tyis-source-groups",
  ".tyis-grid",
  ".tyis-dialog",
  ".tyis-image-viewer",
]) {
  assert.equal((combined.match(new RegExp(selector.replace(".", "\\."), "g")) || []).length >= 1, true);
}
```

同时断言入口精确包含六条 `@import`，不包含样式规则。

- [ ] **Step 2：运行测试确认样式目录不存在**

Run: `node --test tests/frontend/styles.test.mjs`

Expected: FAIL with missing files。

- [ ] **Step 3：按区域移动现有规则**

保持规则顺序在各自文件内不变。媒体查询放到其主要影响的区域文件；跨区域基础规则放 `tokens.css` 或 `workspace.css`。入口只写相对 `@import`。

- [ ] **Step 4：运行格式、前端和选择器测试**

Run:

```powershell
node --test tests\frontend\styles.test.mjs
npm.cmd run format:check
npm.cmd test
```

Expected: PASS；CSS 类名无删除，JS 测试全部通过。

- [ ] **Step 5：提交**

```powershell
git add web tests/frontend/styles.test.mjs
git commit -m "refactor: split frontend styles by surface"
```

### Task 10：重组测试、脚本和用户文档

**文件：**

- Move Python tests into `tests/backend/{app,api,domain,infrastructure,providers,services}/`
- Move JS tests into `tests/frontend/`
- Keep: `tests/fixtures/`
- Move: `tests/test_release.py` -> `tests/release/test_build_release.py`
- Move: `scripts/check_quality.py`, `check_js.mjs`, `test_frontend.mjs` -> `scripts/quality/`
- Move: `scripts/build_release.py` -> `scripts/release/build.py`
- Move user docs into `docs/guides/` and `docs/sources/`
- Modify: `pyproject.toml`, `package.json`, CI, README, CHANGELOG, CONTRIBUTING, THIRD_PARTY_NOTICES and release whitelist

**接口：**

- Consumes: recursive discovery from Task 1 and current release whitelist。
- Produces: organized development tree; all commands and links point to one canonical file path。

- [ ] **Step 1：写仓库链接与结构测试**

创建 `tests/release/test_repository_layout.py`，检查：

```python
def test_repository_uses_organized_development_paths():
    for path in (
        "scripts/quality/check.py",
        "scripts/quality/check_js.mjs",
        "scripts/quality/test_frontend.mjs",
        "scripts/release/build.py",
        "docs/guides/compatibility.md",
        "docs/sources/museum.md",
    ):
        assert Path(path).is_file(), path
```

再遍历仓库内 Markdown 链接，解析不含协议和锚点的相对路径，断言目标存在。

- [ ] **Step 2：运行测试确认目标布局不存在**

Run: `E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest tests\release\test_repository_layout.py -q`

Expected: FAIL on missing organized paths。

- [ ] **Step 3：移动测试并更新导入 fixture 路径**

分类规则：节点/组合根放 `app`，路由/JSON 放 `api`，模型放 `domain`，缓存/下载/网络/安全放 `infrastructure`，所有来源测试放 `providers`，缓存任务与搜索下载服务放 `services`。Pytest `testpaths=["tests"]` 保持递归发现。

- [ ] **Step 4：移动质量与发布脚本**

重命名 `check_quality.py` 为 `scripts/quality/check.py`。脚本的 `ROOT` 从 `parents[1]` 改为 `parents[2]`；发布脚本同理。更新 package scripts、CI、CONTRIBUTING 和测试动态导入路径。

- [ ] **Step 5：移动用户文档并更新所有链接与发布白名单**

映射固定为：

```text
docs/compatibility.md            -> docs/guides/compatibility.md
docs/curated-sources-cache.md    -> docs/guides/cache.md
docs/tmdb-movie-mapping.md       -> docs/guides/tmdb.md
docs/editorial-sources.md        -> docs/sources/editorial.md
docs/loc-source.md               -> docs/sources/loc.md
docs/museum-sources.md           -> docs/sources/museum.md
docs/nasa-source.md              -> docs/sources/nasa.md
docs/source-rights.md            -> 保持原位
```

`scripts/release/build.py` 的 `USER_DOCS` 精确列出新路径。

- [ ] **Step 6：运行完整测试发现、链接和发布检查**

Run:

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -m pytest -q
npm.cmd test
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe scripts\release\build.py --check
```

Expected: Python 与前端测试数量不低于迁移前的 306/83；链接测试 PASS；发布检查 PASS。

- [ ] **Step 7：提交**

```powershell
git add .github CHANGELOG.md CONTRIBUTING.md README.md THIRD_PARTY_NOTICES.md docs package.json pyproject.toml scripts tests
git commit -m "refactor: organize tests scripts and user docs"
```

### Task 11：删除内部历史文档与本地生成物

**文件：**

- Delete tracked: `docs/superpowers/`
- Delete ignored: `.artifacts/`, `dist/`, `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, all `__pycache__/`
- Delete ignored: all `.local/*` except `.local/tmdb.json`
- Modify: `.gitignore`
- Modify: `CHANGELOG.md`

**接口：**

- Consumes: user-approved destructive cleanup scope and Git history containing all tracked design documents。
- Produces: clean source checkout with regenerable output directories absent; `.local/tmdb.json` preserved byte-for-byte。

- [ ] **Step 1：记录清理前安全断言，不读取令牌**

Run:

```powershell
$repoRoot = (Resolve-Path '.').Path
$targets = @('.artifacts','dist','.cache','.pytest_cache','.mypy_cache','.ruff_cache','docs\superpowers')
$targets | ForEach-Object {
  $resolved = [IO.Path]::GetFullPath((Join-Path $repoRoot $_))
  if (-not $resolved.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) { throw "目标越界：$_" }
}
$tmdbExists = Test-Path -LiteralPath '.local\tmdb.json'
```

Expected: 所有解析路径都位于仓库内；只记录 TMDB 文件是否存在，不读取内容。

- [ ] **Step 2：删除 Git 跟踪的内部历史文档**

Run: `git rm -r docs\superpowers`

Expected: 设计、计划和验收历史进入删除状态，可从 Git 提交恢复。

- [ ] **Step 3：删除已确认的忽略目录**

使用同一个 PowerShell 进程与 `-LiteralPath` 删除经过 Step 1 验证的目标：

```powershell
$targets | ForEach-Object {
  if (Test-Path -LiteralPath $_) { Remove-Item -LiteralPath $_ -Recurse -Force }
}
Get-ChildItem -LiteralPath . -Directory -Recurse -Force -Filter '__pycache__' |
  Sort-Object FullName -Descending |
  Remove-Item -Recurse -Force
```

- [ ] **Step 4：清理 `.local` 并保留 TMDB 配置**

```powershell
if (Test-Path -LiteralPath '.local') {
  Get-ChildItem -LiteralPath '.local' -Force |
    Where-Object { $_.Name -ne 'tmdb.json' } |
    Remove-Item -Recurse -Force
}
if ($tmdbExists -and -not (Test-Path -LiteralPath '.local\tmdb.json')) {
  throw 'TMDB 配置被误删'
}
```

- [ ] **Step 5：更新说明并提交跟踪文件清理**

在 CHANGELOG 未发布部分说明项目结构和开发命令迁移，不列出本机路径。确认 `.gitignore` 继续忽略生成目录和 `.local/`。

```powershell
git add .gitignore CHANGELOG.md docs
git commit -m "chore: remove obsolete internal project artifacts"
```

### Task 12：全量验证、可复现发布和 ComfyUI 冒烟

**文件：**

- Modify only if checks reveal defects: owning module/test/document
- Generate temporarily: `dist/verify-a`, `dist/verify-b`，验证后删除

**接口：**

- Consumes: final organized tree and all preserved product contracts。
- Produces: repeatable verification evidence; clean worktree; no generated artifacts retained。

- [ ] **Step 1：运行完整质量入口**

优先使用已安装开发工具的 Python；若便携 Python 缺 Ruff/Mypy，使用仓库既有开发环境执行同一脚本：

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe scripts\quality\check.py
```

Expected: Ruff、Ruff format、Mypy、pytest、Node tests、Prettier、JS syntax、compileall、Git diff checks 全部 PASS。若该解释器缺工具，明确记录并分别运行所有可用门禁，不把缺工具报告为通过。

- [ ] **Step 2：验证可复现发布包**

```powershell
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe scripts\release\build.py --check
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe scripts\release\build.py --output dist\verify-a
E:\ComfyUI_windows_portable-G314\python_embeded\python.exe scripts\release\build.py --output dist\verify-b
Compare-Object (Get-Content dist\verify-a\*.sha256) (Get-Content dist\verify-b\*.sha256)
```

Expected: `Compare-Object` 无输出；ZIP 包含新 `src`、`web` 和用户文档路径，不含 tests/scripts/internal docs/local paths。

- [ ] **Step 3：删除验证生成物并检查仓库结构**

先解析确认 `dist` 位于仓库内，再删除整个 `dist`。运行：

```powershell
rg --files src web scripts tests docs
git status --short
git diff --check
git diff --cached --check
```

Expected: `.artifacts`、`dist`、`docs/superpowers`、各类缓存和 `__pycache__` 不存在；`.local` 最多只含 `tmdb.json`；没有旧平铺模块。

- [ ] **Step 4：验证 ComfyUI 根入口与 24 个 Provider**

Run:

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
from ty_image_spider.app import build_services

services = build_services(Path('.verify/output'), Path('.verify/cache'))
descriptors = services.providers.descriptors()
assert len(descriptors) == 24
assert sum(item.presentation.visible for item in descriptors) == 23
print('providers=24 visible=23')
'@ | E:\ComfyUI_windows_portable-G314\python_embeded\python.exe -
```

Expected: `providers=24 visible=23`。随后删除仓库内 `.verify`。

- [ ] **Step 5：重启 ComfyUI 并执行页面冒烟**

在确认队列空闲后重启 8188，强制刷新浏览器。验证：节点首次加载有组件；两级来源导航可用；任选来源搜索和上下页；详情全屏可滚轮缩放、拖拽和左右切图；向下键保存一张图片并显示 `<ComfyUI>/output/ty-node/ty-image-spider/...` 完整路径。不得读取或显示 `.local/tmdb.json` 内容。

- [ ] **Step 6：最终提交与审查**

若验证产生修复，提交：

```powershell
git add src web scripts tests docs README.md CHANGELOG.md CONTRIBUTING.md package.json pyproject.toml .github
git commit -m "refactor: complete project structure reorganization"
```

然后运行 `git status --short --branch`，确认工作树干净；审查从 `af76882^` 到 HEAD 的完整差异，重点检查未误删运行时文件、旧路径残留、凭据和本机绝对路径。
