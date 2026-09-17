# 可选镜像 / 源码补丁说明

当「仅插件 monkeypatch `APIServerAdapter._set_run_status`」在你的 Hermes 升级路径上不稳定时，
用本目录补丁把**终态门禁**与 **output_refs merge** 固化进镜像。

| 文件 | 用途 |
|------|------|
| `api_server_terminal_gate.md` | 手工改 `gateway/platforms/api_server.py` 的步骤与片段 |
| `hook_track_example.sh` | 在工具包装脚本里显式 `track` 产物路径（收集兜底） |

## 推荐顺序

1. 先装插件，用公网/测试文件服务器验证 AC-1～AC-3。
2. 若 monkeypatch 日志未出现或升级后丢失 → 再打 `api_server` 补丁。
3. 始终保留 `api_server.py.bak`。

## 与插件关系

- 补丁应调用插件暴露的 registry（若已加载），或内联同等 flush 逻辑。
- 禁止在补丁里硬编码公网 RFC URL（那是 spike，不是生产）。
