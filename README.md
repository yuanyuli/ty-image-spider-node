# TY Image Spider

TY Image Spider 是一个零输出端口的 ComfyUI 素材浏览节点。它在节点内完成图片检索、详情查看与下载，不向下游节点传递图片，也不会触发 ComfyUI 工作流执行。

当前固化版本：**2.5.0**。功能范围、验收记录与回退说明见 [更新记录](CHANGELOG.md)。

## 支持的素材源

| 素材源 | 搜索与筛选 | 详情 | 下载 | 额外依赖 |
| --- | --- | --- | --- | --- |
| `civitai.com` | 关键词、周期、排序、SFW、标签、提示词、游标分页 | 提示词、模型、LoRA、workflow、metadata | 单图与本页批量下载 | 可选 Civitai API Key |
| `civitai.red` | 与 `civitai.com` 相同 | 与 `civitai.com` 相同 | 单图与本页批量下载 | 可选 Civitai API Key |
| Wallhaven | 关键词、分类、排序、榜单范围、方向、最低分辨率、页码分页 | 作者、统计、标签、分类、色板、原始来源 | 单图与本页 24 张批量下载 | 无，仅访问公开 SFW API |
| Behance | 全站关键词搜索；空关键词时浏览平面设计或摄影精选 | 项目图集、作者、来源项目 | 项目首图下载 | 无，读取公开项目页面 |
| Colossal | 当代摄影、设计、插画、艺术、手工、书籍；英文关键词与分页 | 专题说明与图集 | 单个专题整组下载 | 无，公开专题接口 |
| Design Milk | 平面设计、摄影、视觉艺术、时尚、空间、家具；英文关键词与分页 | 专题说明与图集 | 单个专题整组下载 | 无，公开专题接口 |
| Feature Shoot | 艺术摄影、纪实、人像、自然、风景、街头、静物；英文关键词与分页 | 摄影专题说明与完整组图 | 单个专题整组下载 | 无，公开专题接口 |
| My Modern Met | 当代艺术、摄影、设计、建筑、雕塑、装置、绘画；英文关键词与分页 | 艺术专题说明与完整组图 | 单个专题整组下载 | 无，公开专题接口 |
| Aperture | 摄影作品集、摄影书、经典档案、摄影师访谈、摄影评论、展览与书评 | 摄影专题说明与完整组图 | 单个专题整组下载 | 无，公开专题接口 |
| PRINT Magazine | 平面设计、品牌与标识、字体与排版、插画、包装、海报、设计史 | 设计专题说明与完整组图 | 单个专题整组下载 | 无，公开专题接口 |
| Are.na | 精选平面设计、摄影、字体频道；支持公开频道链接与分页 | 图片与收藏说明 | 单图与本页下载 | 无，公开频道接口；不支持全站关键词搜索 |
| 美国国会图书馆 | 纪实摄影、经典海报、历史人像、建筑、旅行海报、时尚摄影、日本版画 | 作者、年代、媒介、主题与使用条件 | 单图与本页下载 | 无，官方公开接口 |
| NASA Image Library | 太空、地球、月球、火星、阿波罗、望远镜、宇航员和 NASA 海报 | 日期、摄影者、中心、关键词、说明与 NASA Image ID | 单图与本页下载 | 无，官方公开接口 |
| FilmGrab | 中文精选片单、TMDB 中文电影版本查询、英文关键词；留空浏览全部电影 | 每部电影的静帧原图 | 单图与本页批量下载 | 扩展中文查询可选 TMDB 读取令牌 |
| V&A | 摄影、时装、海报、设计、纺织、建筑、陶瓷；关键词与分页 | 作者、年代、媒介、产地、馆藏说明 | 作品主图 | 无，官方公开接口 |
| 芝加哥艺术 | 绘画、摄影、设计、建筑图纸、雕塑等；关键词与分页 | 作者、年代、媒介、作品尺寸、说明和版权 | 作品主图 | 无，官方公开接口 |
| 克利夫兰 | 摄影、绘画、雕塑、素描、版画、纺织；关键词与分页 | 作者、年代、媒介、说明和许可 | 高清 JPG 主图 | 无，官方公开接口 |
| 小红书（暂隐藏） | 保留接入代码，暂不显示来源入口 | — | — | 恢复后需 OpenCLI、Chrome 扩展及登录会话 |
| 本地历史 | 文件名或内嵌提示词、提示词筛选、分页 | 文件信息与图片 metadata | 文件已经位于本地，无需重复下载 | 无 |

