"""Tests for the Smart Fitness Session Analyzer (Assignment II).

Run from the repository root:
    python3 tests.py

Covers: models, analysis functions, exceptions, io_handler, and full pipeline.
"""

import csv
import tempfile
import unittest
from pathlib import Path

from fitness_analyzer.models import Participant, Observation, InvalidObservation, Session
from fitness_analyzer.analysis import (
    calculate_summary,
    collect_invalid_flags,
    compare_to_baseline,
    detect_recovery,
    classify_session,
    analyse_session,
)
from fitness_analyzer.exceptions import InvalidIdentifierError, InvalidRecordError
from fitness_analyzer.io_handler import (
    load_participants,
    load_sessions,
    write_summary_csv,
    write_report_txt,
    write_rejected_txt,
    PARTICIPANT_ID_PATTERN,
    SESSION_ID_PATTERN,
)

def _make_participant(**kwargs) -> Participant:
    defaults = dict(
        participant_id="P001",
        baseline_heart_rate=65,
        baseline_skin_response=1.5,
        baseline_temperature=32.0,
    )
    defaults.update(kwargs)
    return Participant(**defaults)


def _make_obs(timestamp=0, heart_rate=70, skin_response=1.5,
              temperature=32.0, activity_level=0.3,
              signal_quality=0.90) -> Observation:
    return Observation(
        timestamp=timestamp, heart_rate=heart_rate,
        skin_response=skin_response, temperature=temperature,
        activity_level=activity_level, signal_quality=signal_quality,
    )


def _make_session(participant, obs_list) -> Session:
    session = Session(participant)
    for obs in obs_list:
        session.add_observation(obs)
    return session


