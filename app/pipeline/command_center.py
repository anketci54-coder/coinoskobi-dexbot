def _number(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_command_center_readmodel(
    *,
    candidate=None,
    pipeline_data=None,
    paper_outcome=None,
):
    """
    Phase 14 read-only Command Center composition.

    Existing runtime truth is displayed only.
    No trade, decision, paper, live, wallet,
    execution, provider, AI or override authority.
    """
    candidate = dict(candidate or {})
    data = dict(pipeline_data or {})
    outcome = dict(paper_outcome or {})

    strategy = dict(data.get("strategy") or {})
    score_data = dict(data.get("unified_score") or {})
    decision_data = dict(data.get("unified_decision") or {})
    risk_gate = dict(data.get("risk_gate") or {})
    paper = dict(data.get("paper") or {})
    analyzer = dict(data.get("analyzer_status") or {})
    sellability = dict(analyzer.get("sellability") or {})
    market = dict(data.get("market_context") or {})
    intelligence = dict(data.get("intelligence") or {})
    execution = dict(data.get("execution_cost") or {})
    expected_pnl = dict(data.get("expected_pnl") or {})
    exit_context = dict(data.get("exit_intelligence") or {})
    operating_mode = dict(data.get("operating_mode") or {})
    operator_command = dict(data.get("operator_command") or {})

    score = _number(score_data.get("score"))
    confidence = _number(score_data.get("confidence"))
    hard_block = bool(risk_gate.get("hard_block"))

    liquidity = _number(market.get("liquidity_usd"))
    if liquidity is None:
        liquidity = _number(candidate.get("liquidity"))

    sellability_state = sellability.get("status")
    decision = decision_data.get("decision")

    blockers = []

    if hard_block:
        blockers.append("HARD_RISK_BLOCK")

    if sellability_state in {
        "SELLABILITY_FAIL",
        "BLOCKED",
        "HONEYPOT",
    }:
        blockers.append("SELLABILITY_BLOCK")

    return {
        "contract": "phase14_command_center_readmodel_v1",

        "candidate": {
            "token": candidate.get("token"),
            "pool": candidate.get("pool"),
            "chain": candidate.get("chain"),
            "liquidity_usd": liquidity,
        },

        "decision": {
            "strategy": strategy.get("decision"),
            "unified": decision,
            "score": score,
            "confidence": confidence,
            "hard_block": hard_block,
            "blockers": blockers,
            "approval_required": bool(
                hard_block
                or decision not in {"PAPER", "WATCH"}
            ),
        },

        "paper": {
            "action": paper.get("action"),
            "reason": paper.get("reason"),
            "latest_outcome": outcome.get("outcome_class"),
            "roi_pct": outcome.get("roi_pct"),
        },

        "execution": {
            "sellability": sellability_state,
            "slippage_pct": execution.get("slippage_pct"),
            "mev_cost_pct": execution.get("mev_cost_pct"),
            "gas_cost_usd": execution.get("gas_cost_usd"),
            "net_expected_pnl_pct": (
                expected_pnl.get(
                    "net_expected_pnl_pct"
                )
                if expected_pnl.get(
                    "net_expected_pnl_pct"
                ) is not None
                else execution.get(
                    "net_expected_pnl_pct"
                )
            ),
        },

        "tactical": {
            "entry_plan": data.get("entry_plan"),
            "exit_plan": data.get("exit_plan"),
            "risk_reward": data.get("risk_reward"),
            "exit_context": exit_context,
        },

        "intelligence": {
            "flow": intelligence.get("flow_spread"),
            "wallet": intelligence.get("wallet_readmodel"),
            "adversary": intelligence.get("adversary_readmodel"),
            "runtime_actor": market.get("runtime_actor"),
        },

        "priority": {
            "score": score,
            "confidence": confidence,
            "hard_block": hard_block,
        },

        "operating_mode": operating_mode,

        # Phase 14 structured operator request.
        # Projection only; never execution authority.
        "operator_command": operator_command,

        "bounded": True,
        "read_only": True,
        "hot_path_wait": False,
        "provider_call": False,
        "external_fetch": False,
        "ai_inference": False,

        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
