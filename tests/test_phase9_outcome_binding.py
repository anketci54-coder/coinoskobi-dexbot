import main as application


class Feed:
    wallet_outcome_observer = None


class Intelligence:
    def observe_wallet_outcome(
        self,
        wallet_id,
        token_id,
        return_pct,
        *,
        realized=False,
    ):
        return {
            "state": "OBSERVED",
            "wallet_id": wallet_id,
            "token_id": token_id,
            "return_pct": return_pct,
            "realized": realized,
            "decision_authority": False,
            "execution_authority": False,
        }


class Pipeline:
    def __init__(self):
        self.learning_outcome_feed = Feed()
        self.intelligence = Intelligence()

    def run_cycle(self, **kwargs):
        return {"state": "READY"}


def test_application_binds_phase9_wallet_outcome_observer(monkeypatch):
    monkeypatch.setattr(application, "WSS_URL", "")
    monkeypatch.setattr(application, "WSS_PAIR", "")
    monkeypatch.setattr(application, "UNIVERSE_SHADOW_ENABLED", False)

    pipeline = Pipeline()
    built = application.build_application(
        pipeline=pipeline
    )

    observer = pipeline.learning_outcome_feed.wallet_outcome_observer

    assert callable(observer)
    assert observer.__self__ is pipeline.intelligence
    assert observer.__func__ is pipeline.intelligence.observe_wallet_outcome.__func__
    assert built["decision_authority"] is False
    assert built["live_authority"] is False
    assert built["execution_authority"] is False
