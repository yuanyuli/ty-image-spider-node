# TY Image Spider

TY Image Spider 是一个零输出端口的 ComfyUI 素材浏览节点。它在节点内完成图片检索、详情查看与下载，不向下游节点传递图片，也不会触发 ComfyUI 工作流执行。

## 支持的素材源

| 素材源 | 搜索与筛选 | 详情 | 下载 | 额外依赖 |
| --- | --- | --- | --- | --- |
| `civitai.com` | 关键词、周期、排序、SFW、标签、提示词、游标分页 | 提示词、模型、LoRA、workflow、metadata | 单图与本页批量下载 | 可选 Civitai API Key |
| `civitai.red` | 与 `civitai.com` 相同 | 与 `civitai.com` 相同 | 单图与本页批量下载 | 可选 Civitai API Key |
| 小红书 | 关键词、排序、图文类型、发布时间；支持完整笔记链接 | 正文、互动数据、完整图集 | 一次下载整篇笔记的全部图片 | OpenCLI >= 1.8.8、Chrome 扩展、已登录的小红书会话 |
| 本地历史 | 文件名或内嵌提示词、提示词筛选、分页 | 文件信息与图片 metadata | 文件已经位于本地，无需重复下载 | 无 |

节点会同时读取新版 `output/ty-image-spider/` 与旧版 `output/ty-node/` 历史。各素材源由独立 Provider 实现；新增来源不需要修改现有来源的请求与下载流程。

## 安装

将本仓库放入 ComfyUI 的 `custom_nodes` 目录，然后安装运行时依赖并重启 ComfyUI：

```powershell
cd <ComfyUI>\custom_nodes\ty-image-spider-node
<ComfyUI Python> -m pip install -r requirements.txt
```

本地工作区开发使用 junction，不复制源码：

```powershell
cmd /c mklink /J "C:\path\to\ComfyUI\custom_nodes\ty-image-spider-node" "C:\path\to\ty-image-spider-node"
```

安装后在 `TY Utils/素材浏览` 分类中添加 `TY Image Spider · 素材浏览`。该节点没有输出端口，所有浏览与下载操作都在节点界面内完成。

## Civitai 配置

公开图片通常不要求凭据。需要 API Key 时，在启动 ComfyUI 前设置环境变量：

```powershell
$env:CIVITAI_API_KEY = "你的 API Key"
```

API Key 只通过 `Authorization` 请求头发送，不会放入 URL、缓存、节点属性或工作流。

## 小红书配置

小红书是可选素材源。它不可用时，Civitai 与本地历史仍可正常使用。

1. 安装 Node.js `>= 20.18.1`。
2. 安装 OpenCLI >= 1.8.8。npm 当前公开的最新版仍为 `1.8.7`，请从已验证的上游提交 `8271afc` 构建安装：

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

关键词搜索会先调用 OpenCLI 官方 `xiaohongshu search` 适配器，再从同一个持久会话只读提取卡片封面。完整笔记链接必须包含 `xsec_token`；`xhslink.com` 短链接也会进入单篇流程。节点不会模拟点赞、收藏、评论或发布操作。

## 界面与下载

- 顶部来源控件切换 Civitai、小红书和本地历史；筛选项由各 Provider 的描述符动态生成。
- 画廊在窄节点中显示两列，在宽节点中显示三列；详情弹窗支持图集缩略图、提示词复制和来源跳转。
- Civitai 图片保存到 `output/ty-image-spider/civitai/`。
- 小红书整篇图片保存到 `output/ty-image-spider/xiaohongshu/<note-id>/`。
- 下载器校验来源域名、重定向、响应大小、输出路径和实际图片格式。

## 隐私边界

小红书 Cookie 由 OpenCLI 与 Chrome Browser Bridge 管理，本节点不读取或保存 Cookie。带 `xsec_token` 的签名链接和小红书搜索结果不会写入工作流、节点持久属性或持久缓存，也不会写入 `localStorage`。工作流只保存当前来源、不含凭据的筛选条件与查询摘要。

Civitai API Key 不会写入工作流。HTTP 错误响应会隐藏常见的 key、token、secret、cookie 和 authorization 值。

## 开发与测试

项目使用总工作区的 uv 虚拟环境：

```powershell
cd C:\path\to\source
uv sync
uv run --project . python ty-comfyui-utils-node\ty-image-spider-node\scripts\check_quality.py
```

也可以在节点目录运行分项检查：

```powershell
& '..\..\.venv\Scripts\python.exe' -m pytest -q
npm install
node --test tests/*.test.mjs
```

测试使用固定 fixture、注入式 HTTP/进程替身和临时目录，不依赖 Civitai 或小红书实时网络。

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

检查 ComfyUI 后端日志与 `output/ty-image-spider/`。节点只返回本次新增且通过 Pillow 校验的图片，HTML、文本、越界路径和非可信域名响应会被拒绝。

## 第三方许可

- [OpenCLI](https://github.com/jackwener/opencli) 使用 Apache License 2.0。本项目只通过用户安装的 `opencli` 命令调用它，不打包其源码或浏览器扩展。
- [Pillow](https://python-pillow.org/) 用于图片格式与 metadata 校验。
- [Lucide](https://lucide.dev/) 图标路径用于界面按钮，遵循 ISC License。
- `jsdom` 与 Prettier 仅用于前端开发和测试，不进入 ComfyUI 运行时。
