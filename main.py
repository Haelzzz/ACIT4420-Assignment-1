"""Smart Fitness Session Analyzer - entry point.

Run from the repository root:
    python3 main.py --profiles data/participants.csv \
                    --sessions data/fitness_sessions.csv \
                    --invalid data/fitness_sessions_invalid.csv \
                    --output output
"""

import argparse
from pathlib import Path

from fitness_analyzer.models import Participant
from fitness_analyzer.analysis import analyse_session
from fitness_analyzer.io_handler import (
    load_participants,
    load_sessions,
    ensure_output_dir,
    write_summary_csv,
    write_report_txt,
    write_rejected_txt,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart Fitness Session Analyzer"
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("data/participants.csv"),
        help="Path to participants CSV (default: data/participants.csv)",
    )
    parser.add_argument(
        "--sessions",
        type=Path,
        default=Path("data/fitness_sessions.csv"),
        help="Path to valid sessions CSV (default: data/fitness_sessions.csv)",
    )
    parser.add_argument(
        "--invalid",
        type=Path,
        default=Path("data/fitness_sessions_invalid.csv"),
        help="Path to invalid sessions CSV (default: data/fitness_sessions_invalid.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output/)",
    )
    return parser.parse_args()


def run(profiles_path: Path, sessions_paths: list[Path], output_dir: Path) -> None:

    print(f"\nLoading profiles from {profiles_path} ...")
    try:
        participants = load_participants(profiles_path)
    except (FileNotFoundError, PermissionError) as exc:
        print(f"  [ERROR] {exc}")
        return
    print(f"  Loaded {len(participants)} participant(s).")

    all_sessions: dict = {}
    all_rejected: list[dict] = []

    for path in sessions_paths:
        print(f"\nLoading sessions from {path} ...")
        try:
            sessions, rejected = load_sessions(path, participants)
        except (FileNotFoundError, PermissionError) as exc:
            print(f"  [ERROR] {exc} - skipping file.")
            continue

        accepted_rows = sum(len(s["rows"]) for s in sessions.values())
        print(f"  Accepted {accepted_rows} row(s) across "
              f"{len(sessions)} session(s), rejected {len(rejected)} row(s).")
        all_sessions.update(sessions)
        all_rejected.extend(rejected)

    print(f"\nAnalysing {len(all_sessions)} session(s) ...")
    results = []
    for session_id, data in all_sessions.items():
        participant: Participant = data["participant"]
        raw_obs: list[dict] = data["rows"]
        result = analyse_session(participant, raw_obs)
        result["session_id"] = session_id
        result["participant_id"] = participant.participant_id
        results.append(result)

    ensure_output_dir(output_dir)

    summary_path  = output_dir / "analysis_summary.csv"
    report_path   = output_dir / "analysis_report.txt"
    rejected_path = output_dir / "rejected_records.txt"

    write_summary_csv(summary_path, results)
    write_report_txt(report_path, results)
    write_rejected_txt(rejected_path, all_rejected)

    total_accepted = sum(r["classification"]["total"] for r in results)
    total_rejected = len(all_rejected)

    print(f"\n{'=' * 52}")
    print(f"  COMPLETED")
    print(f"  Sessions analysed : {len(results)}")
    print(f"  Rows accepted     : {total_accepted}")
    print(f"  Rows rejected     : {total_rejected}")
    print(f"  Output files:")
    print(f"    {summary_path}")
    print(f"    {report_path}")
    print(f"    {rejected_path}")
    print(f"{'=' * 52}\n")


def main() -> None:
    args = parse_args()
    sessions_paths = [args.sessions, args.invalid]
    run(
        profiles_path=args.profiles,
        sessions_paths=sessions_paths,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()