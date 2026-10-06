# Flight Booking Agent Homework

## Project layout

```text
Lab3/
|-- README.md
|-- requirements.txt
|-- examples/
|   |-- run_react.py
|   |-- run_plan_execute.py
|   `-- run_hybrid.py
|-- reports/
|   `-- agent_evaluation.md
`-- flight_booking_agent/
    |-- __init__.py
    |-- harness.py
    |-- mock_tools.py
    `-- agents/
        |-- __init__.py
        |-- common.py
        |-- react_agent.py
        |-- plan_execute_agent.py
        `-- hybrid_agent.py
```

## Responsibility boundary

- The model proposes tool calls or a plan; it does not execute tools or declare success.
- `Harness` owns hard constraints, approval gates, budgets, loop/stagnation checks, audit history, and handoff state.
- `MockFlightTools` is deterministic and returns JSON-serializable dictionaries.
- Completion is accepted only after `get_booking` and code-based checks of status, route, date, fare, currency, time, seat, and refundability when requested.

Install dependencies with `pip install -r requirements.txt`. The runner automatically loads `OPENAI_API_KEY` and optional `OPENAI_MODEL` from the project-root `.env`; no terminal export is needed. The default model is `gpt-4o-mini`. Keep `.env` out of source control.

## Run each pattern separately

Each command starts a fresh mock inventory and Harness, and appends metrics only to that pattern's JSONL file. Run one command at a time with the same arguments to compare results fairly:

```powershell
python -m examples.run_react
python -m examples.run_plan_execute
python -m examples.run_hybrid
```

The approval prompt pauses before sensitive booking/payment actions. Metrics are saved to `runs/react.jsonl`, `runs/plan_execute.jsonl`, and `runs/hybrid.jsonl`. Override route, date, budget, model, or output directory with command-line options; run `python -m examples.run_react --help` for available options.

The mock inventory contains sample flights on 2026-11-10 and 2026-11-11. Provide matching `BookingConstraints` when trying the agents.