from app.core.scheduler import Scheduler


class RecordingLog:
    def __init__(self):
        self.calls = []

    def info(self, message, *args):
        self.calls.append((message, args))

    def exception(self, *args, **kwargs):
        raise AssertionError("unexpected scheduler exception")


def test_scheduler_job_log_uses_loguru_formatting(monkeypatch):
    import app.core.scheduler as scheduler_module

    recording_log = RecordingLog()
    monkeypatch.setattr(scheduler_module, "log", recording_log)

    scheduler = Scheduler()
    scheduler.every(60, lambda: None, name="scanner")
    scheduler.tick()

    assert recording_log.calls == [
        ("[JOB] {}", ("scanner",))
    ]
