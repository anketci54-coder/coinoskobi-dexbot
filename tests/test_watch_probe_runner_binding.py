from app.core.runner import Runner


def test_runner_watch_probe_job_uses_ten_second_cadence():
    runner = Runner(
        scan_job=lambda: None,
        position_job=lambda: None,
        watch_probe_job=lambda: None,
    )

    jobs = {
        job["name"]: job
        for job in runner.scheduler.jobs
    }

    assert jobs["paper_manager"]["interval"] == 10
    assert jobs["watch_probe_exit_sweeper"]["interval"] == 10


def test_runner_without_watch_job_does_not_create_sweeper():
    runner = Runner(
        position_job=lambda: None,
    )

    names = {
        job["name"]
        for job in runner.scheduler.jobs
    }

    assert "paper_manager" in names
    assert "watch_probe_exit_sweeper" not in names
