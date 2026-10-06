"""Run only the ReAct architecture."""

from examples.runtime import ask_for_approval, create_harness, create_model, parse_args, run_and_report
from flight_booking_agent.agents.react_agent import ReActAgent


def main() -> None:
    args = parse_args()
    harness = create_harness(args)
    agent = ReActAgent(create_model(args.model), harness, approval_handler=ask_for_approval)
    run_and_report("react", args, harness, agent)


if __name__ == "__main__":
    main()