"""ReAct: reason, call one tool, observe, and repeat."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from flight_booking_agent.harness import Harness, StopReason
from flight_booking_agent.agents.common import (
    account_usage,
    execute_tool_with_approval,
    system_prompt,
    tools_for_harness,
)


class ReActAgent:
    def __init__(
        self,
        model: Any,
        harness: Harness,
        approval_handler: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.harness = harness
        self.approval_handler = approval_handler
        self.tools = tools_for_harness(harness)
        self.model = model.bind_tools(self.tools)

    def run(self, request: str, max_turns: int = 12) -> dict[str, Any]:
        messages = [
            SystemMessage(content=system_prompt(self.harness)),
            HumanMessage(content=request),
        ]
        for _ in range(max_turns):
            response = self.model.invoke(messages)
            budget_handoff = account_usage(self.harness, response)
            if budget_handoff:
                return budget_handoff
            messages.append(response)
            calls = getattr(response, "tool_calls", [])
            if not calls:
                return self.harness.request_handoff(
                    StopReason.TOOL_ERROR,
                    "Chưa có booking được xác minh. Bạn muốn cung cấp thêm thông tin hay dừng?",
                )
            for call in calls:
                result = execute_tool_with_approval(
                    self.harness,
                    call["name"],
                    call["args"],
                    self.approval_handler,
                )
                if "handoff" in result:
                    return result
                messages.append(
                    ToolMessage(
                        content=json.dumps(result, ensure_ascii=False, default=str),
                        tool_call_id=call["id"],
                    )
                )
        return self.harness.request_handoff(
            StopReason.BUDGET_EXHAUSTED,
            "Đã hết số lượt suy luận. Có thể tăng giới hạn lượt hoặc thu hẹp yêu cầu?",
        )