当前下载目录为 `output/ty-node/ty-image-spider/`；同时兼容读取历史 `output/ty-image-spider/` 与 `output/ty-node/` 图片。各素材源由独立 Provider 实现；新增来源不需要修改现有来源的请求与下载流程。

## 安装

将本仓库放入 ComfyUI 的 `custom_nodes` 目录，然后安装运行时依赖并重启 ComfyUI：

```powershell
cd <ComfyUI>\custom_nodes\ty-image-spider-node
<ComfyUI Python> -m pip install -r requirements.txt
```

安装依赖时请使用运行 ComfyUI 的 Python；便携版通常为 `python_embeded/python.exe`。节点运行不需要 Node.js。

安装后在 `TY Utils/素材浏览` 分类中添加 `TY Image Spider · 素材浏览`。该节点没有输出端口，所有浏览与下载操作都在节点界面内完成。

## Civitai 配置

公开图片通常不要求凭据。需要 API Key 时，在启动 ComfyUI 前设置环境变量：

```powershell
$env:CIVITAI_API_KEY = "你的 API Key"
```

API Key 只通过 `Authorization` 请求头发送，不会放入 URL、缓存、节点属性或工作流。

## 小红书配置

当前版本已隐藏小红书入口，以下配置仅供后续恢复接入时参考。旧工作流若选中小红书，打开后会回到 Civitai。

小红书是可选素材源。它不可用时，Civitai 与本地历史仍可正常使用。

1. 安装 Node.js `>= 20.18.1`。
2. 安装 OpenCLI >= 1.8.8。历史验证使用上游提交 `8271afc`；如需复现该版本，可构建安装：

   ```powershell
   git clone https://github.com/jackwener/opencli.git
   Set-Location opencli
   git checkout 8271afc
   npm install --ignore-scripts
   npm run build
   npm pack --ignore-scripts
   npm install -g .\jackwener-opencli-1.8.8.tgz
   opencli --version
   ```

   当 npm 已正式发布 `1.8.8` 或更高版本后，可以改用 `npm install -g @jackwener/opencli@^1.8.8`。

