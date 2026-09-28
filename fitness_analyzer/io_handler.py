"""CSV loading, regex validation, and file writing for the fitness analyzer.

Responsibilities:
- Load and validate participants.csv
- Load and validate session CSV files (valid + invalid)
- Group session rows by session_id and link to participants
- Write output files (summary CSV, report TXT, rejected TXT)
"""

import csv
import re
from pathlib import Path

from fitness_analyzer.exceptions import InvalidIdentifierError, InvalidRecordError
from fitness_analyzer.models import Participant


PARTICIPANT_ID_PATTERN = re.compile(r"^P\d{3}$")
SESSION_ID_PATTERN = re.compile(r"^FIT-\d{4}-\d{3}$")

PROFILE_REQUIRED = {
    "participant_id", "name", "baseline_heart_rate",
    "baseline_skin_response", "baseline_temperature",
}

SESSION_REQUIRED = {
    "session_id", "participant_id", "timestamp", "heart_rate",
    "skin_response", "temperature", "activity_level", "signal_quality",
}


def load_participants(filepath: Path) -> dict[str, Participant]:
    """Load participants.csv and return {participant_id: Participant}.

    Raises FileNotFoundError if the file is missing.
    Skips rows with invalid IDs or unconvertible values, printing a warning.
    """
    participants = {}

    try:
        fh = open(filepath, encoding="utf-8", newline="")
    except FileNotFoundError:
        raise FileNotFoundError(f"Participant profile file not found: {filepath}")
    except PermissionError:
        raise PermissionError(f"No read permission for: {filepath}")

    with fh:
        try:
            reader = csv.DictReader(fh)
        except csv.Error as exc:
            raise csv.Error(f"Could not parse {filepath}: {exc}") from exc

        missing_cols = PROFILE_REQUIRED - set(reader.fieldnames or [])
        if missing_cols:
            raise InvalidRecordError(
                f"participants file missing columns: {missing_cols}",
            )

        for row_num, row in enumerate(reader, start=2):
            pid = row.get("participant_id", "").strip()
            try:
                _validate_participant_id(pid)
                participant = _parse_participant_row(row, row_num, filepath)
                participants[pid] = participant
            except (InvalidIdentifierError, InvalidRecordError) as exc:
                print(f"  [WARN] {filepath.name} row {row_num}: {exc}")

    return participants


def _validate_participant_id(pid: str) -> None:
    if not PARTICIPANT_ID_PATTERN.fullmatch(pid):
        raise InvalidIdentifierError("participant_id", pid, PARTICIPANT_ID_PATTERN.pattern)


def _validate_session_id(sid: str) -> None:
    if not SESSION_ID_PATTERN.fullmatch(sid):
        raise InvalidIdentifierError("session_id", sid, SESSION_ID_PATTERN.pattern)


