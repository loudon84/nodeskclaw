# Compute Providers

实例部署按 `compute_provider` 分发到 K8s、Docker 或本地 Process，向上暴露同一生命周期接口。

生产默认 K8s（VKE amd64）；Docker 便于开发绑定已有容器；Process 用于轻量调试。抽象位于 `app/services/runtime/compute/`。

## Constraints

Docker 镜像构建/拉取必须 `--platform linux/amd64`。K8s 操作必须显式 `--context`，并同时确认 namespace（staging / prod）。

禁止假设 current-context；禁止把「确认了集群」当成「确认了环境」。见 [[architecture/runtime]]。

## Why

三 Provider 让同一套 Instance API 覆盖生产编排与本地开发，避免为调试再维护平行部署协议。
