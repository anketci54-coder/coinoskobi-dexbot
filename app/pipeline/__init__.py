# pipeline package

from app.pipeline.tx_origin_readiness_gate import (
    install_pipeline_tx_origin_readiness_gate,
)


def _install_pipeline_origin_gate():
    from app.pipeline.engine import PipelineEngine

    install_pipeline_tx_origin_readiness_gate(
        PipelineEngine
    )


_install_pipeline_origin_gate()
