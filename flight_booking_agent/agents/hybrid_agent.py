"""Hybrid: plan, execute a short segment, then evaluate and replan as needed."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from flight_booking_agent.harness import Harness, StopReason
from flight_booking_agent.agents.common import (
    FlightPlan,
    PlanReview,
    PlanStep,
    execute_plan_step,
    parse_structured_response,
    stop_if_handoff,
    system_prompt,
)


class HybridAgent:
    def __init__(
        self,
        model: Any,
        harness: Harness,
        chunk_size: int = 2,
        approval_handler: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.model = model
        self.harness = harness
        self.chunk_size = max(1, chunk_size)
        self.approval_handler = approval_handler

    def run(self, request: str, max_replans: int = 3) -> dict[str, Any]:
        planner = self.model.with_structured_output(
            FlightPlan,
            method="function_calling",
            include_raw=True,
        )
        reviewer = self.model.with_structured_output(
            PlanReview,
            method="function_calling",
            include_raw=True,
        )
        response = planner.invoke(
            [
                SystemMessage(content=system_prompt(self.harness)),
                HumanMessage(
                    content=(
                        f"Plan the tool calls needed for: {request}. Use "
                        "$state.last_search.flights[0].flight_id for the selected flight, "
                        "$state.booking.booking_code for payment/verification, and "
                        "$state.booking.price for the amount; do not invent returned values."
                    )
                ),
            ]
        )
        plan, budget_handoff = parse_structured_response(self.harness, response)
        if budget_handoff or plan is None:
            return budget_handoff

        cursor = 0
        replans = 0
        while cursor < len(plan.steps):
            segment = plan.steps[cursor : cursor + self.chunk_size]
            observations: list[dict[str, Any]] = []
            for step in segment:
                result = execute_plan_step(self.harness, step, self.approval_handler)
                if stop_if_handoff(result):
                    return result
                observations.append({"step": step.model_dump(), "result": result})
                cursor += 1

            review_response = reviewer.invoke(
                [
                    SystemMessage(content=system_prompt(self.harness)),
                    HumanMessage(
                        content=(
                            "Review current plan progress and observations. Replan only if needed. "
                            f"Current state: {json.dumps(self.harness.state, ensure_ascii=False, default=str)}\n"
                            f"Recent observations: {json.dumps(observations, ensure_ascii=False, default=str)}"
                        )
                    ),
                ]
            )
            review, budget_handoff = parse_structured_response(self.harness, review_response)
            if budget_handoff or review is None:
                return budget_handoff
            if review.replan:
                replans += 1
                if replans > max_replans:
                    return self.harness.request_handoff(
                        StopReason.STAGNATION,
                        "Đã đạt giới hạn lập lại kế hoạch. Bạn muốn đổi ràng buộc hay dừng?",
                    )
                plan = FlightPlan(steps=review.replacement_steps)
                cursor = 0
                if not plan.steps:
                    return self.harness.request_handoff(
                        StopReason.TOOL_ERROR,
                        "Mô hình chưa đưa ra bước tiếp theo. Bạn muốn bổ sung thông tin nào?",
                    )

        return self.harness.request_handoff(
            StopReason.TOOL_ERROR,
            "Kế hoạch đã chạy nhưng booking chưa được xác minh. Bạn muốn điều chỉnh yêu cầu?",
        )