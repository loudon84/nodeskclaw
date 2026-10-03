"""Task Orchestrator Module - LangGraph-based workflow orchestration system.

DEPRECATED / FROZEN. 流程编排的领域归属是 nodeskclaw-task，不是 backend。
本模块（含 to_* 表与 /api/v1/task-orchestrator）只接受安全性修复：
禁止新增节点类型、执行器类型、状态值、表与端点，禁止补完 stub 适配器，
禁止新增调用方。新的自动化需求一律落 nodeskclaw-task。
边界与退场前置条件见 docs/architecture-domain.md 的 D-01。
"""
