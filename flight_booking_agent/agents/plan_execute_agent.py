"""Plan-then-Execute: create one structured plan, then execute it in order."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from flight_booking_agent.harness import Harness, StopReason
from flight_booking_agent.agents.common import (
    FlightPlan,
    execute_plan_step,
    parse_structured_response,
    stop_if_handoff,
    system_prompt,
)


class PlanThenExecuteAgent:
    def __init__(
        self,
        model: Any,
        harness: Harness,
        approval_handler: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.model = model
        self.harness = harness
        self.approval_handler = approval_handler

    def run(self, request: str) -> dict[str, Any]:
        planner = self.model.with_structured_output(
            FlightPlan,
            method="function_calling",
            include_raw=True,
        )
        response = planner.invoke(
            [
                SystemMessage(content=system_prompt(self.harness)),
                HumanMessage(
                    content=(
                        f"Create a complete ordered flight booking tool plan for: {request}. "
                        "Use only the allowed tool names and include get_booking after payment. "
                        "Use $state.last_search.flights[0].flight_id for the selected flight, "
                        "$state.booking.booking_code for payment/verification, and "
                        "$state.booking.price for the amount; never invent returned values."
                    )
                ),
            ]
        )
        plan, budget_handoff = parse_structured_response(self.harness, response)
        if budget_handoff or plan is None:
            return budget_handoff
        for step in plan.steps:
            result = execute_plan_step(self.harness, step, self.approval_handler)
            if stop_if_handoff(result):
                return result
        return self.harness.request_handoff(
            StopReason.TOOL_ERROR,
            "Kế hoạch đã chạy nhưng booking chưa được xác minh. Bạn muốn điều chỉnh yêu cầu?",
        )