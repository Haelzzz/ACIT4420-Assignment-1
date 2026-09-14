"""Standalone analysis functions for the Smart Fitness Session Analyzer.

All functions operate on plain data (lists, dicts) or Session/Participant
objects. No side effects beyond returning values.
"""

import statistics
from models import Session, Participant


# ---------------------------------------------------------------------------
# 1. Summary
# ---------------------------------------------------------------------------

def calculate_summary(observations: list) -> dict:
    """Return avg / min / max for each numeric field across usable observations.

    Parameters
    ----------
    observations : list of Observation
        Should be the session's usable_observations.

    Returns
    -------
    dict with keys: heart_rate, skin_response, temperature, activity_level,
    signal_quality — each mapping to {"avg": ..., "min": ..., "max": ...}.
    Returns an empty dict if the list is empty.
    """
    if not observations:
        return {}

    fields = ["heart_rate", "skin_response", "temperature",
              "activity_level", "signal_quality"]
    summary = {}
    for field in fields:
        values = [getattr(obs, field) for obs in observations
                  if getattr(obs, field) is not None]
        if values:
            summary[field] = {
                "avg": round(statistics.mean(values), 3),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
            }
    return summary


# ---------------------------------------------------------------------------
# 2. Validation report
# ---------------------------------------------------------------------------

def collect_invalid_flags(session: Session) -> list[dict]:
    """Return a list of flag reports for every non-valid or low-quality obs.

    Each entry: {"timestamp": ..., "flags": [...]}
    """
    flagged = []
    for obs in session.all_observations:
        if obs.flags:
            flagged.append({"timestamp": obs.timestamp, "flags": list(obs.flags)})
    return flagged


# ---------------------------------------------------------------------------
# 3. HR comparison against participant baseline
# ---------------------------------------------------------------------------

def compare_to_baseline(summary: dict, participant: Participant) -> dict:
    """Compare session averages against the participant's personal baselines.

    Returns a dict of {field: {"session_avg": ..., "baseline": ..., "delta": ...}}
    for the fields that have a baseline defined.
    """
    if not summary:
        return {}

    comparisons = {}

    if "heart_rate" in summary:
        avg = summary["heart_rate"]["avg"]
        base = participant.baseline_heart_rate
        comparisons["heart_rate"] = {
            "session_avg": avg,
            "baseline": base,
            "delta": round(avg - base, 3),
        }

    if "skin_response" in summary:
        avg = summary["skin_response"]["avg"]
        base = participant.baseline_skin_response
        comparisons["skin_response"] = {
            "session_avg": avg,
            "baseline": base,
            "delta": round(avg - base, 3),
        }

    if "temperature" in summary:
        avg = summary["temperature"]["avg"]
        base = participant.baseline_temperature
        comparisons["temperature"] = {
            "session_avg": avg,
            "baseline": base,
            "delta": round(avg - base, 3),
        }

    return comparisons


# ---------------------------------------------------------------------------
# 4. Recovery detection
# ---------------------------------------------------------------------------

def detect_recovery(observations: list) -> bool:
    """Return True if HR and activity both decline over the final third of obs.

    Strategy: split usable observations into an early half and a late third,
    then check that the late-third averages are lower for both HR and activity.
    Requires at least 6 usable observations to be meaningful.
    """
    if len(observations) < 6:
        return False

    split = len(observations) // 3
    early = observations[:split * 2]    # first two-thirds
    late = observations[split * 2:]     # final third

    early_hr = statistics.mean(o.heart_rate for o in early)
    late_hr = statistics.mean(o.heart_rate for o in late)

    early_act = statistics.mean(o.activity_level for o in early)
    late_act = statistics.mean(o.activity_level for o in late)

    # Require a meaningful drop, not just noise
    hr_declining = (early_hr - late_hr) >= 8        # at least 8 bpm drop
    activity_declining = (early_act - late_act) >= 0.10  # at least 0.10 drop

    return hr_declining and activity_declining


# ---------------------------------------------------------------------------
# 5. Session classification
# ---------------------------------------------------------------------------

# Thresholds expressed as HR delta above personal baseline
_HR_DELTA_RESTING = 15       # within 15 bpm of baseline → resting
_HR_DELTA_MODERATE_MAX = 40  # 15–40 bpm above baseline → moderate
# > 40 bpm above baseline → high activity

_ACTIVITY_RESTING_MAX = 0.25
_ACTIVITY_MODERATE_MAX = 0.65

_MIN_USABLE_RATIO = 0.5      # need ≥ 50 % usable obs to classify


