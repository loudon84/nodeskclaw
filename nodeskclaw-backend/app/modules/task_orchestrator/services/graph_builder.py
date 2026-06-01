"""Graph builder service - StateGraph construction from templates."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END

from app.modules.task_orchestrator.langgraph.state import WorkflowState
from app.modules.task_orchestrator.langgraph.nodes import (
    dispatch_node,
    wait_human_node,
    finalize_node,
    gateway_node,
)


class WorkflowGraphBuilder:
    """Builder for constructing StateGraph from workflow templates."""

    def __init__(self, template_definition: dict[str, Any], checkpoint_saver: BaseCheckpointSaver | None = None):
        self.definition = template_definition
        self.checkpoint_saver = checkpoint_saver
        self.builder = StateGraph(WorkflowState)

    def build(self) -> Any:
        """Build compiled StateGraph from template definition.

        Returns:
            Compiled StateGraph
        """
        # Extract components
        nodes = self.definition.get("nodes", [])
        edges = self.definition.get("edges", [])
        entry_node = self.definition.get("entry_node")
        terminal_node = self.definition.get("terminal_node")

        # Add workflow nodes
        for node in nodes:
            self._add_node(node)

        # Add special nodes
        self.builder.add_node("finalize", finalize_node)

        # Add entry edge
        if entry_node:
            self.builder.add_edge(START, entry_node)

        # Add workflow edges
        for edge in edges:
            self._add_edge(edge)

        # Add terminal edge
        if terminal_node:
            self.builder.add_edge(terminal_node, "finalize")

        self.builder.add_edge("finalize", END)

        # Compile
        if self.checkpoint_saver:
            return self.builder.compile(checkpointer=self.checkpoint_saver)
        else:
            return self.builder.compile()

    def _add_node(self, node: dict[str, Any]) -> None:
        """Add a node to the graph.

        Args:
            node: Node definition
        """
        node_key = node.get("node_key")
        node_type = node.get("node_type")

        # Select node function
        if node_type == "human_review":
            node_func = wait_human_node
        elif node_type == "gateway_task":
            node_func = gateway_node
        else:
            node_func = dispatch_node

        # Add node with config
        self.builder.add_node(
            node_key,
            lambda state, config=node: node_func(state, config),
        )

    def _add_edge(self, edge: dict[str, Any]) -> None:
        """Add an edge to the graph.

        Args:
            edge: Edge definition
        """
        from_node = edge.get("from_node")
        to_node = edge.get("to_node")
        condition_type = edge.get("condition_type", "always")

        # For now, only support direct edges
        # Conditional edges would require more complex routing logic
        if condition_type == "always":
            self.builder.add_edge(from_node, to_node)
