from __future__ import annotations

import pytest

from app.company_agent.models import (
    CompanyCandidate,
    CompanyResolveRequest,
    CompanyState,
    CompanyStatePhase,
    SelectionPayload,
    ManualInputPayload,
)
from app.company_agent.service import _merge_and_rank, _parse_qixin_candidates


class TestParseQixinCandidates:
    def test_empty_result(self):
        result = _parse_qixin_candidates({})
        assert result == []

    def test_parses_company_name(self):
        payload = {
            "data": [
                {"companyName": "上海字节跳动科技有限公司"},
                {"name": "北京百度网讯科技有限公司"},
            ]
        }
        result = _parse_qixin_candidates(payload)
        assert len(result) == 2
        assert result[0].company_name == "上海字节跳动科技有限公司"
        assert result[0].source == "qixin"
        assert result[0].candidate_id == "qixin_0"

    def test_skips_empty_names(self):
        payload = {
            "data": [
                {"companyName": ""},
                {"name": "有效公司"},
                {},
            ]
        }
        result = _parse_qixin_candidates(payload)
        assert len(result) == 1
        assert result[0].company_name == "有效公司"


class TestMergeAndRank:
    def test_merge_no_overlap(self):
        qixin = [
            CompanyCandidate(candidate_id="q1", company_name="公司A", source="qixin", match_confidence="medium"),
        ]
        web = [
            CompanyCandidate(candidate_id="w1", company_name="公司B", source="web_search", match_confidence="medium"),
        ]
        merged = _merge_and_rank(qixin, web)
        assert len(merged) == 2

    def test_merge_overlap_marks_both(self):
        qixin = [
            CompanyCandidate(candidate_id="q1", company_name="公司A", source="qixin", match_confidence="medium"),
        ]
        web = [
            CompanyCandidate(candidate_id="w1", company_name="公司A", source="web_search", match_confidence="high"),
        ]
        merged = _merge_and_rank(qixin, web)
        assert len(merged) == 1
        assert merged[0].source == "both"
        assert merged[0].match_confidence == "high"

    def test_both_ranked_first(self):
        web = [
            CompanyCandidate(candidate_id="w1", company_name="公司A", source="web_search", match_confidence="high"),
        ]
        merged = _merge_and_rank(
            [CompanyCandidate(candidate_id="q2", company_name="公司A", source="qixin", match_confidence="high")],
            web,
        )
        assert merged[0].source == "both"
        assert merged[0].match_confidence == "high"


class TestCompanyStateModel:
    def test_default_state(self):
        state = CompanyState()
        assert state.phase == CompanyStatePhase.IDLE
        assert state.candidates == []
        assert state.raw_input == ""

    def test_state_transition(self):
        state = CompanyState(
            phase=CompanyStatePhase.AWAITING_SELECTION,
            candidates=[CompanyCandidate(
                candidate_id="1",
                company_name="测试公司",
                source="qixin",
                match_confidence="high",
            )],
            raw_input="测试",
        )
        assert state.phase == CompanyStatePhase.AWAITING_SELECTION
        assert len(state.candidates) == 1


class TestCompanyResolveRequest:
    def test_empty_input(self):
        request = CompanyResolveRequest(user_input="")
        assert request.user_input == ""
        assert request.state is None

    def test_with_state(self):
        state = CompanyState(raw_input="测试")
        request = CompanyResolveRequest(user_input="测试", state=state)
        assert request.state.raw_input == "测试"

    def test_with_selection(self):
        request = CompanyResolveRequest(
            user_input="测试",
            selection_payload=SelectionPayload(candidate_id="qixin_0"),
        )
        assert request.selection_payload.candidate_id == "qixin_0"

    def test_with_manual_input(self):
        request = CompanyResolveRequest(
            user_input="测试",
            manual_input_payload=ManualInputPayload(company_name="测试公司", confirm=True),
        )
        assert request.manual_input_payload.company_name == "测试公司"
        assert request.manual_input_payload.confirm is True
