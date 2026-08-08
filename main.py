from app.core.runner import Runner
from app.pipeline.engine import PipelineEngine

pipeline = PipelineEngine()


def main():

    runner = Runner(
        scan_job=pipeline.run_cycle,
        position_job=None,
    )

    runner.run()


if __name__ == "__main__":
    main()
