"""Custom exceptions for the Smart Fitness Session Analyzer."""


class InvalidIdentifierError(ValueError):
    """Raised when a participant or session identifier fails regex validation."""

    def __init__(self, field: str, value: str, pattern: str):
        self.field = field
        self.value = value
        self.pattern = pattern
        super().__init__(
            f"{field} {value!r} does not match required pattern {pattern!r}"
        )


class InvalidRecordError(ValueError):
    """Raised when a CSV record cannot be accepted for analysis."""

    def __init__(self, reason: str, field: str = "", value: str = ""):
        self.reason = reason
        self.field = field
        self.value = value
        detail = f" (field={field!r}, value={value!r})" if field else ""
        super().__init__(f"Invalid record: {reason}{detail}")