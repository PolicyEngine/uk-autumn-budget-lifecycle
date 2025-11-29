"""
TDD tests for two-child limit / Universal Credit child element calculation.

These tests use policyengine-uk as the oracle to validate our simplified implementation.
The simplified implementation must match policyengine-uk within a reasonable tolerance.

Key insight: We're modeling the IMPACT of removing the 2-child limit, which is:
- For families with 2 or fewer children: £0 (no impact)
- For families with 3+ children: ~£3,514/year per additional child beyond 2

The UC child element amounts (2025-26):
- Standard amount: £292.81/month = £3,513.72/year per child
"""

import pytest
from policyengine_uk import Simulation
import numpy as np

# Import the function we'll implement (will fail initially - TDD!)
import sys
sys.path.insert(0, '/Users/maxghenis/PolicyEngine/uk-autumn-budget-lifecycle/backend')


def get_policyengine_uc_child_element(
    num_children: int,
    children_ages: list[int],
    year: int,
    two_child_limit: bool = True,
) -> float:
    """
    Calculate UC child element using policyengine-uk as the oracle.

    Note: This returns the CHILD ELEMENT only, not full UC.
    The child element is NOT affected by income tapering -
    it's the maximum entitlement component.

    Args:
        num_children: Number of children
        children_ages: List of ages for each child
        year: Tax year (e.g., 2025 for 2025-26)
        two_child_limit: Whether the 2-child limit applies

    Returns:
        Annual UC child element amount
    """
    if num_children == 0:
        return 0.0

    # Build the household structure for policyengine-uk
    people = {
        "adult": {
            "age": {year: 30},
        }
    }

    # Add children - all born after 2017 so subject to limit
    for i, age in enumerate(children_ages):
        people[f"child_{i}"] = {
            "age": {year: age},
        }

    # Create benefit unit with adult and children
    benefit_unit_members = ["adult"] + [f"child_{i}" for i in range(num_children)]

    situation = {
        "people": people,
        "benunits": {
            "benunit": {
                "members": benefit_unit_members,
            }
        },
        "households": {
            "household": {
                "members": benefit_unit_members,
            }
        },
    }

    # Apply reform to remove 2-child limit if needed
    if not two_child_limit:
        reform_dict = {
            "gov.dwp.universal_credit.elements.child.limit.child_count": {
                f"{year}-01-01.{year}-12-31": 1000  # Effectively infinite
            }
        }
        sim = Simulation(situation=situation, reform=reform_dict)
    else:
        sim = Simulation(situation=situation)

    # Get the UC child element
    uc_child_element = sim.calculate("uc_child_element", year)[0]

    return float(uc_child_element)


def get_two_child_limit_impact_from_policyengine(
    num_children: int,
    children_ages: list[int],
    year: int,
) -> float:
    """
    Calculate the IMPACT of removing the two-child limit.

    Impact = (child element without limit) - (child element with limit)

    This is what families GAIN from the limit being abolished.
    """
    with_limit = get_policyengine_uc_child_element(
        num_children, children_ages, year, two_child_limit=True
    )
    without_limit = get_policyengine_uc_child_element(
        num_children, children_ages, year, two_child_limit=False
    )
    return without_limit - with_limit


class TestPolicyEngineUKOracle:
    """Tests to understand how policyengine-uk calculates the child element."""

    def test_oracle_one_child(self):
        """Verify oracle returns expected values for 1 child."""
        result = get_policyengine_uc_child_element(1, [5], 2025)
        # Should be roughly £3,514/year (292.81 * 12)
        assert 3400 < result < 3700

    def test_oracle_two_children(self):
        """Verify oracle returns expected values for 2 children."""
        result = get_policyengine_uc_child_element(2, [5, 3], 2025)
        # Should be roughly 2 * £3,514 = £7,028
        assert 6800 < result < 7300

    def test_oracle_three_children_with_limit(self):
        """With limit, 3 children should get same as 2 children."""
        three = get_policyengine_uc_child_element(3, [7, 5, 3], 2025, two_child_limit=True)
        two = get_policyengine_uc_child_element(2, [7, 5], 2025, two_child_limit=True)
        assert abs(three - two) < 10  # Should be essentially equal

    def test_oracle_three_children_without_limit(self):
        """Without limit, 3 children should get more than 2 children."""
        three = get_policyengine_uc_child_element(3, [7, 5, 3], 2025, two_child_limit=False)
        two = get_policyengine_uc_child_element(2, [7, 5], 2025, two_child_limit=False)
        assert three > two + 3000  # Should get an extra ~£3,514

    def test_oracle_impact_is_zero_for_two_children(self):
        """Removing limit has no impact for 2-child families."""
        impact = get_two_child_limit_impact_from_policyengine(2, [5, 3], 2025)
        assert abs(impact) < 1  # Should be £0

    def test_oracle_impact_is_positive_for_three_children(self):
        """Removing limit benefits 3-child families."""
        impact = get_two_child_limit_impact_from_policyengine(3, [7, 5, 3], 2025)
        assert 3400 < impact < 3700  # Should gain ~£3,514


