# TY Image Spider 2.0 设计规格

## 1. 项目定位

`ty-image-spider-node` 是一个独立发布的 ComfyUI 自定义节点，用于在画布内搜索、浏览、查看和下载不同素材源的图片。它是现有 `civitai-inspiration` 的 2.0 重建版本，但作为全新项目开发，不修改旧仓库、不注册旧节点 ID，也不要求旧工作流自动迁移。

节点继续保持纯浏览下载定位：没有 `IMAGE`、`STRING`、JSON 或路径输出端口，不把素材传给下游节点，不执行外部工作流。它只负责帮助用户发现素材、检查来源信息并主动下载到 ComfyUI 输出目录。

首版正式支持以下来源：

- Civitai：`civitai.com` 与 `civitai.red`。
- 小红书：关键词搜索与单篇笔记链接解析，依赖可选的 OpenCLI 浏览器桥。
- 本地历史：浏览本节点已经下载到 ComfyUI 输出目录的图片。

后续新增来源时，不应修改既有 Provider 的内部流程，也不应让一个来源成为另一个来源的运行时依赖。

## 2. 已确认的产品边界

- 新节点注册名为 `TyImageSpider`，显示名为 `TY Image Spider · 素材浏览`，分类为 `TY Utils/素材浏览`。
- 不注册 `TyHitImageNode` 或 `CivitaiInspirationLoader`，避免与旧节点同时安装时发生冲突。
- 不提供 ComfyUI 输出端口。
- Civitai 保留关键词、周期、排序、SFW、标签、仅显示有提示词、分页、详情、提示词复制和下载能力。
- 小红书首版支持关键词搜索和粘贴单篇笔记链接，不加入推荐流、用户主页、收藏夹、发布或账号管理。
- 小红书搜索结果以笔记为单位。详情展示笔记中的完整图片序列，下载操作一次保存整篇笔记的全部图片。
- 本地历史按修改时间倒序浏览，可按文件名或内嵌 metadata 搜索。
- 视频不是首版素材类型。小红书视频笔记可以显示封面并标记类型，但不下载视频。
- 不绕过登录、验证码、风控、访问权限、付费限制或站点策略。

## 3. 架构选择

采用“Provider 注册表 + 统一素材模型 + ComfyUI HTTP 路由 + 来源感知前端”的架构。

没有采用在旧 `nodes.py` 中持续增加来源条件分支的方案，因为不同来源的认证、筛选、分页、详情和下载语义已经明显不同。也不使用 OpenCLI 代理所有来源，因为 Civitai 的公开 API 更直接稳定，不应因为新增小红书而强制依赖 Chrome。

系统分为四层：

1. Provider 层：封装各来源的查询、详情、分页和下载。
2. 应用服务层：校验请求、调用 Provider、统一缓存与错误格式。
3. ComfyUI 适配层：注册零输出节点和 HTTP 路由。
4. 前端层：在节点 DOM 控件中渲染来源选择、筛选、画廊和详情弹窗。

## 4. 目录结构

```text
ty-image-spider-node/
├─ __init__.py
├─ pyproject.toml
├─ requirements.txt
├─ README.md
├─ src/
│  └─ ty_image_spider/
│     ├─ __init__.py
│     ├─ nodes.py
│     ├─ routes.py
│     ├─ bootstrap.py
│     ├─ models.py
│     ├─ cache.py
│     ├─ security.py
│     ├─ metadata.py
│     ├─ downloads.py
│     ├─ opencli.py
│     ├─ services/
│     │  ├─ __init__.py
│     │  ├─ search.py
│     │  ├─ detail.py
│     │  ├─ download.py
│     │  └─ status.py
│     └─ providers/
│        ├─ __init__.py
│        ├─ base.py
│        ├─ registry.py
│        ├─ civitai.py
│        ├─ xiaohongshu.py
│        └─ local.py
├─ web/
│  ├─ ty_image_spider.js
│  ├─ ty_image_spider.css
│  ├─ api.js
│  ├─ state.js
│  ├─ source_controls.js
│  ├─ gallery.js
│  └─ dialog.js
├─ tests/
└─ docs/
```

根目录 `__init__.py` 只负责把 `src` 加入模块路径并导出 ComfyUI 映射。业务模块之间使用包内相对导入，测试使用 `--import-mode=importlib`，避免依赖当前工作目录或其他节点仓库。

## 5. 设计原则与组合边界

实现以单一职责和组合为硬约束，不设置统管来源、缓存、下载、HTTP 和 UI 状态的“大管家”类。

