from pathlib import Path

SOURCE = Path(
    "app/api/static/dex-terminal.js"
).read_text()


def test_browser_context_is_bounded_to_four_verified_intents():
    assert "const VEZIR_CONTEXT_LIMIT=4;" in SOURCE
    assert "while(vezirIntentContext.length>VEZIR_CONTEXT_LIMIT)" in SOURCE


def test_browser_context_only_uses_allowlisted_server_intents():
    for intent, code in (
        ("WHY_NO_TRADE", "1"),
        ("RISK", "2"),
        ("OPPORTUNITY", "3"),
        ("WATCH", "4"),
        ("POSITIONS", "5"),
        ("SYSTEM", "6"),
        ("GENERAL", "7"),
    ):
        assert f"{intent}:'{code}'" in SOURCE

    assert "rememberVezirIntent(data.ai_routed_intent);" in SOURCE


def test_raw_answer_text_is_never_used_as_context():
    assert "data.answer" not in SOURCE[
        SOURCE.index("function vezirQuestionWithContext"):
        SOURCE.index("async function askVezir")
    ]


def test_context_uses_existing_backend_contract():
    assert "<<VEZIR_CTX:${vezirIntentContext.join(',')}>>" in SOURCE


def test_visible_user_question_does_not_include_context_marker():
    ask = SOURCE[
        SOURCE.index("async function askVezir"):
        SOURCE.index("async function loadAll")
    ]
    assert "addChat(q,'user')" in ask
    assert "{question:vezirQuestionWithContext(q)}" in ask
