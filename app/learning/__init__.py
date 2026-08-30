"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class name while gaining checkpoint-first
scheduling, exact token+pool identity, scientific horizon-label quality and a
conservative one-USDT economic-capacity label.
"""

from . import counterfactual_observation as _counterfactual_observation
from .economic_probe import EconomicProbeCounterfactualObservationStore


_counterfactual_observation.CounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)

__all__ = ["EconomicProbeCounterfactualObservationStore"]
