# CE EE Split

版本能力由 `FeatureGate` 决定：环境变量 `NODESKCLAW_EDITION` 优先，否则检测 `ee/` 目录是否存在。

`edition=ee` 启用全部 EE feature；`ce` 仅 CE。EE 清单来自 `features.yaml`，并可与 `ee/features.yaml` 合并。

## Implementation

实现入口：[[nodeskclaw-backend/app/core/feature_gate.py#FeatureGate]]。业务代码通过 `is_enabled(feature_id)` 判断，禁止散落硬编码 edition 字符串。

默认不读取 `ee/`；未明确要求时不要把 EE 实现复制进公开文档或 CE 路径。

## Why

开源 CE 与私有 EE 同仓并存时，用目录探测 + 清单合并，避免两套后端分叉，同时保证 CE 发行不含企业能力。
