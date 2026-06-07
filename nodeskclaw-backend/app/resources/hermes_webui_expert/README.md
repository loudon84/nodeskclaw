# Hermes WebUI Expert 资源包

内置 Hermes 专家服务（`hermes-webui-expert` runtime）的 Docker 构建模板、专家目录模板与默认技能包。

## 目录结构

- `Dockerfile` — 专家镜像构建骨架（通过 build args 引用私有仓库，不含凭据）
- `docker-compose.template.yml` — Compose 参考模板
- `expert-templates/base/` — 所有专家实例共享的基础目录
- `expert-templates/writer/`、`expert-templates/finance/` — 专家模板 overlay
- `skill-bundles/` — 实例级技能内置包（按 bundle 名分组）

## 占位符

模板文件支持 `__PROFILE__`、`__EXPERT__`、`__INSTANCE_ID__`、`__INSTANCE_NAME__`、`__HINDSIGHT_API_URL__`、`__HINDSIGHT_BANK_ID__` 等占位符，由 `ExpertTemplateService` 在部署前注入。

## 本地开发

专家实例部署依赖 Docker 集群与 `HERMES_EXPERT_*` 配置项，详见 `nodeskclaw-backend/README.md`。
