from __future__ import annotations

from app.company_agent.llm import (
    build_candidates_from_llm_result,
    cross_validate_with_web_search,
    discover_candidates_from_web_search,
    web_search_candidates,
)
from app.company_agent.models import (
    CompanyCandidate,
    CompanyResolveRequest,
    CompanyResolveResponse,
    CompanyState,
    CompanyStatePhase,
)
from app.integrations.qixin import QixinClient


class CompanyAgentService:
    def __init__(self) -> None:
        self._qixin_client: QixinClient | None = None

    @property
    def qixin_client(self) -> QixinClient:
        if self._qixin_client is None:
            self._qixin_client = QixinClient.from_env()
        return self._qixin_client

    def resolve(self, request: CompanyResolveRequest) -> CompanyResolveResponse:
        state = request.state or CompanyState()

        if request.selection_payload is not None:
            return self._handle_selection(state, request.selection_payload.candidate_id)

        if request.manual_input_payload is not None and request.manual_input_payload.confirm:
            return self._handle_manual_confirm(state, request.manual_input_payload.company_name)

        user_input = request.user_input.strip()
        if not user_input:
            return CompanyResolveResponse(
                status="need_manual_input",
                suggested_reply="请输入经销商名称。",
                state=CompanyState(phase=CompanyStatePhase.AWAITING_MANUAL_INPUT, raw_input=""),
            )

        state.raw_input = user_input

        discover_response = self._discover_and_verify(
            state, user_input, allow_unverified_fallback=False
        )
        if discover_response is not None:
            return discover_response

        # 阶段1: 启信宝直搜
        qixin_result = self.qixin_client.adv_search(user_input)

        qixin_candidates = _parse_qixin_candidates(qixin_result)

        # 启信宝返回0条
        if not qixin_candidates:
            return self._web_search_fallback(state, user_input)

        exact_match = next(
            (candidate for candidate in qixin_candidates if candidate.company_name == user_input),
            None,
        )
        if exact_match is not None:
            return CompanyResolveResponse(
                status="resolved",
                company_name=exact_match.company_name,
                suggested_reply=f"已校验通过：{exact_match.company_name}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        # 启信宝返回1条 → 检查是否可自动通过
        if len(qixin_candidates) == 1:
            return CompanyResolveResponse(
                status="resolved",
                company_name=qixin_candidates[0].company_name,
                suggested_reply=f"已校验通过：{qixin_candidates[0].company_name}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        # 启信宝返回2+条 → 联网交叉验证
        return self._cross_validate(state, user_input, qixin_candidates)

    def search_candidates(self, keyword: str) -> CompanyResolveResponse:
        user_input = keyword.strip()
        if not user_input:
            return CompanyResolveResponse(
                status="need_manual_input",
                suggested_reply="请输入经销商名称后再查询。",
                state=CompanyState(
                    phase=CompanyStatePhase.AWAITING_MANUAL_INPUT,
                    raw_input="",
                ),
            )

        qixin_result = self.qixin_client.adv_search(user_input)
        qixin_candidates = _parse_qixin_candidates(qixin_result)
        if not qixin_candidates:
            return CompanyResolveResponse(
                status="need_manual_input",
                suggested_reply="启信宝暂无匹配结果，请继续输入更完整的经销商名称。",
                state=CompanyState(
                    phase=CompanyStatePhase.AWAITING_MANUAL_INPUT,
                    raw_input=user_input,
                ),
            )

        return CompanyResolveResponse(
            status="need_select",
            suggested_reply="已根据当前输入查询到启信宝候选，请选择正确的经销商名称。",
            candidates=qixin_candidates,
            state=CompanyState(
                phase=CompanyStatePhase.AWAITING_SELECTION,
                candidates=qixin_candidates,
                raw_input=user_input,
            ),
        )

    def _web_search_fallback(
        self, state: CompanyState, user_input: str
    ) -> CompanyResolveResponse:
        try:
            result = web_search_candidates(user_input)
        except Exception:
            result = {}
        candidates = build_candidates_from_llm_result(result, default_source="web_search")

        if not candidates:
            return CompanyResolveResponse(
                status="need_manual_input",
                suggested_reply="未能找到匹配的公司，请手动输入完整的公司全称。",
                state=CompanyState(
                    phase=CompanyStatePhase.AWAITING_MANUAL_INPUT,
                    raw_input=user_input,
                ),
            )

        if len(candidates) == 1 and candidates[0].match_confidence == "high":
            return CompanyResolveResponse(
                status="resolved",
                company_name=candidates[0].company_name,
                suggested_reply=f"已校验通过：{candidates[0].company_name}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        return CompanyResolveResponse(
            status="need_select",
            suggested_reply="启信宝暂无匹配的公司，但联网搜索发现以下候选，请确认。",
            candidates=candidates,
            state=CompanyState(
                phase=CompanyStatePhase.AWAITING_SELECTION,
                candidates=candidates,
                raw_input=user_input,
            ),
        )

    def _discover_and_verify(
        self,
        state: CompanyState,
        user_input: str,
        allow_unverified_fallback: bool,
    ) -> CompanyResolveResponse | None:
        try:
            result = discover_candidates_from_web_search(user_input)
        except Exception:
            result = {}

        llm_candidates = build_candidates_from_llm_result(result, default_source="web_search")
        verified_candidates = self._verify_candidates_with_qixin(llm_candidates)

        if len(verified_candidates) == 1:
            return CompanyResolveResponse(
                status="resolved",
                company_name=verified_candidates[0].company_name,
                suggested_reply=f"已校验通过：{verified_candidates[0].company_name}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        if len(verified_candidates) > 1:
            return CompanyResolveResponse(
                status="need_select",
                suggested_reply="联网纠错后找到了多个已校验的公司，请确认。",
                candidates=verified_candidates,
                state=CompanyState(
                    phase=CompanyStatePhase.AWAITING_SELECTION,
                    candidates=verified_candidates,
                    raw_input=user_input,
                ),
            )

        if not allow_unverified_fallback:
            return None

        if not llm_candidates:
            return None

        return CompanyResolveResponse(
            status="need_select",
            suggested_reply="联网搜索发现了可能的公司名称，但暂未完成工商校验，请确认。",
            candidates=llm_candidates,
            state=CompanyState(
                phase=CompanyStatePhase.AWAITING_SELECTION,
                candidates=llm_candidates,
                raw_input=user_input,
            ),
        )

    def _verify_candidates_with_qixin(
        self,
        candidates: list[CompanyCandidate],
    ) -> list[CompanyCandidate]:
        verified: list[CompanyCandidate] = []
        seen_names: set[str] = set()

        for candidate in candidates:
            company_name = candidate.company_name.strip()
            if not company_name or company_name in seen_names:
                continue

            verified_name = self._find_exact_qixin_match(company_name)
            if verified_name is None or verified_name in seen_names:
                continue

            seen_names.add(verified_name)
            verified.append(
                CompanyCandidate(
                    candidate_id=f"verified_{len(verified)}",
                    company_name=verified_name,
                    source="both",
                    match_confidence="high",
                    match_reason=candidate.match_reason,
                )
            )

        return verified

    def _find_exact_qixin_match(self, company_name: str) -> str | None:
        result = self.qixin_client.adv_search(company_name)
        candidates = _parse_qixin_candidates(result)
        exact_match = next(
            (candidate for candidate in candidates if candidate.company_name == company_name),
            None,
        )
        if exact_match is None:
            return None
        return exact_match.company_name

    def _cross_validate(
        self,
        state: CompanyState,
        user_input: str,
        qixin_candidates: list[CompanyCandidate],
    ) -> CompanyResolveResponse:
        try:
            result = cross_validate_with_web_search(user_input, qixin_candidates)
            llm_candidates = build_candidates_from_llm_result(
                result, default_source="web_search"
            )
        except Exception:
            result = {}
            llm_candidates = []

        merged = _merge_and_rank(qixin_candidates, llm_candidates)

        if result.get("auto_resolve"):
            return CompanyResolveResponse(
                status="resolved",
                company_name=result.get("auto_resolve_name"),
                suggested_reply=f"已校验通过：{result.get('auto_resolve_name')}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        if len(merged) == 1:
            return CompanyResolveResponse(
                status="resolved",
                company_name=merged[0].company_name,
                suggested_reply=f"已校验通过：{merged[0].company_name}",
                state=CompanyState(phase=CompanyStatePhase.RESOLVED, raw_input=user_input),
            )

        return CompanyResolveResponse(
            status="need_select",
            suggested_reply="查到了几个可能的公司名称，请选择您要找的那一个。",
            candidates=merged,
            state=CompanyState(
                phase=CompanyStatePhase.AWAITING_SELECTION,
                candidates=merged,
                raw_input=user_input,
            ),
        )

    def _handle_selection(
        self, state: CompanyState, candidate_id: str
    ) -> CompanyResolveResponse:
        for candidate in state.candidates:
            if candidate.candidate_id == candidate_id:
                return CompanyResolveResponse(
                    status="resolved",
                    company_name=candidate.company_name,
                    suggested_reply=f"已校验通过：{candidate.company_name}",
                    state=CompanyState(
                        phase=CompanyStatePhase.RESOLVED,
                        raw_input=state.raw_input,
                    ),
                )

        return CompanyResolveResponse(
            status="need_select",
            suggested_reply="未找到您选择的公司，请重新选择。",
            candidates=state.candidates,
            state=state.model_copy(update={"phase": CompanyStatePhase.AWAITING_SELECTION}),
        )

    def _handle_manual_confirm(
        self, state: CompanyState, company_name: str
    ) -> CompanyResolveResponse:
        return CompanyResolveResponse(
            status="resolved",
            company_name=company_name.strip(),
            suggested_reply=f"已保存公司名称：{company_name.strip()}",
            state=CompanyState(
                phase=CompanyStatePhase.RESOLVED,
                raw_input=state.raw_input,
            ),
        )


def _parse_qixin_candidates(qixin_result: dict) -> list[CompanyCandidate]:
    candidates: list[CompanyCandidate] = []
    data = qixin_result.get("data", [])
    items = data.get("items", []) if isinstance(data, dict) else data
    if isinstance(items, list):
        for idx, item in enumerate(items):
            name = item.get("companyName") or item.get("name") or ""
            if not name:
                continue
            candidates.append(CompanyCandidate(
                candidate_id=f"qixin_{idx}",
                company_name=name,
                source="qixin",
                match_confidence="medium",
            ))
    return candidates


def _merge_and_rank(
    qixin_candidates: list[CompanyCandidate],
    web_candidates: list[CompanyCandidate],
) -> list[CompanyCandidate]:
    seen_names: set[str] = set()
    merged: list[CompanyCandidate] = []

    web_name_set = {c.company_name for c in web_candidates}

    for c in qixin_candidates:
        if c.company_name in seen_names:
            continue
        seen_names.add(c.company_name)
        if c.company_name in web_name_set:
            c.source = "both"
            c.match_confidence = "high"
        merged.append(c)

    for c in web_candidates:
        if c.company_name in seen_names:
            continue
        seen_names.add(c.company_name)
        merged.append(c)

    source_order = {"both": 0, "qixin": 1, "web_search": 2}
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    merged.sort(key=lambda c: (source_order.get(c.source, 3), confidence_order.get(c.match_confidence, 3)))
    return merged
