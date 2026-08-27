"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class name while gaining checkpoint-first
scheduling and exact token+pool observation semantics.
"""

from . import counterfactual_observation as _counterfactual_observation
from .horizon_integrity import IntegrityCounterfactualObservationStore


_counterfactual_observation.CounterfactualObservationStore = (
    IntegrityCounterfactualObservationStore
)

__all__ = ["IntegrityCounterfactualObservationStore"]
