# TY Image Spider 2.5 加固设计规格

## 1. 背景与目标

TY Image Spider 2.4.0 已经具备多来源搜索、分页、详情、下载、后台缓存、工作流隔离和实机验证能力。本轮不再扩充素材源，而是把现有实现加固为适合公开发布、便于第三方安装和后续维护的 2.5.0。

本轮成功标准如下：

- 新增一个来源时，来源分组、短标记、详情名称和下载约束由该来源的描述或策略提供，前后端不再同步维护多份来源映射。
- 不同节点、不同搜索条件的缓存任务互不覆盖；相同任务不会重复启动，并发数量受控。
- 所有 JSON 写入路由都有统一的 1 MiB 请求体上限，包括没有 `Content-Length` 的分块请求。
- Windows 与 Linux 上的 Python 3.10、3.13，以及 Node 20、22 都有自动检查。
- 仓库包含明确许可证、贡献流程、安全报告方式、素材权利边界和兼容矩阵。
- 发布包由脚本从受控文件清单生成，自动排除本地凭据、缓存和开发产物，并输出 SHA256。
- 现有 2.4.0 的搜索、详情、下载、缓存和纯浏览零输出节点行为保持兼容。

## 2. 范围与非目标

本轮包含：

1. Provider 展示元数据归位。
2. Provider 下载策略拆分。
3. 多缓存任务隔离与资源上限。
4. HTTP JSON 请求体限制。
5. 外部来源请求的统一诊断边界。
6. GitHub CI、兼容矩阵与发布脚本。
7. MIT 许可证、贡献、安全、行为准则和素材权利文档。
8. 自动测试、ComfyUI 8188 实机回归、版本提交、标签与分发包。

本轮不包含运行时动态插件发现、第三方 Provider SDK、数据库迁移框架、账号系统、遥测、自动上传 GitHub Release，也不恢复前端已隐藏的小红书入口。这些能力没有当前需求，加入后会扩大维护面。

## 3. 方案选择

### 3.1 推荐方案：扩展现有契约并组合小策略

保留 `AssetProvider`、`ProviderRegistry`、应用服务和 `bootstrap.py` 组合根。给 `ProviderDescriptor` 增加展示元数据；把下载的域名、ID 和 URL 编码差异拆成不可变 `DownloadPolicy`；把缓存任务改为独立上下文映射。

优点是延续现有架构，迁移范围可控，每个新边界都能单独测试。缺点是现有 Provider 构造代码需要一次机械迁移。

### 3.2 备选方案：集中式来源清单

建立一个包含展示、搜索、下载和缓存配置的大型来源清单，所有模块从清单查询。它减少短期重复，但会让来源专属行为持续聚集到中心文件，形成新的大管家，不符合本项目的单一职责要求，因此不采用。

### 3.3 备选方案：动态插件系统

通过入口点或目录扫描动态加载 Provider。它适合稳定 SDK 和第三方生态，但当前 Provider 契约仍在演进，动态发现还会引入版本协商、故障隔离和依赖管理。本轮不采用。

## 4. Provider 展示元数据

`ProviderDescriptor` 增加不可变的展示字段：

```python
@dataclass(frozen=True, slots=True)
class ProviderPresentation:
    group_id: str
    group_label: str
    short_label: str
    detail_label: str
    cache_description: str = ""
    visible: bool = True
```

`ProviderDescriptor` 通过 `presentation` 字段持有它。字段职责如下：

- `group_id`：稳定的机器标识，用于前端分组和排序。
- `group_label`：用户可见的中文分组名。
- `short_label`：缩略图角标，长度建议不超过 8 个字符。
- `detail_label`：详情页来源名。
- `cache_description`：该来源缓存按钮附近的简短说明。
- `visible`：是否出现在前端来源导航；小红书保持 `false`，后端兼容代码仍注册。

