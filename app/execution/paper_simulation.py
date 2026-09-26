"""Unsigned, read-only transaction simulations for paper evidence."""

import json
import secrets
import socket
import subprocess
import time
from urllib.request import Request, urlopen

from app.chains.bsc import w3 as canonical_bsc_web3
from app.config.settings import RPC_URL, RPC_URL_SECONDARY, RPC_URL_TERTIARY, RPC_URL_QUATERNARY
from app.config.contracts import PANCAKE_ROUTER, WBNB, USDT
from web3 import Web3


ROUTER_BUY_ABI = [{
    "inputs": [
        {"name": "amountOutMin", "type": "uint256"},
        {"name": "path", "type": "address[]"},
        {"name": "to", "type": "address"},
        {"name": "deadline", "type": "uint256"},
    ],
    "name": "swapExactETHForTokens",
    "outputs": [{"name": "amounts", "type": "uint256[]"}],
    "stateMutability": "payable",
    "type": "function",
}]

ROUTER_FOT_BUY_ABI = [{
    "inputs": [
        {"name": "amountOutMin", "type": "uint256"},
        {"name": "path", "type": "address[]"},
        {"name": "to", "type": "address"},
        {"name": "deadline", "type": "uint256"},
    ],
    "name": "swapExactETHForTokensSupportingFeeOnTransferTokens",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function",
}]

ROUTER_SELL_ABI = [{
    "inputs": [
        {"name": "amountIn", "type": "uint256"},
        {"name": "amountOutMin", "type": "uint256"},
        {"name": "path", "type": "address[]"},
        {"name": "to", "type": "address"},
        {"name": "deadline", "type": "uint256"},
    ],
    "name": "swapExactTokensForTokens",
    "outputs": [{"name": "amounts", "type": "uint256[]"}],
    "stateMutability": "nonpayable",
    "type": "function",
}]

ROUTER_FOT_SELL_ABI = [{
    "inputs": [
        {"name": "amountIn", "type": "uint256"},
        {"name": "amountOutMin", "type": "uint256"},
        {"name": "path", "type": "address[]"},
        {"name": "to", "type": "address"},
        {"name": "deadline", "type": "uint256"},
    ],
    "name": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function",
}]

