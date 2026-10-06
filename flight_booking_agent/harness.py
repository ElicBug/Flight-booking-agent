"""Code-owned guardrails and termination logic for flight-booking agents."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, Callable


class StopReason(str, Enum):
    GOAL_REACHED = "goal_reached"
    BUDGET_EXHAUSTED = "budget_exhausted"
    LOOP_DETECTED = "loop_detected"
    STAGNATION = "stagnation"
    HUMAN_APPROVAL = "human_approval_required"
    TOOL_ERROR = "tool_error"
    CONSTRAINT_VIOLATION = "constraint_violation"


@dataclass(frozen=True)
class BookingConstraints:
    origin: str
    destination: str
    travel_date: str
    max_price: int
    currency: str = "VND"
    departure_not_before: str | None = None
    departure_not_after: str | None = None
    passenger_name: str | None = None
    preferred_seat: str | None = None
    refundable_only: bool = False


@dataclass(frozen=True)
class HarnessConfig:
    max_steps: int = 16
    max_tokens: int = 8_000
    loop_window: int = 6
    repeated_action_limit: int = 2
    stagnation_limit: int = 4
    approval_price_threshold: int | None = None
    approval_required_for_nonrefundable: bool = True


@dataclass
class Handoff:
    reason: str
    current_state: dict[str, Any]
    failed_directions: list[str]
    question: str


@dataclass
class Harness:
    constraints: BookingConstraints
    tools: Any
    config: HarnessConfig = field(default_factory=HarnessConfig)
    step_count: int = 0
    token_count: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    _recent_actions: deque[str] = field(init=False)
    _no_progress_count: int = 0
    _pending_approval: tuple[str, str, dict[str, Any]] | None = None
    _approved_action: str | None = None
    _stopped: bool = False

    def __post_init__(self) -> None:
        self._recent_actions = deque(maxlen=self.config.loop_window)
        self.state = {"constraints": asdict(self.constraints)}

    def record_model_usage(self, tokens: int) -> None:
        """Account for usage reported by the model adapter, then enforce budget."""
        self.token_count += max(tokens, 0)
        self._check_budget()

    def request_handoff(self, reason: StopReason, question: str) -> dict[str, Any]:
        """Create the standard handoff envelope for an agent-level decision."""
        return self._handoff(reason, question)

    def execute_tool(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        """Validate, authorize, execute, and record one tool call."""
        if not self._check_budget():
            return self._handoff(StopReason.BUDGET_EXHAUSTED, "Có thể tăng ngân sách hoặc thu hẹp yêu cầu?")
        if self._stopped:
            return self._handoff(StopReason.TOOL_ERROR, "Agent đã dừng; cần khởi tạo lượt mới.")

        normalized = json.dumps(
            {"tool": tool_name, "arguments": arguments}, sort_keys=True, ensure_ascii=True
        )
        self.step_count += 1
        approved_replay = self._approved_action == normalized
        if not approved_replay:
            occurrences_in_window = sum(action == normalized for action in self._recent_actions)
            if occurrences_in_window >= self.config.repeated_action_limit - 1:
                return self._handoff(StopReason.LOOP_DETECTED, "Bạn muốn thử hướng khác hay dừng tại đây?")
            self._recent_actions.append(normalized)

        violation = self._validate_call(tool_name, arguments)
        if violation:
            result = {"ok": False, "error": violation}
            self.state.setdefault("failed_directions", []).append(f"{tool_name}: {violation}")
            self._no_progress_count += 1
            self._record(tool_name, arguments, result, progress=False)
            if self._no_progress_count >= self.config.stagnation_limit:
                return self._handoff(
                    StopReason.STAGNATION,
                    "Các hướng hiện tại không đạt ràng buộc. Bạn muốn điều chỉnh ngày, tuyến bay hay ngân sách?",
                )
            return result

        approval_reason = self._approval_reason(tool_name, arguments)
        if approval_reason and self._approved_action != normalized:
            self._pending_approval = (normalized, tool_name, arguments)
            return self._handoff(
                StopReason.HUMAN_APPROVAL,
                f"Duyệt {tool_name} với mức giá/điều kiện này? (Có/Không)",
                extra={"approval_reason": approval_reason, "proposed_action": {"tool": tool_name, "arguments": arguments}},
            )
        if self._approved_action == normalized:
            self._approved_action = None
            self._pending_approval = None

        tool = getattr(self.tools, tool_name, None)
        if not callable(tool) or tool_name.startswith("_"):
            return self._record(tool_name, arguments, {"ok": False, "error": "unknown_tool"}, progress=False)

        previous_state = json.dumps(self.state, sort_keys=True, default=str)
        try:
            result = tool(**arguments)
        except (TypeError, ValueError) as error:
            result = {"ok": False, "error": "invalid_tool_arguments", "detail": str(error)}
        progress = bool(result.get("ok"))
        self._record(tool_name, arguments, result, progress=False)
        if result.get("ok"):
            self._update_state(tool_name, result)
            progress = json.dumps(self.state, sort_keys=True, default=str) != previous_state
        self._no_progress_count = 0 if progress else self._no_progress_count + 1

        if not result.get("ok"):
            self.state.setdefault("failed_directions", []).append(
                f"{tool_name}: {result.get('error', 'unknown error')}"
            )
        if self._no_progress_count >= self.config.stagnation_limit:
            return self._handoff(StopReason.STAGNATION, "Bạn có thể cung cấp lựa chọn thay thế hoặc điều chỉnh yêu cầu?")
        if tool_name == "get_booking" and self._goal_is_met(result):
            return self._handoff(StopReason.GOAL_REACHED, "Đặt chỗ đã được xác nhận.", terminal=True)
        return result

    def resolve_approval(self, approved: bool) -> dict[str, Any]:
        """Resume a gated call after a human explicitly approves or rejects it."""
        if self._pending_approval is None:
            return {"ok": False, "error": "no_pending_approval"}
        normalized, tool_name, arguments = self._pending_approval
        self._pending_approval = None
        if not approved:
            result = self._handoff(
                StopReason.HUMAN_APPROVAL,
                "Có thể chọn chuyến khác hoặc xác nhận dừng?",
            )
            self._stopped = True
            return result
        self._approved_action = normalized
        return self.execute_tool(tool_name, **arguments)

    def verify_booking(self, booking_code: str) -> dict[str, Any]:
        """Fetch and independently validate booking facts against hard constraints."""
        result = self.tools.get_booking(booking_code)
        if not result.get("ok"):
            return {"ok": False, "verified": False, "reason": "booking_not_found", "booking": result}
        booking = result["booking"]
        flight = result.get("flight", {})
        checks = {
            "confirmed": booking.get("status") == "confirmed",
            "date_matches": booking.get("date") == self.constraints.travel_date,
            "price_within_limit": booking.get("price", self.constraints.max_price + 1) <= self.constraints.max_price,
            "currency_matches": booking.get("currency") == self.constraints.currency,
            "route_matches": flight.get("origin") == self.constraints.origin.upper()
            and flight.get("destination") == self.constraints.destination.upper(),
            "departure_time_matches": self._time_matches(flight.get("departure_time")),
            "seat_matches": not self.constraints.preferred_seat
            or booking.get("seat") == self.constraints.preferred_seat.upper(),
        }
        if self.constraints.refundable_only:
            checks["refundable"] = flight.get("refundable") is True
        return {"ok": all(checks.values()), "verified": all(checks.values()), "checks": checks, "booking": booking}

    def _goal_is_met(self, tool_result: dict[str, Any]) -> bool:
        booking = tool_result.get("booking", {})
        if not booking.get("booking_code"):
            return False
        verification = self.verify_booking(booking["booking_code"])
        return verification["verified"]

    def _validate_call(self, tool_name: str, arguments: dict[str, Any]) -> str | None:
        if tool_name == "search_flights":
            if arguments.get("origin", "").upper() != self.constraints.origin.upper():
                return "origin_constraint_violation"
            if arguments.get("destination", "").upper() != self.constraints.destination.upper():
                return "destination_constraint_violation"
            if arguments.get("date") != self.constraints.travel_date:
                return "date_constraint_violation"
            if arguments.get("max_price", self.constraints.max_price + 1) > self.constraints.max_price:
                return "price_constraint_violation"
        elif tool_name in {"check_seat", "book_seat"}:
            flight_result = self.tools.get_flight(arguments.get("flight_id", ""))
            flight = flight_result.get("flight", {})
            if not flight_result.get("ok"):
                return "flight_not_found"
            if flight.get("origin") != self.constraints.origin.upper() or flight.get("destination") != self.constraints.destination.upper():
                return "route_constraint_violation"
            if flight.get("date") != self.constraints.travel_date:
                return "date_constraint_violation"
            if flight.get("price", self.constraints.max_price + 1) > self.constraints.max_price:
                return "price_constraint_violation"
            if not self._time_matches(flight.get("departure_time")):
                return "departure_time_constraint_violation"
            if self.constraints.refundable_only and not flight.get("refundable"):
                return "refundability_constraint_violation"
            if tool_name == "book_seat" and self.constraints.passenger_name:
                if arguments.get("passenger_name") != self.constraints.passenger_name:
                    return "passenger_constraint_violation"
        elif tool_name == "pay":
            booking_result = self.tools.get_booking(arguments.get("booking_code", ""))
            booking = booking_result.get("booking", {})
            if not booking_result.get("ok"):
                return "booking_not_found"
            if arguments.get("amount") != booking.get("price"):
                return "payment_amount_mismatch"
            if arguments["amount"] > self.constraints.max_price:
                return "price_constraint_violation"
        return None

    def _approval_reason(self, tool_name: str, arguments: dict[str, Any]) -> str | None:
        if tool_name == "book_seat":
            flight = self.tools.get_flight(arguments["flight_id"])["flight"]
            threshold = self.config.approval_price_threshold
            if threshold is not None and flight["price"] > threshold:
                return "price_above_approval_threshold"
            if self.config.approval_required_for_nonrefundable and not flight["refundable"]:
                return "nonrefundable_ticket"
        if tool_name == "pay":
            threshold = self.config.approval_price_threshold
            if threshold is not None and arguments["amount"] > threshold:
                return "payment_above_approval_threshold"
        return None

    def _time_matches(self, departure_time: str | None) -> bool:
        if departure_time is None:
            return False
        lower = self.constraints.departure_not_before
        upper = self.constraints.departure_not_after
        return (lower is None or departure_time >= lower) and (upper is None or departure_time <= upper)

    def _update_state(self, tool_name: str, result: dict[str, Any]) -> None:
        if tool_name == "search_flights":
            self.state["last_search"] = result
        elif tool_name == "check_seat":
            self.state["last_seat_check"] = result
        elif tool_name == "book_seat":
            self.state["booking"] = result.get("booking")
        elif tool_name == "pay":
            self.state["payment"] = result
        elif tool_name == "get_booking":
            self.state["booking"] = result.get("booking")

    def _record(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any], progress: bool
    ) -> dict[str, Any]:
        self.history.append({"step": self.step_count, "tool": tool_name, "arguments": arguments, "observation": result})
        return result

    def _check_budget(self) -> bool:
        if self.step_count < self.config.max_steps and self.token_count <= self.config.max_tokens:
            return True
        self._stopped = True
        return False

    def _handoff(
        self,
        reason: StopReason,
        question: str,
        *,
        terminal: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._stopped = terminal or reason not in {
            StopReason.GOAL_REACHED,
            StopReason.HUMAN_APPROVAL,
        }
        handoff = Handoff(
            reason=reason.value,
            current_state=self.state.copy(),
            failed_directions=list(self.state.get("failed_directions", [])),
            question=question,
        )
        result: dict[str, Any] = {"ok": reason == StopReason.GOAL_REACHED, "handoff": asdict(handoff)}
        if extra:
            result.update(extra)
        if reason == StopReason.GOAL_REACHED:
            result["verification"] = self.verify_booking(self.state["booking"]["booking_code"])
        return result
