"""Tests for student loan income-contingent interest rates.

Plan 2 loans use income-contingent interest rates:
- Below lower threshold (£28,470 in 2025): RPI only (prevailing rate)
- Above upper threshold (£51,245 in 2025): RPI + 3%
- Between thresholds: Tapered rate = RPI + 3% × (income - lower) / (upper - lower)

Source: Student Loans Company and policyengine-uk PR #1418
https://github.com/PolicyEngine/policyengine-uk/pull/1418
"""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import (
    get_student_loan_interest_rate,
    calculate_student_loan,
    get_rpi,
    STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024,
    STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024,
    STUDENT_LOAN_INTEREST_ADDITIONAL_RATE,
)


class TestInterestRateParameters:
    """Verify the interest rate threshold parameters are correct."""

    def test_lower_threshold_2024(self):
        """Lower income threshold for 2024-25."""
        assert STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024 == 28_470

    def test_upper_threshold_2024(self):
        """Upper income threshold for 2024-25."""
        assert STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024 == 51_245

    def test_additional_rate(self):
        """Maximum additional rate above RPI."""
        assert STUDENT_LOAN_INTEREST_ADDITIONAL_RATE == 0.03


class TestInterestRateBelowLowerThreshold:
    """Test interest rates for income below the lower threshold."""

    def test_zero_income_2025(self):
        """Zero income should get RPI-only interest rate."""
        expected_rpi = get_rpi(2025)  # 4.16% for 2025
        rate = get_student_loan_interest_rate(0, 2025)
        assert rate == pytest.approx(expected_rpi, abs=0.0001)

    def test_income_at_lower_threshold_2025(self):
        """Income exactly at lower threshold should get RPI-only rate."""
        expected_rpi = get_rpi(2025)
        # Threshold is uprated by RPI from 2024 to 2025
        from main import get_cumulative_inflation
        rpi_factor = get_cumulative_inflation(2024, 2025, use_rpi=True)
        lower_threshold_2025 = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024 * rpi_factor

        rate = get_student_loan_interest_rate(lower_threshold_2025, 2025)
        assert rate == pytest.approx(expected_rpi, abs=0.0001)

    def test_low_income_2024(self):
        """Low income in 2024 should get RPI-only rate."""
        expected_rpi = get_rpi(2024)  # 3.31% for 2024
        rate = get_student_loan_interest_rate(20_000, 2024)
        assert rate == pytest.approx(expected_rpi, abs=0.0001)


class TestInterestRateAboveUpperThreshold:
    """Test interest rates for income above the upper threshold."""

    def test_high_income_2025(self):
        """High income should get RPI + 3%."""
        expected_rpi = get_rpi(2025)
        expected_rate = expected_rpi + 0.03

        rate = get_student_loan_interest_rate(80_000, 2025)
        assert rate == pytest.approx(expected_rate, abs=0.0001)

    def test_income_at_upper_threshold_2025(self):
        """Income exactly at upper threshold should get RPI + 3%."""
        expected_rpi = get_rpi(2025)
        expected_rate = expected_rpi + 0.03

        from main import get_cumulative_inflation
        rpi_factor = get_cumulative_inflation(2024, 2025, use_rpi=True)
        upper_threshold_2025 = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024 * rpi_factor

        rate = get_student_loan_interest_rate(upper_threshold_2025, 2025)
        assert rate == pytest.approx(expected_rate, abs=0.0001)

    def test_very_high_income_2024(self):
        """Very high income should get RPI + 3%."""
        expected_rpi = get_rpi(2024)
        expected_rate = expected_rpi + 0.03

        rate = get_student_loan_interest_rate(200_000, 2024)
        assert rate == pytest.approx(expected_rate, abs=0.0001)


class TestInterestRateTaper:
    """Test tapered interest rates between thresholds."""

    def test_midpoint_income_2024(self):
        """Income at midpoint should get RPI + 1.5% (half of 3%)."""
        lower = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024
        upper = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024
        midpoint = (lower + upper) / 2

        expected_rpi = get_rpi(2024)
        expected_rate = expected_rpi + 0.015  # Half of 3%

        rate = get_student_loan_interest_rate(midpoint, 2024)
        assert rate == pytest.approx(expected_rate, abs=0.0001)

    def test_quarter_point_income_2024(self):
        """Income at quarter point should get RPI + 0.75% (quarter of 3%)."""
        lower = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024
        upper = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024
        quarter_point = lower + (upper - lower) * 0.25

        expected_rpi = get_rpi(2024)
        expected_rate = expected_rpi + 0.0075  # Quarter of 3%

        rate = get_student_loan_interest_rate(quarter_point, 2024)
        assert rate == pytest.approx(expected_rate, abs=0.0001)

    def test_three_quarter_point_income_2024(self):
        """Income at 75% point should get RPI + 2.25% (three-quarters of 3%)."""
        lower = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024
        upper = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024
        three_quarter_point = lower + (upper - lower) * 0.75

        expected_rpi = get_rpi(2024)
        expected_rate = expected_rpi + 0.0225  # Three-quarters of 3%

        rate = get_student_loan_interest_rate(three_quarter_point, 2024)
        assert rate == pytest.approx(expected_rate, abs=0.0001)