前端只根据 `/providers` 返回的描述符分组、显示来源、生成缩略图角标和详情名。`source_controls.js`、`gallery.js`、`dialog.js` 中的来源映射删除。前端对缺失新字段保留兼容回退：分组归入“其他”，短标记与详情名使用 `label`，确保旧缓存的描述符不会导致空白界面。

分组顺序不依赖 Provider 注册顺序。描述符同时提供 `group_order` 与 `source_order` 整数，前端稳定排序；相同序号时按注册顺序保持稳定。

## 5. 下载策略

`CuratedDownloader` 继续负责通用下载流程：HTTPS 校验、重定向后复验、响应大小限制、图片解码、已有文件复用、临时文件和原子移动。来源差异由 `DownloadPolicy` 提供：

```python
class DownloadPolicy(Protocol):
    provider_id: str

    def validate_asset_id(self, item_id: str) -> None: ...
    def validate_url(self, url: str) -> None: ...
    def normalize_url(self, url: str) -> str: ...
```

具体策略使用组合，不通过 `if provider == ...` 分支选择。每个 Provider 在构造时获得自己的策略或已经绑定策略的下载器。需要跨来源缓存预览图时，由轻量 `ImageReaderRegistry` 按 Provider ID 查找已经绑定策略的读取器；注册发生在组合根，缓存服务不理解域名与 ID 规则。域名判断使用精确主机或明确后缀规则，不允许任意子串匹配。重定向后的最终 URL 使用同一策略复验。

策略注册由组合根完成。未知 Provider 没有默认放行策略，返回 `invalid_provider`。资产 ID 策略按来源独立定义，博物馆、NASA、国会图书馆和编辑来源不再共享隐含的正则分支。

## 6. 多缓存任务模型

`CacheJobService` 只负责任务生命周期，单个任务的翻页和写入逻辑下沉到 `CacheJobRunner`。每个任务使用独立的不可变请求、取消事件和状态对象：

```text
CacheJobService
├─ jobs: job_id -> CacheJobContext
├─ active_keys: request_fingerprint -> job_id
├─ semaphore: 全局并发上限
└─ CacheJobRunner: 单任务执行策略
```

行为规则：

- 请求指纹由 Provider、规范化查询和稳定排序后的筛选条件生成，不包含游标。
- 相同指纹已有运行任务时返回 `cache_duplicate` 和现有 `job_id`，HTTP 状态为 409。
- 不同指纹可以并行，默认全局最多运行 3 个任务。
- 达到上限时返回 `cache_capacity`，不建立等待线程，避免用户重复点击堆积任务。
- 每个任务有自己的 `threading.Event`；取消只影响指定任务。
- 状态读取和更新在锁内完成，耗时搜索、详情、下载和索引写入不持锁。
- 已完成、失败和取消的任务最多保留 64 个，或保留 24 小时，以先满足的条件清理；运行任务永不清理。
- `CacheProgress` 继续按请求隔离游标，实现“每次新增 100 张”；任务完成后保持现有继续缓存语义。
- 进程退出不等待后台线程，不声称跨重启恢复正在运行的任务；只恢复分页进度。

接口保持现有 `start`、`status(job_id)`、`cancel(job_id)`。状态响应新增 `request_key`、`created_at`、`updated_at`，已有前端字段不删除。

## 7. HTTP 请求体限制

所有接收 JSON 的路由统一调用一个窄职责解析器 `JsonBodyReader`。默认上限为 1 MiB，行为如下：

1. `Content-Length` 非法或大于上限时，立即返回 HTTP 413 和 `request_too_large`。
2. 对没有 `Content-Length` 或使用 chunked 的请求，逐块读取，累计超过上限立即停止并返回 413。
3. 空正文、非法 UTF-8、非法 JSON 或 JSON 顶层不是对象时返回 HTTP 400 和 `invalid_json`。
4. 解析器不记录正文内容，错误响应不回显用户输入。
5. aiohttp 自身先抛出的大小异常也转换为统一错误格式。

应用设置的 `client_max_size` 不能替代该解析器，因为节点可能被加载到已有的 ComfyUI aiohttp 应用中，本项目不拥有全局应用配置。

