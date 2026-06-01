from app.services.workspace_service import _next_available_hex_position


def test_next_available_hex_position_skips_existing_nodes() -> None:
    occupied = {
        (0, 0),
        (1, 0),
        (1, -1),
        (0, -1),
        (-1, 0),
    }

    assert _next_available_hex_position(occupied) == (-1, 1)
