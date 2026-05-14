from app.services.agent_output_sanitizer import (
    ThinkBlockStreamSanitizer,
    strip_think_blocks,
)
from app.services.workspace_message_service import is_no_reply, visible_agent_content


def test_strip_think_blocks_keeps_normal_content():
    assert strip_think_blocks("正常回复") == "正常回复"


def test_strip_think_blocks_removes_single_multiline_block():
    assert strip_think_blocks("前文\n<think>\nEnglish reasoning\n</think>\n正文") == "前文\n正文"


def test_strip_think_blocks_removes_multiple_mixed_case_blocks():
    assert strip_think_blocks("<THINK>one</THINK>答复<think>two</think>结束") == "答复结束"


def test_strip_think_blocks_drops_unclosed_block():
    assert strip_think_blocks("正文<think>unfinished") == "正文"


def test_visible_agent_content_only_sanitizes_agents():
    content = "用户写的 <think>不是思考</think>"

    assert visible_agent_content("user", content) == content
    assert visible_agent_content("system", content) == content
    assert visible_agent_content("agent", content) == "用户写的"


def test_is_no_reply_ignores_reasoning_block():
    assert is_no_reply("<think>deciding</think>\nNO_REPLY") is True


def test_stream_sanitizer_filters_split_tags_without_leaking_content():
    sanitizer = ThinkBlockStreamSanitizer()

    assert sanitizer.feed("开头 <thi") == "开头 "
    assert sanitizer.feed("nk>hidden") == ""
    assert sanitizer.feed(" text</thi") == ""
    assert sanitizer.feed("nk>正文") == "正文"
    assert sanitizer.flush() == ""


def test_stream_sanitizer_discards_unclosed_block_on_flush():
    sanitizer = ThinkBlockStreamSanitizer()

    assert sanitizer.feed("正文<think>hidden") == "正文"
    assert sanitizer.flush() == ""


def test_stream_sanitizer_keeps_normal_split_content():
    sanitizer = ThinkBlockStreamSanitizer()

    assert sanitizer.feed("普通") == "普通"
    assert sanitizer.feed("回复") == "回复"
    assert sanitizer.flush() == ""
