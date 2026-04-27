import time
from bot.state import RateLimiter

def test_rate_limiter_allow_and_reset(monkeypatch):
    limiter = RateLimiter(window_seconds=10, max_requests=2)
    
    current_time = 100.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)
    
    # Allow 2 requests
    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    
    # Exceeded
    assert limiter.allow(1) is False
    
    # Different user can still make requests
    assert limiter.allow(2) is True
    
    # Advance time within window, still blocked for user 1
    current_time = 105.0
    assert limiter.allow(1) is False
    
    # Advance time past window for the first request
    current_time = 111.0
    # Now user 1 can make requests again
    assert limiter.allow(1) is True
