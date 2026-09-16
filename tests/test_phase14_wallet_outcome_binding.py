from app.paper.manager import PaperManager


class Feed:
    def __init__(self):
        self.kwargs = None

    def observe_paper_close(self, **kwargs):
        self.kwargs = kwargs
        return kwargs


def test_paper_close_uses_persisted_entry_wallet_only():
    feed = Feed()

    manager = object.__new__(PaperManager)
    manager.learning_feed = feed

    wallet_id = (
        "bsc:"
        "0x1111111111111111111111111111111111111111"
    )

    pos = {
        "id": 7,
        "token": "0xtoken",
        "created_at": "2026-01-01T00:00:00Z",
        "entry_price": 1.0,
        "tp_price": 2.0,
        "sl_price": 0.5,
        "highest_price": 1.8,
        "lowest_price": 0.9,
        "gross_pnl_usdt": 4.0,
        "net_pnl_usdt": 3.5,
        "opening_context_json": (
            '{"actor_identity":{'
            f'"wallet_id":"{wallet_id}",'
            f'"actor_id":"{wallet_id}",'
            '"identity_source":"TRANSACTION_FROM_ONLY",'
            '"hindsight_reconstructed":false'
            '}}'
        ),
    }

    manager._observe_learning_outcome(
        pos,
        current=1.5,
        roi=0.5,
        reason="TAKE_PROFIT",
        closed_at="2026-01-01T01:00:00Z",
    )

    assert feed.kwargs["wallet_id"] == wallet_id
    assert feed.kwargs["actor_id"] == wallet_id
    assert feed.kwargs["highest_price"] == 1.8
    assert feed.kwargs["lowest_price"] == 0.9
    assert feed.kwargs["gross_pnl_usdt"] == 4.0
    assert feed.kwargs["net_pnl_usdt"] == 3.5

    context = feed.kwargs["opening_context"]

    assert (
        context["actor_identity"]["identity_source"]
        == "TRANSACTION_FROM_ONLY"
    )
    assert (
        context["actor_identity"]["hindsight_reconstructed"]
        is False
    )


def test_missing_entry_wallet_remains_unknown():
    feed = Feed()

    manager = object.__new__(PaperManager)
    manager.learning_feed = feed

    pos = {
        "id": 8,
        "token": "0xtoken",
        "created_at": "2026-01-01T00:00:00Z",
        "entry_price": 1.0,
        "tp_price": 2.0,
        "sl_price": 0.5,
        "opening_context_json": (
            '{"captured_at_entry":true}'
        ),
    }

    manager._observe_learning_outcome(
        pos,
        current=1.5,
        roi=0.5,
        reason="TAKE_PROFIT",
        closed_at="2026-01-01T01:00:00Z",
    )

    assert feed.kwargs["wallet_id"] is None
    assert feed.kwargs["actor_id"] is None
    assert feed.kwargs["highest_price"] is None
    assert feed.kwargs["lowest_price"] is None
    assert feed.kwargs["gross_pnl_usdt"] is None
    assert feed.kwargs["net_pnl_usdt"] is None