3. 从 [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk) 安装 OpenCLI Chrome 扩展。也可以从 [OpenCLI Releases](https://github.com/jackwener/opencli/releases) 下载扩展压缩包，在 `chrome://extensions` 中启用开发者模式后加载解压目录。
4. 在 Chrome 中登录小红书并保持登录状态。
5. 验证桥接与登录：

   ```powershell
   opencli doctor
   opencli xiaohongshu whoami --format json
   ```

也可以在节点切换到“小红书”后点击“一键连接 OpenCLI”。按钮会依次检查版本、重启
OpenCLI 守护进程、等待 Chrome 扩展恢复连接并确认登录账号；它不会代替 Chrome 登录，
也不会读取或保存 Cookie。

关键词搜索会先调用 OpenCLI 官方 `xiaohongshu search` 适配器，再从同一个持久会话只读提取卡片封面。完整笔记链接必须包含 `xsec_token`；`xhslink.com` 短链接也会进入单篇流程。节点不会模拟点赞、收藏、评论或发布操作。

如果 OpenCLI 的筛选选择器与当前小红书页面不兼容，节点会保留已打开的同关键词页面，
以只读方式提取可见卡片，并在状态栏标明筛选可能未生效。此时可升级 OpenCLI 后再重试。

## 界面与下载

- 顶部将17个可见来源入口分为“AI 与壁纸、摄影与设计、艺术馆藏、电影、本地”五类。第一行切换分类，第二行只显示组内来源并可横向滚动；切换分类不会提前加载其他来源。小红书暂隐藏，筛选项仍由各 Provider 的描述符动态生成。
- 除本地历史外，当前显示的来源均支持“新增缓存100张”：只将本次新增素材计入100张，已缓存的跳过；显示新增、跳过和失败数量。每组来源、搜索词和筛选条件独立保存断点，再次点击从断点继续，来源耗尽时按实际数量结束。
- 缓存按来源、站点与素材 ID 建立持久索引，再次检索复用本地预览、详情和提示词。每项缓存一张预览，高清原图和图集其余图片按需联网加载。小红书暂不支持此批量缓存。
- Behance 精选画廊与关键词搜索均支持上下页，每页24项，使用来源返回的真实游标。
- FilmGrab 可直接选择中文精选片单；配置 TMDB 后也支持片单以外的中文电影名。先确认电影及上映年份，再匹配 FilmGrab 条目，确认的映射会保存在本机。“查找电影版本”可重新选择同名电影。清空关键词则浏览全部电影。详见 [中文电影查询与配置](docs/tmdb-movie-mapping.md)。
- 三家博物馆可直接用中文分类浏览，搜索框留空即可；作品名和作者建议使用英文，例如 `Monet`、`landscape`、`portrait`。暂未提供馆藏关键词的中文自动翻译。三家均无需注册、密钥或浏览器扩展；图片规格与来源说明见 [馆藏素材源](docs/museum-sources.md)。
- Colossal、Design Milk、Feature Shoot、My Modern Met、Aperture 与 PRINT Magazine 每张卡片是一个专题，右上角显示图集张数，“下载图集”保存整组图片。缓存100张指100个专题封面及图集资料，图集原图按需下载。Are.na 每张卡片是一张公开图片，可直接用中文精选频道浏览。详见 [摄影与设计素材源](docs/editorial-sources.md)。
- 美国国会图书馆使用中文分类浏览公开视觉档案，详情保留来源提供的作者、媒介和使用条件；英文关键词可继续缩小范围。详见 [美国国会图书馆素材源](docs/loc-source.md)。
- NASA 使用中文分类浏览官方图片库，预览选择不超过800像素的版本，详情与下载优先来源标记的原图。详见 [NASA 图片素材源](docs/nasa-source.md)。
- 画廊在窄节点中显示两列，在宽节点中显示三列；详情弹窗支持图集缩略图、提示词复制和来源跳转。
- 下载统一保存到 `output/ty-node/ty-image-spider/` 下的来源子目录；后台缓存保存在 `cache/`，索引文件为 `cache/index.sqlite3`。
- 路径根目录通过 ComfyUI 的 `folder_paths.get_output_directory()` 动态获取，不绑定开发者盘符或安装目录。默认位于 `<ComfyUI>/output/`；若启动时指定了自定义输出目录，下载和缓存都会跟随该目录。
- 下载完成后，节点顶部会显示本次文件的完整绝对路径；整页下载的路径列表可在该区域滚动查看。
- 搜索框提供最近关键词列表，按素材源分别保存在本机浏览器中；不会保存笔记链接或签名参数。
- 下载器校验来源域名、重定向、响应大小、输出路径和实际图片格式。
- 策展来源下载时会校验并复用已经存在的图片，损坏文件重新下载。专题图集部分失败时显示已保存路径和失败数量，再次下载可补齐缺失图片。

## 隐私边界

小红书 Cookie 由 OpenCLI 与 Chrome Browser Bridge 管理，本节点不读取或保存 Cookie。带 `xsec_token` 的签名链接和小红书搜索结果不会写入工作流、节点持久属性或持久缓存，也不会写入 `localStorage`。工作流只保存当前来源、不含凭据的筛选条件与查询摘要。

Civitai API Key 不会写入工作流。HTTP 错误响应会隐藏常见的 key、token、secret、cookie 和 authorization 值。

TMDB API 读取访问令牌只保存在本地 `.local/tmdb.json` 或环境变量中，不发送到浏览器、不写入工作流和电影映射。`.local/` 已被 Git 忽略。

Wallhaven 只调用 `https://wallhaven.cc/api/v1` 的公开接口，并固定发送 `purity=100`，不会请求 Sketchy 或 NSFW 内容。搜索与详情不需要账号或 API Key；原图下载只接受 `w.wallhaven.cc`，重定向到其他域名会被拒绝。

## 开发与测试

源码仓库可独立创建虚拟环境并运行测试，完整步骤见 [贡献指南](CONTRIBUTING.md)。测试使用固定 fixture、注入式 HTTP/进程替身和临时目录，不依赖实时外部站点。

## 故障排查

### 节点未出现

确认 junction 或仓库目录位于 ComfyUI `custom_nodes`，查看后端启动日志，并在修改 Python 文件后重启后端。只修改前端文件时刷新浏览器即可。

### Civitai 返回 403 或 429

403 通常表示 API Key 无效或请求被拒绝；检查 `CIVITAI_API_KEY` 后重启 ComfyUI。429 表示请求过快，节点会尊重 `Retry-After` 并有限重试，仍失败时稍后再试。

### 小红书显示 OpenCLI 不可用

依次运行 `opencli --version` 和 `opencli doctor`。确认 OpenCLI Chrome 扩展已启用、Chrome 正在运行，并允许本机 `localhost:19825` 通信。

### 小红书要求登录或完整签名链接

在 Chrome 中重新登录小红书，然后从关键词搜索结果打开笔记。直接粘贴链接时需使用包含 `xsec_token` 的完整链接或 `xhslink.com` 短链接；普通无签名 `/explore/<id>` 链接无法可靠复用登录态。

### 下载后看不到文件

先看节点顶部显示的完整保存路径，再检查 ComfyUI 后端日志。节点只返回本次新增且通过 Pillow 校验的图片，HTML、文本、越界路径和非可信域名响应会被拒绝。

## 第三方许可

- [TMDB](https://www.themoviedb.org/) 提供电影身份与译名资料；非商业用途免费但须遵守署名要求，商业使用请核对其许可。[官方说明](https://developer.themoviedb.org/docs/faq)。This product uses the TMDB API but is not endorsed or certified by TMDB.
- [OpenCLI](https://github.com/jackwener/opencli) 使用 Apache License 2.0。本项目只通过用户安装的 `opencli` 命令调用它，不打包其源码或浏览器扩展。
- [Wallhaven API](https://wallhaven.cc/help/api) 用于访问公开 SFW 素材。图片版权与使用许可由原作者、上传者及原始来源决定，下载前请自行确认使用范围。
- V&A、芝加哥艺术博物馆和克利夫兰艺术博物馆提供馆藏资料及图片；详情展示来源链接与可用的版权标记，具体许可以各作品页面为准。官方接口资料见 [馆藏素材源](docs/museum-sources.md)。
- Colossal、Design Milk、Feature Shoot、My Modern Met 和 Are.na 提供公开摄影、设计与收藏内容；图片署名及使用条件以原专题、作品来源为准。节点保留来源入口，Are.na 的收藏者不标作摄影师或设计师。
- 美国国会图书馆接口提供作品资料和可用图片；每件作品的版权与复制限制以详情中的官方说明为准。
- [Pillow](https://python-pillow.org/) 用于图片格式与 metadata 校验。
- [Lucide](https://lucide.dev/) 图标路径用于界面按钮，遵循 ISC License。
- `jsdom` 与 Prettier 仅用于前端开发和测试，不进入 ComfyUI 运行时。

## 开源与维护

代码采用 [MIT](LICENSE)，外部素材不包含在该授权内。请阅读 [素材权利](docs/source-rights.md)、[第三方声明](THIRD_PARTY_NOTICES.md)、[兼容性](docs/compatibility.md)、[贡献指南](CONTRIBUTING.md)、[安全政策](SECURITY.md) 和 [行为准则](CODE_OF_CONDUCT.md)。