- Provider 使用策略模式：每个来源独立实现相同协议，来源差异留在自己的策略中。
- Provider 注册表兼具轻量工厂职责：只负责按 ID 创建、注册和查找策略，不执行搜索、详情或下载。
- 搜索、详情、下载和来源状态分别由小型应用服务处理。每个服务只编排一个用例，并通过构造参数接收 Provider、缓存或 Runner 等依赖。
- `bootstrap.py` 是唯一组合根，只负责构造依赖并向路由暴露用例，不包含业务分支。
- `routes.py` 只完成 HTTP 输入解析、调用用例和响应序列化，不直接访问站点、文件或子进程。
- `OpenCliRunner` 只负责安全执行、超时、输出限制和错误码转换，不理解小红书素材字段。
- 缓存组件只保存和读取结构化值，不决定某个来源的缓存键、有效期或陈旧回退规则。
- 下载校验、metadata 解析和本地文件索引保持无状态或窄状态组件，可以脱离 ComfyUI 单独测试。
- 前端入口 `ty_image_spider.js` 只安装扩展并组合控制器；API、状态、来源控件、画廊和详情弹窗分别维护自己的职责与生命周期。
- 模块之间传递 `SearchRequest`、`SearchPage`、`AssetItem`、`AssetDetail`、`DownloadResult` 等明确数据对象，不传递可被任意模块改写的大型上下文字典。

设计模式只用于已经存在的变化点。首版不建立抽象工厂层级、事件总线、依赖注入框架或通用插件 SDK；注册表、协议和构造注入已足够支持新增来源。任一模块如果需要了解两个以上无关用例，或测试必须一次构造大部分系统，视为职责边界需要重新拆分。

## 6. Provider 契约

每个 Provider 实现以下稳定接口：

```python
class AssetProvider(Protocol):
    id: str

    def descriptor(self) -> ProviderDescriptor: ...
    def status(self) -> ProviderStatus: ...
    def search(self, request: SearchRequest) -> SearchPage: ...
    def detail(self, item: AssetItem) -> AssetDetail: ...
    def download(self, item: AssetItem, output_root: Path) -> DownloadResult: ...
```

`ProviderDescriptor` 描述来源名称、状态能力、支持的筛选字段、分页类型、详情能力和批量下载能力。前端通过描述动态生成来源专属筛选，而不是在主界面硬编码所有站点控件。

首版支持的字段类型限定为：单行文本、整数、布尔开关、单选菜单和只读状态。复杂筛选器等出现真实需求后再扩展。

统一的 `AssetItem` 至少包含：

- `provider`、`id`、`kind`。
- `preview_url`、`source_url`。
- `title`、`author`、`created_at`。
- `width`、`height`、`image_count`。
- `has_prompt`、`prompt`、`negative_prompt`。
- `stats`、`tags`、`metadata`。
- `download_mode`：`single`、`note` 或 `none`。

不存在的字段保持空值，不把小红书正文冒充成生成提示词，也不把 Civitai workflow JSON 冒充成正向提示词。

`SearchPage` 包含规范化结果、下一页游标、是否使用陈旧缓存、来源状态和可读提示。Provider 自己解释游标；服务层和前端只保存并原样回传。

## 7. 各来源流程

### 7.1 Civitai

迁移旧节点已经验证的 HTTPS 客户端、重试、`Retry-After`、metadata 解析、提示词识别、缓存和安全下载逻辑，并整理为 `CivitaiProvider`。

- `civitai.com` 与 `civitai.red` 作为同一个 Provider 的站点选项。
- API Key 仅从 `CIVITAI_API_KEY` 环境变量读取。
- 搜索与详情结果归一化为 `AssetItem` 和 `AssetDetail`。
- 单图下载和当前页下载均可用。
- API 暂时失败时可以返回仍在有效保留期内的陈旧缓存，并明确标记。

### 7.2 小红书

小红书 Provider 是可选能力。用户需要安装 `@jackwener/opencli`、OpenCLI Chrome 扩展，并在 Chrome 中保持小红书登录。缺少任一条件都不影响其他 Provider。

搜索流程：

1. 用参数数组启动 `opencli xiaohongshu search`，传递查询、数量和来源支持的筛选。
2. 使用 `--format json --site-session persistent --window background`，让官方适配器负责登录态、筛选、滚动、风控识别和带 `xsec_token` 的链接。
3. 官方搜索完成后，复用 `site:xiaohongshu` 会话调用只读 `opencli browser ... eval`，提取当前搜索卡片的封面 URL。
4. 以可信笔记 ID 或规范化原帖 URL 合并官方结果与封面数据。
5. 不向日志、缓存错误或持久化前端状态泄露 Cookie；短期缓存中的原帖 URL 可能包含站点签名，只保存在本机节点缓存和当前页面内存中。

