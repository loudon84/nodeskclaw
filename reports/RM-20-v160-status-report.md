# RM-20 / SKILL-RUN-CONTRACT v1.6.0 进展报告

日期：2026-09-12  
范围：当前 APPROVED PRD、canonical Plan、产物闭环边界、v1.6.0 待办。  
本报告不连接 live Hermes / MinIO。

---

## 1. 当前进行的 PRD 与实现 Plan

| 项 | 路径 | 状态 |
|----|------|------|
| Architecture Source | `docs_agent/architecture/AD-SKILL-AGENT-V16.md` `@1.9.0` | APPROVED |
| Stage PRD | `docs_agent/prd-v1.6.20-skill-run-v160-rich-runtime-events-and-artifacts.md` | APPROVED（`approved_at`: 2026-09-11T23:50:29+08:00；Review PASS） |
| Canonical Plan | `.cursor/plans/rm-20_skill-run-v160-rich-runtime-events-and-artifacts.plan.md` | Plan Review PASS；`commit_policy: post_review`；`plan_id: RM-20` |
| Plan Review | `docs_agent/reviews/rm-20-rich-runtime-events-plan-review.md` | PASS |
| Roadmap Item | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-20 | **仍为 `IN_PRD`**（未 DONE） |
| 目标合同 | Public `SKILL-RUN-CONTRACT v1.6.0`（tag `skill-run-contract-v1.6.0`） | **未打 tag** |
| Hermes 外依赖交付包 | `reports/hermes-agent/`（插件 + MinIO/S3 模式） | 供实例手工安装；**不是** RM-20 Todo 写集 |

PRD 目标（本仓 Provider）：在不改写 v1.2.1～v1.5.0 的前提下，发布累积 Public Bundle，使仓外 Work 可消费：

- 安全 `tool.call.arguments`
- 独立 `tool.result`
- Runtime 声明输出经 Agent 持久化后的可下载 Artifact

Depends On：RM-19 `DONE`。不依赖 RM-08，不并入 RM-09。仓外 Work UI / consumer-lock **不是** 本仓 DONE。

---

## 2. Plan 已完成的 Todo

Canonical Plan frontmatter（Cursor Todo 投影）当前均为 `completed`：

| Todo | 内容 | Plan status |
|------|------|-------------|
| T1 | Agent `tool.call` arguments + `tool.result` + first-pass sanitizer（C01, C02, C03） | completed |
| T2 | Agent / Backend v1.6 event schema（C04） | completed |
| T3 | Public SSE projection 与 `contract_version` 真值（C05, C10） | completed |
| T4 | Runtime output ingest 与 required artifact barrier（C06, C07） | completed |
| T5 | v1.6.0 Bundle generate/check 与两提交发布语义（C08, C09） | completed |
| T6 | Live conformance runner 与 LAT（C11, C12） | completed |

约束（治理事实，不是「代码已上生产」）：

- Todo `completed` **不等于** `IMPLEMENTED_AND_PROVEN`
- 本地 blocking 单测/文档类 Verification 多数曾 PASS（V01–V09、V12–V14、V16）
- **V10 LIVE FAIL**（缺多文件 public artifacts）
- **V11、V15 无 ledger 记录**（release check / tag tree）
- implementation commit A、Bundle-only commit B、annotated tag **尚未按两提交模型完成**

因此：实现切片在 Plan 里已勾完，**发布与 live 证明未完成**。

---

## 3. 产物闭环：Hermes 插件负责上传；本仓只对接合同标准

### 3.1 分工（事实）

| 角色 | 负责 | 不负责 |
|------|------|--------|
| Hermes 插件 `hermes-output-artifacts`（实例侧手工安装） | 收集本 run 文件 → 上传文件服务器 → 终态 `GET /v1/runs/{id}` **merge 绝对 URL `output_refs`** → upload+refs 完成前不得成功 `completed` | 不写 NoDeskClaw Public 合同、不给 Portal 直链 |
| `nodeskclaw-agent` | 按 v1.6.0 **ingest 标准**：读取 `output_refs` → 授权 GET 字节 → 既有 `store_artifact_bytes` / StoragePort → `artifact.persisted`；required 失败 `ARTIFACT_PERSIST_FAILED` | **不**扫描 Hermes workspace；**不**把文件服务器 URL 当作 Public 下载地址 |
| `nodeskclaw-backend` | Public list/download 鉴权代理：`GET /api/v1/runs/{run_id}/artifacts` 与 `.../artifacts/{artifact_id}/download` | 不把 MinIO/文件服务器当员工产物 SoT |
| 仓外 Work / 前端 | 消费 Bundle 后的 `artifact_id` + run 作用域下载 | 不是 RM-20 Provider DONE |

Hermes 插件解决的是 **Runtime 如何声明可拉字节**（产物闭环的南向）。本仓 RM-20 只保证 **合同与 ingest/投影标准**，不替代实例上的 MinIO/插件安装。

### 3.2 约定的 Hermes 上传与 `output_refs`

实例侧指定文件服务（你提供的地址）：

