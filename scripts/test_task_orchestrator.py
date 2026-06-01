#!/usr/bin/env python
"""Task Orchestrator 功能完整性测试脚本

测试 Phase 1 完整链路:
1. 模板管理 (CRUD)
2. 工作流实例创建和执行
3. 人工介入 (Human-in-the-loop)
4. 完整链路验证

使用方法:
    python scripts/test_task_orchestrator.py --base-url http://localhost:4510 --token <JWT_TOKEN>
"""

import argparse
import json
import sys
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TaskOrchestratorTestClient:
    """Task Orchestrator API 测试客户端"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置默认请求头
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """发送请求并处理响应"""
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, **kwargs)

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {"raw_text": response.text}

        if not response.ok:
            print(f"❌ 请求失败: {method} {url}")
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            response.raise_for_status()

        return data

    # ========== 模板管理 API ==========

    def create_template(self, template_data: dict) -> dict:
        """创建工作流模板"""
        return self._request("POST", "/api/v1/admin/task-orchestrator/templates", json=template_data)

    def list_templates(self, template_key: str | None = None) -> dict:
        """查询模板列表"""
        params = {}
        if template_key:
            params["template_key"] = template_key
        return self._request("GET", "/api/v1/admin/task-orchestrator/templates", params=params)

    def get_template(self, template_id: str) -> dict:
        """查询模板详情"""
        return self._request("GET", f"/api/v1/admin/task-orchestrator/templates/{template_id}")

    def update_template(self, template_id: str, updates: dict) -> dict:
        """更新模板"""
        return self._request("PATCH", f"/api/v1/admin/task-orchestrator/templates/{template_id}", json=updates)

    def activate_template(self, template_id: str) -> dict:
        """激活模板"""
        return self._request("POST", f"/api/v1/admin/task-orchestrator/templates/{template_id}/activate")

    def deprecate_template(self, template_id: str) -> dict:
        """废弃模板"""
        return self._request("POST", f"/api/v1/admin/task-orchestrator/templates/{template_id}/deprecate")

    # ========== 工作流实例 API ==========

    def create_workflow(self, workflow_data: dict) -> dict:
        """创建工作流实例"""
        return self._request("POST", "/api/v1/task-orchestrator/workflow-instances", json=workflow_data)

    def get_workflow(self, workflow_id: str) -> dict:
        """查询工作流详情"""
        return self._request("GET", f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}")

    def get_timeline(self, workflow_id: str) -> dict:
        """查询工作流时间线"""
        return self._request("GET", f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/timeline")

    def pause_workflow(self, workflow_id: str) -> dict:
        """暂停工作流"""
        return self._request("POST", f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/pause")

    def resume_workflow(self, workflow_id: str) -> dict:
        """恢复工作流"""
        return self._request("POST", f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/resume")

    def cancel_workflow(self, workflow_id: str) -> dict:
        """取消工作流"""
        return self._request("POST", f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/cancel")

    # ========== 人工介入 API ==========

    def create_intervention(self, workflow_id: str, intervention_data: dict) -> dict:
        """创建人工介入"""
        return self._request(
            "POST",
            f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/interventions",
            json=intervention_data,
        )

    def retry_node(self, workflow_id: str, node_key: str) -> dict:
        """重试节点"""
        return self._request(
            "POST",
            f"/api/v1/task-orchestrator/workflow-instances/{workflow_id}/retry-node",
            json={"node_key": node_key},
        )


def print_json(data: dict, title: str = ""):
    """美化打印 JSON"""
    if title:
        print(f"\n{title}:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def test_template_management(client: TaskOrchestratorTestClient):
    """测试模板管理功能"""
    print("\n" + "=" * 60)
    print("📋 测试模板管理功能")
    print("=" * 60)

    # 1. 创建模板
    print("\n1️⃣ 创建工作流模板...")
    template_data = {
        "template_key": "test_approval_workflow",
        "name": "测试审批工作流",
        "description": "包含人工审批节点的测试工作流",
        "definition": {
            "nodes": [
                {
                    "key": "start",
                    "name": "开始",
                    "type": "start",
                    "executor_type": "system",
                    "config": {},
                },
                {
                    "key": "approval",
                    "name": "审批节点",
                    "type": "human_review",
                    "executor_type": "human_review",
                    "config": {
                        "approval_type": "single",
                        "timeout_seconds": 3600,
                    },
                },
                {
                    "key": "end",
                    "name": "结束",
                    "type": "end",
                    "executor_type": "system",
                    "config": {},
                },
            ],
            "edges": [
                {"source": "start", "target": "approval"},
                {"source": "approval", "target": "end"},
            ],
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "applicant": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["applicant", "reason"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "approver": {"type": "string"},
            },
        },
    }

    template = client.create_template(template_data)
    print_json(template, "✅ 模板创建成功")
    template_id = template["id"]

    # 2. 查询模板列表
    print("\n2️⃣ 查询模板列表...")
    templates = client.list_templates(template_key="test_approval_workflow")
    print_json(templates, "✅ 模板列表")

    # 3. 查询模板详情
    print("\n3️⃣ 查询模板详情...")
    template_detail = client.get_template(template_id)
    print_json(template_detail, "✅ 模板详情")

    # 4. 激活模板
    print("\n4️⃣ 激活模板...")
    activated = client.activate_template(template_id)
    print_json(activated, "✅ 模板已激活")

    return template_id


def test_workflow_instance(client: TaskOrchestratorTestClient, template_id: str):
    """测试工作流实例创建和执行"""
    print("\n" + "=" * 60)
    print("🔄 测试工作流实例功能")
    print("=" * 60)

    # 1. 创建工作流实例
    print("\n1️⃣ 创建工作流实例...")
    workflow_data = {
        "template_id": template_id,
        "input_data": {
            "applicant": "张三",
            "reason": "测试申请",
        },
        "metadata": {
            "test_run": True,
            "environment": "development",
        },
    }

    workflow = client.create_workflow(workflow_data)
    print_json(workflow, "✅ 工作流实例创建成功")
    workflow_id = workflow["id"]
    thread_id = workflow["thread_id"]

    # 2. 查询工作流详情
    print("\n2️⃣ 查询工作流详情...")
    time.sleep(1)  # 等待状态更新
    workflow_detail = client.get_workflow(workflow_id)
    print_json(workflow_detail, "✅ 工作流详情")

    # 3. 查询时间线
    print("\n3️⃣ 查询工作流时间线...")
    timeline = client.get_timeline(workflow_id)
    print_json(timeline, "✅ 工作流时间线")

    # 4. 测试暂停/恢复
    print("\n4️⃣ 测试暂停工作流...")
    paused = client.pause_workflow(workflow_id)
    print_json(paused, "✅ 工作流已暂停")

    print("\n5️⃣ 测试恢复工作流...")
    resumed = client.resume_workflow(workflow_id)
    print_json(resumed, "✅ 工作流已恢复")

    return workflow_id, thread_id


def test_human_intervention(client: TaskOrchestratorTestClient, workflow_id: str):
    """测试人工介入功能"""
    print("\n" + "=" * 60)
    print("👤 测试人工介入功能")
    print("=" * 60)

    # 1. 查询工作流状态,等待人工审批节点
    print("\n1️⃣ 等待工作流进入人工审批节点...")
    max_wait = 10
    for i in range(max_wait):
        workflow = client.get_workflow(workflow_id)
        status = workflow.get("status")
        print(f"   当前状态: {status} (等待 {max_wait - i} 秒)")

        if status == "waiting_human":
            print("✅ 工作流已进入人工审批节点")
            break
        elif status in ["completed", "failed", "cancelled"]:
            print(f"❌ 工作流意外结束: {status}")
            return False

        time.sleep(1)
    else:
        print("❌ 超时: 工作流未进入人工审批节点")
        return False

    # 2. 提交人工介入
    print("\n2️⃣ 提交人工审批...")
    intervention_data = {
        "node_key": "approval",
        "intervention_type": "approval",
        "payload": {
            "approved": True,
            "approver": "管理员",
            "comment": "同意申请",
        },
    }

    intervention = client.create_intervention(workflow_id, intervention_data)
    print_json(intervention, "✅ 人工审批已提交")

    # 3. 等待工作流完成
    print("\n3️⃣ 等待工作流完成...")
    max_wait = 10
    for i in range(max_wait):
        workflow = client.get_workflow(workflow_id)
        status = workflow.get("status")
        print(f"   当前状态: {status} (等待 {max_wait - i} 秒)")

        if status == "completed":
            print("✅ 工作流已完成")
            break
        elif status in ["failed", "cancelled"]:
            print(f"❌ 工作流异常结束: {status}")
            return False

        time.sleep(1)
    else:
        print("❌ 超时: 工作流未完成")
        return False

    # 4. 查询最终时间线
    print("\n4️⃣ 查询最终时间线...")
    timeline = client.get_timeline(workflow_id)
    print_json(timeline, "✅ 最终时间线")

    return True


def test_full_lifecycle(client: TaskOrchestratorTestClient):
    """测试完整生命周期"""
    print("\n" + "=" * 60)
    print("🚀 测试完整生命周期")
    print("=" * 60)

    try:
        # Phase 1: 模板管理
        template_id = test_template_management(client)

        # Phase 2: 工作流实例
        workflow_id, thread_id = test_workflow_instance(client, template_id)

        # Phase 3: 人工介入
        success = test_human_intervention(client, workflow_id)

        if success:
            print("\n" + "=" * 60)
            print("✅ 所有测试通过!")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ 测试失败")
            print("=" * 60)
            return False

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Task Orchestrator 功能测试")
    parser.add_argument("--base-url", default="http://localhost:4510", help="API 基础 URL")
    parser.add_argument("--token", required=True, help="JWT 认证令牌")
    parser.add_argument("--test", choices=["template", "workflow", "intervention", "full"], default="full", help="测试类型")

    args = parser.parse_args()

    print("=" * 60)
    print("Task Orchestrator 功能完整性测试")
    print("=" * 60)
    print(f"API 地址: {args.base_url}")
    print(f"测试类型: {args.test}")

    client = TaskOrchestratorTestClient(args.base_url, args.token)

    if args.test == "full":
        success = test_full_lifecycle(client)
    elif args.test == "template":
        test_template_management(client)
        success = True
    elif args.test == "workflow":
        # 需要先创建模板
        template_id = test_template_management(client)
        test_workflow_instance(client, template_id)
        success = True
    elif args.test == "intervention":
        print("❌ intervention 测试需要先创建模板和工作流,请使用 --test full")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
