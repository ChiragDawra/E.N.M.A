from jarvis.security.sanitizer import sanitize


def test_clean_passes():
    out, err = sanitize("what time is it")
    assert err is None and out == "what time is it"


def test_sql_injection_blocked():
    out, err = sanitize("'; DROP TABLE users; --")
    assert out is None and err


def test_shell_metacharacters_blocked():
    out, err = sanitize("turn volume up && rm -rf /")
    assert out is None and err


def test_path_traversal_blocked():
    out, err = sanitize("../../etc/passwd")
    assert out is None and err


def test_too_long():
    out, err = sanitize("a" * 1000)
    assert out is None and "too long" in (err or "")


def test_empty():
    out, err = sanitize("")
    assert out is None and err


def test_control_chars_stripped():
    out, err = sanitize("hello\x00world")
    assert err is None
    assert out == "helloworld"
