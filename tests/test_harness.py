import json
import unittest

from flight_booking_agent.agents.common import tools_for_harness
from flight_booking_agent.harness import (
    BookingConstraints,
    Harness,
    HarnessConfig,
    StopReason,
)
from flight_booking_agent.mock_tools import MockFlightTools


class HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.constraints = BookingConstraints(
            origin="HAN",
            destination="SGN",
            travel_date="2026-11-10",
            max_price=2_500_000,
            passenger_name="Test User",
            preferred_seat="12A",
        )

    def test_approved_booking_is_verified_by_code(self) -> None:
        tools = MockFlightTools()
        harness = Harness(
            self.constraints,
            tools,
            HarnessConfig(max_steps=8, approval_price_threshold=2_400_000),
        )
        self.assertEqual(
            harness.execute_tool(
                "search_flights",
                origin="HAN",
                destination="SGN",
                date="2026-11-10",
                max_price=2_500_000,
            )["count"],
            2,
        )
        self.assertTrue(harness.execute_tool("check_seat", flight_id="VN101", seat="12A")["available"])
        pending = harness.execute_tool(
            "book_seat", flight_id="VN101", seat="12A", passenger_name="Test User"
        )
        self.assertEqual(pending["handoff"]["reason"], StopReason.HUMAN_APPROVAL.value)
        booking = harness.resolve_approval(True)["booking"]
        code = booking["booking_code"]
        self.assertEqual(
            harness.execute_tool("pay", booking_code=code, amount=2_450_000)["handoff"]["reason"],
            StopReason.HUMAN_APPROVAL.value,
        )
        self.assertEqual(harness.resolve_approval(True)["status"], "paid")
        result = harness.execute_tool("get_booking", booking_code=code)
        self.assertEqual(result["handoff"]["reason"], StopReason.GOAL_REACHED.value)
        self.assertTrue(result["verification"]["verified"])

    def test_hard_constraint_blocks_tool_execution(self) -> None:
        tools = MockFlightTools()
        harness = Harness(self.constraints, tools)
        result = harness.execute_tool(
            "search_flights",
            origin="HAN",
            destination="SGN",
            date="2026-11-11",
            max_price=2_500_000,
        )
        self.assertEqual(result["error"], "date_constraint_violation")
        self.assertEqual(tools._bookings, {})
        self.assertEqual(harness.state["failed_directions"], ["search_flights: date_constraint_violation"])

    def test_stagnation_hands_off_with_failed_directions(self) -> None:
        harness = Harness(
            self.constraints,
            MockFlightTools(),
            HarnessConfig(stagnation_limit=2, repeated_action_limit=10),
        )
        arguments = {
            "origin": "HAN",
            "destination": "SGN",
            "date": "2026-11-11",
            "max_price": 2_500_000,
        }
        harness.execute_tool("search_flights", **arguments)
        result = harness.execute_tool("search_flights", **arguments)
        self.assertEqual(result["handoff"]["reason"], StopReason.STAGNATION.value)
        self.assertEqual(
            result["handoff"]["failed_directions"],
            ["search_flights: date_constraint_violation"] * 2,
        )

    def test_rejected_approval_stops_the_session(self) -> None:
        harness = Harness(self.constraints, MockFlightTools())
        pending = harness.execute_tool(
            "book_seat", flight_id="VJ203", seat="18A", passenger_name="Test User"
        )
        self.assertEqual(pending["handoff"]["reason"], StopReason.HUMAN_APPROVAL.value)
        harness.resolve_approval(False)
        result = harness.execute_tool(
            "search_flights",
            origin="HAN",
            destination="SGN",
            date="2026-11-10",
            max_price=2_500_000,
        )
        self.assertEqual(result["handoff"]["reason"], StopReason.TOOL_ERROR.value)

    def test_loop_detector_uses_recent_action_window(self) -> None:
        harness = Harness(self.constraints, MockFlightTools(), HarnessConfig(loop_window=2))
        action = {
            "origin": "HAN",
            "destination": "SGN",
            "date": "2026-11-10",
            "max_price": 2_500_000,
        }
        harness.execute_tool("search_flights", **action)
        result = harness.execute_tool("search_flights", **action)
        self.assertEqual(result["handoff"]["reason"], StopReason.LOOP_DETECTED.value)

        fresh = Harness(self.constraints, MockFlightTools(), HarnessConfig(loop_window=2))
        fresh.execute_tool("search_flights", **action)
        fresh.execute_tool("check_seat", flight_id="VN101", seat="12A")
        fresh.execute_tool("search_flights", **{**action, "max_price": 2_400_000})
        result = fresh.execute_tool("search_flights", **action)
        self.assertNotIn("handoff", result)

    def test_step_and_token_budgets(self) -> None:
        harness = Harness(self.constraints, MockFlightTools(), HarnessConfig(max_steps=1))
        action = {
            "origin": "HAN",
            "destination": "SGN",
            "date": "2026-11-10",
            "max_price": 2_500_000,
        }
        self.assertTrue(harness.execute_tool("search_flights", **action)["ok"])
        result = harness.execute_tool("search_flights", **action)
        self.assertEqual(result["handoff"]["reason"], StopReason.BUDGET_EXHAUSTED.value)

        token_limited = Harness(self.constraints, MockFlightTools(), HarnessConfig(max_tokens=2))
        token_limited.record_model_usage(3)
        result = token_limited.execute_tool("search_flights", **action)
        self.assertEqual(result["handoff"]["reason"], StopReason.BUDGET_EXHAUSTED.value)

    def test_langchain_tools_return_structured_observations_through_harness(self) -> None:
        harness = Harness(self.constraints, MockFlightTools())
        search_tool = tools_for_harness(harness)[0]
        response = json.loads(
            search_tool.invoke(
                {
                    "origin": "HAN",
                    "destination": "SGN",
                    "date": "2026-11-10",
                    "max_price": 2_500_000,
                }
            )
        )
        self.assertEqual(response["count"], 2)
        self.assertEqual(harness.history[-1]["tool"], "search_flights")


if __name__ == "__main__":
    unittest.main()