# 当代摄影与平面设计素材源

2.2.0 新增 Colossal、Design Milk 和 Are.na；2.3.0 增加 Feature Shoot 与 My Modern Met。沿用现有工作流，均无需注册、密钥或浏览器扩展。

## 推荐浏览方式

| 来源 | 默认内容 | 其他中文选项 | 搜索方式 |
| --- | --- | --- | --- |
| Colossal | 当代摄影 | 设计、插画、当代艺术、手工与材质、艺术书籍 | 英文关键词，例如 `portrait`；留空浏览分类 |
| Design Milk | 平面设计 | 摄影、视觉艺术、时尚与配饰、空间设计、家具与产品 | 英文关键词，例如 `poster`；留空浏览分类 |
| Feature Shoot | 艺术摄影 | 纪实摄影、人像、自然、风景、街头、静物 | 英文关键词，例如 `portrait`；留空浏览分类 |
| My Modern Met | 当代艺术 | 摄影、设计、建筑、雕塑、装置艺术、绘画 | 英文关键词，例如 `installation`；留空浏览分类 |
| Are.na | 平面设计公开频道 | 当代摄影、字体与排版 | 留空选择频道，或粘贴完整公开频道链接 |

Are.na 链接格式为 `https://www.are.na/用户名/频道名`。它的全站图片搜索当前返回403，频道内搜索接口返回410，所以节点不提供关键词搜索，也不要求登录来绕过限制。切换精选频道会清空已填的自定义链接。

## 图集、下载与缓存

Colossal、Design Milk、Feature Shoot 和 My Modern Met 每张卡片代表一个专题，详情可切换多张图片，并全屏缩放、拖拽查看。“下载图集”保存该专题整组图片，上限60张。只提供单专题下载，不放置容易一次下载数百张的“下载本页”按钮。

Feature Shoot 每页读取24篇专题。My Modern Met 的单篇正文图片较多，每页读取12篇，避免公开接口的大体积响应中途断开；没有有效图片的文章会被过滤，所以页面实际卡片数可能少于12。

Are.na 只提取公开的图片块，排除文本、频道和其他块；每页读取24个原始块，所以可见图片可能少于24张。分页根据频道总块数计算，不会因为某页图片少就提前停止。摄影师和设计师身份不能从收藏者信息推断，卡片使用“收藏：姓名”。

三家均可后台新增缓存100张：

- 四个专题来源缓存100个新专题的封面，以及说明、图集地址等资料，不下载每个专题全部原图。
- Are.na 缓存100张新图片的预览及说明。
- 已有缓存跳过，进度和索引沿用现有机制，重复点击按当前查询条件从断点继续。
- 搜索再次命中已缓存素材时使用本地预览和详情；高清图集仍按需联网下载。

下载仍跟随 ComfyUI 的输出目录：`output/ty-node/ty-image-spider/colossal/`、`designmilk/`、`arena/`。专题图片文件名使用 `专题ID-序号`，Are.na 使用图片块 ID。缓存仍共用 `cache/index.sqlite3`。

重复下载会先解码验证已有文件，有效图片直接复用；损坏文件重新获取。图集部分失败时返回成功保存的路径和失败张数，再次点击下载可补齐缺失项。

## 实现职责

- `PublicJsonClient`：固定来源根地址、JSON读取、响应大小限制、跨域拒绝和带分页响应头的短期缓存。
- `EditorialSource`：每个网站的真实分类、标签和默认值。Design Milk 平面设计对应标签206，摄影对应标签93；不误用分类参数。
- `EditorialProvider`：两个 WordPress 公开专题源的检索和下载策略。
- `editorial_images`：正文静态图片提取，选择 srcset 高清尺寸，忽略脚本与追踪小图，校验域名并去重。
- `ArenaProvider`：独立处理公开频道链接、图片块转换和频道分页。
- `editorial_detail.js`：作品说明与异步更新；图集操作继续复用已有查看器。

来源新增无需改动缓存任务或索引逻辑，原 Civitai、博物馆和电影解析流程保持独立。

## 公开接口与实测依据

- [Colossal](https://www.thisiscolossal.com/) 的 WordPress 公开接口：`/wp-json/wp/v2/posts`、`categories`。
- [Design Milk](https://design-milk.com/) 的 WordPress 公开接口：`/wp-json/wp/v2/posts`、`categories`、`tags`。
- [WordPress REST API 文档](https://developer.wordpress.org/rest-api/reference/posts/)：分类、标签、搜索、分页和嵌入媒体。
- [Are.na](https://www.are.na/) 的公开频道接口：`https://api.are.na/v2/channels/{slug}`，使用 `page`、`per` 和 `direction`。
- [Feature Shoot](https://www.featureshoot.com/) 与 [My Modern Met](https://mymodernmet.com/) 的 WordPress 公开专题接口。

2026-09-20 实测：Colossal 与 Design Milk 首两页均为24个专题，Are.na 默认频道首两页均为23张图片，三家两页间无重复。Colossal 的 `portrait`、Design Milk 的 `poster` 和完整 Are.na 频道链接均成功检索。网站允许一个专题属于多个分类，因此分类切换后首项相同不代表筛选失效，已核对返回记录的分类 ID 和后续条目。

真实下载包含 Colossal 摄影专题477835的10张图、Design Milk 平面设计专题603619的21张图，以及 Are.na 图片块15134574。网页实测完成图集切换、全屏适配和保存路径展示。外部图片偶发断流会记录为失败，不计入新增缓存成功数量。

2.2.0 的三家来源均完成真实新增缓存100项：Colossal失败1项、Are.na失败2项后继续补足，Design Milk 无失败。Are.na 初次用动态缩略图缓存时失败率较高，现已改为浏览器显示轻量缩略图、后台缓存原图，修正后100项任务成功完成。

2.3.0 的 Feature Shoot 与 My Modern Met 也完成真实新增缓存100项：Feature Shoot 无失败；My Modern Met 失败1项后继续补足。Feature Shoot 的 WordPress CDN 预览在 Python 后端返回404，因此该来源通过独立配置缓存可稳定下载的原站封面；My Modern Met 优先从 `srcset` 选择不超过800像素的预览。