def _write_csv(path: Path,rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

class TestExceptions(unittest.TestCase):

    def test_invalid_identifier_error_is_value_error(self):
        exc = InvalidIdentifierError("participant_id", "ABC", r"^P\d{3}$")
        self.assertIsInstance(exc, ValueError)
        self.assertIn("ABC", str(exc))

    def test_invalid_identifier_stores_fields(self):
        exc = InvalidIdentifierError("session_id", "BAD", r"^FIT-\d{4}-\d{3}$")
        self.assertEqual(exc.field, "session_id")
        self.assertEqual(exc.value, "BAD")

    def test_invalid_record_error_is_value_error(self):
        exc = InvalidRecordError("missing value", field="heart_rate", value="")
        self.assertIsInstance(exc, ValueError)
        self.assertIn("heart_rate", str(exc))

    def test_invalid_record_no_field(self):
        exc = InvalidRecordError("row too short")
        self.assertEqual(exc.field, "")

class TestRegexPatterns(unittest.TestCase):

    def test_valid_participant_ids(self):
        for pid in ["P001", "P099", "P999"]:
            self.assertIsNotNone(PARTICIPANT_ID_PATTERN.fullmatch(pid), pid)

    def test_invalid_participant_ids(self):
        for pid in ["P01", "P0001", "001", "p001", "P00A", ""]:
            self.assertIsNone(PARTICIPANT_ID_PATTERN.fullmatch(pid), pid)

    def test_valid_session_ids(self):
        for sid in ["FIT-2026-001", "FIT-2024-999", "FIT-0000-000"]:
            self.assertIsNotNone(SESSION_ID_PATTERN.fullmatch(sid), sid)

    def test_invalid_session_ids(self):
        for sid in ["FIT-26-001", "FIT-2026-01", "fit-2026-001", "FIT-2026-0001", ""]:
            self.assertIsNone(SESSION_ID_PATTERN.fullmatch(sid), sid)

class TestLoadParticipants(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_profiles(self,rows):
        path = self.dir / "participants.csv"
        _write_csv(path, rows, [
            "participant_id", "name",
            "baseline_heart_rate", "baseline_skin_response", "baseline_temperature"
        ])
        return path

    def test_loads_valid_participants(self):
        path = self._write_profiles([
            {"participant_id": "P001", "name": "Alice",
             "baseline_heart_rate": 65, "baseline_skin_response": 1.5,
             "baseline_temperature": 32.0},
        ])
        participants = load_participants(path)
        self.assertIn("P001", participants)
        self.assertEqual(participants["P001"].baseline_heart_rate, 65)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_participants(self.dir / "nonexistent.csv")

    def test_invalid_participant_id_skipped(self):
        path = self._write_profiles([
            {"participant_id": "001", "name": "Bad",
             "baseline_heart_rate": 65, "baseline_skin_response": 1.5,
             "baseline_temperature": 32.0},
        ])
        participants =load_participants(path)
        self.assertEqual(len(participants), 0)

    def test_multiple_participants_loaded(self):
        path = self._write_profiles([
            {"participant_id": "P001", "name": "Alice",
             "baseline_heart_rate": 65, "baseline_skin_response": 1.5,
             "baseline_temperature": 32.0},
            {"participant_id": "P002", "name": "Bob",
             "baseline_heart_rate": 72, "baseline_skin_response": 1.8,
             "baseline_temperature": 32.5},
        ])
        participants = load_participants(path)
        self.assertEqual(len(participants), 2)

class TestLoadSessions(unittest.TestCase):

    FIELDS = [
        "session_id", "participant_id", "timestamp", "heart_rate",
        "skin_response", "temperature", "activity_level", "signal_quality",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.participant = _make_participant(participant_id="P001")
        self.participants = {"P001": self.participant}

    def tearDown(self):
        self.tmp.cleanup()

    def _valid_row(self, **overrides):
        base = {
            "session_id": "FIT-2026-001", "participant_id": "P001",
            "timestamp": 0, "heart_rate": 70, "skin_response": 1.5,
            "temperature": 32.0, "activity_level": 0.3, "signal_quality": 0.90,
        }
        base.update(overrides)
        return {k: str(v) for k, v in base.items()}

    def _write_sessions(self, rows):
        path = self.dir / "sessions.csv"
        _write_csv(path, rows, self.FIELDS)
        return path

    def test_valid_row_accepted(self):
        path = self._write_sessions([self._valid_row()])
        sessions, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(rejected), 0)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_sessions(self.dir / "missing.csv", self.participants)

    def test_invalid_session_id_rejected(self):
        path = self._write_sessions([self._valid_row(session_id="FIT-26-001")])
        sessions, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["field"], "session_id")

    def test_invalid_participant_id_format_rejected(self):
        path = self._write_sessions([self._valid_row(participant_id="001")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)
        self.assertIn("participant_id", rejected[0]["field"])

    def test_unknown_participant_rejected(self):
        path = self._write_sessions([self._valid_row(participant_id="P999")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)
        self.assertIn("unknown participant", rejected[0]["reason"])

    def test_non_numeric_heart_rate_rejected(self):
        path = self._write_sessions([self._valid_row(heart_rate="fast")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["field"], "heart_rate")

    def test_out_of_range_heart_rate_rejected(self):
        path = self._write_sessions([self._valid_row(heart_rate=265)])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)

    def test_negative_heart_rate_rejected(self):
        path = self._write_sessions([self._valid_row(heart_rate=-15)])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)

    def test_missing_activity_level_rejected(self):
        path = self._write_sessions([self._valid_row(activity_level="")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["field"], "activity_level")

    def test_out_of_range_signal_quality_rejected(self):
        path = self._write_sessions([self._valid_row(signal_quality=1.4)])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(len(rejected), 1)

    def test_multiple_sessions_grouped(self):
        rows = [
            self._valid_row(session_id="FIT-2026-001", timestamp=0),
            self._valid_row(session_id="FIT-2026-001", timestamp=1),
            self._valid_row(session_id="FIT-2026-002", timestamp=0),
        ]
        path = self._write_sessions(rows)
        sessions, _ = load_sessions(path, self.participants)
        self.assertEqual(len(sessions), 2)
        self.assertEqual(len(sessions["FIT-2026-001"]["rows"]), 2)

    def test_rejection_records_source_filename(self):
        path = self._write_sessions([self._valid_row(heart_rate="bad")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(rejected[0]["source_file"], path.name)

    def test_rejection_records_row_number(self):
        path = self._write_sessions([self._valid_row(heart_rate="bad")])
        _, rejected = load_sessions(path, self.participants)
        self.assertEqual(rejected[0]["row"], 2)


class TestOutputWriters(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _dummy_result(self):
        p =_make_participant()
        obs = [_make_obs(heart_rate=70, activity_level=0.1) for _ in range(6)]
        result = analyse_session(p, [
            {"timestamp": i, "heart_rate": 70, "skin_response": 1.5,
             "temperature": 32.0, "activity_level": 0.1, "signal_quality": 0.90}
            for i in range(6)
        ])
        result["session_id"] = "FIT-2026-001"
        result["participant_id"] = "P001"
        return result

    def test_summary_csv_created(self):
        path = self.dir / "summary.csv"
        write_summary_csv(path, [self._dummy_result()])
        self.assertTrue(path.exists())
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], "FIT-2026-001")

    def test_report_txt_created(self):
        path = self.dir / "report.txt"
        write_report_txt(path, [self._dummy_result()])
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("SMART FITNESS SESSION REPORT", content)

    def test_rejected_txt_no_rejections(self):
        path =self.dir / "rejected.txt"
        write_rejected_txt(path, [])
        self.assertTrue(path.exists())
        self.assertIn("No records were rejected", path.read_text(encoding="utf-8"))

    def test_rejected_txt_with_entries(self):
        path = self.dir / "rejected.txt"
        rejected = [{"source_file": "test.csv", "row": 3,
                     "session_id": "FIT-2026-001", "field": "heart_rate",
                     "value": "fast", "reason": "cannot convert to integer"}]
        write_rejected_txt(path, rejected)
        content = path.read_text(encoding="utf-8")
        self.assertIn("heart_rate", content)
        self.assertIn("fast", content)

    def test_summary_csv_overwrites_on_rerun(self):
        path = self.dir / "summary.csv"
        write_summary_csv(path, [self._dummy_result()])
        write_summary_csv(path, [self._dummy_result()])
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)

class TestCalculateSummary(unittest.TestCase):

    def test_empty_returns_empty(self):
        self.assertEqual(calculate_summary([]), {})

    def test_avg_min_max(self):
        obs = [_make_obs(heart_rate=60), _make_obs(heart_rate=80)]
        s = calculate_summary(obs)
        self.assertEqual(s["heart_rate"]["avg"], 70.0)
        self.assertEqual(s["heart_rate"]["min"], 60)
        self.assertEqual(s["heart_rate"]["max"], 80)


class TestDetectRecovery(unittest.TestCase):

    def test_too_few_obs(self):
        self.assertFalse(detect_recovery([_make_obs() for _ in range(4)]))

    def test_clear_recovery(self):
        early = [_make_obs(timestamp=i, heart_rate=130, activity_level=0.85)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=80, activity_level=0.20)
                for i in range(4)]
        self.assertTrue(detect_recovery(early + late))

    def test_noise_not_recovery(self):
        early = [_make_obs(timestamp=i, heart_rate=100, activity_level=0.5)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=97, activity_level=0.45)
                for i in range(4)]
        self.assertFalse(detect_recovery(early + late))


class TestClassifySession(unittest.TestCase):

    def _run(self, obs_list, baseline_hr=65):
        p = _make_participant(baseline_heart_rate=baseline_hr)
        session = _make_session(p, obs_list)
        summary = calculate_summary(session.usable_observations)
        comparisons = compare_to_baseline(summary, p)
        return classify_session(session, summary, comparisons)

    def test_resting(self):
        obs = [_make_obs(heart_rate=67, activity_level=0.10) for _ in range(12)]
        self.assertEqual(self._run(obs)["label"], "resting")

    def test_moderate(self):
        obs = [_make_obs(heart_rate=90, activity_level=0.50) for _ in range(12)]
        self.assertEqual(self._run(obs)["label"], "moderate activity")

    def test_high_activity(self):
        obs = [_make_obs(heart_rate=130, activity_level=0.85) for _ in range(12)]
        self.assertEqual(self._run(obs)["label"], "high activity")

    def test_recovering(self):
        early = [_make_obs(timestamp=i, heart_rate=130, activity_level=0.85)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=80, activity_level=0.20)
                for i in range(4)]
        self.assertEqual(self._run(early + late)["label"], "recovering")

    def test_insufficient_data(self):
        obs = [_make_obs(heart_rate=None) for _ in range(12)]
        self.assertEqual(self._run(obs)["label"], "insufficient data")

