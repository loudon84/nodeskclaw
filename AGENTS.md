# AGENTS.md - NoDeskClaw 开发指南

## 项目概述

NoDeskClaw 是 DeskClaw 实例可视化管理系统（社区版 / CE），通过 Web 界面管理 K8s 集群上的 DeskClaw 实例。本仓库为开源版本，下载后不再引用 `ee/` 企业版模块。

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + PostgreSQL |
| 用户门户 | Vue 3 + Vite + TypeScript + Tailwind CSS + Three.js |

## 产品称呼

- 对外发布、群聊公告、Release Note、客户沟通和文档摘要中，首次出现必须称为“DeskClaw 团队版”。
- 禁止写成“个人版”，也禁止省略“团队版”导致对外产品定位错误。
- 技术上下文中可使用 DeskClaw、NoDeskClaw、CE、EE 等名称，但不得影响对外称呼的一致性。

## 构建/测试命令

### 后端（nodeskclaw-backend）

```bash
cd nodeskclaw-backend
uv sync
uv run uvicorn app.main:app --reload --port 4510
uv run pytest                              # 运行全部测试
uv run pytest tests/test_xxx.py            # 运行指定文件
uv run pytest tests/test_xxx.py::test_func # 运行指定函数
uv run ruff check .                        # Lint 检查
uv run ruff check --fix .                  # 自动修复
```

### 前端（nodeskclaw-portal）

```bash
cd nodeskclaw-portal
npm install
npm run dev
npm run build
vue-tsc -b                                # 类型检查
```

## 代码风格

### 命名约定

| 类型 | 规则 |
|------|------|
| 组件文件 | PascalCase（如 `UserProfile.vue`） |
| 工具函数 | camelCase（如 `useAuth.ts`） |
| 类型/接口 | PascalCase（如 `UserInfo`） |
| 常量 | UPPER_SNAKE_CASE |
| Python 模块/函数 | snake_case |
| Python 类 | PascalCase |
| 布尔变量 | `is_`、`has_`、`can_` 前缀 |
| 通用 | 禁止中文命名、禁用缩写（API/URL/ID/DB 除外） |

### Emoji 禁止

禁止使用 emoji，使用 `lucide-vue-next` 图标库。

```vue
<!-- 禁止 -->
<span>🔍 搜索</span>
<!-- 正确 -->
<Search class="w-4 h-4" />
```

### 语言表达

所有专业术语、变量名、配置项后面必须跟中文说明。

- `IMAGE_REGISTRY`（镜像仓库地址）
- SSE（服务端推送）、KubeConfig（集群连接凭证）

### 软删除规则

所有数据删除必须使用逻辑删除，严禁物理删除。

- 删除操作设置 `deleted_at = func.now()`
- 所有查询过滤：`Model.deleted_at.is_(None)`
- 禁止 `db.delete()` 和原生 `DELETE FROM`
- 唯一约束使用 Partial Unique Index：`Index(..., unique=True, postgresql_where=text("deleted_at IS NULL"))`

### Alembic 迁移规则

新增或修改数据模型后，必须通过 `alembic revision --autogenerate` 生成迁移文件，作为同一个 commit 的一部分。

- 禁止手写 revision ID — 必须由命令自动生成
- 禁止只加 Model 不加迁移 — 启动时走 `alembic upgrade head`，缺迁移 = 表不存在 = 启动崩溃
- 生成后 Review：autogenerate 无法检测列重命名，Partial Unique Index 需确认

### Docker 镜像架构

所有 Docker 操作必须显式指定 `linux/amd64` 平台。

```bash
docker build --platform linux/amd64 -t my-image:latest .
```

### 导入完整性

在函数/代码块内使用模型或工具类时，必须确保该作用域内有对应的 import。不要假设外层已导入。

### i18n 规则

新增或修改用户可见文案时，必须同步接入 i18n 词条，不允许新增硬编码中文 UI 文案。

- 统一使用小写点分级：`errors.auth.token_invalid`
- 一律使用命名参数：`t('errors.instance.not_found', { name })`
- 错误响应必须包含 `error_code` + `message_key` + `message`

## 错误处理原则

### 必须遵循

- **先查证再开口**：不确定的事情先查证，查不到就说查不到
- **明确依据来源**：回答时说明依据（哪个文件、哪行代码）
- **不知道就是不知道**：列出做了哪些尝试，最终为什么仍不确定
- **出错就认**：说错了直接承认

### 严禁

- 禁止猜测性断言（"应该是这样"）
- 禁止想当然（"一般项目都这样"）
- 禁止半吊子回答（查一半就急着回答）
- 禁止信息编造