class TestOurImplementation:
    """Tests for our simplified implementation."""

    TOLERANCE = 50.0  # Allow £50 tolerance vs policyengine-uk

    def test_import_works(self):
        """Test that we can import the function."""
        from main import calculate_uc_child_element_impact
        assert callable(calculate_uc_child_element_impact)

    def test_no_children_returns_zero(self):
        """No children = no impact."""
        from main import calculate_uc_child_element_impact
        result = calculate_uc_child_element_impact(0, [], 2025)
        assert result == 0

    def test_one_child_returns_zero_impact(self):
        """1 child = no impact from limit removal."""
        from main import calculate_uc_child_element_impact
        result = calculate_uc_child_element_impact(1, [5], 2025)
        assert result == 0

    def test_two_children_returns_zero_impact(self):
        """2 children = no impact from limit removal."""
        from main import calculate_uc_child_element_impact
        result = calculate_uc_child_element_impact(2, [5, 3], 2025)
        assert result == 0

    def test_three_children_matches_policyengine(self):
        """3 children impact should match policyengine-uk."""
        from main import calculate_uc_child_element_impact

        pe_impact = get_two_child_limit_impact_from_policyengine(3, [7, 5, 3], 2025)
        our_impact = calculate_uc_child_element_impact(3, [7, 5, 3], 2025)

        assert abs(pe_impact - our_impact) <= self.TOLERANCE

    def test_four_children_matches_policyengine(self):
        """4 children impact should match policyengine-uk."""
        from main import calculate_uc_child_element_impact

        pe_impact = get_two_child_limit_impact_from_policyengine(4, [10, 7, 5, 2], 2025)
        our_impact = calculate_uc_child_element_impact(4, [10, 7, 5, 2], 2025)

        assert abs(pe_impact - our_impact) <= self.TOLERANCE

    def test_five_children_matches_policyengine(self):
        """5 children impact should match policyengine-uk."""
        from main import calculate_uc_child_element_impact

        pe_impact = get_two_child_limit_impact_from_policyengine(5, [12, 10, 7, 5, 2], 2025)
        our_impact = calculate_uc_child_element_impact(5, [12, 10, 7, 5, 2], 2025)

        assert abs(pe_impact - our_impact) <= self.TOLERANCE


class TestYearUprating:
    """Tests for year-on-year uprating of child element amounts."""

    TOLERANCE = 100.0  # Allow more tolerance for projected years

    def test_2026_impact_matches_policyengine(self):
        """2026 impact should match policyengine-uk (post-limit-removal year)."""
        from main import calculate_uc_child_element_impact

        pe_impact = get_two_child_limit_impact_from_policyengine(3, [8, 6, 4], 2026)
        our_impact = calculate_uc_child_element_impact(3, [8, 6, 4], 2026)

        assert abs(pe_impact - our_impact) <= self.TOLERANCE

    def test_impact_grows_with_inflation(self):
        """Impact should grow over time with CPI uprating."""
        from main import calculate_uc_child_element_impact

        impact_2025 = calculate_uc_child_element_impact(3, [7, 5, 3], 2025)
        impact_2030 = calculate_uc_child_element_impact(3, [12, 10, 8], 2030)

        # Should be higher in 2030 due to CPI uprating (unless children aged out)
        # But children are still under 18 so should get more
        assert impact_2030 >= impact_2025