class TestThresholdUprating:
    """Test that thresholds are correctly uprated by RPI over time."""

    def test_thresholds_uprated_2030(self):
        """By 2030, thresholds should be higher due to RPI uprating."""
        from main import get_cumulative_inflation

        # Calculate expected thresholds in 2030
        rpi_factor = get_cumulative_inflation(2024, 2030, use_rpi=True)
        lower_2030 = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024 * rpi_factor
        upper_2030 = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024 * rpi_factor

        # At income = £40,000 in 2024, this is well within taper range
        # But in 2030, £40,000 might be below the lower threshold
        rate_2024 = get_student_loan_interest_rate(40_000, 2024)
        rate_2030 = get_student_loan_interest_rate(40_000, 2030)

        # In 2030, £40,000 should have lower additional rate than in 2024
        # because thresholds have grown with RPI
        rpi_2024 = get_rpi(2024)
        rpi_2030 = get_rpi(2030)

        # Rate in 2024 should be higher relative to RPI base than in 2030
        # (due to threshold uprating)
        additional_2024 = rate_2024 - rpi_2024
        additional_2030 = rate_2030 - rpi_2030

        # The 2030 additional rate should be lower because £40k is closer
        # to the (now higher) lower threshold
        assert additional_2030 < additional_2024


class TestStudentLoanWithIncomeContingentInterest:
    """Integration tests for student loan calculation with income-contingent rates."""

    def test_low_income_pays_less_interest(self):
        """Low income borrower should accrue less interest than high income."""
        initial_debt = 50_000
        year = 2025

        # Low income (below threshold) - gets RPI only
        _, debt_low = calculate_student_loan(
            gross_income=20_000,
            remaining_debt=initial_debt,
            year=year,
            years_since_graduation=1,
            threshold=27_295,  # Below repayment threshold
        )

        # High income - gets RPI + 3%
        _, debt_high = calculate_student_loan(
            gross_income=80_000,
            remaining_debt=initial_debt,
            year=year,
            years_since_graduation=1,
            threshold=27_295,
        )

        # Low income should have lower debt growth (less interest)
        # Note: High income also makes repayments, so we compare interest rates used
        expected_rpi = get_rpi(2025)
        expected_low_rate = expected_rpi  # RPI only
        expected_high_rate = expected_rpi + 0.03  # RPI + 3%

        # Check rates are correctly applied
        low_rate = get_student_loan_interest_rate(20_000, 2025)
        high_rate = get_student_loan_interest_rate(80_000, 2025)

        assert low_rate == pytest.approx(expected_low_rate, abs=0.0001)
        assert high_rate == pytest.approx(expected_high_rate, abs=0.0001)

    def test_medium_income_tapered_rate(self):
        """Medium income should get tapered rate between thresholds."""
        from main import get_cumulative_inflation

        # Use 2025 and uprate thresholds
        rpi_factor = get_cumulative_inflation(2024, 2025, use_rpi=True)
        lower = STUDENT_LOAN_INTEREST_LOWER_THRESHOLD_2024 * rpi_factor
        upper = STUDENT_LOAN_INTEREST_UPPER_THRESHOLD_2024 * rpi_factor

        # Income at midpoint of thresholds
        midpoint_income = (lower + upper) / 2

        rate = get_student_loan_interest_rate(midpoint_income, 2025)
        expected_rpi = get_rpi(2025)
        expected_rate = expected_rpi + 0.015  # Half of 3%

        assert rate == pytest.approx(expected_rate, abs=0.0001)


class TestComparisonWithOldBehavior:
    """Tests comparing new income-contingent rates vs old fixed rate."""

    def test_old_fixed_rate_was_rpi_plus_3(self):
        """Document that old implementation used fixed RPI+3% for everyone."""
        # The old implementation did: min(rpi + 0.03, 0.071)
        # This was applied regardless of income
        rpi_2025 = get_rpi(2025)
        old_rate = min(rpi_2025 + 0.03, 0.071)

        # New implementation gives different rates based on income
        low_income_rate = get_student_loan_interest_rate(20_000, 2025)
        high_income_rate = get_student_loan_interest_rate(80_000, 2025)

        # Low income should now get LESS than old rate (RPI only vs RPI+3%)
        assert low_income_rate < old_rate

        # High income should still get the same as old rate
        assert high_income_rate == pytest.approx(old_rate, abs=0.001)

    def test_benefit_for_low_income_borrowers(self):
        """Low income borrowers benefit from income-contingent rates."""
        # This is the policy intent: lower earners pay less interest
        rpi = get_rpi(2025)
        low_rate = get_student_loan_interest_rate(20_000, 2025)
        high_rate = get_student_loan_interest_rate(80_000, 2025)

        # Low income gets RPI only
        assert low_rate == pytest.approx(rpi, abs=0.0001)

        # High income gets RPI + 3%
        assert high_rate == pytest.approx(rpi + 0.03, abs=0.0001)

        # Difference should be the full 3% additional rate
        assert (high_rate - low_rate) == pytest.approx(0.03, abs=0.0001)
