from app.pipeline.engine import PipelineEngine

def test_pipeline():
    engine = PipelineEngine()

    assert hasattr(engine, "run")
    assert hasattr(engine, "run_cycle")
