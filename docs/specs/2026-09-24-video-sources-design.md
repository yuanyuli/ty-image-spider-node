# 视频素材源设计

## 目标

TY Image Spider 增加独立“视频素材”分类，首批接入 Internet Archive 的 Prelinger Archives、Wikimedia Commons 视频和 NASA 视频。用户可以搜索、分页、查看封面和资料，在详情中按需播放，并明确下载选中的视频文件。

这次扩展继续保持节点零输出端口，不把视频传给下游 ComfyUI 节点。后台“新增缓存100条”只保存封面、详情和索引，不自动下载视频文件。

## 产品边界

- 首批来源均不要求账号或 API Key。
- 列表卡片只显示静态封面，不创建隐藏视频元素，也不预加载视频。
- 打开详情后才设置视频播放地址；默认不自动播放，关闭详情时暂停并释放媒体地址。
- 每个视频支持单项下载；首批来源不提供“下载本页”，避免一次操作产生大量流量和磁盘占用。
- 视频保存到 `<ComfyUI>/output/ty-node/ty-image-spider/<provider>/`。
- 页面展示来源提供的作者、日期、说明、许可、时长、尺寸、格式和文件大小；素材是否可商用由用户依据单项许可判断。
- 不抓取 YouTube、影视剪辑站或需要绕过访问控制的文件。TMDB 预告片索引不在首批范围内，因为它主要返回第三方播放链接，不能提供同等可靠的直接下载能力。

## 来源设计

### Prelinger Archives

Provider ID 为 `prelinger`。列表通过 Internet Archive Advanced Search API 检索 `collection:prelinger AND mediatype:movies`，每页24项，支持英文关键词、排序和页码分页。详情通过 Metadata API 读取文件、说明、作者、年代、许可和文件大小。

封面使用 Internet Archive 的 item image 服务。播放优先选择体积适中的 H.264/MPEG-4 派生文件，下载优先选择可在浏览器和常见剪辑软件中使用的高质量 MPEG-4 文件。只接受 `archive.org` 及其受控资源主机。

### Wikimedia Commons 视频

Provider ID 为 `commons-video`。使用 MediaWiki API 搜索 File 命名空间中的视频文件，支持中英文关键词、中文分类预设和游标分页。详情读取 `videoinfo`、派生格式与 `extmetadata`。

播放器优先选择浏览器可播放的 MP4 或 WebM 派生版本，下载保存来源标记的原始视频。许可、作者与署名要求保持在详情中。只接受 Wikimedia 固定上传主机及受控转码主机。

### NASA 视频

Provider ID 为 `nasa-video`。复用 NASA Image and Video Library 搜索接口，但固定 `media_type=video`，保留太空、地球、月球、火星、阿波罗、望远镜和宇航员等中文分类。

列表使用 NASA 返回的静态预览图。详情读取素材清单，播放器选择中等规格 MP4，下载选择最高质量的受支持 MP4。现有 `nasa` 图片 Provider 保持不变，两者共享客户端基础设施但不共享解析策略。

## 领域模型

`AssetItem.kind` 使用现有字段，视频固定为 `video`。新增可选整数 `duration_seconds`，用于列表和详情统一展示时长。

新增不可变值对象 `MediaResource`：

- `kind`：首批固定为 `video`。
- `url`：经过 Provider 来源约束的 HTTPS 地址。
- `mime_type`：如 `video/mp4`、`video/webm`、`video/ogg`。
- `role`：`playback` 或 `download`。
- `width`、`height`、`duration_seconds`、`size_bytes`：来源可用时填写。
- `label`：面向用户的规格名称。

`AssetDetail` 新增 `media` 元组，现有 `images` 字段保持不变。图片 Provider 不需要修改行为；视频 Provider 使用 `images` 保存封面或补充图片，使用 `media` 保存播放与下载资源。SQLite 索引序列化并恢复 `media`，旧索引中没有该字段时按空元组读取。

## 后端职责