class TestChildAgingOut:
    """Tests for children aging out of eligibility."""

    def test_child_over_18_not_counted(self):
        """Children over 18 (not in education) shouldn't count."""
        from main import calculate_uc_child_element_impact

        # 3 children where oldest is 19 - only 2 are eligible
        result = calculate_uc_child_element_impact(3, [19, 5, 3], 2025)

        # With only 2 eligible children, impact should be £0
        assert result == 0

    def test_child_under_20_in_education_still_counts(self):
        """Children under 20 in approved education still count."""
        # Note: Our simplified model may not distinguish this
        # For now, we'll use age < 19 as the cutoff
        pass


class TestIncomeTapering:
    """Tests for UC income tapering effect on two-child limit impact."""

    def test_low_income_gets_full_benefit(self):
        """Low income below work allowance gets full child element impact."""
        from main import calculate_uc_child_element_impact, UC_WORK_ALLOWANCE_WITH_HOUSING_2025

        # Net earnings below work allowance (~£4,848)
        result = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=4000,  # Below work allowance
            has_housing_element=True
        )

        # Should get full ~£3,514 impact
        assert 3400 < result < 3700

    def test_high_income_gets_zero_benefit(self):
        """High income completely tapers away UC entitlement."""
        from main import calculate_uc_child_element_impact

        # Net earnings very high (£50k net would be well over threshold)
        result = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=50000,
            has_housing_element=True
        )

        # UC should be fully tapered to zero
        assert result == 0

    def test_medium_income_gets_partial_benefit(self):
        """Medium income gets partial benefit due to taper."""
        from main import (
            calculate_uc_child_element_impact,
            UC_WORK_ALLOWANCE_WITH_HOUSING_2025,
            UC_TAPER_RATE,
            UC_CHILD_ELEMENT_ANNUAL_2025
        )

        # Net earnings slightly above work allowance
        net_earnings = UC_WORK_ALLOWANCE_WITH_HOUSING_2025 + 2000  # ~£6,848

        result = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=net_earnings,
            has_housing_element=True
        )

        # Expected: full benefit minus taper
        # Taper reduction = £2000 * 0.55 = £1100
        expected_reduction = 2000 * UC_TAPER_RATE  # £1100
        expected = UC_CHILD_ELEMENT_ANNUAL_2025 - expected_reduction  # ~£2,414

        assert abs(result - expected) < 10

    def test_no_housing_element_higher_allowance(self):
        """Without housing element, work allowance is higher (more benefit preserved)."""
        from main import (
            calculate_uc_child_element_impact,
            UC_WORK_ALLOWANCE_WITH_HOUSING_2025,
            UC_WORK_ALLOWANCE_NO_HOUSING_2025
        )

        # Same earnings, compare with/without housing element
        net_earnings = 7000  # Above housing allowance, below no-housing allowance

        with_housing = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=net_earnings,
            has_housing_element=True  # Lower work allowance
        )

        without_housing = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=net_earnings,
            has_housing_element=False  # Higher work allowance
        )

        # Without housing should get MORE benefit (higher allowance threshold)
        assert without_housing > with_housing

    def test_income_taper_applies_to_uprated_values(self):
        """Work allowance should be uprated with CPI in future years."""
        from main import calculate_uc_child_element_impact

        # Same net earnings in 2025 vs 2030
        # In 2030, the work allowance should be higher (CPI-uprated)
        # So same nominal earnings should result in HIGHER benefit in 2030
        net_earnings = 6000

        benefit_2025 = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=net_earnings,
            has_housing_element=True
        )

        benefit_2030 = calculate_uc_child_element_impact(
            3, [12, 10, 8], 2030,  # Same children, aged 5 years
            net_earnings=net_earnings,
            has_housing_element=True
        )

        # 2030 should give higher benefit due to CPI-uprated thresholds and amounts
        assert benefit_2030 > benefit_2025

    def test_impact_can_decrease_year_over_year_if_income_rises(self):
        """If income rises faster than CPI, UC impact can decrease YoY."""
        from main import calculate_uc_child_element_impact, get_cumulative_inflation

        # Low income in 2026 (just getting UC)
        benefit_2026 = calculate_uc_child_element_impact(
            3, [8, 6, 4], 2026,
            net_earnings=10000,
            has_housing_element=True
        )

        # Higher income in 2027 (income rose faster than CPI)
        benefit_2027 = calculate_uc_child_element_impact(
            3, [9, 7, 5], 2027,  # Same children, aged 1 year
            net_earnings=20000,  # Income doubled (faster than CPI)
            has_housing_element=True
        )

        # With significantly higher income, benefit should decrease
        assert benefit_2027 < benefit_2026
