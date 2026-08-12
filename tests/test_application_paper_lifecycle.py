import importlib


class FakePipeline:
    def run_cycle(self):
        return None

    def process_positions(self):
        return []


def test_application_binds_paper_lifecycle(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        "",
    )

    app = module.build_application(
        pipeline=FakePipeline(),
    )

    assert app[
        "paper_lifecycle_bound"
    ] is True

    names = {
        task["name"]
        for task
        in app[
            "runner"
        ].scheduler.jobs
    }

    assert (
        "paper_manager"
        in names
    )


class LegacyPipeline:
    def run_cycle(self):
        return None


def test_legacy_pipeline_without_position_job_is_safe(
    monkeypatch,
):
    module = importlib.import_module(
        "main"
    )

    monkeypatch.setattr(
        module,
        "WSS_URL",
        "",
    )

    monkeypatch.setattr(
        module,
        "WSS_PAIR",
        "",
    )

    app = module.build_application(
        pipeline=LegacyPipeline(),
    )

    assert app[
        "paper_lifecycle_bound"
    ] is False
