# 模块职责边界

本文定义 TY Image Spider 的稳定依赖方向。新增功能必须放入拥有该职责的目录，禁止通过通用模块识别具体来源来绕过边界。

## `domain/`

- 负责：不可变领域值、序列化契约、错误和 Provider 协议。
- 允许依赖：Python 标准库及同目录模块。
- 禁止依赖：基础设施、具体 Provider、API、应用装配、ComfyUI 运行时。
- 扩展方式：先增加与来源无关的字段或协议，并用往返测试证明兼容旧数据。

## `infrastructure/video/`

- 负责：视频 URL 策略、文件签名、流式写入、原子替换和已有文件复用。
- 允许依赖：领域模型、Python 标准库和项目通用的低层 HTTP 抽象。
- 禁止依赖：具体 Provider、API 路由、应用装配和 UI。
- 扩展方式：通过策略对象注入来源主机和素材 ID 规则，不判断具体 Provider ID。

## `providers/videos/`

- 负责：视频来源的 Client、纯数据归一化器和 Provider 编排。
- 允许依赖：领域模型、共享基础设施、本来源子包及 `videos/shared/` 的纯辅助函数。
- 禁止依赖：API、应用服务定位器、ComfyUI 适配器，以及其他具体视频来源子包。
- 扩展方式：每个来源新增独立子目录并实现完整 `AssetProvider` 契约，再在应用工厂注册。

## `web/features/video/`

- 负责：视频资源选择、卡片装饰和播放器生命周期。
- 允许依赖：`web/core/` 及稳定的通用 UI 接口。
- 禁止依赖：`web/app/`、后端请求、工作流持久化和具体来源 ID。
- 扩展方式：依据 `kind`、`media` 和能力字段组合行为。

## `web/ui/`

- 负责：来源无关的界面组件和 feature 组合。
- 禁止行为：识别 `prelinger`、`commons-video`、`nasa-video` 等具体来源并分支。

后端依赖方向固定为 `app/api -> services -> provider protocols/domain`。具体 Provider 可以依赖 `domain + infrastructure`；基础设施只能向内依赖领域。前端依赖方向固定为 `app -> ui/features -> core`。