详情流程：

1. 仅接受小红书可信域名、可信路径和带有效签名的完整 URL，或官方支持的短链接。
2. 调用官方 `xiaohongshu note` 获取正文和互动字段。
3. 复用持久会话，通过只读提取脚本优先读取 `window.__INITIAL_STATE__` 的图片顺序，DOM 仅作为回退。
4. 详情返回完整图片列表，但不包含视频下载地址。

下载流程调用官方 `xiaohongshu download`，目标固定为 `<ComfyUI output>/ty-image-spider/xiaohongshu/<note-id>/`。命令执行前后对目标目录做快照，只把本次生成且通过图片校验的相对路径返回前端。一个笔记的下载是单个显式操作；首版不提供整页批量下载，以降低误操作和风控风险。

同一 OpenCLI 小红书会话的操作使用进程内互斥锁串行执行。子进程不经过 shell，设置总超时、UTF-8 解码、最大输出长度和明确退出码映射。停止搜索或 ComfyUI 退出时不主动关闭用户自己的浏览器窗口，仅管理 OpenCLI 创建的后台会话。

### 7.3 本地历史

本地 Provider 只扫描 `<ComfyUI output>/ty-image-spider/`，兼容读取旧节点的 `<ComfyUI output>/ty-node/`，但新下载不再写入旧目录。

- 只接受目录内的普通图片文件，不跟随指向目录外的链接。
- 使用 `/view?filename=...&type=output&subfolder=...` 生成预览地址。
- 从 PNG/JPEG metadata 中读取可展示字段。
- 不显示下载按钮，因为文件已经位于输出目录。

## 8. HTTP 路由

路由统一使用 `/ty-image-spider` 前缀：

- `GET /providers`：Provider 描述和轻量状态。
- `POST /search`：执行搜索或读取下一页。
- `POST /detail`：读取一个素材的来源专属详情。
- `POST /download`：下载单图或整篇笔记。
- `POST /download-page`：仅对声明支持批量下载的 Provider 开放。
- `POST /providers/xiaohongshu/check`：运行 OpenCLI 安装、桥接和登录检查。

所有响应使用 `{ok, data}` 或 `{ok: false, error: {code, message, action}}`。路由用 `asyncio.to_thread` 执行同步网络或子进程任务，避免阻塞 ComfyUI 的 aiohttp 事件循环。

错误码区分：参数错误、来源不可用、OpenCLI 未安装、浏览器桥未连接、需要登录、风控限制、超时、内容不存在、下载失败和内部错误。前端显示可执行的中文处理建议，日志保留不含凭据的技术上下文。

## 9. 节点状态与生命周期

节点是零输出节点，普通浏览操作不进入 ComfyUI 执行队列。`INPUT_TYPES` 只保留一个隐藏的 `state_json` 字段用于工作流序列化；前端 DOM 控件是主要交互界面。

前端将以下状态写入 `state_json`：当前 Provider、筛选值和不含凭据的最近一次查询摘要。Civitai 与本地搜索结果可以写入节点 properties 和按工作流、节点 ID 隔离的 `localStorage`，用于切换工作流后的快速恢复。

小红书结果采用单独的持久化策略：带 `xsec_token` 的原帖 URL、详情数据和下载上下文只存在于后端短期缓存与当前页面内存，不写入 `state_json`、节点 properties、`localStorage` 或工作流文件。页面刷新或工作流重新打开后保留小红书筛选条件，但要求重新搜索，避免签名链接长期落盘或过期后产生误导。

节点执行函数不发起网络搜索，只返回当前状态摘要供 ComfyUI 正常完成零输出节点执行。用户点击搜索、下一页、详情和下载时均调用 HTTP 路由。

节点移除时清理事件监听、进行中的前端请求和弹窗。工作流重新配置时恢复状态，避免重复安装监听器或 DOM 控件。

## 10. 界面设计

界面采用安静、紧凑的深色素材工作台风格，视觉层级来自清晰的间距、边框、字重和来源色，不使用大面积渐变、装饰光斑或多层卡片。

默认节点宽度约 460 像素，最小宽度 400 像素。主要区域依次为：

1. 顶部来源分段控件：Civitai、小红书、本地；右侧显示来源状态。
2. 搜索行：关键词或链接输入、搜索按钮、刷新按钮。
3. 紧凑筛选区：根据 Provider 描述渲染，可折叠但保留常用条件。
4. 状态工具栏：结果数、页码、缓存状态、下一页和当前页下载。
5. 图片网格：根据节点宽度在两列和三列间切换，卡片使用稳定比例，加载与错误状态不改变布局。

