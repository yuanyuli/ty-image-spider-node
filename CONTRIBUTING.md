# 参与开发

请先阅读 [行为准则](CODE_OF_CONDUCT.md)；安全问题请走 [私密报告流程](SECURITY.md)。提交的代码按项目 MIT 许可证分发，请保留引用代码的第三方许可与署名。

## 独立开发环境

克隆源码仓库，在仓库根目录执行（不要使用 ComfyUI 的嵌入式 Python 安装开发依赖）：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm ci
python scripts/check_quality.py
```

Linux 使用 `python3 -m venv .venv` 和 `source .venv/bin/activate`，后续命令相同。开发需要 Python 3.10+、Git 和 Node 20.19+ 或 22.12+；用户安装节点不需要 Node。安装包不含开发文件，请从源码仓库贡献。

## 新增来源

1. 在 `providers/` 新建来源 Provider 或编辑类来源的独立配置。复用公共 HTTP 读取器与图片解析，不在通用服务增加来源名称分支。
2. 声明 `ProviderDescriptor` 的筛选、能力和 `ProviderPresentation`：分组、顺序、短标记、详情名称、可见性。来源 ID 一经发布保持稳定。
3. 在来源模块持有 `DownloadPolicy`，限制 HTTPS 主机、素材 ID、URL 编码规则；不接受用户任意 URL。来源特有流程留在该来源模块。
4. 在 `bootstrap.py` 注册实例及其图片读取器。支持缓存时确认详情、预览读取器和下载能力均已注入。
5. 用固定 fixture 和注入式 HTTP 替身验证分页、空结果、异常、提示词状态、非法域名和下载。不要让 CI 请求真实站点。
6. 更新 `tests/fixtures/provider_descriptors.json`，运行描述符契约测试及完整质量门禁。增加来源说明、权利说明与变更记录。

`services/` 负责用例编排，Provider 负责来源差异；缓存任务生命周期和单任务执行器独立。新增前端行为以小模块组合，展示标签从描述符读取。

## 提交与验收

PR 说明具体问题、修复后的行为、测试命令与结果；UI 变化附截图，外部请求变化注明有限超时和重试边界。修复复杂行为先写可复现测试；文档和低风险格式改动不写存在性测试。

不得提交 `.local/`、访问令牌、Cookie、输出图片、缓存、个人绝对路径或带签名的笔记链接。不要在 Issue 或测试 fixture 放真实凭据。修改 Python 后重启测试 ComfyUI；重启前确认运行和等待队列均为空。

发布前运行 `python scripts/build_release.py --check`，提交后以目标提交构建 ZIP；重复构建应产生相同 SHA256。最终验证记录和兼容边界见 [兼容性](docs/compatibility.md)。