## K8s/DeskClaw 排查

**必须先通过 kubectl 实际查看集群状态，再作判断。**

排查流程：
1. `kubectl get pods -n <namespace>` — Pod 状态
2. `kubectl describe pod <pod> -n <namespace>` — 详情和 Events
3. `kubectl logs <pod> -n <namespace>` — 日志

### 多集群上下文选择

执行 kubectl 前必须确认目标集群：
- 先 `kubectl config get-contexts` 确认上下文
- 每条命令显式指定 `--context <name>`
- 禁止盲用 current-context

## 问题处理流程

发现问题后不要立即动手修，先报告给用户，等用户确认方案后再改。

流程：
1. 明确描述问题、影响范围、根因分析
2. 提出建议修复方案（可多个），说明优缺点
3. 等待用户确认
4. 确认后执行修复

例外（可直接修）：明显拼写错误、导入缺失、lint 错误、用户明确说"直接修"。

## Git 规范

### 分支命名

格式：`<type>/<kebab-case-description>`

- 前缀：`feat`、`fix`、`refactor`、`chore`、`docs`、`perf`、`test`、`build`
- description 使用 kebab-case，2-5 个词，描述分支做什么
- 特殊分支：`main`、`release-<version>`

```
feat/operation-audit
fix/deploy-env-serialize
refactor/ce-ee-split
chore/upgrade-fastapi
```

禁止无意义名称（`cccc`、`temp`）、纯日期名称（`chore/openclaw-2026.3.8`）、`feature/` 全称、中文/大写/下划线。

### PR 标题

格式与 commit message 一致：`<type>(<scope>): <中文描述>`，概括整个 PR 的变更目标。

```
feat(backend): CE 操作审计系统 — Hook 埋点 + 持久化 + AuthActor 识别
fix(portal): 修复实例列表分页后状态丢失问题
```

### 自动提交

- 非治理改动：每完成一个单元性改动后，应立即提交 commit，不要攒多个独立改动一起提交
- 单元性改动指：一个可独立描述、可独立验证、可独立回滚的最小完整改动（如一个 bug 修复、一次样式微调、一次规则更新）
- 只有多个修改明确属于同一个改动单元时，才允许合并为一个 commit
- 治理例外（优先于默认提交）：执行任何 Plan Todo、创建/修订未 APPROVED 的 PRD/Architecture/Roadmap 时禁止立刻 commit；implementation commit 必须等 Review PASS + Verification PASS；禁止把 artifact 与代码、implementation 与 Roadmap status 打进同一 commit
- 任何新建/改写的 `.plan.md` frontmatter 必须含 `commit_policy: post_review`；缺字段一律按 `post_review` 推断

### Commit Message 格式

```
<type>(<scope>): <subject>
```

- type：feat、fix、docs、style、refactor、perf、test、chore
- subject：**必须使用中文**，祈使语态，50字符内

### 示例

```
feat(instance): 实例列表新增搜索和过滤功能
fix(deploy): 修复 env_vars 存数据库未序列化的问题
```

### 社区 PR 合并

- 必须保留外部贡献者的 commit 归属（Author 字段）
- 使用 `git cherry-pick`（不加 `--no-commit`）保留原始 author
- 维护者的修复作为独立 commit 叠加在原始 commit 之上
- 合并前用 `git log --format="%an - %s"` 验证归属正确
- 禁止 squash merge 吞掉贡献者的 commit

### 禁止

- 禁止 `Co-authored-by` 署名
- 禁止提交 `.env`、`.venv/`、`node_modules/`

## 用户偏好

- 使用中文交流
- 代码不加注释（除非特别要求）
- 回答风格：简洁直接

## 破坏性操作确认

以下操作执行前必须逐项列出并获得用户明确确认：
- K8s 资源删除/替换
- 数据库操作（DROP/DELETE/TRUNCATE）
- DNS/域名变更
- Docker 镜像删除
- `git push --force`、`git reset --hard`

## 同源逻辑同步

修改一处逻辑后，必须搜索项目中是否存在相同或相似的逻辑副本，全部同步修改。

| 逻辑类型 | 可能位置 |
|---------|----------|
| slug 生成、表单校验 | `nodeskclaw-portal` 页面 |
| API 调用封装 | `nodeskclaw-portal` 的 `api.ts` |
| K8s 资源构建逻辑 | `resource_builder.py`、`deploy_service.py` |

%% lat:begin %%
# Before starting work

- Run `lat search` to find sections relevant to your task. Read them to understand the design intent before writing code.
- Run `lat expand` on user prompts to expand any `[[refs]]` — this resolves section names to file locations and provides context.