ERC20_BALANCE_ABI = [{
    "inputs": [{"name": "account", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function",
}]

ERC20_ALLOWANCE_ABI = [{
    "inputs": [
        {"name": "owner", "type": "address"},
        {"name": "spender", "type": "address"},
    ],
    "name": "allowance",
    "outputs": [{"name": "", "type": "uint256"}],
    "stateMutability": "view",
    "type": "function",
}]

ANVIL_BIN = "/root/.foundry/bin/anvil"
ANVIL_STARTUP_TIMEOUT_SECONDS = 20
ANVIL_EXECUTION_TIMEOUT_SECONDS = 30
ANVIL_FORK_TIMEOUT_MS = 10000


class AnvilForkBalanceDelta:
    """Execute unsigned swaps on a disposable exact-block BSC fork."""

    def __call__(self, *, client, transaction, token, recipient, block_number,
                 operation="buy", seed_transaction=None, fee_on_transfer=False,
                 deadline=None):
        # The source provider supplies an explicit block hash for provenance;
        # use configured URLs only as private subprocess arguments, never output.
        rpc_urls = [url for url in (
            RPC_URL, RPC_URL_SECONDARY, RPC_URL_TERTIARY, RPC_URL_QUATERNARY
        ) if url]
        if not rpc_urls:
            raise _UnknownEvidence("BSC fork provider unavailable")
        port = _available_port()
        command = [ANVIL_BIN, "--host", "127.0.0.1", "--port", str(port),
                   "--fork-url", rpc_urls[0], "--fork-block-number",
                   str(int(block_number)), "--timeout", str(ANVIL_FORK_TIMEOUT_MS),
                   "--silent"]
        process = None
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True,
            )
            endpoint = f"http://127.0.0.1:{port}"
            _wait_for_anvil(process, endpoint)
            chain_id = _rpc(endpoint, "eth_chainId", [])
            if int(chain_id, 16) != 56:
                raise _UnknownEvidence("Anvil fork is not BSC chain 56")
            fork_block = _rpc(endpoint, "eth_getBlockByNumber",
                              [hex(int(block_number)), False])
            source_block = client.eth.get_block(int(block_number))
            if (not fork_block or int(fork_block["number"], 16) != int(block_number)
                    or fork_block["hash"].lower() != _hex(source_block["hash"]).lower()):
                raise _UnknownEvidence("Anvil fork block provenance mismatch")

            _rpc(endpoint, "anvil_impersonateAccount", [recipient])
            _rpc(endpoint, "anvil_setBalance", [recipient, hex(10**20)])
            gas_price = int(_rpc(endpoint, "eth_gasPrice", []), 16)
            snapshot = _rpc(endpoint, "evm_snapshot", [])
            provenance = {
                "chain_id": int(chain_id, 16),
                "block_number": int(fork_block["number"], 16),
                "block_hash": fork_block["hash"],
            }
            approval_receipt = None
            seed_receipt = None
            if operation == "sell":
                if deadline is None:
                    raise _UnknownEvidence("sell deadline unavailable")
                quote_token = Web3.to_checksum_address(
                    transaction.get("quote_token")
                    or USDT
                )
                if quote_token.lower() != USDT.lower():
                    raise _UnknownEvidence("non-USDT sell route rejected")
                pool = Web3.to_checksum_address(
                    transaction.get("pool")
                )
                seed_token_raw = int(
                    transaction.get("seed_token_raw")
                    or 0
                )
                if seed_token_raw <= 0:
                    raise _UnknownEvidence("sell token seed unavailable")

                balance_slot = _seed_local_erc20_balance(
                    endpoint=endpoint,
                    token=Web3.to_checksum_address(token),
                    source_account=pool,
                    recipient=Web3.to_checksum_address(recipient),
                    amount=seed_token_raw,
                )
                token_balance = _local_balance(
                    endpoint,
                    token,
                    recipient,
                )
                if token_balance <= 0:
                    raise _UnknownEvidence("local fork token seed unavailable")
                router = Web3.to_checksum_address(PANCAKE_ROUTER)
                sell_abi = ROUTER_FOT_SELL_ABI if fee_on_transfer else ROUTER_SELL_ABI
                sell_name = ("swapExactTokensForTokensSupportingFeeOnTransferTokens"
                             if fee_on_transfer else "swapExactTokensForTokens")
                sell_data = _encode_data(
                    client, router, sell_abi, sell_name,
                    [token_balance, 0,
                     [Web3.to_checksum_address(token), quote_token],
                     Web3.to_checksum_address(recipient), int(deadline)],
                )
                transaction = {"to": router, "data": sell_data, "value": 0,
                               "gas": 2_000_000,
                               "quote_token": quote_token,
                               "pool": pool,
                               "seed_token_raw": seed_token_raw,
                               "seed_balance_slot": balance_slot}
                allowance = _local_allowance(endpoint, token, recipient, router)
                if allowance < token_balance:
                    approval_data = _encode_data(
                        client, token, [{"inputs": [
                            {"name": "spender", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                        ], "name": "approve", "outputs": [
                            {"name": "", "type": "bool"}],
                            "stateMutability": "nonpayable", "type": "function"}],
                        "approve", [router, token_balance],
                    )
                    approval_receipt = _send_local_transaction(
                        endpoint, recipient,
                        {"to": token, "data": approval_data, "value": 0},
                        gas_price,
                    )
                before = _local_balance(
                    endpoint,
                    quote_token,
                    recipient,
                    block_number,
                )
            else:
                before = _local_balance(endpoint, token, recipient, block_number)
            execution_receipt = _send_local_transaction(
                endpoint, recipient, transaction, gas_price
            )
            after = _local_balance(
                endpoint,
                (
                    transaction.get("quote_token")
                    if operation == "sell"
                    else token
                ),
                recipient,
                "latest",
            )
            delta = int(after) - int(before)
            _rpc(endpoint, "evm_revert", [snapshot])
            if delta <= 0:
                raise _UnknownEvidence("simulated recipient balance delta unavailable")
            return {
                "delta": delta,
                "balance_before": int(before),
                "balance_after": int(after),
                "receipt": execution_receipt,
                "seed_receipt": seed_receipt,
                "approval_receipt": approval_receipt,
                "provenance": provenance,
                "transaction": transaction,
            }
        except _EVMRevert:
            raise
        except _UnknownEvidence:
            raise
        except Exception as exc:
            raise _UnknownEvidence("Anvil fork infrastructure failure") from exc
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


def _available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _rpc(endpoint, method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode()
    request = Request(endpoint, data=payload,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=ANVIL_EXECUTION_TIMEOUT_SECONDS) as response:
        result = json.loads(response.read())
    if "error" in result:
        message = str(result["error"].get("message", "RPC error"))
        if "revert" in message.lower():
            raise _EVMRevert("execution reverted on isolated Anvil fork")
        raise RuntimeError(f"local Anvil RPC failure: {message}")
    return result["result"]


def _wait_for_anvil(process, endpoint):
    end = time.monotonic() + ANVIL_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError("Anvil exited before readiness")
        try:
            _rpc(endpoint, "eth_chainId", [])
            return
        except Exception:
            time.sleep(0.1)
    raise TimeoutError("Anvil startup timed out")


def _wait_for_receipt(endpoint, tx_hash):
    end = time.monotonic() + ANVIL_EXECUTION_TIMEOUT_SECONDS
    while time.monotonic() < end:
        try:
            receipt = _rpc(endpoint, "eth_getTransactionReceipt", [tx_hash])
        except RuntimeError as exc:
            # Anvil may briefly surface its lazy fork-state fetch failure on a
            # receipt query. Keep polling only for this observed 403 condition;
            # the next local query can succeed once the fork read is cached.
            if "archive requests require a personal token" not in str(exc).lower():
                raise
            time.sleep(0.1)
            continue
        if receipt is not None:
            return receipt
        time.sleep(0.1)
    raise TimeoutError("Anvil transaction timed out")


def _balance_data(address):
    return "0x70a08231" + address.lower().removeprefix("0x").rjust(64, "0")


def _allowance_data(owner, spender):
    return ("0xdd62ed3e" + owner.lower().removeprefix("0x").rjust(64, "0")
            + spender.lower().removeprefix("0x").rjust(64, "0"))


def _local_balance(endpoint, token, recipient, block="latest"):
    result = _rpc(endpoint, "eth_call", [
        {"to": token, "data": _balance_data(recipient)},
        hex(int(block)) if isinstance(block, int) else block,
    ])
    return int(result, 16)


def _local_allowance(endpoint, token, owner, spender):
    result = _rpc(endpoint, "eth_call", [
        {"to": token, "data": _allowance_data(owner, spender)}, "latest",
    ])
    return int(result, 16)


def _mapping_storage_key(account, slot):
    return Web3.keccak(
        bytes.fromhex(
            str(account).lower().removeprefix("0x").rjust(64, "0")
        )
        + int(slot).to_bytes(32, "big")
    ).hex().removeprefix("0x")


def _seed_local_erc20_balance(*, endpoint, token, source_account, recipient, amount):
    source_balance = _local_balance(
        endpoint,
        token,
        source_account,
    )
    if source_balance <= 0:
        raise _UnknownEvidence("pool token balance unavailable")

    matched_slot = None

    for slot in range(64):
        source_key = _mapping_storage_key(
            source_account,
            slot,
        )
        raw = _rpc(
            endpoint,
            "eth_getStorageAt",
            [token, "0x" + source_key, "latest"],
        )
        if int(raw, 16) == int(source_balance):
            matched_slot = slot
            break

    if matched_slot is None:
        raise _UnknownEvidence("erc20 balance storage slot unavailable")

    recipient_key = _mapping_storage_key(
        recipient,
        matched_slot,
    )
    value = "0x" + int(amount).to_bytes(32, "big").hex()

    _rpc(
        endpoint,
        "anvil_setStorageAt",
        [token, "0x" + recipient_key, value],
    )

    seeded = _local_balance(
        endpoint,
        token,
        recipient,
    )
    if int(seeded) != int(amount):
        raise _UnknownEvidence("erc20 local balance seed verification failed")

    return int(matched_slot)


def _encode_data(client, address, abi, function_name, args):
    contract = client.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
    return getattr(contract.functions, function_name)(*args)._encode_transaction_data()


def _send_local_transaction(endpoint, sender, transaction, gas_price):
    tx_hash = _rpc(endpoint, "eth_sendTransaction", [{
        "from": sender,
        "to": transaction["to"],
        "data": transaction.get("data", "0x"),
        "value": hex(int(transaction.get("value", 0))),
        "gas": hex(int(transaction.get("gas", 2_000_000))),
        "gasPrice": hex(int(gas_price)),
    }])
    receipt = _wait_for_receipt(endpoint, tx_hash)
    if int(receipt["status"], 16) == 0:
        raise _EVMRevert("execution reverted on isolated Anvil fork",
                         receipt=receipt)
    return receipt


def _hex(value):
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value
    return "0x" + bytes(value).hex()


class _EVMRevert(RuntimeError):
    """An unsigned transaction reverted in the local fork."""

    def __init__(self, message, *, receipt=None):
        super().__init__(message)
        self.receipt = receipt


def simulate_paper_buy(
    *, token, amount_in_wei, block_number,
    deadline, web3=None, gas_price_wei=None, fee_on_transfer=False,
):
    """Simulate an unsigned Pancake V2 BUY against one explicit block.

    Returns evidence only. It never signs, submits, or changes PAPER state.
    """
    client = web3 or canonical_bsc_web3
    result = {
        "contract": "phase15h_transaction_simulation_v1",
        "side": "BUY",
        "status": "UNKNOWN",
        "block": {"number": None, "hash": None, "chain_id": None},
        "received_token_raw": None,
        "router_returned_token_raw": None,
        "recipient_balance_delta_raw": None,
        "gas_used": None,
        "effective_gas_price": None,
        "execution_gas_cost_wei": None,
        "execution_price_native_per_token": None,
        "gas_estimate": None,
        "fee_native_estimate": None,
        "slippage_pct": None,
        "fill_status": "UNKNOWN",
        "raw": {"transaction": None, "receipt": None, "call_result": None,
                "gas_result": None, "errors": []},
        "read_only": True, "signing": False, "broadcast": False,
        "wallet_use": False, "paper_authority": False,
        "live_authority": False, "execution_authority": False,
    }

    try:
        amount_in = int(amount_in_wei)
        block_number = int(block_number)
        deadline = int(deadline)
        if amount_in <= 0 or block_number < 0 or deadline <= 0:
            raise ValueError("invalid amount, block, or deadline")
        token_address = Web3.to_checksum_address(token)
        # Generate only an address, not a key. Anvil impersonates and funds
        # this disposable account inside the local fork.
        sender = Web3.to_checksum_address("0x" + secrets.token_hex(20))
        router_address = Web3.to_checksum_address(PANCAKE_ROUTER)
        wbnb_address = Web3.to_checksum_address(WBNB)
        if token_address == wbnb_address:
            raise ValueError("BUY token must differ from WBNB")

        block = client.eth.get_block(block_number)
        block_hash = block.get("hash")
        if block_hash is None:
            raise ValueError("explicit block hash unavailable")
        chain_id = int(client.eth.chain_id)
        result["block"] = {
            "number": block_number,
            "hash": Web3.to_hex(block_hash),
            "chain_id": chain_id,
        }
        abi = ROUTER_FOT_BUY_ABI if fee_on_transfer else ROUTER_BUY_ABI
        function_name = ("swapExactETHForTokensSupportingFeeOnTransferTokens"
                         if fee_on_transfer else "swapExactETHForTokens")
        data = _encode_data(
            client, router_address, abi, function_name,
            [0, [wbnb_address, token_address], sender, deadline],
        )
        transaction = {
            "from": sender,
            "value": amount_in,
            "gas": 2_000_000,
            "nonce": 0,
            "chainId": chain_id,
            "to": router_address,
            "data": data,
        }
        # Keep only unsigned call fields as raw provenance. No signing or send path.
        result["raw"]["transaction"] = dict(transaction)
        # The router is submitted only to a fresh local Anvil fork. Balance
        # evidence is measured around that state transition.
        delta = AnvilForkBalanceDelta()(
            client=client, transaction=transaction, token=token_address,
            recipient=sender, block_number=block_number,
        )
        details = delta if isinstance(delta, dict) else {"delta": delta}
        _require_success_receipt(details)
        delta = details.get("delta")
        if delta is None or int(delta) <= 0:
            raise _UnknownEvidence("simulated recipient balance delta unavailable")
        delta = int(delta)
        _add_receipt_evidence(result, details)
        result["recipient_balance_delta_raw"] = delta
        result["received_token_raw"] = delta
        result["execution_price_native_per_token"] = amount_in / delta
        result["fill_status"] = "SIMULATED_RECIPIENT_DELTA"

        result["status"] = "SUCCESS"
    except Exception as exc:
        message = str(exc).lower()
        is_revert = isinstance(exc, _EVMRevert) or any(marker in message for marker in (
            "execution reverted", "revert", "0x08c379a0", "0x4e487b71",
        ))
        result["status"] = (
            "UNKNOWN" if isinstance(exc, _UnknownEvidence)
            else "REVERT" if is_revert
            else "UNKNOWN"
        )
        result["raw"]["errors"].append({
            "stage": "simulation", "type": type(exc).__name__,
            "message": ("execution reverted" if isinstance(exc, _EVMRevert)
                        else str(exc)),
        })
        if isinstance(exc, _EVMRevert):
            result["raw"]["receipt"] = exc.receipt
    return result


def simulate_paper_sell(
    *, token, pool, quote_token, block_number, deadline, web3=None,
    seed_token_raw, fee_on_transfer=False,
):
    """Simulate a Pancake V2 TOKEN/USDT SELL on a local Anvil fork.

    The PAPER universe is USDT-only. Token inventory is seeded only inside the
    disposable fork by locating the ERC20 balance mapping from the real pool
    balance, then writing the disposable recipient balance. No WBNB route,
    signing, broadcast, wallet, or PAPER-state mutation is used.
    """
    client = web3 or canonical_bsc_web3
    result = {
        "contract": "phase15h_transaction_simulation_v1",
        "side": "SELL", "status": "UNKNOWN",
        "block": {"number": None, "hash": None, "chain_id": None},
        "received_quote_raw": None,
        "quote_token": None,
        "recipient_balance_delta_raw": None,
        "gas_used": None, "effective_gas_price": None,
        "execution_gas_cost_wei": None,
        "fill_status": "UNKNOWN",
        "raw": {"transaction": None, "receipt": None, "seed_receipt": None,
                "approval_receipt": None, "errors": []},
        "read_only": True, "signing": False, "broadcast": False,
        "wallet_use": False, "paper_authority": False,
        "live_authority": False, "execution_authority": False,
    }
    try:
        block_number = int(block_number)
        deadline = int(deadline)
        seed_token_raw = int(seed_token_raw)
        if block_number < 0 or deadline <= 0 or seed_token_raw <= 0:
            raise ValueError("invalid token amount, block, or deadline")
        token_address = Web3.to_checksum_address(token)
        pool_address = Web3.to_checksum_address(pool)
        quote_address = Web3.to_checksum_address(quote_token)
        if quote_address.lower() != USDT.lower():
            raise ValueError("SELL quote must be USDT")
        if token_address.lower() == quote_address.lower():
            raise ValueError("SELL token must differ from USDT")
        sender = Web3.to_checksum_address("0x" + secrets.token_hex(20))
        router_address = Web3.to_checksum_address(PANCAKE_ROUTER)
        block = client.eth.get_block(block_number)
        if block.get("hash") is None:
            raise ValueError("explicit block hash unavailable")
        chain_id = int(client.eth.chain_id)
        result["block"] = {
            "number": block_number,
            "hash": Web3.to_hex(block["hash"]),
            "chain_id": chain_id,
        }
        result["quote_token"] = quote_address
        outcome = AnvilForkBalanceDelta()(
            client=client,
            transaction={
                "to": router_address,
                "data": "0x",
                "value": 0,
                "quote_token": quote_address,
                "pool": pool_address,
                "seed_token_raw": seed_token_raw,
            },
            token=token_address,
            recipient=sender,
            block_number=block_number,
            operation="sell",
            fee_on_transfer=fee_on_transfer,
            deadline=deadline,
        )
        details = outcome if isinstance(outcome, dict) else {"delta": outcome}
        _require_success_receipt(details)
        delta = int(details["delta"])
        _add_receipt_evidence(result, details)
        result["raw"].update({
            "transaction": details.get("transaction"),
            "seed_receipt": details.get("seed_receipt"),
            "approval_receipt": details.get("approval_receipt"),
            "balance_before": details.get("balance_before"),
            "balance_after": details.get("balance_after"),
            "recipient": sender,
        })
        result["received_quote_raw"] = delta
        result["recipient_balance_delta_raw"] = delta
        result["fill_status"] = "SIMULATED_RECIPIENT_DELTA"
        result["status"] = "SUCCESS"
    except Exception as exc:
        message = str(exc).lower()
        is_revert = isinstance(exc, _EVMRevert) or any(marker in message for marker in (
            "execution reverted", "revert", "0x08c379a0", "0x4e487b71",
        ))
        result["status"] = "REVERT" if is_revert else "UNKNOWN"
        result["raw"]["errors"].append({
            "stage": "simulation", "type": type(exc).__name__,
            "message": ("execution reverted" if isinstance(exc, _EVMRevert)
                        else str(exc)),
        })
        if isinstance(exc, _EVMRevert):
            result["raw"]["receipt"] = exc.receipt
    return result

def _require_success_receipt(details):
    receipt = details.get("receipt")
    if receipt is None:
        raise _UnknownEvidence("local execution receipt unavailable")
    status = int(receipt.get("status", "0x0"), 16)
    if status == 0:
        raise _EVMRevert("execution reverted on isolated Anvil fork",
                         receipt=receipt)
    if status != 1:
        raise _UnknownEvidence("local execution receipt status unavailable")


def _add_receipt_evidence(result, details):
    receipt = details.get("receipt")
    result["raw"]["receipt"] = receipt
    if receipt is None:
        return
    gas_used = int(receipt["gasUsed"], 16)
    price = receipt.get("effectiveGasPrice")
    effective_gas_price = int(price, 16) if price is not None else None
    result["gas_used"] = gas_used
    result["effective_gas_price"] = effective_gas_price
    result["execution_gas_cost_wei"] = (
        gas_used * effective_gas_price if effective_gas_price is not None else None
    )


class _UnknownEvidence(RuntimeError):
    """Required state or provenance could not be proved."""
