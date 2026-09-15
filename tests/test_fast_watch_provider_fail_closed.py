import requests

from app.pipeline.fast_watch_revisit import FastWatchRevisitJob


class Pipeline:
    pass


def test_snapshot_connection_error_fails_closed():
    job = FastWatchRevisitJob(Pipeline())

    def snapshots(*args, **kwargs):
        raise requests.ConnectionError("provider unavailable")

    rows = job._fetch_snapshot_batch(
        snapshots,
        ["0x0000000000000000000000000000000000000001"],
    )

    assert rows == []


def test_snapshot_http_error_fails_closed():
    job = FastWatchRevisitJob(Pipeline())

    def snapshots(*args, **kwargs):
        raise requests.HTTPError("503")

    rows = job._fetch_snapshot_batch(
        snapshots,
        ["0x0000000000000000000000000000000000000002"],
    )

    assert rows == []


def test_non_provider_value_error_still_propagates():
    job = FastWatchRevisitJob(Pipeline())

    def snapshots(*args, **kwargs):
        raise ValueError("unexpected validation failure")

    try:
        job._fetch_snapshot_batch(
            snapshots,
            ["0x0000000000000000000000000000000000000003"],
        )
    except ValueError as exc:
        assert str(exc) == "unexpected validation failure"
    else:
        raise AssertionError("ValueError must propagate")