# Post-task checklist (REQUIRED — do not skip)

After EVERY task, before responding to the user:

- [ ] Update `lat.md/` if you added or changed any functionality, architecture, tests, or behavior
- [ ] Run `lat check` — all wiki links and code refs must pass
- [ ] Do not skip these steps. Do not consider your task done until both are complete.

---

# What is lat.md?

This project uses [lat.md](https://www.npmjs.com/package/lat.md) to maintain a structured knowledge graph of its architecture, design decisions, and test specs in the `lat.md/` directory. It is a set of cross-linked markdown files that describe **what** this project does and **why** — the domain concepts, key design decisions, business logic, and test specifications. Use it to ground your work in the actual architecture rather than guessing.

# Commands

```bash
lat locate "Section Name"      # find a section by name (exact, fuzzy)
lat refs "file#Section"        # find what references a section
lat search "natural language"  # semantic search across all sections
lat expand "user prompt text"  # expand [[refs]] to resolved locations
lat check                      # validate all links and code refs
```

Run `lat --help` when in doubt about available commands or options.

If `lat search` fails because no API key is configured, explain to the user that semantic search requires a key provided via `LAT_LLM_KEY` (direct value), `LAT_LLM_KEY_FILE` (path to key file), or `LAT_LLM_KEY_HELPER` (command that prints the key). Supported key prefixes: `sk-...` (OpenAI) or `vck_...` (Vercel). If the user doesn't want to set it up, use `lat locate` for direct lookups instead.

# Syntax primer

- **Section ids**: `lat.md/path/to/file#Heading#SubHeading` — full form uses project-root-relative path (e.g. `lat.md/tests/search#RAG Replay Tests`). Short form uses bare file name when unique (e.g. `search#RAG Replay Tests`, `cli#search#Indexing`).
- **Wiki links**: `[[target]]` or `[[target|alias]]` — cross-references between sections. Can also reference source code: `[[src/foo.ts#myFunction]]`.
- **Source code links**: Wiki links in `lat.md/` files can reference functions, classes, constants, and methods in TypeScript/JavaScript/Python/Rust/Go/C files. Use the full path: `[[src/config.ts#getConfigDir]]`, `[[src/server.ts#App#listen]]` (class method), `[[lib/utils.py#parse_args]]`, `[[src/lib.rs#Greeter#greet]]` (Rust impl method), `[[src/app.go#Greeter#Greet]]` (Go method), `[[src/app.h#Greeter]]` (C struct). `lat check` validates these exist.
- **Code refs**: `// @lat: [[section-id]]` (JS/TS/Rust/Go/C) or `# @lat: [[section-id]]` (Python) — ties source code to concepts

# Test specs

Key tests can be described as sections in `lat.md/` files (e.g. `tests.md`). Add frontmatter to require that every leaf section is referenced by a `// @lat:` or `# @lat:` comment in test code:

```markdown
---
lat:
  require-code-mention: true
---
# Tests

Authentication and authorization test specifications.

## User login

Verify credential validation and error handling for the login endpoint.

### Rejects expired tokens
Tokens past their expiry timestamp are rejected with 401, even if otherwise valid.

### Handles missing password
Login request without a password field returns 400 with a descriptive error.
```

Every section MUST have a description — at least one sentence explaining what the test verifies and why. Empty sections with just a heading are not acceptable. (This is a specific case of the general leading paragraph rule below.)

Each test in code should reference its spec with exactly one comment placed next to the relevant test — not at the top of the file:

```python
# @lat: [[tests#User login#Rejects expired tokens]]
def test_rejects_expired_tokens():
    ...

# @lat: [[tests#User login#Handles missing password]]
def test_handles_missing_password():
    ...
```

Do not duplicate refs. One `@lat:` comment per spec section, placed at the test that covers it. `lat check` will flag any spec section not covered by a code reference, and any code reference pointing to a nonexistent section.

# Section structure

Every section in `lat.md/` **must** have a leading paragraph — at least one sentence immediately after the heading, before any child headings or other block content. The first paragraph must be ≤250 characters (excluding `[[wiki link]]` content). This paragraph serves as the section's overview and is used in search results, command output, and RAG context — keeping it concise guarantees the section's essence is always captured.

```markdown
# Good Section

Brief overview of what this section documents and why it matters.

More detail can go in subsequent paragraphs, code blocks, or lists.

## Child heading

Details about this child topic.
```

```markdown
# Bad Section

## Child heading

Details about this child topic.
```

The second example is invalid because `Bad Section` has no leading paragraph. `lat check` validates this rule and reports errors for missing or overly long leading paragraphs.
%% lat:end %%
