"""Analysis module for hypothesis suggestions and checking."""

from .suggestions import HypothesisSuggestionModel, suggest_hypotheses
from .hypothesis import check_hypothesis

__all__ = [
    "suggest_hypotheses",
    "HypothesisSuggestionModel",
    "check_hypothesis",
]
