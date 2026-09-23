"""Domain classes for the Smart Fitness Session Analyzer."""


# ---------------------------------------------------------------------------
# Validation thresholds
# ---------------------------------------------------------------------------

HEART_RATE_MIN = 35
HEART_RATE_MAX = 205
TEMPERATURE_MIN = 25.0
TEMPERATURE_MAX = 42.0
SKIN_RESPONSE_MIN = 0.0
ACTIVITY_MIN = 0.0
ACTIVITY_MAX = 1.0
SIGNAL_QUALITY_MIN = 0.0
SIGNAL_QUALITY_MAX = 1.0
SIGNAL_QUALITY_THRESHOLD = 0.70   # observations below this are flagged low-quality


# ---------------------------------------------------------------------------
# Participant
# ---------------------------------------------------------------------------

class Participant:
    """Stores personal identity and baseline reference values.

    Encapsulation: _participant_id is private; accessed via a read-only property.
    """

    def __init__(self, participant_id: str, baseline_heart_rate: int,
                 baseline_skin_response: float, baseline_temperature: float):
        self._participant_id = participant_id          # private
        self.baseline_heart_rate = baseline_heart_rate
        self.baseline_skin_response = baseline_skin_response
        self.baseline_temperature = baseline_temperature

    # -- property (encapsulation requirement) --------------------------------

    @property
    def participant_id(self) -> str:
        return self._participant_id

    # -- factory (class method requirement) ----------------------------------

    @classmethod
    def from_dict(cls, profile: dict) -> "Participant":
        """Create a Participant from the generator's profile dictionary."""
        return cls(
            participant_id=profile["participant_id"],
            baseline_heart_rate=profile["baseline_heart_rate"],
            baseline_skin_response=profile["baseline_skin_response"],
            baseline_temperature=profile["baseline_temperature"],
        )

    def __repr__(self) -> str:
        return (f"Participant(id={self._participant_id}, "
                f"hr_base={self.baseline_heart_rate}, "
                f"temp_base={self.baseline_temperature})")


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class Observation:
    """Represents one sensor window.

    An observation may be valid, low-quality, or invalid.
    Invalid observations are kept as objects but excluded from analysis.
    """

    def __init__(self, timestamp: int, heart_rate, skin_response,
                 temperature, activity_level, signal_quality):
        self.timestamp = timestamp
        self.heart_rate = heart_rate
        self.skin_response = skin_response
        self.temperature = temperature
        self.activity_level = activity_level
        self.signal_quality = signal_quality

        self.valid: bool = True
        self.low_quality: bool = False
        self.flags: list[str] = []

        self._validate()

    # -- validation ----------------------------------------------------------

    def _validate(self) -> None:
        """Check all fields; set valid/low_quality and collect flags."""
        if self.heart_rate is None:
            self.flags.append("heart_rate: missing")
            self.valid = False
        elif not (HEART_RATE_MIN <= self.heart_rate <= HEART_RATE_MAX):
            self.flags.append(f"heart_rate: {self.heart_rate} out of range "
                              f"[{HEART_RATE_MIN}, {HEART_RATE_MAX}]")
            self.valid = False

        if self.skin_response is None:
            self.flags.append("skin_response: missing")
            self.valid = False
        elif self.skin_response < SKIN_RESPONSE_MIN:
            self.flags.append(f"skin_response: {self.skin_response} below 0")
            self.valid = False

        if self.temperature is None:
            self.flags.append("temperature: missing")
            self.valid = False
        elif not (TEMPERATURE_MIN <= self.temperature <= TEMPERATURE_MAX):
            self.flags.append(f"temperature: {self.temperature} out of range "
                              f"[{TEMPERATURE_MIN}, {TEMPERATURE_MAX}]")
            self.valid = False

        if self.activity_level is None:
            self.flags.append("activity_level: missing")
            self.valid = False
        elif not (ACTIVITY_MIN <= self.activity_level <= ACTIVITY_MAX):
            self.flags.append(f"activity_level: {self.activity_level} out of range "
                              f"[{ACTIVITY_MIN}, {ACTIVITY_MAX}]")
            self.valid = False

        if self.signal_quality is None:
            self.flags.append("signal_quality: missing")
            self.valid = False
        elif not (SIGNAL_QUALITY_MIN <= self.signal_quality <= SIGNAL_QUALITY_MAX):
            self.flags.append(f"signal_quality: {self.signal_quality} out of range "
                              f"[{SIGNAL_QUALITY_MIN}, {SIGNAL_QUALITY_MAX}]")
            self.valid = False
        elif self.signal_quality < SIGNAL_QUALITY_THRESHOLD:
            self.flags.append(f"signal_quality: {self.signal_quality} below threshold "
                              f"{SIGNAL_QUALITY_THRESHOLD}")
            self.low_quality = True
            # Low quality alone does not make invalid; caller may still exclude

    # -- factory (static method) ---------------------------------------------

    @staticmethod
    def from_dict(data: dict) -> "Observation":
        """Create an Observation from a raw generator dictionary."""
        return Observation(
            timestamp=data.get("timestamp"),
            heart_rate=data.get("heart_rate"),
            skin_response=data.get("skin_response"),
            temperature=data.get("temperature"),
            activity_level=data.get("activity_level"),
            signal_quality=data.get("signal_quality"),
        )

    def __repr__(self) -> str:
        status = "valid" if self.valid else "invalid"
        if self.valid and self.low_quality:
            status = "low-quality"
        return f"Observation(t={self.timestamp}, hr={self.heart_rate}, [{status}])"


