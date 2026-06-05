from __future__ import annotations

from app.agent.asr_realtime import normalize_asr_base_url


def test_normalize_asr_base_url_fixes_scheme_and_trailing_slash() -> None:
    assert (
        normalize_asr_base_url("hwss://dashscope.aliyuncs.com/api-ws/v1/realtime/")
        == "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    )


def test_normalize_asr_base_url_keeps_empty_value() -> None:
    assert normalize_asr_base_url("") == ""
