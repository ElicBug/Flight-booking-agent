"""Shared setup and per-architecture metrics for the independent demo commands."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv

from flight_booking_agent.harness import BookingConstraints, Harness, HarnessConfig
from flight_booking_agent.mock_tools import MockFlightTools

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one flight-booking agent architecture.")
    parser.add_argument("--origin", default="HAN")
    parser.add_argument("--destination", default="SGN")
    parser.add_argument("--date", default="2026-11-10")
    parser.add_argument("--max-price", type=int, default=2_500_000)
    parser.add_argument("--currency", default="VND")
    parser.add_argument("--passenger", default="Demo Passenger")
    parser.add_argument("--seat", default="12A")
    parser.add_argument("--approval-price-threshold", type=int, default=1_500_000)
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=8_000)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "runs")
    parser.add_argument("--chunk-size", type=int, default=2)
    parser.add_argument("--max-turns", type=int, default=12)
    return parser.parse_args()


def create_harness(args: argparse.Namespace) -> Harness:
    constraints = BookingConstraints(
        origin=args.origin,
        destination=args.destination,
        travel_date=args.date,
        max_price=args.max_price,
        currency=args.currency,
        passenger_name=args.passenger,
        preferred_seat=args.seat,
    )
    config = HarnessConfig(
        max_steps=args.max_steps,
        max_tokens=args.max_tokens,
        approval_price_threshold=args.approval_price_threshold,
    )
    return Harness(constraints=constraints, tools=MockFlightTools(), config=config)


def create_model(model_name: str) -> Any:
    from langchain_openai import ChatOpenAI

    if model_name.startswith("openai/"):
        model_name = model_name.removeprefix("openai/")
    return ChatOpenAI(model=model_name, temperature=0)


def ask_for_approval(handoff: dict[str, Any]) -> bool:
    print("\nHuman approval required:")
    print(json.dumps(handoff.get("proposed_action", {}), indent=2, ensure_ascii=False))
    print(f"Reason: {handoff.get('approval_reason', 'sensitive action')}")
    return input("Approve? [y/N]: ").strip().lower() == "y"


def request_from_args(args: argparse.Namespace) -> str:
    return (
        f"Book one flight from {args.origin} to {args.destination} on {args.date}, "
        f"up to {args.max_price} {args.currency}. Passenger: {args.passenger}. "
        f"Use seat {args.seat}, then pay and verify the confirmed booking."
    )


def run_and_report(
    architecture: str,
    args: argparse.Namespace,
    harness: Harness,
    agent: Any,
) -> dict[str, Any]:
    started = time.perf_counter()
    request = request_from_args(args)
    if architecture == "react":
        result = agent.run(request, max_turns=args.max_turns)
    else:
        result = agent.run(request)
    elapsed_seconds = time.perf_counter() - started
    verification = result.get("verification", {})
    handoff = result.get("handoff", {})
    metrics = {
        "architecture": architecture,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "tool_steps": harness.step_count,
        "model_tokens": harness.token_count,
        "tool_calls": [entry["tool"] for entry in harness.history],
        "success": verification.get("verified", False),
        "stop_reason": handoff.get("reason", "unknown"),
        "failed_directions": handoff.get("failed_directions", harness.state.get("failed_directions", [])),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{architecture}.jsonl"
    with output_path.open("a", encoding="utf-8") as output_file:
        output_file.write(json.dumps(metrics, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {"result": result, "metrics": metrics, "metrics_file": str(output_path)},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return result