# ---------------------------------------------------------------------------
# InvalidObservation  (inheritance + method overriding)
# ---------------------------------------------------------------------------

class InvalidObservation(Observation):
    """An observation that was immediately rejected due to a structural problem.

    Reuses Observation's initialization, but overrides field validation because
    a missing dictionary key makes the entire measurement window unusable.
    """

    def __init__(self, timestamp, reason: str):
        self._reason = reason
        super().__init__(timestamp, None, None, None, None, None)

    def _validate(self) -> None:
        """Report the structural error instead of five misleading field errors."""
        self.valid = False
        self.flags.append(self._reason)

    def __repr__(self) -> str:
        return f"InvalidObservation(t={self.timestamp}, reason={self.flags[0]!r})"


# ---------------------------------------------------------------------------
# Session  (composition: contains Participant + list of Observations)
# ---------------------------------------------------------------------------

class Session:
    """Groups observations for one participant into an analysable session.

    Composition:
        - holds a Participant instance
        - holds a list of Observation instances
    """

    MIN_USABLE_RATIO = 0.5   # need at least 50 % valid obs to classify

    def __init__(self, participant: Participant):
        self.participant = participant           # composition
        self._observations: list[Observation] = []

    # -- building the session ------------------------------------------------

    def add_observation(self, obs: Observation) -> None:
        self._observations.append(obs)

    @classmethod
    def from_data(cls, participant: Participant,
                  raw_observations: list[dict]) -> "Session":
        """Build a Session from a participant and raw observation dicts."""
        session = cls(participant)
        for data in raw_observations:
            required_keys = {"timestamp", "heart_rate", "skin_response",
                             "temperature", "activity_level", "signal_quality"}
            missing = required_keys - data.keys()
            if missing:
                obs = InvalidObservation(
                    timestamp=data.get("timestamp", "?"),
                    reason=f"missing keys: {missing}",
                )
            else:
                obs = Observation.from_dict(data)
            session.add_observation(obs)
        return session

    # -- accessors -----------------------------------------------------------

    @property
    def all_observations(self) -> list[Observation]:
        return list(self._observations)

    @property
    def usable_observations(self) -> list[Observation]:
        """Valid observations — low-quality are also excluded here."""
        return [o for o in self._observations if o.valid and not o.low_quality]

    @property
    def total_count(self) -> int:
        return len(self._observations)

    @property
    def usable_count(self) -> int:
        return len(self.usable_observations)

    def __repr__(self) -> str:
        return (f"Session(participant={self.participant.participant_id}, "
                f"total={self.total_count}, usable={self.usable_count})")
