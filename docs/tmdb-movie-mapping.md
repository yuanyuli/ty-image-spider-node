# 中文电影查询与 FilmGrab 映射

FilmGrab 提供电影静帧，TMDB 提供中文名、原名、上映年份、导演等身份资料。配置后，可查询内置精选片单以外的中文电影名，例如“低俗小说”。TMDB 能识别电影不代表 FilmGrab 一定收录了该电影的静帧。

## 本地配置

在节点根目录创建 `.local/tmdb.json`，参考根目录的 `tmdb.example.json`：

```json
{
  "read_access_token": "在这里填写 API Read Access Token"
}
```

填写 TMDB 的 **API 读取访问令牌**，不需要填写短版 API Key。保存后再次搜索即可，修改令牌无需重启。首次安装本功能的 Python 代码需要重启 ComfyUI，再刷新页面。

也支持环境变量 `TMDB_READ_ACCESS_TOKEN`，其优先级高于文件。运行中的 ComfyUI 只能读取启动时继承的环境变量，因此修改系统环境变量后需要重启。凭据文件应保存在 ComfyUI 后端所在电脑，不是远程浏览器电脑。

`.local/` 已加入 Git 忽略规则。令牌仅由后端通过 Authorization 头发送给 TMDB，不进入节点属性、浏览器或工作流。未配置时，内置精选片单仍可使用。

## 使用方法

1. 在节点中选择 FilmGrab，输入中文电影名，点击“搜索”。可在片名后补年份，例如“沙丘 2021”。
2. 首次查询会列出电影候选，按中文名、原名、年份和海报选择具体电影。
3. 后端根据英文名、原名及别名查找 FilmGrab。仅在片名与上映年份一致、且导演无冲突的唯一候选上自动建立映射。年份缺失、存在冲突或有多个候选时，需要再核对来源条目。
4. 确认后显示电影静帧，再次搜索相同关键词直接复用本地映射。
5. 如需切换同名电影版本，输入片名并点击“查找电影版本”。取消选择会保留当前已显示的图片。

没有可靠来源匹配时，节点会说明已识别的电影及年份，不自动替换成其他电影。FilmGrab 目录每个检索词最多读取100个结果，因此“暂未找到可靠匹配”不等于该站绝对未收录。

“新增缓存100张”沿用已确认的电影映射；如果尚未选择电影，先搜索并确认，再启动缓存。仍按新增素材计数，跳过已缓存项，电影静帧不足100张时按实际数量结束。

## 本地资料与图片缓存

相对于 ComfyUI 的 `output`：

| 内容 | 路径 | 行为 |
| --- | --- | --- |
| 电影身份及来源映射 | `ty-image-spider/.cache/movie-mappings.sqlite3` | 持久保存，重启后复用；可通过“查找电影版本”更新 |
| TMDB 资料 | `ty-image-spider/.cache/tmdb/` | 24小时 |
| FilmGrab 电影目录 | `ty-image-spider/.cache/film-directory/` | 1小时 |
| FilmGrab 静帧文章 | `ty-image-spider/.cache/filmgrab/` | 5分钟；来源失败时可回退已有数据 |
| 图片预览与素材索引 | `ty-node/ty-image-spider/cache/` | 批量缓存及浏览复用；原图按需下载 |
| 手动下载静帧 | `ty-node/ty-image-spider/filmgrab/` | 下载完成后界面显示完整路径 |

电影映射只保存电影资料、来源条目与查询别名，不包含令牌。已有映射不需要再次请求 TMDB，但没有图片缓存时仍需访问 FilmGrab。

## 费用与署名

TMDB 的非商业 API 使用免费，需要遵守署名及使用条款；商业使用请向 TMDB 确认许可。节点的“TMDB 配置与鸣谢”包含官方 Logo、链接与规定声明：

> This product uses the TMDB API but is not endorsed or certified by TMDB.

- [API 设置与凭据](https://www.themoviedb.org/settings/api)
- [官方 FAQ](https://developer.themoviedb.org/docs/faq)
- [Logo 与署名要求](https://www.themoviedb.org/about/logos-attribution)

电影静帧来自 FilmGrab，其版权与使用范围仍由原始权利人决定。

## 验证记录（2026-09-19）

- 使用实际本地凭据查询“低俗小说”：TMDB 680，Pulp Fiction，1994，Quentin Tarantino；FilmGrab 对应文章7882，标题、年份与导演一致。
- 通过应用服务执行候选选择后返回24张首屏静帧和下一页游标；重新创建服务后，相同中文关键词复用持久映射，无需重新选片。
- 实际后台缓存共65张：首轮新增63张、2张网络读取失败；再次执行新增2张、跳过63张、失败0张，后续搜索返回本地预览地址。
- 149项 Python、56项前端测试通过；Ruff、Prettier与差异空白检查通过。Mypy仍有既有4处类型注解问题（节点适配器3处、小红书锁协议1处），本次新增电影模块无类型错误。
- 2026-09-20 补充验收：空闲时已重启 ComfyUI，真实页面完成“查找电影版本”→选择《低俗小说》→24张图片加载，下一页从第25张开始、上一页恢复第1张。取消候选框保留24张图片，再次搜索直接复用映射，并保存同一工作流。既有4处类型问题已在2.0.0固化时修复，全量44个模块类型检查通过。
