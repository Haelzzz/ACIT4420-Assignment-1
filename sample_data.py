"""Five required scenarios using the instructor-supplied data generator."""

from data_generator import generate_fitness_data

SCENARIOS = [
    {
        "label": "Resting",
        "participant_id": "P001",
        "scenario": "resting",
        "seed": 1,
        "windows": 12,
    },
    {
        "label": "Moderate Activity",
        "participant_id": "P002",
        "scenario": "moderate_activity",
        "seed": 2,
        "windows": 12,
    },
    {
        "label": "High Activity",
        "participant_id": "P003",
        "scenario": "high_activity",
        "seed": 3,
        "windows": 12,
    },
    {
        "label": "Recovery",
        "participant_id": "P004",
        "scenario": "recovery",
        "seed": 4,
        "windows": 12,
    },
    {
        "label": "Poor Quality / Invalid Data",
        "participant_id": "P005",
        "scenario": "poor_quality",
        "seed": 5,
        "windows": 12,
    },
]


def load_all_scenarios() -> list[dict]:
    """Return a list of scenario dicts, each with label, profile, observations."""
    result = []
    for cfg in SCENARIOS:
        profile, observations = generate_fitness_data(
            participant_id=cfg["participant_id"],
            scenario=cfg["scenario"],
            seed=cfg["seed"],
            number_of_windows=cfg["windows"],
        )
        result.append({
            "label": cfg["label"],
            "profile": profile,
            "observations": observations,
        })
    return result