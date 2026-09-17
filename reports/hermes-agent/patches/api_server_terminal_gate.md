# api_server 终态门禁补丁（Hermes v0.21）

目标文件（容器内典型路径，以你镜像为准）：

```text
.../gateway/platforms/api_server.py
```

类：`APIServerAdapter`  
方法：`_set_run_status(self, run_id, status, **fields)`

## 改动意图

在把 status 写成 `completed` / `succeeded` / `success` **之前**：

1. Flush 本 run 上传队列；
2. Merge `output_refs`（绝对 URL）；
3. 若 required 上传失败 → 改为 `failed` 并带 `error`。

## 手工合并片段

在 `_set_run_status` 开头（或写入 store 之前）插入：

```python
def _set_run_status(self, run_id, status, **fields):
    status_l = str(status).lower()
    if status_l in {"completed", "succeeded", "success"}:
        try:
            from hermes_output_artifacts.refs import REGISTRY
            refs = REGISTRY.merge_output_refs(str(run_id), fields.get("output_refs"), force_flush=True)
            ok, err = REGISTRY.can_complete(str(run_id))
            fields = dict(fields)
            fields["output_refs"] = refs
            if not ok:
                status = "failed"
                fields["error"] = err or "artifact upload gate failed"
                status_l = "failed"
        except Exception as exc:
            # 若要求严格门禁：失败则不要 completed
            fields = dict(fields)
            fields.setdefault("error", f"output_artifacts gate error: {exc}")
            status = "failed"
            status_l = "failed"
    # ... 原有写入 status / 通知逻辑 ...
```

若插件未安装，可改为从环境变量读取「已生成的 refs JSON 文件」：

```text
/tmp/hermes-output-refs/{run_id}.json
```

由外部上传脚本写好后再 completed（运维临时方案，不如插件）。

## 验证

1. 备份：`cp api_server.py api_server.py.bak`
2. 打补丁并重启 API Server
3. 故意把 `HERMES_ARTIFACT_UPLOAD_URL` 指到不可达地址 → run 应变 `failed`，不得 `completed`
4. 修复 URL 后成功 run 的 `GET /v1/runs/{id}` 含绝对 URL `output_refs`

## 回滚

```bash
cp api_server.py.bak api_server.py
# 重启容器 / 进程
```
