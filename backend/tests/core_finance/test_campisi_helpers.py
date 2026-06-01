from backend.app.core_finance.campisi import classify_primary_driver


class TestClassifyPrimaryDriver:
    def test_clear_income_driver(self):
        assert classify_primary_driver(1000.0, 100.0, 50.0, 20.0) == "income"

    def test_clear_treasury_driver(self):
        assert classify_primary_driver(100.0, -5000.0, 200.0, 50.0) == "treasury"

    def test_mixed_when_top_two_close(self):
        """两个主项绝对值接近（差 <10%）→ mixed"""
        assert classify_primary_driver(1000.0, -950.0, 100.0, 10.0) == "mixed"

    def test_not_mixed_when_difference_exceeds_threshold(self):
        """差 >10% → 不是 mixed"""
        assert classify_primary_driver(1000.0, -800.0, 100.0, 10.0) == "income"

    def test_all_zero_unknown(self):
        assert classify_primary_driver(0.0, 0.0, 0.0, 0.0) == "unknown"

    def test_negative_values_use_abs(self):
        """用绝对值比较"""
        assert classify_primary_driver(-5000.0, 100.0, 50.0, 20.0) == "income"

    def test_selection_can_be_driver(self):
        assert classify_primary_driver(100.0, 50.0, 30.0, 9999.0) == "selection"
