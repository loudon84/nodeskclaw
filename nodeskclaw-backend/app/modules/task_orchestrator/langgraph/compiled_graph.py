"""LangGraph compiled graph - Graph building and caching."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END

from app.modules.task_orchestrator.langgraph.state import WorkflowState
from app.modules.task_orchestrator.langgraph.nodes import (
    dispatch_node,
    wait_human_node,
    finalize_node,
    gateway_node,
    error_handler_node,
)


class CompiledGraphCache:
    """Cache for compiled workflow graphs.

    This class caches compiled StateGraph instances to avoid
    recompiling the same template multiple times.
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def get(self, template_key: str, version: int) -> Any | None:
        """Get compiled graph from cache.

        Args:
            template_key: Template key
            version: Template version

        Returns:
            Compiled graph if cached, None otherwise
        """
        cache_key = f"{template_key}:v{version}"
        return self._cache.get(cache_key)

    def put(self, template_key: str, version: int, graph: Any) -> None:
        """Put compiled graph into cache.

        Args:
            template_key: Template key
            version: Template version
            graph: Compiled graph to cache
        """
        cache_key = f"{template_key}:v{version}"
        self._cache[cache_key] = graph

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def remove(self, template_key: str, version: int) -> None:
        """Remove a specific graph from cache.

        Args:
            template_key: Template key
            version: Template version
        """
        cache_key = f"{template_key}:v{version}"
        self._cache.pop(cache_key, None)


# Global cache instance
_graph_cache = CompiledGraphCache()


def get_graph_cache() -> CompiledGraphCache:
    """Get the global graph cache.

    Returns:
        Global graph cache instance
    """
    return _graph_cache


def build_workflow_graph(
    template_definition: dict[str, Any],
    checkpoint_saver: BaseCheckpointSaver | None = None,
) -> Any:
    """Build a compiled workflow graph from template definition.

    Args:
        template_definition: Template definition containing nodes and edges
        checkpoint_saver: Optional checkpoint saver for persistence

    Returns:
        Compiled StateGraph
    """
    # Create state graph
    builder = StateGraph(WorkflowState)

    # Extract template components
    nodes = template_definition.get("nodes", [])
    edges = template_definition.get("edges", [])
    entry_node = template_definition.get("entry_node")
    terminal_node = template_definition.get("terminal_node")

    # Add workflow nodes
    for node in nodes:
        node_key = node.get("node_key")
        node_type = node.get("node_type")

        # Select appropriate node function based on type
        if node_type == "human_review":
            node_func = wait_human_node
        elif node_type == "gateway_task":
            node_func = gateway_node
        else:
            node_func = dispatch_node

        # Add node with configuration
        builder.add_node(
            node_key,
            lambda state, config=node: node_func(state, config),
        )

    # Add special nodes
    builder.add_node("finalize", finalize_node)
    builder.add_node("error_handler", error_handler_node)

    # Add entry edge
    if entry_node:
        builder.add_edge(START, entry_node)

    # Add workflow edges
    for edge in edges:
        from_node = edge.get("from_node")
        to_node = edge.get("to_node")
        condition_type = edge.get("condition_type", "always")

        if condition_type == "always":
            # Direct edge
            builder.add_edge(from_node, to_node)
        else:
            # Conditional edge (would need conditional routing logic)
            # For now, add as direct edge
            builder.add_edge(from_node, to_node)

    # Add terminal edge to finalize
    if terminal_node:
        builder.add_edge(terminal_node, "finalize")

    # Add finalize to END
    builder.add_edge("finalize", END)

    # Compile with checkpoint saver
    if checkpoint_saver:
        return builder.compile(checkpointer=checkpoint_saver)
    else:
        return builder.compile()


def get_or_build_graph(
    template_key: str,
    version: int,
    template_definition: dict[str, Any],
    checkpoint_saver: BaseCheckpointSaver | None = None,
    use_cache: bool = True,
) -> Any:
    """Get cached graph or build new one.

    Args:
        template_key: Template key
        version: Template version
        template_definition: Template definition
        checkpoint_saver: Optional checkpoint saver
        use_cache: Whether to use cache (default: True)

    Returns:
        Compiled StateGraph
    """
    if use_cache:
        # Try to get from cache
        cached_graph = _graph_cache.get(template_key, version)
        if cached_graph:
            return cached_graph

    # Build new graph
    graph = build_workflow_graph(template_definition, checkpoint_saver)

    # Cache if enabled
    if use_cache:
        _graph_cache.put(template_key, version, graph)

    return graph


def invalidate_graph_cache(template_key: str, version: int) -> None:
    """Invalidate cached graph for a template.

    This should be called when a template is updated or deleted.

    Args:
        template_key: Template key
        version: Template version
    """
    _graph_cache.remove(template_key, version)


def clear_graph_cache() -> None:
    """Clear the entire graph cache.

    This should be called during testing or when templates are bulk updated.
    """
    _graph_cache.clear()
