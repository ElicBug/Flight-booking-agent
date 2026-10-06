"""Deterministic mock tools that return JSON-serializable dictionaries."""

from __future__ import annotations

from typing import Any


class MockFlightTools:
    """In-memory flight inventory and booking service for agent exercises."""

    def __init__(self) -> None:
        self._flights: dict[str, dict[str, Any]] = {
            "VN101": {
                "flight_id": "VN101",
                "origin": "HAN",
                "destination": "SGN",
                "date": "2026-11-10",
                "departure_time": "08:30",
                "arrival_time": "10:40",
                "price": 2_450_000,
                "currency": "VND",
                "refundable": True,
                "seats_available": ["12A", "12B", "14C"],
            },
            "VJ203": {
                "flight_id": "VJ203",
                "origin": "HAN",
                "destination": "SGN",
                "date": "2026-11-10",
                "departure_time": "13:15",
                "arrival_time": "15:25",
                "price": 1_850_000,
                "currency": "VND",
                "refundable": False,
                "seats_available": ["18A", "18B"],
            },
            "VN104": {
                "flight_id": "VN104",
                "origin": "SGN",
                "destination": "HAN",
                "date": "2026-11-11",
                "departure_time": "18:00",
                "arrival_time": "20:10",
                "price": 2_600_000,
                "currency": "VND",
                "refundable": True,
                "seats_available": ["10A"],
            },
        }
        self._bookings: dict[str, dict[str, Any]] = {}

    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        max_price: int | None = None,
    ) -> dict[str, Any]:
        matches = [
            self._public_flight(flight)
            for flight in self._flights.values()
            if flight["origin"] == origin.upper()
            and flight["destination"] == destination.upper()
            and flight["date"] == date
            and (max_price is None or flight["price"] <= max_price)
        ]
        matches.sort(key=lambda flight: flight["price"])
        return {"ok": True, "count": len(matches), "flights": matches}

    def check_seat(self, flight_id: str, seat: str) -> dict[str, Any]:
        flight = self._flights.get(flight_id)
        if flight is None:
            return {"ok": False, "error": "flight_not_found", "flight_id": flight_id}
        available = seat.upper() in flight["seats_available"]
        return {
            "ok": True,
            "flight_id": flight_id,
            "seat": seat.upper(),
            "available": available,
        }

    def book_seat(
        self,
        flight_id: str,
        seat: str,
        passenger_name: str,
    ) -> dict[str, Any]:
        flight = self._flights.get(flight_id)
        normalized_seat = seat.upper()
        if flight is None:
            return {"ok": False, "error": "flight_not_found", "flight_id": flight_id}
        if normalized_seat not in flight["seats_available"]:
            return {
                "ok": False,
                "error": "seat_unavailable",
                "flight_id": flight_id,
                "seat": normalized_seat,
            }

        flight["seats_available"].remove(normalized_seat)
        booking_code = f"BK{len(self._bookings) + 1:05d}"
        self._bookings[booking_code] = {
            "booking_code": booking_code,
            "flight_id": flight_id,
            "seat": normalized_seat,
            "passenger_name": passenger_name,
            "date": flight["date"],
            "price": flight["price"],
            "currency": flight["currency"],
            "status": "pending_payment",
            "payment_id": None,
        }
        return {"ok": True, "booking": dict(self._bookings[booking_code])}

    def pay(self, booking_code: str, amount: int) -> dict[str, Any]:
        booking = self._bookings.get(booking_code)
        if booking is None:
            return {"ok": False, "error": "booking_not_found", "booking_code": booking_code}
        if amount != booking["price"]:
            return {
                "ok": False,
                "error": "amount_mismatch",
                "expected_amount": booking["price"],
                "received_amount": amount,
            }
        if booking["status"] == "confirmed":
            return {"ok": True, "payment_id": booking["payment_id"], "status": "already_paid"}

        payment_id = f"PAY{len(self._bookings):05d}"
        booking["payment_id"] = payment_id
        booking["status"] = "confirmed"
        return {
            "ok": True,
            "payment_id": payment_id,
            "booking_code": booking_code,
            "amount": amount,
            "currency": booking["currency"],
            "status": "paid",
        }

    def get_booking(self, booking_code: str) -> dict[str, Any]:
        booking = self._bookings.get(booking_code)
        if booking is None:
            return {"ok": False, "error": "booking_not_found", "booking_code": booking_code}
        return {
            "ok": True,
            "booking": dict(booking),
            "flight": self.get_flight(booking["flight_id"])["flight"],
        }

    def get_flight(self, flight_id: str) -> dict[str, Any]:
        """Return public itinerary facts for code-owned constraint verification."""
        flight = self._flights.get(flight_id)
        if flight is None:
            return {"ok": False, "error": "flight_not_found", "flight_id": flight_id}
        return {"ok": True, "flight": self._public_flight(flight)}

    @staticmethod
    def _public_flight(flight: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in flight.items() if key != "seats_available"}
