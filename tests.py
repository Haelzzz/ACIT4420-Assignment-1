"""Tests for the Smart Fitness Session Analyzer.

Run from the repository root:
    python3 tests.py

Uses only the standard-library unittest module.
"""

import unittest

from models import Participant, Observation, InvalidObservation, Session
from analysis import (
    calculate_summary,
    collect_invalid_flags,
    compare_to_baseline,
    detect_recovery,
    classify_session,
    analyse_session,
)
from sample_data import load_all_scenarios


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_participant(**kwargs) -> Participant:
    defaults = dict(
        participant_id="TEST",
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
        timestamp=timestamp,
        heart_rate=heart_rate,
        skin_response=skin_response,
        temperature=temperature,
        activity_level=activity_level,
        signal_quality=signal_quality,
    )


def _make_session(participant, obs_list) -> Session:
    session = Session(participant)
    for obs in obs_list:
        session.add_observation(obs)
    return session


# ---------------------------------------------------------------------------
# Participant tests
# ---------------------------------------------------------------------------

class TestParticipant(unittest.TestCase):

    def test_from_dict(self):
        profile = {
            "participant_id": "P001",
            "baseline_heart_rate": 70,
            "baseline_skin_response": 1.8,
            "baseline_temperature": 32.5,
        }
        p = Participant.from_dict(profile)
        self.assertEqual(p.participant_id, "P001")
        self.assertEqual(p.baseline_heart_rate, 70)

    def test_participant_id_is_read_only(self):
        p = _make_participant()
        with self.assertRaises(AttributeError):
            p.participant_id = "HACKED"

    def test_repr_contains_id(self):
        p = _make_participant(participant_id="P99")
        self.assertIn("P99", repr(p))


# ---------------------------------------------------------------------------
# Observation validation tests
# ---------------------------------------------------------------------------

class TestObservationValidation(unittest.TestCase):

    def test_valid_observation(self):
        obs = _make_obs()
        self.assertTrue(obs.valid)
        self.assertFalse(obs.low_quality)
        self.assertEqual(obs.flags, [])

    def test_missing_heart_rate(self):
        obs = _make_obs(heart_rate=None)
        self.assertFalse(obs.valid)
        self.assertTrue(any("heart_rate" in f for f in obs.flags))

    def test_heart_rate_too_high(self):
        obs = _make_obs(heart_rate=265)
        self.assertFalse(obs.valid)

    def test_heart_rate_too_low(self):
        obs = _make_obs(heart_rate=20)
        self.assertFalse(obs.valid)

    def test_negative_activity_level(self):
        obs = _make_obs(activity_level=-0.2)
        self.assertFalse(obs.valid)

    def test_activity_level_above_one(self):
        obs = _make_obs(activity_level=1.5)
        self.assertFalse(obs.valid)

    def test_missing_skin_response(self):
        obs = _make_obs(skin_response=None)
        self.assertFalse(obs.valid)

    def test_negative_skin_response(self):
        obs = _make_obs(skin_response=-1.0)
        self.assertFalse(obs.valid)

    def test_temperature_out_of_range(self):
        obs = _make_obs(temperature=50.0)
        self.assertFalse(obs.valid)

    def test_low_signal_quality_flags_but_stays_valid(self):
        # Signal quality below threshold → low_quality=True, but valid is True
        # (low-quality obs are excluded from analysis, not marked invalid)
        obs = _make_obs(signal_quality=0.40)
        self.assertTrue(obs.valid)
        self.assertTrue(obs.low_quality)
        self.assertTrue(any("signal_quality" in f for f in obs.flags))

    def test_from_dict_factory(self):
        data = {
            "timestamp": 3,
            "heart_rate": 80,
            "skin_response": 1.6,
            "temperature": 32.1,
            "activity_level": 0.4,
            "signal_quality": 0.91,
        }
        obs = Observation.from_dict(data)
        self.assertEqual(obs.timestamp, 3)
        self.assertTrue(obs.valid)


# ---------------------------------------------------------------------------
# InvalidObservation tests
# ---------------------------------------------------------------------------

