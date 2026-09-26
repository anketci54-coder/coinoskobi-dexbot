from types import SimpleNamespace
from unittest.mock import patch

from app.config.contracts import USDT
from app.execution.paper_simulation import (
    _UnknownEvidence,
    _wait_for_receipt,
    simulate_paper_buy,
    simulate_paper_sell,
)


TOKEN = "0x0000000000000000000000000000000000000002"
SENDER = "0x0000000000000000000000000000000000000003"
POOL = "0x0000000000000000000000000000000000000005"


class _Call:
    def __init__(self, response, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def build_transaction(self, fields):
        return {"to": "0x0000000000000000000000000000000000000004", **fields}

    def _encode_transaction_data(self):
        return "0x12345678"

    def call(self, transaction, *, block_identifier):
        self.calls.append((transaction, block_identifier))
        if self.error:
            raise self.error
        return self.response

    def estimate_gas(self, transaction, *, block_identifier):
        return 123456


class _Balance:
    def call(self, *, block_identifier):
        return 17


class _Functions:
    def __init__(self, call):
        self._call = call

    def swapExactETHForTokens(self, *_args):
        return self._call

    def swapExactETHForTokensSupportingFeeOnTransferTokens(self, *_args):
        return self._call

    def swapExactTokensForTokens(self, *_args):
        return self._call

    def swapExactTokensForTokensSupportingFeeOnTransferTokens(self, *_args):
        return self._call


class _Eth:
    chain_id = 56

    def __init__(self, call):
        self._call = call
        self.blocks = []

    def get_block(self, number):
        self.blocks.append(number)
        return {"hash": bytes.fromhex("ab" * 32)}

    def contract(self, **_kwargs):
        if _kwargs["abi"][0]["name"] == "balanceOf":
            return SimpleNamespace(functions=SimpleNamespace(
                balanceOf=lambda _recipient: _Balance()
            ))
        return SimpleNamespace(functions=_Functions(self._call))

    def get_balance(self, _sender, *, block_identifier):
        return 10**30


def _client(call):
    eth = _Eth(call)
    return SimpleNamespace(eth=eth), eth


def _run(call, *, delta=2_000_000, fee_on_transfer=False):
    client, eth = _client(call)
    def simulated_delta(**_kwargs):
        if call.error:
            raise call.error
        return {
            "delta": delta,
            "receipt": {"status": "0x1", "gasUsed": hex(123456),
                        "effectiveGasPrice": "0x3"},
        }
    with patch("app.execution.paper_simulation.AnvilForkBalanceDelta",
               return_value=simulated_delta):
        result = simulate_paper_buy(
            token=TOKEN, pool=POOL, quote_token=USDT, amount_in_usdt_raw=10**18, block_number=12345,
            deadline=2_000_000_000,
            web3=client, fee_on_transfer=fee_on_transfer,
        )
    return result, eth, call


def test_success_is_explicit_block_unsigned_and_provenanced():
    result, eth, call = _run(_Call([10**18, 2_000_000]))
    assert result["status"] == "SUCCESS"
    assert result["block"] == {
        "number": 12345, "hash": "0x" + "ab" * 32, "chain_id": 56
    }
    assert result["received_token_raw"] == 2_000_000
    assert result["recipient_balance_delta_raw"] == 2_000_000
    assert result["execution_price_usdt_per_token"] == 500_000_000_000
    assert result["gas_used"] == 123456
    assert result["effective_gas_price"] == 3
    assert result["execution_gas_cost_wei"] == 370368
    assert eth.blocks == [12345]
    assert call.calls == []
    assert result["quote_token"].lower() == USDT.lower()
    for key in ("signing", "broadcast", "wallet_use", "paper_authority",
                "live_authority", "execution_authority"):
        assert result[key] is False


def test_revert_at_known_block_is_reported_without_execution():
    result, _eth, call = _run(_Call(None, RuntimeError("execution reverted")))
    assert result["status"] == "REVERT"
    assert result["block"]["number"] == 12345
    assert result["received_token_raw"] is None
    assert result["raw"]["errors"][0]["message"] == "execution reverted"
    assert call.calls == []


def test_provider_or_block_identity_unavailable_stays_unknown():
    call = _Call([10**18, 2_000_000])
    client, _eth = _client(call)
    client.eth.get_block = lambda _number: (_ for _ in ()).throw(
        ConnectionError("unavailable")
    )
    result = simulate_paper_buy(
        token=TOKEN, pool=POOL, quote_token=USDT, amount_in_usdt_raw=10**18, block_number=12345,
        deadline=2_000_000_000, web3=client,
    )
    assert result["status"] == "UNKNOWN"
    assert result["block"]["hash"] is None
    assert result["received_token_raw"] is None


def test_rpc_unavailable_after_block_read_stays_unknown():
    result, _eth, call = _run(_Call(None, ConnectionError("provider timeout")))
    assert result["status"] == "UNKNOWN"
    assert result["block"]["hash"] is not None
    assert result["received_token_raw"] is None
    assert call.calls == []


def test_invalid_or_unavailable_transaction_inputs_stay_unknown():
    result = simulate_paper_buy(
        token=TOKEN, pool=POOL, quote_token=USDT, amount_in_usdt_raw=10**18, block_number=12345,
        deadline=2_000_000_000,
        web3=SimpleNamespace(eth=object()),
    )
    assert result["status"] == "UNKNOWN"
    assert result["execution_price_usdt_per_token"] is None


def test_generated_synthetic_sender_does_not_need_historical_chain_funding():
    call = _Call([10**18, 2_000_000])
    client, _eth = _client(call)
    client.eth.get_balance = lambda *_args, **_kwargs: 0
    with patch("app.execution.paper_simulation.AnvilForkBalanceDelta",
               return_value=lambda **_kwargs: {
                   "delta": 2_000_000,
                   "receipt": {"status": "0x1", "gasUsed": "0x1",
                               "effectiveGasPrice": "0x3"},
               }):
        result = simulate_paper_buy(
            token=TOKEN, pool=POOL, quote_token=USDT, amount_in_usdt_raw=10**18, block_number=12345,
            deadline=2_000_000_000, web3=client,
        )
    assert result["status"] == "SUCCESS"
    assert result["received_token_raw"] == 2_000_000


def test_missing_balance_delta_cannot_claim_standard_router_output():
    result, _eth, _call = _run(_Call([10**18, 2_000_000]), delta=None)
    assert result["status"] == "UNKNOWN"
    assert result["received_token_raw"] is None


def test_buy_without_successful_local_receipt_stays_unknown():
    call = _Call([10**18, 2_000_000])
    client, _eth = _client(call)
    with patch("app.execution.paper_simulation.AnvilForkBalanceDelta",
               return_value=lambda **_kwargs: {"delta": 2_000_000}):
        result = simulate_paper_buy(
            token=TOKEN, pool=POOL, quote_token=USDT, amount_in_usdt_raw=10**18, block_number=12345,
            deadline=2_000_000_000, web3=client,
        )
    assert result["status"] == "UNKNOWN"
    assert result["received_token_raw"] is None


def test_fee_on_transfer_output_uses_recipient_delta_not_router_quote():
    result, _eth, _call = _run(
        _Call([]), delta=1_700_000, fee_on_transfer=True
    )
    assert result["status"] == "SUCCESS"
    assert result["received_token_raw"] == 1_700_000
    assert result["recipient_balance_delta_raw"] == 1_700_000
    assert result["execution_price_usdt_per_token"] == 10**18 / 1_700_000


def test_authority_fields_are_false_even_when_state_delta_is_proven():
    result, _eth, _call = _run(_Call([10**18, 2_000_000]))
    for key in ("signing", "broadcast", "wallet_use", "paper_authority",
                "live_authority", "execution_authority"):
        assert result[key] is False


def test_receipt_poll_retries_anvil_archive_fetch_error(monkeypatch):
    receipt = {"status": "0x1"}
    responses = iter([
        RuntimeError(
            "local Anvil RPC failure: Fork Error: Transport(HttpError "
            "Archive requests require a personal token)"
        ),
        receipt,
    ])
    calls = []

    def rpc(_endpoint, method, params):
        calls.append((method, params))
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr("app.execution.paper_simulation._rpc", rpc)
    monkeypatch.setattr("app.execution.paper_simulation.time.sleep", lambda _s: None)

    assert _wait_for_receipt("http://127.0.0.1:8545", "0xabc") == receipt
    assert len(calls) == 2


def _sell_run(*, delta=900, error=None, fee_on_transfer=False,
              receipt_status="0x1", include_receipt=True):
    call = _Call(None, error=error)
    client, _eth = _client(call)
    details = {
        "delta": delta,
        "receipt": ({"status": receipt_status, "gasUsed": "0x5208",
                     "effectiveGasPrice": "0x3b9aca00"}
                    if include_receipt else None),
        "seed_receipt": {"status": "0x1"},
        "approval_receipt": {"status": "0x1"},
        "balance_before": 0,
        "balance_after": delta,
        "transaction": {"to": "0x0000000000000000000000000000000000000004",
                        "data": "0x12345678", "value": 0},
    }
    with patch("app.execution.paper_simulation.AnvilForkBalanceDelta",
               return_value=lambda **_kwargs: (_raise(error) if error else details)):
        result = simulate_paper_sell(
            token=TOKEN,
            pool=POOL,
            quote_token=USDT,
            block_number=12345,
            deadline=2_000_000_000,
            seed_token_raw=10**18,
            web3=client,
            fee_on_transfer=fee_on_transfer,
        )
    return result


def _raise(error):
    raise error


def test_sell_uses_receipt_and_actual_quote_balance_delta():
    result = _sell_run()
    assert result["side"] == "SELL"
    assert result["status"] == "SUCCESS"
    assert result["received_quote_raw"] == 900
    assert result["quote_token"].lower() == USDT.lower()
    assert result["raw"]["balance_after"] - result["raw"]["balance_before"] == 900
    assert result["gas_used"] == 0x5208
    assert result["effective_gas_price"] == 1_000_000_000
    assert result["execution_gas_cost_wei"] == 0x5208 * 1_000_000_000
    assert result["raw"]["approval_receipt"]["status"] == "0x1"


def test_fee_on_transfer_sell_uses_same_local_delta_contract():
    result = _sell_run(delta=700, fee_on_transfer=True)
    assert result["status"] == "SUCCESS"
    assert result["received_quote_raw"] == 700


def test_sell_local_revert_and_infrastructure_failure_classification():
    reverted = _sell_run(receipt_status="0x0")
    unknown = _sell_run(error=_UnknownEvidence("fork provider unavailable"))
    assert reverted["status"] == "REVERT"
    assert reverted["raw"]["receipt"]["status"] == "0x0"
    assert unknown["status"] == "UNKNOWN"


def test_sell_without_receipt_cannot_claim_success():
    result = _sell_run(include_receipt=False)
    assert result["status"] == "UNKNOWN"
    assert result["received_quote_raw"] is None
