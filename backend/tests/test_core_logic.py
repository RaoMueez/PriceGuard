# backend/tests/test_core_logic.py
#
# Run with: pytest tests/test_core_logic.py -v
# (from the backend/ folder, with your venv activated)
#
# These target the pure, standalone functions in your pipeline — no
# database, no HTTP, no mocking required. That's deliberate: these are
# the functions doing the actual fraud-detection reasoning, and testing
# them in isolation is both the simplest and most meaningful place to
# start.

import pytest
from app.api.routers.complaints import (
    is_underpriced_or_equal,
    is_absurd_price,
    _normalize_effective_price,
)
from app.services.security_service import haversine_distance_km


# ------------------------------------------------------------------
# MATH FILTER
# ------------------------------------------------------------------
class TestMathFilter:
    def test_reported_price_below_official_is_underpriced(self):
        # Rs. 100 reported against Rs. 120 official — no violation
        assert is_underpriced_or_equal(100.0, 120.0) is True

    def test_reported_price_equal_to_official_is_underpriced(self):
        # Exactly matching the official rate is NOT a violation
        assert is_underpriced_or_equal(120.0, 120.0) is True

    def test_reported_price_above_official_is_not_underpriced(self):
        # Genuine overpricing — should NOT be flagged as "underpriced"
        assert is_underpriced_or_equal(150.0, 120.0) is False

    def test_no_official_price_available_never_flags_underpriced(self):
        # If there's no official rate on record, we can't judge — must not
        # silently treat this as "no violation" via a crash or false positive
        assert is_underpriced_or_equal(150.0, None) is False


# ------------------------------------------------------------------
# ABSURD PRICE / SPAM THRESHOLD
# ------------------------------------------------------------------
class TestAbsurdPriceThreshold:
    def test_just_below_threshold_is_not_absurd(self):
        # Official 120, multiplier 2.0 -> threshold is 240
        assert is_absurd_price(239.0, 120.0, multiplier=2.0) is False

    def test_at_threshold_is_absurd(self):
        assert is_absurd_price(240.0, 120.0, multiplier=2.0) is True

    def test_far_above_threshold_is_absurd(self):
        # 5000 for a Rs. 120 item — the textbook spam case
        assert is_absurd_price(5000.0, 120.0, multiplier=2.0) is True

    def test_no_official_price_never_flags_absurd(self):
        assert is_absurd_price(5000.0, None, multiplier=2.0) is False


# ------------------------------------------------------------------
# QUANTITY NORMALIZATION (fractional purchase / short-weight)
# ------------------------------------------------------------------
class TestPriceNormalization:
    def test_fractional_purchase_normalizes_correctly(self):
        # Scenario: paid Rs. 210 for 0.5kg -> effective Rs. 420/kg
        assert _normalize_effective_price(210.0, 0.5) == 420.0

    def test_short_weight_normalizes_correctly(self):
        # Scenario: paid Rs. 300, received only 0.6kg -> effective Rs. 500/kg
        assert _normalize_effective_price(300.0, 0.6) == 500.0

    def test_zero_quantity_is_rejected(self):
        with pytest.raises(Exception):
            _normalize_effective_price(210.0, 0.0)

    def test_absurdly_tiny_quantity_is_rejected(self):
        # A typo like 0.001 instead of 0.1 shouldn't be allowed to produce
        # an astronomical effective price
        with pytest.raises(Exception):
            _normalize_effective_price(210.0, 0.001)


# ------------------------------------------------------------------
# HAVERSINE DISTANCE (GPS geo-fencing)
# ------------------------------------------------------------------
class TestHaversineDistance:
    def test_same_point_is_zero_distance(self):
        dist = haversine_distance_km(33.6844, 73.0479, 33.6844, 73.0479)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_known_real_world_distance(self):
        # Islamabad (Blue Area) to Rawalpindi (Saddar) — verified against
        # an independent reference calculation: ~12.3 km
        islamabad = (33.7077, 73.0563)
        rawalpindi = (33.5973, 73.0479)
        dist = haversine_distance_km(*islamabad, *rawalpindi)
        assert dist == pytest.approx(12.3, abs=0.5)

    def test_distance_is_symmetric(self):
        a = (33.7077, 73.0563)
        b = (33.5973, 73.0479)
        assert haversine_distance_km(*a, *b) == pytest.approx(haversine_distance_km(*b, *a), abs=0.001)