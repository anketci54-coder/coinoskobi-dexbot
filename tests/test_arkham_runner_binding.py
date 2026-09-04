from app.core import application_services
from app.core.runner import Runner
from app.dex.arkham_successful_wallet_service import ArkhamSuccessfulWalletService


def test_auxiliary_registry_is_empty_without_arkham_key(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)

    assert application_services.build_application_auxiliary_services() == []


def test_auxiliary_registry_binds_arkham_when_configured(monkeypatch, tmp_path):
    path = tmp_path / "paper.db"
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    monkeypatch.setattr(application_services, "PAPER_DB", path)

    services = application_services.build_application_auxiliary_services()

    assert len(services) == 1
    service = services[0]
    assert isinstance(service, ArkhamSuccessfulWalletService)
    assert service.db_path == path
    assert service.status()["wallet_authority"] is False
    assert service.status()["execution_authority"] is False


def test_runner_owns_auxiliary_service_lifecycle_without_scheduler_job():
    calls = []

    class Service:
        name = "aux"

        @staticmethod
        def start():
            calls.append("start")

        @staticmethod
        def stop():
            calls.append("stop")

        @staticmethod
        def status():
            return {"name": "aux", "state": "RUNNING"}

    runner = Runner(
        auxiliary_service_factory=lambda: [Service()],
    )

    assert runner.scheduler.jobs == []
    assert len(runner.services) == 1

    runner._start_services()
    assert calls == ["start"]
    assert runner.service_status() == [{"name": "aux", "state": "RUNNING"}]

    runner._stop_services()
    assert calls == ["start", "stop"]


def test_existing_explicit_services_and_auxiliary_services_are_both_preserved():
    class Service:
        def __init__(self, name):
            self.name = name

        def start(self):
            pass

        def stop(self):
            pass

        def status(self):
            return {"name": self.name}

    wss = Service("wss")
    arkham = Service("arkham")

    runner = Runner(
        services=[wss],
        auxiliary_service_factory=lambda: [arkham],
    )

    assert runner.services == [wss, arkham]
