from app.pipeline.paper_admission import (
    paper_admission_decision,
)


def test_unknown_without_local_evidence_stays_watch():
    result = (
        paper_admission_decision(
            {
                "decision": (
                    "PAPER_BUY"
                )
            },

            {
                "decision": (
                    "PAPER_BUY_CANDIDATE"
                )
            },

            {
                "hard_block": False,

                "local_evidence_complete": (
                    False
                ),
            },

            sellability_status=(
                "SELLABILITY_UNKNOWN"
            ),
        )
    )

    assert result == "WATCH"


def test_unknown_with_local_evidence_stays_watch():
    result = paper_admission_decision(
        {"decision": "PAPER_BUY"},
        {"decision": "PAPER_BUY_CANDIDATE"},
        {
            "hard_block": False,
            "local_evidence_complete": True,
        },
        sellability_status="SELLABILITY_UNKNOWN",
    )
    assert result == "WATCH"



def test_confirmed_unsellable_rejects():
    result = (
        paper_admission_decision(
            {
                "decision": (
                    "PAPER_BUY"
                )
            },

            {
                "decision": (
                    "PAPER_BUY_CANDIDATE"
                )
            },

            {
                "hard_block": True,

                "local_evidence_complete": (
                    True
                ),
            },

            sellability_status=(
                "SELLABILITY_FAIL"
            ),
        )
    )

    assert (
        result
        == "REJECT"
    )
