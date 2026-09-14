# Smart Fitness Session Analyzer

**Assignment:** Python Programming Assignment I — Option A  
**Student:** hahar1799  
**Course:** ACIT4420 Problem Solving with Scripting

---

## Description

A command-line Python application that ingests simulated wearable sensor
observations, validates each measurement window, computes session summaries,
compares readings against a participant's personal baselines, detects recovery
patterns, and classifies each session into one of five intensity labels.

The application uses only the Python standard library.

---

## File structure

```
your-repository/
├── main.py            — entry point; runs all five scenarios
├── models.py          — domain classes (Participant, Observation, Session, …)
├── analysis.py        — standalone analysis functions
├── sample_data.py     — five scenario definitions using the data generator
├── tests.py           — 45 unit and integration tests (unittest)
├── data_generator.py  — instructor-supplied data generator (do not modify)
├── requirements.txt   — empty; standard library only
└── README.md
```

---

## Class design

### `Participant` — `models.py`
Stores the participant identifier and personal baseline reference values
(resting heart rate, baseline skin response, baseline temperature).

- `_participant_id` is a **private attribute** exposed through a read-only
  `@property`, satisfying the encapsulation requirement.
- `Participant.from_dict(profile)` is a **class method** that constructs a
  `Participant` directly from the generator's profile dictionary.

### `Observation` — `models.py`
Represents one sensor measurement window. On construction it immediately
validates all fields and sets `valid`, `low_quality`, and `flags`.

- `Observation.from_dict(data)` is a **static method** factory.
- An observation is marked **invalid** if any field is `None` or outside its
  physiologically possible range.
- An observation is marked **low-quality** (but not invalid) if
  `signal_quality` is below 0.70. Low-quality observations are excluded from
  analysis alongside invalid ones.

### `InvalidObservation(Observation)` — `models.py`
**Inherits** from `Observation` and **overrides** `_validate` with a no-op,
because structural problems (entirely missing keys in the raw dictionary) are
caught before field-level validation is relevant. Used by `Session.from_data`
when a required key is absent from the raw dict.

### `Session` — `models.py`
Groups a `Participant` and a list of `Observation` instances for one recording
session. This is the primary **composition** site in the design.

- `Session.from_data(participant, raw_observations)` is a **class method**
  that builds the session from raw dicts, routing each dict to either
  `Observation.from_dict` or `InvalidObservation` as appropriate.
- `usable_observations` (property) returns only observations that are both
  valid and not low-quality; this is the filtered list passed to all analysis
  functions.

---

## OOP requirements checklist

| Requirement | Where |
|---|---|
| ≥ 4 meaningful classes | `Participant`, `Observation`, `InvalidObservation`, `Session` |
| Composition | `Session` holds a `Participant` + `list[Observation]` |
| Encapsulation | `Participant._participant_id` + read-only `@property`; `Session._observations` only writable via `add_observation` |
| Inheritance | `InvalidObservation` extends `Observation` |
| Method overriding | `InvalidObservation._validate` overrides `Observation._validate` |
| Class method | `Participant.from_dict`, `Session.from_data` |
| Static method | `Observation.from_dict` |

---

## Standalone functions — `analysis.py`

| Function | Purpose |
|---|---|
| `calculate_summary(observations)` | Computes avg / min / max for every numeric field |
| `collect_invalid_flags(session)` | Collects flag messages from all non-clean observations |
| `compare_to_baseline(summary, participant)` | Computes delta between session averages and personal baselines |
| `detect_recovery(observations)` | Returns `True` if HR and activity both decline meaningfully in the final third |
| `classify_session(session, summary, comparisons)` | Applies classification rules and returns a structured result dict |
| `format_report(...)` | Builds and returns a readable console report string |
| `analyse_session(participant, raw_observations)` | Convenience wrapper running the full pipeline in one call |

---

## Assumptions and classification rules

### Validation thresholds

| Field | Valid range |
|---|---|
| `heart_rate` | 35–205 bpm |
| `skin_response` | ≥ 0 |
| `temperature` | 25–42 °C |
| `activity_level` | 0–1 |
| `signal_quality` | 0–1; values below 0.70 are flagged low-quality |

