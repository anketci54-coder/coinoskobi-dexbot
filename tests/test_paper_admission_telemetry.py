from app.pipeline.paper_admission_telemetry import log_paper_admission


def test_paper_admission_telemetry_does_not_raise(caplog):
    with caplog.at_level("INFO"):
        log_paper_admission(
            token_address="0x1234567890abcdef",
            strategy={"decision": "WATCH"},
            unified={"decision": "UNKNOWN"},
            gate={"hard_block": True},
            sellability="SELLABILITY_FAIL",
            plan_blockers=["EMPIRICAL_MOVEMENT_INSUFFICIENT"],
            decision="REJECT",
        )

    assert "PAPER_ADMISSION" in caplog.text
    assert "strategy=WATCH" in caplog.text
    assert "sellability=SELLABILITY_FAIL" in caplog.text
    assert "decision=REJECT" in caplog.text