class TestInvalidObservation(unittest.TestCase):

    def test_is_invalid(self):
        inv = InvalidObservation(timestamp=0, reason="missing keys: {'heart_rate'}")
        self.assertFalse(inv.valid)
        self.assertEqual(len(inv.flags), 1)

    def test_is_subclass_of_observation(self):
        inv = InvalidObservation(timestamp=1, reason="test")
        self.assertIsInstance(inv, Observation)

    def test_repr(self):
        inv = InvalidObservation(timestamp=2, reason="bad data")
        self.assertIn("InvalidObservation", repr(inv))


# ---------------------------------------------------------------------------
# Session tests
# ---------------------------------------------------------------------------

class TestSession(unittest.TestCase):

    def test_usable_excludes_invalid(self):
        p = _make_participant()
        obs_valid = _make_obs(timestamp=0)
        obs_invalid = _make_obs(timestamp=1, heart_rate=None)
        session = _make_session(p, [obs_valid, obs_invalid])
        self.assertEqual(session.usable_count, 1)
        self.assertEqual(session.total_count, 2)

    def test_usable_excludes_low_quality(self):
        p = _make_participant()
        obs_good = _make_obs(timestamp=0)
        obs_low = _make_obs(timestamp=1, signal_quality=0.3)
        session = _make_session(p, [obs_good, obs_low])
        self.assertEqual(session.usable_count, 1)

    def test_from_data_handles_missing_key(self):
        p = _make_participant()
        raw = [{"timestamp": 0, "heart_rate": 70}]  # missing most keys
        session = Session.from_data(p, raw)
        self.assertEqual(session.total_count, 1)
        self.assertEqual(session.usable_count, 0)

    def test_all_observations_returns_copy(self):
        p = _make_participant()
        session = _make_session(p, [_make_obs()])
        copy = session.all_observations
        copy.clear()
        self.assertEqual(session.total_count, 1)


# ---------------------------------------------------------------------------
# calculate_summary tests
# ---------------------------------------------------------------------------

class TestCalculateSummary(unittest.TestCase):

    def test_empty_returns_empty_dict(self):
        self.assertEqual(calculate_summary([]), {})

    def test_avg_min_max_correct(self):
        obs_a = _make_obs(heart_rate=60, activity_level=0.2)
        obs_b = _make_obs(heart_rate=80, activity_level=0.4)
        summary = calculate_summary([obs_a, obs_b])
        self.assertEqual(summary["heart_rate"]["avg"], 70.0)
        self.assertEqual(summary["heart_rate"]["min"], 60)
        self.assertEqual(summary["heart_rate"]["max"], 80)

    def test_all_fields_present(self):
        summary = calculate_summary([_make_obs()])
        for field in ["heart_rate", "skin_response", "temperature",
                      "activity_level", "signal_quality"]:
            self.assertIn(field, summary)


# ---------------------------------------------------------------------------
# compare_to_baseline tests
# ---------------------------------------------------------------------------

class TestCompareToBaseline(unittest.TestCase):

    def test_positive_delta(self):
        p = _make_participant(baseline_heart_rate=65)
        summary = {"heart_rate": {"avg": 90.0, "min": 80, "max": 100}}
        result = compare_to_baseline(summary, p)
        self.assertAlmostEqual(result["heart_rate"]["delta"], 25.0)

    def test_empty_summary_returns_empty(self):
        p = _make_participant()
        self.assertEqual(compare_to_baseline({}, p), {})


# ---------------------------------------------------------------------------
# detect_recovery tests
# ---------------------------------------------------------------------------

class TestDetectRecovery(unittest.TestCase):

    def test_too_few_obs_returns_false(self):
        obs = [_make_obs() for _ in range(4)]
        self.assertFalse(detect_recovery(obs))

    def test_recovery_detected(self):
        # Early obs: high HR + activity; late obs: low HR + activity
        early = [_make_obs(timestamp=i, heart_rate=130, activity_level=0.85)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=80, activity_level=0.20)
                for i in range(4)]
        self.assertTrue(detect_recovery(early + late))

    def test_stable_session_not_recovery(self):
        obs = [_make_obs(timestamp=i, heart_rate=100, activity_level=0.5)
               for i in range(12)]
        self.assertFalse(detect_recovery(obs))

    def test_noise_dip_not_recovery(self):
        # Only a 3 bpm dip — below the 8 bpm threshold
        early = [_make_obs(timestamp=i, heart_rate=100, activity_level=0.5)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=97, activity_level=0.45)
                for i in range(4)]
        self.assertFalse(detect_recovery(early + late))


