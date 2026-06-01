#!/usr/bin/env python
"""Test script to verify task_orchestrator module imports."""

import sys
sys.path.insert(0, '.')

print("Testing task_orchestrator module...")

# Test constants, enums, errors
from app.modules.task_orchestrator import constants, enums, errors
print("[OK] constants, enums, errors")

# Test models
from app.modules.task_orchestrator.models import (
    WorkflowTemplate, WorkflowInstance, WorkflowNode,
    WorkflowEvent, HumanIntervention, CheckpointSnapshot, ExecutorBinding
)
print("[OK] All 7 models")

# Test schemas
from app.modules.task_orchestrator.schemas import (
    common, template, workflow, intervention, adapters, paperclip
)
print("[OK] All 6 schemas")

# Test repositories
from app.modules.task_orchestrator.repositories import (
    TemplateRepository, WorkflowRepository, EventRepository, CheckpointRepository
)
print("[OK] All 4 repositories")

# Test langgraph core
from app.modules.task_orchestrator.langgraph import (
    state, reducers, nodes, commands, compiled_graph
)
print("[OK] LangGraph core")

# Test adapters
from app.modules.task_orchestrator.adapters import (
    base, human_review_adapter, openclaw_adapter
)
print("[OK] All 3 adapters")

print("\n[SUCCESS] All task_orchestrator module imports successful!")