## 8. 外部来源的可靠性和诊断

保留各客户端已经存在的缓存与重试逻辑。本轮增加统一约束，而不建立通用网络框架：

- 连接和读取必须有有限超时。
- 只重试超时、连接失败、HTTP 429 和 5xx；参数错误、认证失败和 4xx 不盲目重试。
- 429 尊重有限范围内的 `Retry-After`。
- 每次请求设置明确 User-Agent。
- 错误对前端只暴露稳定错误码、中文消息和操作建议；技术细节进入日志且经过凭据脱敏。
- Provider 状态检查保持轻量，不因列出来源而下载大量数据。

新增 `src/ty_image_spider/version.py` 作为运行时产品标识的唯一来源，导出 `__version__ = "2.5.0"` 与由它生成的 `USER_AGENT`。所有 HTTP 客户端引用该常量，清除当前并存的 `2.0`、`2.1`、`2.4` 字符串。`pyproject.toml`、`package.json` 和 `package-lock.json` 仍保留生态工具要求的版本字段，但由发布校验保证它们与运行时版本一致。

新增契约测试扫描所有可见 Provider，确认描述符完整、下载策略存在、缓存能力声明与实际注入一致。真实站点测试仍属于手动验收，CI 不依赖外部站点可用性。

## 9. 开源治理和素材权利

仓库增加以下文件：

- `LICENSE`：MIT License，版权主体统一写 `TY Image Spider contributors`，不包含第三方素材授权。
- `CONTRIBUTING.md`：环境、测试命令、Provider 新增清单、提交与 PR 要求。
- `SECURITY.md`：支持版本、私下报告方式、响应范围；不要求在公开 Issue 中提交凭据或漏洞细节。
- `CODE_OF_CONDUCT.md`：采用 Contributor Covenant 2.1。
- `docs/compatibility.md`：ComfyUI、Python、Node、浏览器和操作系统兼容矩阵。
- `docs/source-rights.md`：逐来源说明数据入口、署名、版权与下载者责任，并明确缓存和下载不改变原素材许可。

README 只提供摘要并链接这些文档。任何来源的“公开可访问”都不等于“可自由商用”；节点保留来源链接和可获得的权利字段，不替用户作版权判断。

`SECURITY.md` 优先要求使用 GitHub Security Advisories 的 `Report a vulnerability` 私密入口。仓库尚未启用私密入口时，只允许在公开 Issue 中请求维护者提供私密联系方式，不得附带漏洞细节或凭据；文档不公布 Git 配置中的私人邮箱，也不虚构邮箱。

## 10. CI 与兼容矩阵

GitHub Actions 拆为两个独立作业，避免一个大作业掩盖失败来源：

- Python：Windows、Ubuntu；Python 3.10、3.13。安装运行和开发依赖，运行 pytest、Ruff、Mypy、编译检查。
- Frontend：Ubuntu；Node 20、22。使用 `npm ci`，运行 Node 测试、Prettier 检查和 JavaScript 语法检查。

另设轻量发布包检查作业，在 Python 3.13/Ubuntu 上运行打包脚本的校验模式。CI 使用固定 major 版本的官方 Actions，并赋予最小 `contents: read` 权限。

兼容矩阵区分“CI 自动验证”和“维护者实机验证”。ComfyUI 版本无法稳定固定为包依赖，因此记录最近一次通过实机验证的 ComfyUI 日期或提交，而不声称兼容所有版本。

## 11. 可复现发布

新增 `scripts/build_release.py`。脚本只读取 Git 已跟踪文件，并使用明确的运行时白名单生成 ZIP。白名单包含根入口、`src/`、`web/`、`LICENSE`、`README.md`、`CHANGELOG.md`、`requirements.txt`、`pyproject.toml`、`tmdb.example.json`，以及面向用户的来源、兼容性和权利说明文档。