# ---------------------------------------------------------------------------
# classify_session tests
# ---------------------------------------------------------------------------

class TestClassifySession(unittest.TestCase):

    def _run(self, obs_list, baseline_hr=65):
        p = _make_participant(baseline_heart_rate=baseline_hr)
        session = _make_session(p, obs_list)
        summary = calculate_summary(session.usable_observations)
        comparisons = compare_to_baseline(summary, p)
        return classify_session(session, summary, comparisons)

    def test_insufficient_data_all_invalid(self):
        obs = [_make_obs(heart_rate=None) for _ in range(12)]
        result = self._run(obs)
        self.assertEqual(result["label"], "insufficient data")

    def test_resting_classification(self):
        obs = [_make_obs(heart_rate=67, activity_level=0.10) for _ in range(12)]
        result = self._run(obs, baseline_hr=65)
        self.assertEqual(result["label"], "resting")

    def test_moderate_classification(self):
        obs = [_make_obs(heart_rate=90, activity_level=0.50) for _ in range(12)]
        result = self._run(obs, baseline_hr=65)
        self.assertEqual(result["label"], "moderate activity")

    def test_high_activity_classification(self):
        obs = [_make_obs(heart_rate=130, activity_level=0.85) for _ in range(12)]
        result = self._run(obs, baseline_hr=65)
        self.assertEqual(result["label"], "high activity")

    def test_recovery_classification(self):
        early = [_make_obs(timestamp=i, heart_rate=130, activity_level=0.85)
                 for i in range(8)]
        late = [_make_obs(timestamp=i+8, heart_rate=80, activity_level=0.20)
                for i in range(4)]
        result = self._run(early + late, baseline_hr=65)
        self.assertEqual(result["label"], "recovering")
        self.assertTrue(result["recovery"])

    def test_result_has_required_keys(self):
        obs = [_make_obs() for _ in range(12)]
        result = self._run(obs)
        for key in ["label", "explanation", "recovery", "usable", "total"]:
            self.assertIn(key, result)


# ---------------------------------------------------------------------------
# collect_invalid_flags tests
# ---------------------------------------------------------------------------

class TestCollectInvalidFlags(unittest.TestCase):

    def test_no_flags_on_clean_session(self):
        p = _make_participant()
        session = _make_session(p, [_make_obs() for _ in range(6)])
        self.assertEqual(collect_invalid_flags(session), [])

    def test_flags_collected(self):
        p = _make_participant()
        bad = _make_obs(heart_rate=None)
        session = _make_session(p, [bad])
        flagged = collect_invalid_flags(session)
        self.assertEqual(len(flagged), 1)
        self.assertTrue(any("heart_rate" in f for f in flagged[0]["flags"]))


# ---------------------------------------------------------------------------
# Full pipeline integration tests (using the 5 generator scenarios)
# ---------------------------------------------------------------------------

class TestFullPipelineScenarios(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenarios = load_all_scenarios()
        cls.results = []
        for s in cls.scenarios:
            p = Participant.from_dict(s["profile"])
            cls.results.append(analyse_session(p, s["observations"]))

    def _result(self, index):
        return self.results[index]

    def test_scenario_resting(self):
        r = self._result(0)
        self.assertEqual(r["classification"]["label"], "resting")
        self.assertEqual(r["classification"]["total"], 12)

    def test_scenario_moderate_activity(self):
        r = self._result(1)
        self.assertEqual(r["classification"]["label"], "moderate activity")

    def test_scenario_high_activity(self):
        r = self._result(2)
        self.assertEqual(r["classification"]["label"], "high activity")

    def test_scenario_recovery(self):
        r = self._result(3)
        self.assertEqual(r["classification"]["label"], "recovering")
        self.assertTrue(r["classification"]["recovery"])

    def test_scenario_poor_quality(self):
        r = self._result(4)
        self.assertEqual(r["classification"]["label"], "insufficient data")
        self.assertGreater(len(r["flagged"]), 0)

    def test_all_results_have_report_string(self):
        for r in self.results:
            self.assertIsInstance(r["report"], str)
            self.assertGreater(len(r["report"]), 0)

    def test_poor_quality_has_zero_usable(self):
        r = self._result(4)
        self.assertEqual(r["classification"]["usable"], 0)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)