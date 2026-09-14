"""Smart Fitness Session Analyzer — entry point.

Run from the repository root:
    python3 main.py
"""

from models import Participant
from analysis import analyse_session
from sample_data import load_all_scenarios


def main() -> None:
    scenarios = load_all_scenarios()

    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n{'#' * 52}")
        print(f"  SCENARIO {i}: {scenario['label']}")
        print(f"{'#' * 52}")

        participant = Participant.from_dict(scenario["profile"])
        results = analyse_session(participant, scenario["observations"])

        print(results["report"])


if __name__ == "__main__":
    main()