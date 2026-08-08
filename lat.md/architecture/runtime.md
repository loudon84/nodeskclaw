# Runtime Architecture

Runtime 屏蔽 OpenClaw / Hermes 等 Agent 运行时差异，向上提供统一的实例生命周期、消息与 Gene 安装接口。

代码集中在 `nodeskclaw-backend/app/services/runtime/`。CODEMAP：`.cursor/context/runtime-codemap.md`。协作消息见 [[domain/collaboration]]。

## Compute Providers

计算 Provider 抽象 Pod/容器/进程的创建销毁与资源挂载；生产默认 K8s，开发可用 Docker，调试可用 Process。

选型由实例 `compute_provider` 决定（[[decisions/compute-providers]]）。K8s 路径负责 Namespace、Deployment、Service、Ingress、PVC/NFS。

## Adapters And Gene Install

Runtime adapter 对接外部 Agent 平台；Gene 安装另有 `GeneInstallAdapter` 族（OpenClaw / Hermes / noop）。

安装失败必须可观测（状态与日志），禁止静默跳过。NFS 场景下容器绝对路径不可直接当本机路径使用。

## Lifecycle

实例生命周期：PENDING → DEPLOYING → INITIALIZING → RUNNING → STOPPING / DESTROYING / FAILED。

钩子点（pre-deploy、post-deploy、pre-stop、post-destroy）供 EE 与自定义逻辑挂载。Companion 是每实例运维代理；故障由 `failure_recovery` 处理。

## Channel Plugins

Channel 插件是独立 TypeScript 包（`openclaw-channel-*`），负责协议侧消息收发，不并入 Portal/Backend 构建。

改插件时同步检查 runtime adapters 与 Backend 的 `PLUGIN_FILES` 等分发白名单，避免新文件未复制到实例。

## External Runtimes

`openclaw/` 等外部源码默认不读；判断 DeskClaw 内部行为时优先读本地 `openclaw/src/`，再用 kubectl 验证运行态。

禁止仅凭 UI 或「框架常见做法」断言 skill 已生效；应追到 system prompt / session 层并用运行证据确认。
