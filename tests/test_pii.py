from jarvis.memory.pii import redact


def test_redact_phone():
    assert "[REDACTED-PHONE]" in redact("call me at +1 415 555 1234")


def test_redact_email():
    assert "[REDACTED-EMAIL]" in redact("email me at foo.bar+42@example.com thanks")


def test_redact_card():
    assert "[REDACTED-CARD]" in redact("my card is 4111 1111 1111 1111")


def test_redact_aadhaar():
    assert "[REDACTED-AADHAAR]" in redact("aadhaar 1234 5678 9012")


def test_nothing_to_redact():
    assert redact("turn the volume down") == "turn the volume down"
