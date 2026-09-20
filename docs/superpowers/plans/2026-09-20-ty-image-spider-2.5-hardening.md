# TY Image Spider 2.5.0 加固实施计划

批准范围见 [设计规格](../specs/2026-09-20-ty-image-spider-2.5-hardening-design.md)。用户授权在当前目录 main 直接执行，不创建 worktree，不推送、不创建远端 Release。

## 执行顺序与验收

1. **版本与展示契约**：新增不可变 ProviderPresentation；18个来源声明分组、标签、顺序与可见性，小红书保持隐藏；统一运行时 USER_AGENT 与各版本清单。测试序列化、必填字段、隐藏行为及版本一致性。
2. **前端描述符驱动**：来源分组、角标、详情名称由后端描述符驱动，缺字段兼容回退；删除重复的中心映射。使用真实描述符快照验证导航、排序与详情。
3. **下载策略**：各 Provider 或 EditorialSource 自持独立策略；通用下载器通过策略校验ID、URL、编码和最终域名；ImageReaderRegistry只派发已绑定读取器。验证非法主机、ID、端口、图片格式与落盘路径。
4. **并发缓存**：分离 CacheRequest、CacheJobRunner、CacheJobService；3项容量、同条件409去重、独立取消、64项/24小时终态清理；素材级锁避免重复计数。前端按来源分别轮询，删除节点后忽略迟到结果。测试并发、指纹、取消、进度断点及异常回滚。
5. **JSON正文限制**：独立解析器统一限制1MiB，覆盖Content-Length和chunked，不依赖ComfyUI全局配置；400格式错误，413过大正文，禁止回显内容。通过真实aiohttp测试服务器验证边界。
6. **开源治理**：MIT、贡献指南、安全报告流程、Contributor Covenant 2.1中文、逐来源权利、完整第三方许可与兼容矩阵；README改为独立安装与贡献步骤。文档改动使用人工审阅与链接检查，不新增存在性测试。
7. **CI矩阵**：Python Windows/Ubuntu × 3.10/3.13；Node 20.19.0/22.12.0；最小contents:read权限；本地可运行全部质量命令。Node测试入口显式展开文件，兼容Windows与旧Node版本。未实际执行的Linux/远端作业不得写成通过。
8. **可复现安装包**：读取指定Git提交对象，采用运行时文件白名单，排除开发资料；验证版本、敏感路径与凭据格式；固定排序、时间、权限、归档方式；输出ZIP和外部SHA256。测试工作区漂移、两次构建一致、敏感文件拒绝及只检查模式。最终提交后重新构建，不能把自身哈希写回归档内文档。
9. **交付验证**：完整质量门禁、独立环境兼容验证、代码独立审查及必要修复；8188队列空闲后完成导航、分页、提示词详情、下载、缓存隔离与跨工作流输出隔离验收。补充实际证据，提交版本、创建本地v2.5.0标签，从最终提交重复构建并校验。

## 网络与诊断补充

审计所有客户端的有限超时、产品标识与异常映射。使用窄职责重试策略处理幂等读取的网络故障、429和5xx；最多3次，Retry-After支持秒与日期并限制30秒；不重试坏JSON、认证和参数错误。来源解析、错误文案和下载策略留在各自模块。技术日志仅记录错误类别与源码位置，不写上游异常文本或局部变量。下载器保留有限超时的单次请求，避免图集自动重试放大带宽。

## 常用验证命令

```text
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy --explicit-package-bases --follow-imports=skip src
python -m pytest -q
npm test
npm run format:check
node scripts/check_js.mjs
python -m compileall -q src
git diff --check
python scripts/build_release.py --check
python scripts/check_quality.py
```

## 安全约束

不读取、打印或提交本地`.local/tmdb.json`。不操作8189。重启8188前重新确认Running=0且Pending=0；保留实际启动命令，只重启该进程。下载和缓存根目录跟随ComfyUI output配置。实机日志和截图保存在被Git忽略的`.artifacts/2.5.0/`；发布包不包含它们。
