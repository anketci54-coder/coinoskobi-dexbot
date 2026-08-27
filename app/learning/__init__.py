"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class name while gaining checkpoint-first
scheduling, exact token+pool identity and scientific horizon-label quality.
"""

from . import counterfactual_observation as _counterfactual_observation
from .horizon_quality import ScientificCounterfactualObservationStore


_counterfactual_observation.CounterfactualObservationStore = (
    ScientificCounterfactualObservationStore
)

__all__ = ["ScientificCounterfactualObservationStore"]