def classify_session(session: Session, summary: dict,
                     baseline_comparisons: dict) -> dict:
    """Classify the session and return a structured result dict.

    Returns
    -------
    dict with keys:
        label       : str  — one of the five classification labels
        explanation : str  — human-readable reason
        recovery    : bool — whether recovery was detected
        usable      : int
        total       : int
    """
    usable = session.usable_observations
    total = session.total_count
    n_usable = len(usable)

    result = {
        "label": "",
        "explanation": "",
        "recovery": False,
        "usable": n_usable,
        "total": total,
    }

    # --- insufficient data --------------------------------------------------
    if total == 0 or (n_usable / total) < _MIN_USABLE_RATIO:
        result["label"] = "insufficient data"
        result["explanation"] = (
            f"Only {n_usable}/{total} observations were usable "
            f"(threshold: {int(_MIN_USABLE_RATIO * 100)} %)."
        )
        return result

    if not summary or "heart_rate" not in summary:
        result["label"] = "insufficient data"
        result["explanation"] = "No usable heart-rate data available."
        return result

    # --- recovery check (takes priority over intensity label) ---------------
    recovery = detect_recovery(usable)
    result["recovery"] = recovery

    hr_delta = baseline_comparisons.get("heart_rate", {}).get("delta", 0)
    avg_activity = summary.get("activity_level", {}).get("avg", 0)

    # --- classify intensity -------------------------------------------------
    if recovery:
        result["label"] = "recovering"
        result["explanation"] = (
            f"HR and activity both declined in the final third of the session. "
            f"Avg HR was {hr_delta:+.1f} bpm relative to baseline."
        )

    elif hr_delta <= _HR_DELTA_RESTING and avg_activity <= _ACTIVITY_RESTING_MAX:
        result["label"] = "resting"
        result["explanation"] = (
            f"HR was only {hr_delta:+.1f} bpm above baseline and avg activity "
            f"was {avg_activity:.2f} — consistent with rest."
        )

    elif hr_delta <= _HR_DELTA_MODERATE_MAX and avg_activity <= _ACTIVITY_MODERATE_MAX:
        result["label"] = "moderate activity"
        result["explanation"] = (
            f"HR was {hr_delta:+.1f} bpm above baseline and avg activity "
            f"was {avg_activity:.2f} — consistent with moderate exercise."
        )

    else:
        result["label"] = "high activity"
        result["explanation"] = (
            f"HR was {hr_delta:+.1f} bpm above baseline and avg activity "
            f"was {avg_activity:.2f} — consistent with high-intensity exercise."
        )

    return result


# ---------------------------------------------------------------------------
# 6. Console report
# ---------------------------------------------------------------------------

def format_report(participant: Participant, session: Session,
                  summary: dict, comparisons: dict,
                  classification: dict, flagged: list) -> str:
    """Build and return a readable console report as a string."""

    lines = []
    sep = "-" * 52

    lines.append("=" * 52)
    lines.append("  SMART FITNESS SESSION REPORT")
    lines.append("=" * 52)

    # Participant
    lines.append(f"  Participant : {participant.participant_id}")
    lines.append(f"  HR baseline : {participant.baseline_heart_rate} bpm")
    lines.append(f"  Temp base   : {participant.baseline_temperature} °C")
    lines.append(f"  Skin base   : {participant.baseline_skin_response}")
    lines.append(sep)

    # Observation counts
    lines.append(f"  Total observations  : {classification['total']}")
    lines.append(f"  Usable observations : {classification['usable']}")
    lines.append(sep)

    # Summary stats
    if summary:
        lines.append("  SUMMARY STATISTICS")
        col = "{:<18} {:>8} {:>8} {:>8}"
        lines.append(col.format("  Field", "Avg", "Min", "Max"))
        for field, stats in summary.items():
            label = field.replace("_", " ").capitalize()
            lines.append(col.format(
                f"  {label}",
                stats["avg"], stats["min"], stats["max"]
            ))
        lines.append(sep)

    # Baseline comparisons
    if comparisons:
        lines.append("  BASELINE COMPARISON")
        for field, data in comparisons.items():
            label = field.replace("_", " ").capitalize()
            sign = "+" if data["delta"] >= 0 else ""
            lines.append(
                f"  {label:<18}  session {data['session_avg']:.1f}  "
                f"vs baseline {data['baseline']:.1f}  "
                f"(delta {sign}{data['delta']:.1f})"
            )
        lines.append(sep)

    # Classification
    lines.append(f"  CLASSIFICATION  :  {classification['label'].upper()}")
    lines.append(f"  {classification['explanation']}")
    if classification["recovery"]:
        lines.append("  Recovery pattern detected in final observations.")
    lines.append(sep)

    # Flagged observations
    if flagged:
        lines.append(f"  FLAGGED OBSERVATIONS  ({len(flagged)} window(s))")
        for entry in flagged:
            for flag in entry["flags"]:
                lines.append(f"  t={entry['timestamp']:>3}  {flag}")
    else:
        lines.append("  No flagged observations.")

    lines.append("=" * 52)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. Full pipeline convenience function
# ---------------------------------------------------------------------------

def analyse_session(participant: Participant, raw_observations: list) -> dict:
    """Run the complete pipeline and return all results as a dict.

    Returns
    -------
    {
        "session"        : Session,
        "summary"        : dict,
        "comparisons"    : dict,
        "classification" : dict,
        "flagged"        : list,
        "report"         : str,
    }
    """
    session = Session.from_data(participant, raw_observations)
    summary = calculate_summary(session.usable_observations)
    comparisons = compare_to_baseline(summary, participant)
    classification = classify_session(session, summary, comparisons)
    flagged = collect_invalid_flags(session)
    report = format_report(participant, session, summary,
                           comparisons, classification, flagged)
    return {
        "session": session,
        "summary": summary,
        "comparisons": comparisons,
        "classification": classification,
        "flagged": flagged,
        "report": report,
    }