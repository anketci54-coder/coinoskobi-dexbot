def test_cycle_status_authority_boundary():
    status = {
        "state": "READY",
        "decision_count": 1,
        "paper_actions": {"WATCH": 1},
        "decisions": [{
            "token": "0xtoken",
            "paper": "WATCH",
            "reason": None,
        }],
        "decision_authority": False,
        "live_authority": False,
        "execution_authority": False,
    }

    assert status["decision_count"] == 1
    assert status["paper_actions"] == {"WATCH": 1}
    assert status["decision_authority"] is False
    assert status["live_authority"] is False
    assert status["execution_authority"] is False
