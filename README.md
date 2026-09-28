# Smart Fitness Session Analyzer

**Assignment:** Python Programming Assignment II - Option A  
**Student:** Hallvard, student number: 364743
**Course:** Object-Oriented Analysis Systems

---

## Description

A command-line Python application that loads wearable fitness session data from
CSV files, validates every record, compares measurements against each
participant's personal baselines, classifies sessions by intensity, and writes
structured reports to an output directory.

This is an extension of Assignment I. The core analysis logic from Assignment I
is reused unchanged inside the `fitness_analyzer` package. Assignment II adds
CSV I/O, regular-expression validation, custom exceptions, error handling, and
file-based output.

---

## File structure

```
your-repository/
├── fitness_analyzer/
│   ├── __init__.py          - package marker
│   ├── exceptions.py        - custom exception classes
│   ├── io_handler.py        - CSV loading, regex validation, output writers
│   ├── models.py            - domain classes (from Assignment I)
│   └── analysis.py          - analysis functions (from Assignment I)
├── data/
│   ├── participants.csv          - participant profiles
│   ├── fitness_sessions.csv      - valid session observations
│   └── fitness_sessions_invalid.csv  - intentionally invalid session data
├── output/                  - created at runtime; not committed to git
│   ├── analysis_summary.csv
│   ├── analysis_report.txt
│   └── rejected_records.txt
├── main.py                  - entry point with CLI
├── tests.py                 - 51 unit and integration tests
├── data_generator.py        - instructor-supplied generator (Assignment I)
├── sample_data.py           - Assignment I scenario definitions (no longer used by main.py)
├── requirements.txt
└── README.md
```

`data_generator.py` and `sample_data.py` are retained from Assignment I to
show the design progression. They are not imported by the Assignment II code.

---

## Class design

### `Participant`: `fitness_analyzer/models.py`
Stores the participant identifier and personal baseline reference values.
`_participant_id` is a private attribute exposed through a read-only `@property`
(encapsulation). `Participant.from_dict()` is a class method factory.

### `Observation`: `fitness_analyzer/models.py`
Represents one sensor measurement window. Validates all fields on construction
and sets `valid`, `low_quality`, and `flags`. `Observation.from_dict()` is a
static method factory.

### `InvalidObservation(Observation)`: `fitness_analyzer/models.py`
Inherits from `Observation` and overrides `_validate` with a no-op. Used when
a required CSV key is missing entirely from a raw dictionary.

### `Session`: `fitness_analyzer/models.py`
Groups a `Participant` and a list of `Observation` objects (composition).
`Session.from_data()` is a class method that builds the session from raw dicts.
`usable_observations` (property) filters to valid, non-low-quality observations.

---

## OOP requirements

| Requirement | Where |
|---|---|
| ≥ 4 classes | `Participant`, `Observation`, `InvalidObservation`, `Session` |
| Composition | `Session` holds a `Participant` + `list[Observation]` |
| Encapsulation | `Participant._participant_id` + read-only `@property`; `Session._observations` only writable via `add_observation` |
| Inheritance | `InvalidObservation` extends `Observation` |
| Method overriding | `InvalidObservation._validate` overrides `Observation._validate` |
| Class method | `Participant.from_dict`, `Session.from_data` |
| Static method | `Observation.from_dict` |

---

## Modules

| Module | Responsibility |
|---|---|
| `fitness_analyzer/models.py` | Domain classes and validation |
| `fitness_analyzer/analysis.py` | Standalone analysis functions |
| `fitness_analyzer/io_handler.py` | CSV I/O, regex validation, output writing |
| `fitness_analyzer/exceptions.py` | Custom exception classes |

---

## Custom exceptions

```python
class InvalidIdentifierError(ValueError):
    """Raised when a participant or session identifier fails regex validation."""

class InvalidRecordError(ValueError):
    """Raised when a CSV record cannot be accepted for analysis."""
```

Both are raised inside `io_handler.py` and handled at the row level so that
one bad record does not abort the entire file.

---

## Regex validations

| Identifier | Pattern |
|---|---|
| Participant ID | `^P\d{3}$` |
| Session ID | `^FIT-\d{4}-\d{3}$` |

Both use `fullmatch` for anchored validation. Numerical range checks (heart
rate, temperature, etc.) use plain comparisons, not regular expressions.

---

## Standalone functions: `fitness_analyzer/analysis.py`

