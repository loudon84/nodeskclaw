# Native Run Finalizer Contract v1

该契约把 run 终态写入与插件的必需工件上传串联为单一流程。Core 是唯一终态与 SSE 写入者，插件只能追加 `output_refs` 或把候选成功终态降为失败。

## 注册

Core 在 `PluginContext` 提供：

```python
ctx.register_native_run_finalizer(callback)
```

每个 profile 只允许注册一个 finalizer。重复注册必须在插件加载时失败。Core 必须在插件卸载时移除注册。

同时，Core 对正式 `post_tool_call` hook 增量提供：

```python
{
    "tool_name": str,
    "args": dict,
    "result": object,
    "native_run_id": str,
    "workspace_root": str,
}
```

`native_run_id` 不能由插件通过 `session_id`、`task_id` 或任意上下文属性猜测。

## 输入

`callback` 接收 `NativeRunFinalizeRequest`：

```python
NativeRunFinalizeRequest(
    schema_version=1,
    run_id="runtime-run-id",
    session_id="session-id-or-none",
    proposed_status="completed",
    fields={...},
    workspace_root=Path("..."),
)
```

`fields` 为只读映射。Core 传入的 `workspace_root` 是可收集文件的唯一根目录。

## 输出

`callback` 返回 `NativeRunFinalizeResult`：

```python
NativeRunFinalizeResult.ready(
    (
        NativeOutputRef(
            name="report.csv",
            content_type="text/csv",
            url="https://minio.smc.lan:9000/...presigned...",
            required=True,
            size_bytes=123,
            checksum_sha256="<64 lowercase hex>",
            expires_at="2026-09-12T00:00:00+00:00",
        ),
    )
)
```

或：

```python
NativeRunFinalizeResult.failed(
    "artifact_upload_failed",
    "required MinIO upload failed",
    output_refs=(),
)
```

Core 必须校验 URL 为绝对 HTTP(S) 地址、SHA-256 为 64 位小写十六进制、大小非负。输出引用是追加的，不得覆盖 Core 已有 `output_refs`。

## 调用顺序和失败语义

```text
Core 计算候选终态
  -> 状态保持 finalizing
  -> 调用 finalizer
  -> 校验并合并 output_refs
  -> 计算最终状态
  -> 持久化最终状态
  -> 用最终状态发送 SSE
  -> 清理 Core 运行态
```

候选成功终态中，finalizer 超时、异常或返回 `failed` 必须使最终状态为 `failed`。候选 `failed` / `cancelled` 不得被 finalizer 升级为成功。Core 负责总超时；插件负责 MinIO 请求超时。

Core 可以在异常恢复时再次调用同一 run 的 finalizer，因此回调必须按 `run_id` 幂等。Core 不得通过普通 observer hook 实现此门禁。