开发资料不进入用户安装包：`.github/`、`.gitignore`、`.prettierrc.json`、`tests/`、`scripts/`、`requirements-dev.txt`、`package.json`、`package-lock.json` 与 `docs/superpowers/` 全部排除。它们继续保留在源码仓库中供贡献者使用。这样避免延续 2.4.0 将测试、开发依赖和设计草稿一并分发的行为。

归档规则如下：

- 顶层目录固定为 `ty-image-spider-node/`。
- 文件时间统一为 `SOURCE_DATE_EPOCH`，未设置时使用目标 Git 提交时间。
- 文件顺序、路径分隔符和压缩参数固定。
- 白名单以外的文件全部拒绝进入归档；`.local`、缓存、输出、虚拟环境、`node_modules`、`dist` 和本地凭据即使被误跟踪也不能进入归档。
- 打包前校验 `pyproject.toml`、`package.json`、`package-lock.json` 和 `src/ty_image_spider/version.py` 的版本一致。
- 扫描归档路径与文本文件，拒绝 `tmdb.json`、常见密钥文件名、绝对本机路径和已知凭据格式。
- 输出 ZIP 与同名 `.sha256` 文件；连续运行两次必须得到相同哈希。

脚本支持 `--check`，只校验文件集合、版本和敏感内容，不写最终发布包。发布流程不自动创建或推送 GitHub Release，避免在没有明确授权时对外发布。

## 12. 测试策略

实现遵循测试先行，每一组行为先看到针对性测试失败，再写最小实现。

Python 测试新增：

- 描述符展示字段序列化、完整性与隐藏来源。
- 每类下载策略的 ID、主机、重定向和 URL 规范化。
- 两个不同缓存任务并发运行、相同任务去重、容量限制、独立取消和过期清理。
- 带 `Content-Length`、chunked、刚好 1 MiB、超过 1 MiB、非法 UTF-8 和非对象 JSON。
- 发布脚本的确定性、运行时白名单、开发文件排除、版本不一致和敏感文件拒绝。
- 全部注册 Provider 的契约检查。
- 所有 HTTP 客户端使用统一的运行时 `USER_AGENT`，仓库内不残留旧版本请求标识。

前端测试新增：

- 来源分组、排序、隐藏和标签完全来自描述符。
- 新字段缺失时的兼容回退。
- 详情和缩略图不再依赖硬编码来源映射。

回归检查包括现有全部 Python 与前端测试、Ruff、Mypy、Prettier、JS 语法、Python 编译、`git diff --check`。实机验收前先请求 `http://127.0.0.1:8188/queue`，仅在 Running 和 Pending 都为 0 时重启 8188；不访问或操作 8189。

## 13. 迁移与兼容

- HTTP 路由路径、成功响应包络和现有错误字段保持不变。
- Provider ID、筛选字段、素材模型和下载目录保持不变。
- 下载继续落到 `<ComfyUI>/output/ty-node/ty-image-spider/`；索引缓存继续使用当前相对路径。
- 缓存任务状态保留已有字段，前端无需同时发布破坏性改动。
- 小红书 Provider 继续注册以兼容已有请求，但 `presentation.visible=false`，不会出现在来源导航。
- 旧前端若忽略新增描述符字段，仍能使用 `id`、`label`、筛选和能力字段。

## 14. 完成定义

以下条件全部满足后，才能将目标标记完成：

1. 自动测试和质量检查全部通过。
2. CI 配置可被本地静态检查，工作流使用的命令均在本地实际执行通过。
3. 发布包连续构建两次哈希相同，归档内容不含 `.local`、缓存、绝对路径或凭据。
4. 8188 队列空闲后完成实机回归：来源导航、搜索、详情、下载、缓存任务和工作流隔离正常。
5. 文档能让一名没有项目上下文的维护者安装、验证、增加 Provider 和报告安全问题。
6. 版本统一更新为 2.5.0，提交发布版本并创建本地 `v2.5.0` 标签。
7. 除非用户另行授权，不推送远端、不创建 GitHub Release。
