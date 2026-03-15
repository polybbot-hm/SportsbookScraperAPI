"""Tests del rate limiter y rotación de User-Agent."""
from app.infrastructure.rate_limiter import get_user_agent_rotator, next_user_agent


def test_next_user_agent_returns_string():
    ua = next_user_agent()
    assert isinstance(ua, str)
    assert "Mozilla" in ua


def test_user_agent_rotator_cycles():
    rotator = get_user_agent_rotator()
    uas = [rotator() for _ in range(5)]
    assert len(uas) == 5
    assert all("Mozilla" in u for u in uas)