| Function | Purpose |
|---|---|
| `calculate_summary` | avg / min / max per numeric field |
| `collect_invalid_flags` | collects flag messages from non-clean observations |
| `compare_to_baseline` | delta between session averages and personal baselines |
| `detect_recovery` | True if HR and activity decline meaningfully in the final third |
| `classify_session` | applies classification rules; returns a structured result dict |
| `format_report` | builds a readable console/file report string |
| `analyse_session` | convenience wrapper running the full pipeline |

---

## Assumptions and classification rules

### Validation thresholds

| Field | Valid range |
|---|---|
| `heart_rate` | 35–205 bpm |
| `skin_response` | ≥ 0 |
| `temperature` | 25–42 °C |
| `activity_level` | 0–1 |
| `signal_quality` | 0–1; values below 0.70 are treated as low-quality and excluded from analysis |

A `None` or missing value for any field marks the observation invalid.

### Classification rules (applied in order)

1. **Insufficient data** - fewer than 50 % of observations are usable.
2. **Recovering** - HR and activity both decline by at least 8 bpm / 0.10 units between the first two-thirds and final third of usable observations.
3. **Resting** - avg HR within +15 bpm of baseline AND avg activity ≤ 0.25.
4. **Moderate activity** - avg HR within +40 bpm of baseline AND avg activity ≤ 0.65.
5. **High activity** - everything above the moderate thresholds.

---

## Installation and running instructions

```bash
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
python3 main.py --profiles data/participants.csv \
                --sessions data/fitness_sessions.csv \
                --invalid  data/fitness_sessions_invalid.csv \
                --output   output
```

On Windows, `python` and `python3` both work. All arguments have defaults
matching the paths above, so the following also works:

```bash
python3 main.py
```

To run the test suite:

```bash
python3 tests.py
```

No third-party packages are required.

---

## Example output

### Console completion summary

```
Loading profiles from data/participants.csv ...
  Loaded 3 participant(s).

Loading sessions from data/fitness_sessions.csv ...
  Accepted 29 row(s) across 5 session(s), rejected 0 row(s).

Loading sessions from data/fitness_sessions_invalid.csv ...
  Accepted 1 row(s) across 1 session(s), rejected 10 row(s).

Analysing 6 session(s) ...

====================================================
  COMPLETED
  Sessions analysed : 6
  Rows accepted     : 30
  Rows rejected     : 10
  Output files:
    output/analysis_summary.csv
    output/analysis_report.txt
    output/rejected_records.txt
====================================================
```

### output/analysis_summary.csv

```
session_id,participant_id,total_observations,usable_observations,classification,avg_heart_rate,avg_activity_level,recovery_detected
FIT-2026-001,P001,6,6,resting,68.833,0.093,False
FIT-2026-002,P002,6,6,moderate activity,102,0.495,False
FIT-2026-003,P003,6,6,high activity,132.5,0.747,False
FIT-2026-004,P001,6,6,recovering,113.167,0.547,True
FIT-2026-005,P002,5,0,insufficient data,,,False
FIT-2026-101,P001,1,1,resting,72,0.1,False
```

### output/rejected_records.txt (excerpt)

```
SOURCE                               ROW  SESSION          FIELD              VALUE        REASON
----------------------------------------------------------------------------------------------------------
fitness_sessions_invalid.csv           3  FIT-2026-101     heart_rate         fast         cannot convert to integer
fitness_sessions_invalid.csv           4  FIT-2026-101     participant_id     001          participant_id '001' does not match required pattern '^P\d{3}$'
fitness_sessions_invalid.csv           5  FIT-2026-101     activity_level                  missing required value
fitness_sessions_invalid.csv           6  FIT-2026-101     signal_quality     1.4          signal_quality out of range [0, 1]
fitness_sessions_invalid.csv           7  FIT-26-102       session_id         FIT-26-102   session_id 'FIT-26-102' does not match required pattern '^FIT-\d{4}-\d{3}$'
```

---

## Known limitations

- Classification thresholds are fixed constants tuned to the supplied CSV data.
  They are not derived from clinical guidelines.
- The recovery detector uses a simple early/late split. A regression-based
  approach would be more robust but is outside scope.
- Skin response and temperature appear in the baseline comparison but are not
  used in the classification label itself.
- The `output/` directory is overwritten on each run without archiving previous
  results. This is intentional, the assignment requires predictable output
  without manual cleanup.
- `data_generator.py` and `sample_data.py` from Assignment I are retained for
  reference but are not used by `main.py`.
