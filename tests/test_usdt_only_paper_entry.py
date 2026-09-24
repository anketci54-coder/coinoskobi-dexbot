from app.config.contracts import USDT


def test_canonical_usdt_contract():
    assert (
        USDT.lower()
        == "0x55d398326f99059ff775485246999027b3197955"
    )


def test_engine_has_fail_closed_usdt_paper_gate():
    from pathlib import Path

    source = Path("app/pipeline/engine.py").read_text()

    assert 'market_context.get("candidate_quote_token")' in source
    assert 'candidate_quote_token != USDT.lower()' in source
    assert '"reason": "NON_USDT_QUOTE"' in source