每个来源拆分为 Client、Normalizer/Parser 和 Provider：Client 只负责受限 HTTP 与短时 JSON 缓存，Normalizer 只负责上游数据转换，Provider 只负责业务组合、描述符和下载入口。

新增通用 `VideoDownloader`，但来源规则仍由各 Provider 注入：

- 验证素材 ID、HTTPS 主机、重定向目标和允许的 MIME 类型。
- 分块流式写入临时文件，不把视频整体读入内存。
- 默认单文件上限 2 GiB；响应超过上限或磁盘写入失败时删除临时文件。
- 通过 MP4 `ftyp`、WebM EBML 或 Ogg 文件头拒绝 HTML 和伪装响应。
- 使用原子替换完成写入；同一素材已有有效视频时直接复用，不生成编号副本。
- 下载结果继续返回相对于 `output/ty-node` 的路径和完整输出根目录。

视频 Provider 仍声明独立的封面图片策略，供现有 `ImageReaderRegistry` 和缓存任务读取。视频下载器不注册为缓存读取器，确保“新增缓存100条”不会下载视频。

## 前端职责

画廊卡片根据 `item.kind` 选择展示策略。视频卡片继续使用 `<img>` 封面，在封面上显示播放图标、时长和分辨率；现有图片卡片保持原样。

详情对话框把媒体区域拆成图片视图和视频视图。视频视图使用原生 `<video controls playsinline preload="metadata">`：

- 不自动播放、不循环，默认静音状态由浏览器控制。
- 优先选择 `role=playback` 的资源，缺失时使用第一个可播放资源。
- 下载按钮保存 `role=download` 的资源，缺失时回退当前播放资源。
- `←`、`→` 继续切换本页相邻素材；`↓` 保存当前视频。
- 关闭、切换素材或销毁节点时暂停视频、移除 `src` 并调用 `load()`，释放网络和解码资源。
- 使用浏览器原生全屏按钮，不把视频接入图片缩放与拖拽查看器。

视频区域固定为16:9的响应式容器，竖版视频使用 `object-fit: contain` 显示完整画面。加载、不可播放和下载失败使用现有活动状态区域反馈。

## 缓存与状态

缓存键继续使用来源、站点和素材 ID。缓存任务读取视频的静态 `preview_url`，把封面保存为现有图片缓存，并把 `AssetDetail.media` 序列化进索引。搜索命中缓存后复用本地封面和详情，但播放与手动下载仍访问来源视频地址。

每个视频来源的缓存文案明确写成“新增最多100条封面与资料；视频按需播放和下载”。缓存任务停止、并发、断点和失败计数沿用现有逻辑。

## 安全与失败处理

- 上游 JSON、文件名、MIME、尺寸、时长和文件大小均视为不可信输入。
- 文件名只由经过验证的 Provider ID、素材 ID 和检测出的扩展名生成。
- 不信任上游提供的本地路径，不接受 HTTP、凭据 URL、非标准端口和来源范围外重定向。
- 播放资源失效时保留封面与来源链接，并显示“当前视频暂不可播放”；不把播放失败误报为搜索失败。
- 下载过程中断时不保留半成品；已有有效文件不被失败请求覆盖。
- 单项许可缺失时明确显示“请查看来源页面确认使用条件”，不推断公共领域或商用许可。

## 测试与验收

后端测试覆盖三个来源的搜索、分页、详情、格式选择、许可字段、恶意 URL、超大响应、中断写入、文件头校验、重复下载复用和缓存恢复。固定 fixture 作为主要测试输入，真实网络只用于人工烟测。

前端测试覆盖静态视频卡片、详情按需创建播放器、无自动播放、播放/下载资源选择、键盘切换与保存、关闭释放资源、竖版 contain 布局，以及图片详情不受影响。

验收时分别搜索三个来源，确认列表无视频预加载；打开详情后能够播放至少一个真实样本；保存后文件位于来源子目录；同一视频重复保存复用原文件；缓存100条不产生视频文件。最终运行全量 Python、前端、类型、格式、发布快照与 ComfyUI 实机检查。