def _parse_participant_row(row: dict, row_num: int, filepath: Path) -> Participant:
    try:
        return Participant(
            participant_id=row["participant_id"].strip(),
            baseline_heart_rate=int(row["baseline_heart_rate"]),
            baseline_skin_response=float(row["baseline_skin_response"]),
            baseline_temperature=float(row["baseline_temperature"]),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidRecordError(
            f"could not parse participant row", value=str(exc)
        ) from exc



def load_sessions(
    filepath: Path,
    participants: dict[str, Participant],
) -> tuple[dict, list[dict]]:
    """Load a session CSV file.

    Returns:
        sessions  : {session_id: {"participant": Participant, "rows": [dict]}}
        rejected  : list of rejection report dicts
    """
    sessions: dict = {}
    rejected: list[dict] = []

    try:
        fh = open(filepath, encoding="utf-8", newline="")
    except FileNotFoundError:
        raise FileNotFoundError(f"Session file not found: {filepath}")
    except PermissionError:
        raise PermissionError(f"No read permission for: {filepath}")

    with fh:
        try:
            reader = csv.DictReader(fh)
        except csv.Error as exc:
            raise csv.Error(f"Could not parse {filepath}: {exc}") from exc

        missing_cols = SESSION_REQUIRED - set(reader.fieldnames or [])
        if missing_cols:
            raise InvalidRecordError(
                f"session file missing columns: {missing_cols}"
            )

        for row_num, row in enumerate(reader, start=2):

            if len(row) != len(reader.fieldnames):
                rejected.append(_rejection(
                    filepath, row_num, row.get("session_id", "?"),
                    "row", str(len(row)),
                    f"unexpected number of fields "
                    f"(got {len(row)}, expected {len(reader.fieldnames)})",
                ))
                continue

            sid = row.get("session_id", "").strip()
            pid = row.get("participant_id", "").strip()

            try:
                _validate_session_id(sid)
            except InvalidIdentifierError as exc:
                rejected.append(_rejection(filepath, row_num, sid,
                                           "session_id", sid, str(exc)))
                continue

            try:
                _validate_participant_id(pid)
            except InvalidIdentifierError as exc:
                rejected.append(_rejection(filepath, row_num, sid,
                                           "participant_id", pid, str(exc)))
                continue

         
            if pid not in participants:
                rejected.append(_rejection(filepath, row_num, sid,
                                           "participant_id", pid,
                                           f"unknown participant {pid!r}"))
                continue

            try:
                obs_row = _parse_session_row(row)
            except InvalidRecordError as exc:
                rejected.append(_rejection(filepath, row_num, sid,
                                           exc.field, exc.value, exc.reason))
                continue

          
            if sid not in sessions:
                sessions[sid] = {
                    "participant": participants[pid],
                    "rows": [],
                }
            sessions[sid]["rows"].append(obs_row)

    return sessions, rejected


def _parse_session_row(row: dict) -> dict:
    """Convert string fields to correct types; raise InvalidRecordError on failure."""

    def _int(field):
        v =(row.get(field) or "").strip()
        try:
            return int(v)
        except ValueError:
            raise InvalidRecordError(
                f"cannot convert to integer", field=field, value=v
            )

    def _float(field):
        v = (row.get(field) or "").strip()
        if v== "":
            raise InvalidRecordError(
                f"missing required value", field=field, value=v
            )
        try:
            return float(v)
        except ValueError:
            raise InvalidRecordError(
                f"cannot convert to float", field=field, value=v
            )

    heart_rate = _int("heart_rate")
    skin_response = _float("skin_response")
    temperature = _float("temperature")
    activity_level = _float("activity_level")
    signal_quality = _float("signal_quality")
    timestamp = _int("timestamp")

    # Range checks (do not use regex for these per assignment rules)
    if not (35<= heart_rate <= 205):
        raise InvalidRecordError(
            "heart_rate out of range [35, 205]", field="heart_rate", value=str(heart_rate)
        )
    if skin_response < 0:
        raise InvalidRecordError(
            "skin_response must be >= 0", field="skin_response", value=str(skin_response)
        )
    if not (25.0 <= temperature <= 42.0):
        raise InvalidRecordError(
            "temperature out of range [25, 42]", field="temperature", value=str(temperature)
        )
    if not (0.0 <= activity_level <= 1.0):
        raise InvalidRecordError(
            "activity_level out of range [0, 1]", field="activity_level", value=str(activity_level)
        )
    if not (0.0 <= signal_quality <= 1.0):
        raise InvalidRecordError(
            "signal_quality out of range [0, 1]", field="signal_quality", value=str(signal_quality)
        )

    return {
        "timestamp": timestamp,
        "heart_rate": heart_rate,
        "skin_response": skin_response,
        "temperature": temperature,
        "activity_level": activity_level,
        "signal_quality": signal_quality,
    }


def _rejection(filepath: Path, row_num: int, session_id: str,
               field: str, value: str, reason: str) -> dict:
    return {
        "source_file": filepath.name,
        "row": row_num,
        "session_id": session_id,
        "field": field,
        "value": value,
        "reason": reason,
    }


def ensure_output_dir(path: Path) -> None:
    """Create the output directory (and parents) if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def write_summary_csv(filepath: Path, results: list[dict]) -> None:
    """Write one row per session to analysis_summary.csv."""
    fieldnames = [
        "session_id", "participant_id", "total_observations",
        "usable_observations", "classification",
        "avg_heart_rate", "avg_activity_level", "recovery_detected",
    ]
    with open(filepath, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            c = r["classification"]
            summary = r["summary"]
            writer.writerow({
                "session_id": r["session_id"],
                "participant_id": r["participant_id"],
                "total_observations": c["total"],
                "usable_observations": c["usable"],
                "classification": c["label"],
                "avg_heart_rate": summary.get("heart_rate", {}).get("avg", ""),
                "avg_activity_level": summary.get("activity_level", {}).get("avg", ""),
                "recovery_detected": c["recovery"],
            })


def write_report_txt(filepath: Path, results: list[dict]) -> None:
    """Write the human-readable analysis report."""
    with open(filepath, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(r["report"])
            fh.write("\n")


def write_rejected_txt(filepath: Path, rejected: list[dict]) -> None:
    """Write all rejected records with source, row, field and reason."""
    with open(filepath, "w", encoding="utf-8") as fh:
        if not rejected:
            fh.write("No records were rejected.\n")
            return
        fh.write(f"{'SOURCE':<35} {'ROW':>4}  {'SESSION':<16} "
                 f"{'FIELD':<18} {'VALUE':<12} REASON\n")
        fh.write("-" * 110 + "\n")
        for r in rejected:
            fh.write(
                f"{r['source_file']:<35} {r['row']:>4}  {r['session_id']:<16} "
                f"{r['field']:<18} {str(r['value']):<12} {r['reason']}\n"
            )