Civitai 卡片显示提示词状态和作者；小红书卡片显示作者、点赞数和多图数量；本地卡片显示文件名和时间。图片操作在悬停或键盘聚焦时出现，触屏设备保持可访问入口。

详情使用页面级模态框：左侧是可检查的主图与缩略图带，右侧是来源信息和操作。Civitai 详情展示正向提示词、负向提示词、模型、LoRA、workflow 和 metadata；小红书详情展示标题、作者、正文、互动数据和完整图集；本地详情展示文件信息和内嵌 metadata。

对话框支持 Escape 关闭、焦点陷阱、关闭后恢复焦点。按钮使用明确的命令文案或熟悉图标并带 tooltip。所有网格、按钮和状态区域设置稳定尺寸，避免图片加载或文字变化导致节点跳动。

## 11. 缓存与安全

- 查询缓存键包含 Provider、规范化筛选、游标和节点缓存版本。
- Civitai 与小红书使用不同的有效期；小红书带签名结果采用短有效期，不把 Cookie 写入缓存。
- 缓存采用原子写入、条目上限和损坏文件自动清理。
- 远程 URL 必须为 HTTPS，并通过 Provider 自己的域名白名单。
- Civitai 下载只允许 Civitai 官方域名及 CDN；小红书图片只接受小红书和 `xhscdn` 家族的可信主机。
- 所有下载使用临时文件、响应大小限制、图片格式和像素上限校验、安全文件名与原子移动。
- 输出目标通过 `resolve()` 校验必须位于 ComfyUI output 根目录内。
- 日志和错误响应递归隐藏 key、token、secret、cookie、authorization 等字段。
- OpenCLI 命令使用参数列表启动，不拼接 shell 命令。查询、URL和路径不会作为可执行文本解释。

## 12. 测试策略

开发遵循测试先行。每个 Provider 使用真实业务对象和固定 fixture，不让测试依赖实时站点。

Python 测试包括：

- Provider 注册、描述和统一模型契约。
- Civitai 查询、分页、缓存、metadata、提示词识别和错误映射。
- 小红书命令参数、JSON 解析、结果合并、详情图片顺序、退出码映射、超时和串行锁。
- 本地目录边界、排序、搜索和 metadata。
- 下载白名单、重定向、大小限制、路径穿越、临时文件清理和凭据脱敏。
- HTTP 路由的成功、参数错误与 Provider 错误响应。
- ComfyUI 包入口、节点注册、零输出契约和路由幂等注册。

前端测试使用 Node 内置测试运行器，重点覆盖：

- Provider 描述到筛选控件的映射。
- 状态序列化、工作流隔离和恢复。
- 搜索竞态保护、分页和错误状态。
- 来源专属动作的显示规则。
- 详情弹窗内容选择和生命周期清理。

验证命令至少包括 pytest、Node 前端测试、JavaScript 语法检查、Python 编译、Ruff、Mypy、Prettier 和 `git diff --check`。完成自动测试后，通过 junction 接入本地 ComfyUI，重启后端，并在桌面与窄视口检查节点、详情弹窗和来源错误状态。

## 13. 依赖与安装

Python 运行依赖保持最小，只使用 ComfyUI 已有能力以及明确列入 `requirements.txt` 的包。开发工具由总工作区 uv 环境管理，不修改 ComfyUI 内置 Python。

OpenCLI 是小红书 Provider 的可选外部依赖：

```powershell
npm install -g @jackwener/opencli
opencli doctor
```

节点不自动全局安装 OpenCLI、不自动安装浏览器扩展，也不修改用户浏览器配置。Provider 状态面板提供安装和诊断入口。首版要求 OpenCLI `>=1.8.8`，并在 README 中记录；低版本按来源不可用处理，不尝试兼容缺少持久站点会话或结构化退出码的版本。

## 14. 交付与验收

满足以下条件后视为首版完成：

- 节点可以与旧 `civitai-inspiration` 同时安装，注册名和路由不冲突。
- Civitai 两个站点能够搜索、分页、查看 metadata、复制提示词并安全下载。
- OpenCLI 已正确配置时，小红书能够按关键词搜索、显示封面、展开完整图集并下载整篇图片。
- OpenCLI 不可用时，界面准确指出缺失环节，Civitai 与本地来源仍可使用。
- 本地来源可以浏览新旧下载目录且不能越过 ComfyUI output 边界。
- 来源切换只显示适用的筛选与操作，状态恢复后不重复注册控件或监听器。
- 自动测试和质量检查通过，本地 ComfyUI 中的节点与详情界面经过截图和交互验证。