class TestFullPipelineIntegration(unittest.TestCase):

    DATA = Path("data")

    @classmethod
    def setUpClass(cls):
        cls.participants = load_participants(cls.DATA / "participants.csv")
        sessions_valid, rejected_valid = load_sessions(
            cls.DATA / "fitness_sessions.csv", cls.participants
        )
        sessions_invalid, rejected_invalid = load_sessions(
            cls.DATA / "fitness_sessions_invalid.csv", cls.participants
        )
        cls.sessions_valid = sessions_valid
        cls.sessions_invalid = sessions_invalid
        cls.rejected_valid = rejected_valid
        cls.rejected_invalid = rejected_invalid

    def test_three_participants_loaded(self):
        self.assertEqual(len(self.participants), 3)

    def test_valid_file_has_five_sessions(self):
        self.assertEqual(len(self.sessions_valid), 5)

    def test_valid_file_zero_rejections(self):
        self.assertEqual(len(self.rejected_valid), 0)

    def test_invalid_file_has_rejections(self):
        self.assertGreater(len(self.rejected_invalid), 0)

    def test_all_rejection_fields_present(self):
        for r in self.rejected_invalid:
            for key in ["source_file", "row", "session_id", "field", "reason"]:
                self.assertIn(key, r)

    def test_session_FIT_2026_001_is_resting(self):
        data = self.sessions_valid["FIT-2026-001"]
        p = data["participant"]
        result = analyse_session(p, data["rows"])
        self.assertEqual(result["classification"]["label"], "resting")

    def test_session_FIT_2026_003_is_high_activity(self):
        data = self.sessions_valid["FIT-2026-003"]
        p = data["participant"]
        result = analyse_session(p, data["rows"])
        self.assertEqual(result["classification"]["label"], "high activity")

    def test_session_FIT_2026_004_is_recovering(self):
        data = self.sessions_valid["FIT-2026-004"]
        p = data["participant"]
        result = analyse_session(p, data["rows"])
        self.assertEqual(result["classification"]["label"], "recovering")

    def test_session_FIT_2026_005_is_insufficient_data(self):
        data = self.sessions_valid["FIT-2026-005"]
        p = data["participant"]
        result = analyse_session(p, data["rows"])
        self.assertEqual(result["classification"]["label"], "insufficient data")

    def test_missing_profiles_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_participants(Path("data/nonexistent.csv"))

    def test_missing_sessions_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_sessions(Path("data/nonexistent.csv"), self.participants)


if __name__ == "__main__":
    unittest.main(verbosity=2)