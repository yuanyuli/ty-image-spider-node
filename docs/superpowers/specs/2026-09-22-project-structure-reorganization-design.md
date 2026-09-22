# TY Image Spider 项目结构重构设计

日期：2026-09-22

## 1. 目标

本轮重构解决源码、前端、开发脚本和文档随功能增长后平铺散落的问题。重构完成后，目录应直接表达业务领域和技术职责，大型文件应拆成可独立理解、替换和验证的小模块。

重构不改变以下产品契约：

- ComfyUI 节点类型 `TyImageSpider`、显示名称和零输出端口行为；
- Provider ID、来源显示顺序和工作流保存字段；
- `/ty-image-spider/*` HTTP 路由、请求与响应结构；
- 下载目录、缓存索引格式和已有工作流恢复逻辑；
- 前端 CSS 类名、键盘操作和用户可见交互。

内部 Python 与 JavaScript 模块路径不是公开 SDK，不保留旧路径兼容空壳。所有仓库内引用一次迁移到新路径。

## 2. 现状与问题

审计时仓库包含 203 个 Git 跟踪文件。主要问题如下：

- `src/ty_image_spider/providers/` 平铺 34 个以上模块，公共工具、客户端、解析器和具体来源混在同一层；
- `models.py`、`bootstrap.py`、`routes.py` 同时承载多类职责；多个 Provider 文件混合网络访问、HTML/JSON 解析、标准化和业务策略；
- `web/` 平铺 20 个文件，入口文件约 611 行、详情弹窗约 412 行、样式文件约 1292 行；
- `scripts/` 同时放置质量检查、前端测试启动器和发布构建；
- `tests/` 平铺后端与前端测试，无法从路径判断覆盖领域；
- `docs/` 同时包含用户文档与内部阶段计划；
- `.artifacts` 有 2435 个文件、约 72.38 MB，`dist` 有 7 个历史 ZIP 及校验文件、约 2.03 MB，均不参与运行且被 Git 忽略。

## 3. 目标目录

```text
src/ty_image_spider/
  app/                 # ComfyUI 节点入口和应用组合
  api/                 # 路由、请求解析、响应与错误映射
  domain/              # 业务错误、素材、来源、搜索和下载模型
  infrastructure/      # 缓存、索引、网络、安全、元数据、OpenCLI
  providers/
    shared/            # Provider 协议、注册表、通用客户端和下载策略
    ai/                # Civitai、小红书
    wallpapers/        # Wallhaven、彼岸、壁纸网、WallpapersCraft
    editorial/         # Behance、专题站、Are.na
    collections/       # 博物馆、Commons、The Met、LOC、NASA
    movies/            # FilmGrab、TMDB 图片
    local/             # 本地历史
  movies/              # 中文电影身份、映射与解析
  services/            # 搜索、详情、下载和缓存任务用例
  version.py

web/
  ty_image_spider.js   # 唯一自动注册入口
  app/                 # 节点生命周期和控制器
  core/                # API、状态、展示描述符和 DOM 小工具
  ui/                  # 来源栏、画廊、弹窗和图片查看器
  features/            # 缓存、电影、详情和预览隔离
  assets/
  styles/

scripts/
  quality/
  release/

tests/
  backend/
    app/
    api/
    domain/
    infrastructure/
    providers/
    services/
  frontend/
  release/
  fixtures/

docs/
  guides/
  sources/
  source-rights.md
```

`version.py` 保留在包根，便于运行时和发布构建使用单一版本来源。`web/ty_image_spider.js` 保留为唯一自动注册入口，其余 JavaScript 模块只导出能力，不产生加载副作用。

## 4. 后端职责拆分

### 4.1 应用、API 与领域

- `app` 只负责 ComfyUI 节点声明与依赖组合；来源构造按类别分成小型函数，不创建持有业务状态的总管类；
- `api` 将路由注册、有限 JSON 正文读取、响应转换和异常映射分开；
- `domain` 将现有 `models.py` 拆成错误、来源描述、素材和用例输入输出。领域模块不依赖 ComfyUI、文件系统或网络；
- `infrastructure` 承载文件系统、SQLite、HTTP、安全校验、图片 metadata 和 OpenCLI 进程适配。

应用服务继续一类一个用例，通过构造参数依赖 Provider 注册表、索引或下载器。缓存协调、任务执行和进度存储保持独立。

### 4.2 Provider

Provider 先按用户界面领域归组。一个来源只有单一、短小实现时保留为一个模块；混合三个以上职责或超过约 250 行时拆成来源子包：

```text
wallpapers/wallpaperscraft/
  provider.py
  client.py
  parser.py
  policy.py
```

各部分职责如下：

- `provider.py`：描述符、筛选解释、搜索/详情/下载编排；
- `client.py`：固定域名、超时、重试、响应大小和上游错误转换；
- `parser.py` 或 `normalizer.py`：把外部 HTML/JSON 转成领域模型，不执行网络访问；
- `policy.py`：该来源专属下载主机、素材 ID 和 URL 约束。

