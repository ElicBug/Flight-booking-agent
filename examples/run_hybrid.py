"""Run only the Hybrid architecture."""

from examples.runtime import ask_for_approval, create_harness, create_model, parse_args, run_and_report
from flight_booking_agent.agents.hybrid_agent import HybridAgent


def main() -> None:
    args = parse_args()
    harness = create_harness(args)
    agent = HybridAgent(
        create_model(args.model),
        harness,
        chunk_size=args.chunk_size,
        approval_handler=ask_for_approval,
    )
    run_and_report("hybrid", args, harness, agent)


if __name__ == "__main__":
    main()