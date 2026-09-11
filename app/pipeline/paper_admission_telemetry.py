import logging

logger = logging.getLogger(__name__)


def log_paper_admission(*, token_address, strategy, unified, gate, sellability, plan_blockers, decision):
    """Emit one compact, searchable record for every paper-admission evaluation."""
    blockers = ",".join(str(x) for x in (plan_blockers or ())) or "-"
    logger.info(
        "PAPER_ADMISSION token=%s strategy=%s unified=%s risk_hard_block=%s sellability=%s plan_blockers=%s decision=%s",
        str(token_address or "")[:16],
        str((strategy or {}).get("decision") or "UNKNOWN"),
        str((unified or {}).get("decision") or "UNKNOWN"),
        bool((gate or {}).get("hard_block")),
        str(sellability or "UNKNOWN"),
        blockers,
        str(decision or "UNKNOWN"),
    )
