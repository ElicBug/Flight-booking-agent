"""Run only the Plan-then-Execute architecture."""

from examples.runtime import ask_for_approval, create_harness, create_model, parse_args, run_and_report
from flight_booking_agent.agents.plan_execute_agent import PlanThenExecuteAgent


def main() -> None:
    args = parse_args()
    harness = create_harness(args)
    agent = PlanThenExecuteAgent(create_model(args.model), harness, approval_handler=ask_for_approval)
    run_and_report("plan_execute", args, harness, agent)


if __name__ == "__main__":
    main()