A `None` value for any field marks the observation invalid.

### Classification rules (applied in order)

1. **Insufficient data** — fewer than 50 % of observations are usable, or no
   usable heart-rate data is available.
2. **Recovering** — HR and activity both decline by at least 8 bpm / 0.10
   units between the first two-thirds and the final third of usable
   observations. Recovery is checked before intensity to avoid
   misclassifying a tapering high-intensity session as moderate.
3. **Resting** — average HR is within +15 bpm of baseline AND average
   activity ≤ 0.25.
4. **Moderate activity** — average HR is within +40 bpm of baseline AND
   average activity ≤ 0.65.
5. **High activity** — everything above the moderate thresholds.

The minimum-decline thresholds in `detect_recovery` (8 bpm, 0.10 activity)
prevent natural end-of-session noise from being misread as recovery.

---

## Installation and running instructions

```bash
git clone https://github.com/Haelzzz/ACIT4420-Assignment-1.git
cd ACIT4420-Assignment-1
python3 main.py
```

To run the test suite:

```bash
python3 tests.py
```

No third-party packages are required. If your system uses `python` instead of
`python3`, substitute accordingly.

---

## Example output

```
####################################################
  SCENARIO 1: Resting
####################################################
====================================================
  SMART FITNESS SESSION REPORT
====================================================
  Participant : P001
  HR baseline : 62 bpm
  Temp base   : 32.86 °C
  Skin base   : 1.85
----------------------------------------------------
  Total observations  : 12
  Usable observations : 12
----------------------------------------------------
  SUMMARY STATISTICS
  Field                 Avg      Min      Max
  Heart rate          63.25       57       67
  Skin response       1.837     1.69      2.0
  Temperature         32.82    32.65    32.92
  Activity level      0.136     0.05      0.2
  Signal quality      0.917     0.82     0.99
----------------------------------------------------
  BASELINE COMPARISON
  Heart rate          session 63.2  vs baseline 62.0  (delta +1.2)
  Skin response       session 1.8  vs baseline 1.9  (delta -0.0)
  Temperature         session 32.8  vs baseline 32.9  (delta -0.0)
----------------------------------------------------
  CLASSIFICATION  :  RESTING
  HR was only +1.2 bpm above baseline and avg activity was 0.14 — consistent with rest.
----------------------------------------------------
  No flagged observations.
====================================================

####################################################
  SCENARIO 5: Poor Quality / Invalid Data
####################################################
====================================================
  SMART FITNESS SESSION REPORT
====================================================
  Participant : P005
  HR baseline : 77 bpm
  Temp base   : 32.11 °C
  Skin base   : 1.38
----------------------------------------------------
  Total observations  : 12
  Usable observations : 0
----------------------------------------------------
  CLASSIFICATION  :  INSUFFICIENT DATA
  Only 0/12 observations were usable (threshold: 50 %).
----------------------------------------------------
  FLAGGED OBSERVATIONS  (12 window(s))
  t=  0  heart_rate: missing
  t=  0  signal_quality: 0.17 below threshold 0.7
  t=  1  heart_rate: 265 out of range [35, 205]
  t=  1  signal_quality: 0.24 below threshold 0.7
  ...
====================================================
```

---

## Known limitations

- Classification thresholds (HR delta, activity bands) are fixed constants
  chosen to produce correct results on the supplied generator scenarios. They
  are not derived from real clinical guidelines and may not generalise to
  other seeds or participant profiles without adjustment.
- The recovery detector requires at least 6 usable observations and uses a
  simple early/late split. More sophisticated trend detection (e.g. linear
  regression over the full session) would be more robust but is outside the
  scope of this assignment.
- Skin response and temperature are validated for structural correctness
  (non-negative, in-range) but are not used in classification — only in
  the baseline comparison summary. Future work could incorporate them into
  a composite intensity score.
- The program prints to stdout only; there is no file export or persistent
  storage.