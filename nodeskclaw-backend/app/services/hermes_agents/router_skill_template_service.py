import re
from typing import Any

ROUTER_SKILL_NAME = "nodeskclaw-skill-router"

FORBIDDEN_CONTENT_FRAGMENTS = (
    "ndsk_mcp_",
    "Bearer ",
    "Authorization",
    "NODESKCLAW_MCP_TOKEN",
)

TITLE_OVERRIDES: dict[str, str] = {
    "customer-profiling": "客户画像与销售机会分析",
    "enterprise-risk-analysis": "企业风险分析",
    "manufacturer-profiling": "原厂画像分析",
    "semiconductor-marketing-copy": "半导体营销文案",
}


def tool_display_title(tool_name: str) -> str:
    slug = tool_name.split("__")[-1] if "__" in tool_name else tool_name
    slug = slug.replace("skill.", "")
    if slug in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[slug]
    parts = re.split(r"[-_.]+", slug)
    return " ".join(p.capitalize() for p in parts if p)


def extract_trigger_rules(description: str, tool_name: str) -> list[str]:
    rules: list[str] = []
    text = (description or "").strip()
    if text:
        for line in text.splitlines():
            line = line.strip().lstrip("-*•").strip()
            if line and len(line) > 4:
                rules.append(line)
    title = tool_display_title(tool_name)
    if not rules:
        rules.append(f"用户提出与「{title}」相关的业务需求")
        rules.append(f"用户描述的任务类型匹配 `{tool_name}` 的能力")
    if len(rules) > 6:
        rules = rules[:6]
    return rules


def render_tool_section(tool: dict[str, Any]) -> str:
    name = tool.get("name") or ""
    description = (tool.get("description") or "").strip() or "无描述"
    title = tool_display_title(name)
    triggers = extract_trigger_rules(description, name)
    trigger_lines = "\n".join(f"- {rule}" for rule in triggers)
    return (
        f"### {title}\n\n"
        f"工具名：\n\n"
        f"`{name}`\n\n"
        f"能力说明：\n\n"
        f"{description}\n\n"
        f"适合场景：\n\n"
        f"{trigger_lines}\n\n"
        f"调用要求：\n\n"
        f"当用户需求匹配以上场景时，调用 `{name}`。\n"
    )


def render_router_skill_md(mcp_name: str, tools: list[dict[str, Any]]) -> str:
    tools_section = "\n".join(render_tool_section(t) for t in tools)
    content = (
        f"# {ROUTER_SKILL_NAME}\n\n"
        "## 作用\n\n"
        "你是 nodeskclaw MCP Skill Router。\n\n"
        "你的任务是根据用户的自然语言需求，自动选择 common-skills MCP 中最合适的远程技能并调用。\n\n"
        "用户不需要知道英文工具名。\n\n"
        "## MCP 工具集\n\n"
        "MCP Server 名称：\n\n"
        f"{mcp_name}\n\n"
        "## 可用远程技能\n\n"
        f"{tools_section}\n"
        "## 路由规则\n\n"
        "1. 用户提出业务需求时，不要求用户输入英文 skill 名称。\n"
        "2. 根据用户意图、公司名称、产品类型、任务类型选择最匹配的远程技能。\n"
        "3. 如果用户意图明确，直接调用对应 MCP tool。\n"
        "4. 如果多个 tool 都匹配，选择最贴近用户最终产出的一个。\n"
        "5. 只有在用户缺少必要参数时才追问。\n"
        "6. 不要向用户暴露内部路由过程。\n"
        "7. 不要要求用户说出 tool name。\n"
        "8. 业务 MCP tool 返回 `ready=true` 或 `status=completed` 时，直接向用户展示结果，不要再查询本地端口。\n"
        "9. 如果 MCP 调用失败，说明失败原因，并给出下一步建议。\n\n"
        "## 异步任务等待规则\n\n"
        "远程 MCP business skill 默认由 MCP Gateway 托管等待。\n\n"
        "当业务 tool 返回 `ready=true` 或 `status=completed` 时，直接向用户展示结果，不要再查询本地端口。\n\n"
        "当业务 tool 返回 `ready=false` 且包含 `next_tool=nodeskclaw_task_wait` 时，只能调用 `nodeskclaw_task_wait` 继续等待。\n\n"
        "禁止行为：\n\n"
        "- 不要访问 localhost、4030、8642 或其他本地端口。\n"
        "- 不要直接访问 NoDeskClaw REST API。\n"
        "- 不要尝试读取 API Key 或 MCP Token。\n"
        "- 不要再次调用原业务 tool 查询同一任务结果。\n"
        "- 不要使用联网搜索替代已提交的远程 Skill 结果。\n\n"
        "## 最终结果展示规则\n\n"
        "任务完成后，最终回答必须包含：\n\n"
        "- task_no\n"
        "- status\n"
        "- result_summary\n"
        "- server_artifacts\n"
        "- preview_url\n"
        "- download_url\n"
        "- suggested_workspace_path\n"
        "- kb_status\n\n"
        "如果 server_artifacts 为空，应说明任务完成但未发现中心产物。\n\n"
        "不要声明文档已保存到当前 Hermes workspace。\n\n"
        "如果用户需要文件，说明可从 NoDeskClaw 中心产物库下载，或按 suggested_workspace_path 导入。\n\n"
        "## 工具选择优先级\n\n"
        "1. 用户明确要求客户画像、采购需求、销售机会 → 使用客户画像工具。\n"
        "2. 用户明确要求风险评估、信用评级、经营风险 → 使用企业风险分析工具。\n"
        "3. 用户明确要求芯片原厂、厂家画像、供应商合作 → 使用原厂画像工具。\n"
        "4. 用户明确要求推广文案、产品介绍、技术方案营销 → 使用半导体营销文案工具。\n\n"
        "## 产物处理规则\n\n"
        "当远程 MCP skill 生成报告、文案、分析文档或联系人清单时，以 MCP Gateway 返回的 server_artifacts 为准。\n\n"
        "如果返回中包含 server_artifacts、download_url、preview_url、suggested_workspace_path，最终回答必须展示这些信息。\n\n"
        "不要声明文档已保存到当前 Hermes workspace。\n\n"
        "不要伪造 workspace 保存路径。\n\n"
        "如果用户要求保存到当前 workspace，应说明当前 MCP Gateway 采用 pull-only 模式：报告已保存到 nodeskclaw 中心产物库，可下载或按 suggested_workspace_path 导入。\n\n"
        "## 禁止行为\n\n"
        "- 不要让用户输入英文 tool name。\n"
        "- 不要伪造远程工具结果。\n"
        "- 不要绕过 common-skills MCP Gateway。\n"
        "- 不要修改用户输入的公司名称、品牌、产品线。\n"
    )
    for fragment in FORBIDDEN_CONTENT_FRAGMENTS:
        if fragment in content:
            raise ValueError(f"Router skill content must not contain forbidden fragment: {fragment}")
    return content