- 上传目标：`http://192.168.102.247:9100`
- 专用存储：全体 agent runtime 使用独立 bucket / 前缀（`agent-runtime-export`，不要复用工作区/附件存储）
- Hermes Native 终态 status 合并 **绝对 URL** `output_refs`，例如：

```json
{
  "status": "completed",
  "output_refs": [
    {
      "name": "report.md",
      "content_type": "text/markdown",
      "url": "http://192.168.102.247:9100/agent-runtime-export/<run_id>/report.md",
      "required": true
    }
  ]
}
```

（若启用 presigned GET，`url` 带签名查询串，仍必须是绝对 `http(s)`。）

Spike 已证明：当终态含 **公网绝对 URL** refs 时，Agent ingest PASS。当前缺口是 live 多文件 + 内网拉取策略，不是本仓再发明第二条产物协议。

### 3.3 本仓对接标准（Agent → 前端）——与「把 9100 拼给前端」不一致

**已批准合同与现码事实：`nodeskclaw-agent` 不会把 `http://192.168.102.247:9100` 拼接后交给前端。**

正确链路：

```text
Hermes 上传到 http://192.168.102.247:9100/...
  → Native GET /v1/runs/{id} 带 output_refs.url（绝对地址，供 Agent 内部 GET）
  → nodeskclaw-agent _persist_declared_outputs：拉取字节 → store_artifact_bytes
  → Public：artifact_id + artifact.persisted（无文件服务器 download_url）
  → 前端/Work：鉴权下载
       GET /api/v1/runs/{run_id}/artifacts/{artifact_id}/download
```

依据：

- PRD：公共 descriptor **无永久 `download_url`**；下载走既有 run-scoped endpoint
- Agent `public_artifact_persisted_event` / `artifact_persisted_payload` 只暴露 `artifact_id`、name、size、checksum 等
- Live runner 若 artifacts list 出现 `download_url` 直接 FAIL
- 内网 `192.168.*` 默认 SSRF 拦截；Agent 若要 GET `http://192.168.102.247:9100`，必须另加 **origin allowlist**（见 `reports/hermes-agent/AGENT-SIDE-REQUIREMENTS.md`）

若把 `192.168.102.247:9100` 拼给前端：浏览器通常不可达内网 MinIO，且会泄漏文件服务器地址，**违反 v1.6.0 Public 合同**。那不是本仓要对齐的标准。

---

## 4. v1.6.0 合同待完成事项

Todo 勾完 ≠ 合同已发布。阻塞项：

### 4.1 Live 证明（V10 / AC-16 / DOD-05）

`python tools/acceptance/run_rm20_live_rich_runtime_events.py` 必须 FRESH PASS（`user_jwt`，禁止 mock-only）：

1. 员工路径 `contract_version=1.6.0`
2. `tool.call(started)` 带安全 `arguments`；terminal 省略 `arguments`
3. 每个 terminal call 恰好一个 `tool.result`
4. **≥2 个** public artifacts：可按 `artifact_id` 下载，checksum 一致，list **无** `download_url`
5. `RM20_FAIL_ARGUMENTS` 第二条 run：`FAILED` + `ARTIFACT_PERSIST_FAILED`

外依赖：Hermes 插件 + `192.168.102.247:9100` 上传与 refs；必要时 Agent allowlist。缺工具事件则 `VERIFICATION_BLOCKED`，不得假 PASS。

### 4.2 不可变 Bundle 发布（AC-10～13 / DOD-04 / DOD-06）

1. **V11**：`contracts.py check --family skill-run --version 1.6.0 --release`
2. **Commit A**：Agent/Backend 行为；manifest `backendCommit` / `releaseCommit` 均指向 A
3. **Commit B**：仅 `contracts/skill-run/v1.6.0/`
4. Annotated tag `skill-run-contract-v1.6.0` 指向 B（禁止 `-f`）
5. **V15**：`check --release --tag skill-run-contract-v1.6.0`（tag tree：A 祖先 B，A..B 仅 Bundle）

当前：**无** `skill-run-contract-v1.6.0` tag；V11/V15 无 PASS 记录。

### 4.3 治理收口

1. Implementation Review FRESH PASS
2. V01–V16 blocking Verification FRESH PASS + Evidence Manifest  
   （提交后 fingerprint 变化须重跑，不能只吃旧 ledger）
3. **独立** Roadmap commit：RM-20 `IN_PRD` → `DONE`（不得与 implementation / Bundle 打成同一 commit）

### 4.4 明确不做

- Portal / 仓外 Work UI / 写入 `consumer-lock.json`
- 第二套 Event Store / SSE / artifact store
- 改写已发布 v1.2.1～v1.5.0
- 把文件服务器 URL 作为 Public 下载面

### 4.5 建议顺序

```text
Hermes 插件 → 上传 192.168.102.247:9100 且终态带 output_refs
  → Agent 能 GET 该 origin（必要时 allowlist）
  → V10 live PASS（工具事件 + 多文件 artifact_id 下载 + required-fail）
  → Review + 全量 Verification FRESH
  → commit A → commit B → tag v1.6.0
  → V11 / V15 PASS
  → Roadmap DONE
```
