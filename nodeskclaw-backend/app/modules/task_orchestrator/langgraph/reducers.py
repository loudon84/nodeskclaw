"""LangGraph custom reducers - State transformation functions."""

from typing import Any, Callable


def merge_dict_reducer(
    left: dict[str, Any] | None, right: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge two dictionaries with right taking precedence.

    Args:
        left: Existing dictionary
        right: New dictionary

    Returns:
        Merged dictionary
    """
    if left is None:
        left = {}
    if right is None:
        right = {}
    result = dict(left)
    result.update(right)
    return result


def merge_list_reducer(
    left: list[Any] | None, right: list[Any] | None
) -> list[Any]:
    """Concatenate two lists.

    Args:
        left: Existing list
        right: New list

    Returns:
        Concatenated list
    """
    if left is None:
        left = []
    if right is None:
        right = []
    return left + right


def overwrite_reducer(
    left: Any | None, right: Any | None
) -> Any:
    """Overwrite left value with right value.

    Args:
        left: Existing value
        right: New value

    Returns:
        Right value if not None, otherwise left value
    """
    return right if right is not None else left


def max_reducer(left: int | None, right: int | None) -> int:
    """Take maximum of two integers.

    Args:
        left: Existing integer
        right: New integer

    Returns:
        Maximum value
    """
    if left is None:
        left = 0
    if right is None:
        right = 0
    return max(left, right)


def min_reducer(left: int | None, right: int | None) -> int:
    """Take minimum of two integers.

    Args:
        left: Existing integer
        right: New integer

    Returns:
        Minimum value
    """
    if left is None:
        left = 0
    if right is None:
        right = 0
    return min(left, right)


def increment_reducer(left: int | None, right: int | None) -> int:
    """Increment counter.

    Args:
        left: Existing counter value
        right: Increment value

    Returns:
        Incremented counter
    """
    if left is None:
        left = 0
    if right is None:
        right = 0
    return left + right


def merge_set_reducer(
    left: set[Any] | None, right: set[Any] | None
) -> set[Any]:
    """Merge two sets.

    Args:
        left: Existing set
        right: New set

    Returns:
        Merged set
    """
    if left is None:
        left = set()
    if right is None:
        right = set()
    return left | right


def create_field_reducer(field_name: str) -> Callable:
    """Create a reducer for a specific field.

    This factory function creates a reducer that knows which field it's reducing,
    useful for logging and debugging.

    Args:
        field_name: Name of the field being reduced

    Returns:
        Reducer function
    """

    def reducer(left: Any, right: Any) -> Any:
        """Field-specific reducer."""
        # For debugging: print(f"Reducing {field_name}: {left} + {right}")
        return merge_dict_reducer(left, right)

    reducer.__name__ = f"{field_name}_reducer"
    return reducer


# Pre-defined reducers for common use cases
node_status_reducer = create_field_reducer("node_statuses")
node_result_reducer = create_field_reducer("node_results")
node_error_reducer = create_field_reducer("node_errors")