通用 JSON 客户端、策展下载器、Provider 协议和注册表放入 `providers/shared`。来源差异不得加入共享模块的来源 ID 条件分支。

## 5. 前端职责拆分

`ty_image_spider.js` 只导入并注册扩展。当前入口中的职责拆分为：

- 节点生命周期：挂载、恢复、销毁和 ComfyUI 预览隔离；
- 来源会话：来源切换、筛选默认值和每来源状态保存；
- 检索控制器：请求竞态、上下页和电影版本选择；
- 下载控制器：单图、当前图、本页和路径提示；
- 缓存控制器：任务启动、轮询、取消和条件指纹；
- 渲染组合：来源控件、画廊和详情弹窗之间的事件连接。

`dialog.js` 拆分为弹窗外壳、详情字段渲染、来源专属详情和复制/跳转动作。`source_controls.js` 拆分为分组导航、搜索区和筛选字段。`gallery.js` 拆分为工具栏、素材卡片、分页和状态视图。

样式以一个入口 CSS 引入以下文件：

- `tokens.css`：颜色、间距、边框和稳定尺寸变量；
- `workspace.css`：节点容器和页头；
- `controls.css`：来源、搜索与筛选；
- `gallery.css`：工具栏、卡片、骨架和空状态；
- `dialog.css`：详情与电影选择；
- `viewer.css`：全屏查看、缩放、拖拽和预览动作。

拆分不改已有选择器名称，避免视觉和测试契约漂移。

## 6. 脚本、测试与文档

- `scripts/quality` 保存完整质量入口、递归 JS 语法检查和递归前端测试启动器；
- `scripts/release` 保存可复现发布构建；CI、npm 命令和发布测试更新到新路径；
- 测试按后端层、Provider 领域和前端功能归组，fixture 保持集中；Pytest 和 Node 启动器递归发现测试；
- `docs/guides` 保存兼容性、缓存和 TMDB 配置；`docs/sources` 保存各来源说明；`docs/source-rights.md` 保持为醒目的统一权利入口；
- README、CHANGELOG、贡献指南、第三方声明和发布白名单更新全部相对链接。

## 7. 清理策略

以下内容在迁移末尾删除：

- 整个 `.artifacts`；
- 整个 `dist`；
- 整个 `docs/superpowers`，包括本设计文档在最终工作树中的副本；
- `.cache`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache` 与所有 `__pycache__`；
- `.local` 内除 `.local/tmdb.json` 之外的历史探测文件和日志。

`.local/tmdb.json` 原地保留，不读取、不输出、不提交。`node_modules` 保留供本地前端测试使用并继续由 Git 忽略。

Git 已跟踪的内部设计文档可从历史提交恢复。忽略目录中的安装包、日志、缓存和烟测文件均可由脚本或测试重新生成。旧迁移备份按用户确认一并删除。

## 8. 迁移与回滚

实施采用阶段提交：

1. 质量脚本递归化并锁定外部契约；
2. 领域、基础设施、应用和 API 迁移；
3. Provider 分类与大型 Provider 拆分；
4. 前端模块与样式拆分；
5. 测试、脚本和用户文档归组；
6. 生成物、探测资料和内部历史文档清理；
7. 完整质量门禁和 ComfyUI 实机冒烟。

每阶段先更新引用并运行对应测试，通过后再进入下一阶段。发生失败时只修复当前阶段，不继续叠加移动。阶段提交允许按边界回退，不使用破坏性 Git 重置。

## 9. 验收标准

自动验证必须覆盖：

- Python 测试、Ruff 规则与格式、Mypy、Python 编译；
- 前端测试、Prettier、所有递归 JavaScript 模块语法；
- Git 未暂存和已暂存差异检查；
- 发布白名单、敏感路径扫描，以及同一提交两次构建 SHA256 一致；
- 24 个 Provider 全部注册、23 个可见来源分组和顺序不变；
- 节点类型、路由集合、工作流序列化、输出路径和缓存索引契约不变；
- 仓库内 Markdown 相对链接不存在断链；
- `.artifacts`、`dist`、内部方案文档和生成缓存均不再残留。

实机验证在 ComfyUI 重启后执行：节点首次加载、来源导航、至少一个来源搜索和翻页、详情全屏、键盘切图、单图下载与完整路径显示。实机测试不读取或展示本地 TMDB 凭据。

## 10. 非目标

- 不新增或删除素材来源；
- 不修改 UI 视觉设计和文案；
- 不改变缓存 100 张、分页、下载或提示词行为；
- 不更新依赖版本或发布产品版本；
- 不建立框架级依赖注入容器、事件总线或插件 SDK；
- 不为未公开的旧内部模块路径长期维护兼容层。
