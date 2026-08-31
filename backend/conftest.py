import pytest
from django.test import override_settings


@pytest.fixture(autouse=True)
def _disable_throttling_limits():
    """Prevent DRF throttle limits from tripping the long test suite.

    Real limits are enforced in production settings; tests raise the ceiling so
    that repeated API calls in a single run do not trigger 429 responses.
    Throttling behavior itself is covered by dedicated tests that apply a
    stricter rate via ``override_settings``.
    """

    with override_settings(
        DEFAULT_THROTTLE_RATES={
            "anon": "100000/min",
            "user": "100000/min",
            "auth_login": "100000/min",
            "payment_initiate": "100000/min",
        }
    ):
        yield


@pytest.fixture(autouse=True)
def _disable_clickpesa_payouts():
    """Never hit the real ClickPesa payout API during tests.

    Withdrawal completions record payouts as UNAVAILABLE unless a test opts in
    via ``override_settings(CLICKPESA_PAYOUTS_ENABLED=True)`` + a mocked
    gateway. This keeps the suite offline and deterministic.
    """

    with override_settings(CLICKPESA_PAYOUTS_ENABLED=False):
        yield
