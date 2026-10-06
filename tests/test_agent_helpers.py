import unittest

from flight_booking_agent.agents.common import (
    PlanStep,
    execute_plan_step,
    execute_tool_with_approval,
)
from flight_booking_agent.harness import BookingConstraints, Harness, HarnessConfig
from flight_booking_agent.mock_tools import MockFlightTools


class AgentHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.constraints = BookingConstraints(
            origin="HAN",
            destination="SGN",
            travel_date="2026-11-10",
            max_price=2_500_000,
            passenger_name="Demo Passenger",
            preferred_seat="18A",
        )

    def test_plan_references_resolve_values_from_observations(self) -> None:
        harness = Harness(
            self.constraints,
            MockFlightTools(),
            HarnessConfig(approval_required_for_nonrefundable=False),
        )
        harness.execute_tool(
            "search_flights",
            origin="HAN",
            destination="SGN",
            date="2026-11-10",
            max_price=2_500_000,
        )
        booked = execute_plan_step(
            harness,
            PlanStep(
                tool="book_seat",
                arguments={
                    "flight_id": "$state.last_search.flights[0].flight_id",
                    "seat": "18A",
                    "passenger_name": "$constraints.passenger_name",
                },
            ),
        )
        booking_code = booked["booking"]["booking_code"]
        paid = execute_plan_step(
            harness,
            PlanStep(
                tool="pay",
                arguments={
                    "booking_code": "$state.booking.booking_code",
                    "amount": "$state.booking.price",
                },
            ),
        )
        self.assertEqual(paid["status"], "paid")
        completed = execute_plan_step(
            harness,
            PlanStep(
                tool="get_booking",
                arguments={"booking_code": booking_code},
            ),
        )
        self.assertTrue(completed["verification"]["verified"])

    def test_approval_callback_executes_only_after_approval(self) -> None:
        harness = Harness(self.constraints, MockFlightTools())
        result = execute_tool_with_approval(
            harness,
            "book_seat",
            {
                "flight_id": "VJ203",
                "seat": "18A",
                "passenger_name": "Demo Passenger",
            },
            lambda handoff: handoff["approval_reason"] == "nonrefundable_ticket",
        )
        self.assertTrue(result["ok"])
        self.assertIn("booking", result)


if __name__ == "__main__":
    unittest.main()