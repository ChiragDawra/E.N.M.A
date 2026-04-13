from jarvis.security.rate_limiter import RateLimiter


def test_allows_under_limit():
    rl = RateLimiter({"x": (3, 60)})
    assert rl.allow("x")
    assert rl.allow("x")
    assert rl.allow("x")
    assert not rl.allow("x")


def test_check_all_atomic_denial():
    rl = RateLimiter({"a": (1, 60), "b": (5, 60), "total": (100, 60)})
    assert rl.check_all("a", "b")
    # 'a' is now full; the next check_all must deny and not consume 'b'.
    assert not rl.check_all("a", "b")
    # But 'b' alone should still work — verifying we didn't over-consume.
    assert rl.allow("b")


def test_circuit_breaker():
    rl = RateLimiter({})
    for _ in range(3):
        rl.record_failure()
    assert rl.circuit_open()
    rl.record_success()
    assert not rl.circuit_open()


def test_unknown_bucket_allows():
    rl = RateLimiter({"x": (1, 60)})
    for _ in range(100):
        assert rl.allow("unknown")
