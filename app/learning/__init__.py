"""Learning package bootstrap.

The durable counterfactual store is hardened at package import so existing
runtime imports keep the same public class contract while gaining checkpoint-
first scheduling, exact token+pool identity, scientific horizon-label quality
and a conservative one-USDT economic-capacity label.
"""

from . import counterfactual_observation as _counterfactual_observation
from . import horizon_quality as _horizon_quality
from .economic_probe import EconomicProbeCounterfactualObservationStore


# Preserve the established public scientific-store identity while layering the
# Phase 13 economic probe underneath the same runtime-facing class contract.
_horizon_quality.ScientificCounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)
_counterfactual_observation.CounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)

ScientificCounterfactualObservationStore = (
    EconomicProbeCounterfactualObservationStore
)

__all__ = ["ScientificCounterfactualObservationStore"]
