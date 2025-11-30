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

    def test_medium_income_gets_full_benefit(self):
        """Medium income still gets full benefit - taper applies to total UC.

        KEY INSIGHT from policyengine-uk: The UC taper applies to TOTAL UC, not
        specifically to the child element. The impact of removing the 2-child limit
        equals the full child element amount UNTIL total UC with the limit would
        be zero. At moderate incomes (~£6,848), total UC (~£11,829) is still positive
        after taper, so the impact remains the full ~£3,514.
        """
        from main import (
            calculate_uc_child_element_impact,
            UC_WORK_ALLOWANCE_WITH_HOUSING_2025,
            UC_CHILD_ELEMENT_ANNUAL_2025
        )

        # Net earnings slightly above work allowance
        net_earnings = UC_WORK_ALLOWANCE_WITH_HOUSING_2025 + 2000  # ~£6,848

        result = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025,
            net_earnings=net_earnings,
            has_housing_element=True
        )

        # At this income level, total UC with limit is still positive after taper
        # so the impact is the FULL child element amount
        assert 3400 < result < 3700  # Full ~£3,514

    def test_no_housing_element_higher_allowance(self):
        """Without housing element, work allowance is higher - difference appears at high income.

        At moderate incomes, both cases get full benefit because total UC hasn't
        been fully tapered. The housing element work allowance only matters when
        income is high enough to nearly taper out UC entirely.
        """
        from main import (
            calculate_uc_child_element_impact,
            UC_WORK_ALLOWANCE_WITH_HOUSING_2025,
            UC_WORK_ALLOWANCE_NO_HOUSING_2025,
            UC_STANDARD_ALLOWANCE_SINGLE_PARENT_2025,
            UC_CHILD_ELEMENT_ANNUAL_2025,
            UC_TAPER_RATE
        )

        # At £7k, both get full benefit (UC not fully tapered)
        low_earnings = 7000
        with_housing_low = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025, net_earnings=low_earnings, has_housing_element=True
        )
        without_housing_low = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025, net_earnings=low_earnings, has_housing_element=False
        )
        assert 3400 < with_housing_low < 3700  # Both get full benefit
        assert 3400 < without_housing_low < 3700

        # At very high income where UC with limit is nearly/fully tapered, differences emerge.
        # UC with limit = standard + 2*child = ~£11,829
        # To fully taper (with housing): 4848 + (11829 / 0.55) = £26,355
        # UC without limit = standard + 3*child = ~£15,343
        # To fully taper (with housing): 4848 + (15343 / 0.55) = £32,744

        # At £28k, UC with limit is fully tapered (£0), but without limit still positive
        high_earnings = 28000

        with_housing_high = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025, net_earnings=high_earnings, has_housing_element=True
        )
        without_housing_high = calculate_uc_child_element_impact(
            3, [7, 5, 3], 2025, net_earnings=high_earnings, has_housing_element=False
        )

        # With housing: income reduction = (28000 - 4848) * 0.55 = £12,733
        # UC with limit = 0, UC without = 15343 - 12733 = £2,610 → impact = £2,610
        # Without housing: income reduction = (28000 - 8076) * 0.55 = £10,958
        # UC with limit = 11829 - 10958 = £871, UC without = 15343 - 10958 = £4,385
        # Impact = 4385 - 871 = £3,514 (full child element!)

        # At high income, without housing (higher work allowance) should preserve MORE impact
        assert without_housing_high > with_housing_high
        # Without housing still gets full benefit, with housing gets reduced
        assert 3400 < without_housing_high < 3700  # Full benefit
        assert with_housing_high < 3000  # Reduced benefit

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
        """If income rises faster than CPI, UC impact can decrease YoY.

        For the impact to decrease, income must be high enough to start
        tapering UC with the limit toward zero. At that point, further
        income increases reduce the remaining UC and thus the impact.
        """
        from main import calculate_uc_child_element_impact, get_cumulative_inflation

        # In 2026, UC max with limit ~£12,195 (uprated). Work allowance ~£4,991.
        # At £22k net earnings: taper = (22000 - 4991) * 0.55 = £9,355
        # Remaining UC with limit = 12195 - 9355 = ~£2,840 (positive)
        # Impact = full ~£3,622 (child element, uprated)
        benefit_2026 = calculate_uc_child_element_impact(
            3, [8, 6, 4], 2026,
            net_earnings=22000,
            has_housing_element=True
        )

        # In 2027, at £30k: taper = (30000 - 5091) * 0.55 = £13,700
        # UC max with limit ~£12,439. Remaining = 12439 - 13700 = £0 (fully tapered)
        # UC max without limit ~£16,132. Remaining = 16132 - 13700 = ~£2,432
        # Impact = £2,432 (less than full child element)
        benefit_2027 = calculate_uc_child_element_impact(
            3, [9, 7, 5], 2027,
            net_earnings=30000,  # Much higher income
            has_housing_element=True
        )

        # 2026 should get full benefit, 2027 should get reduced benefit
        assert 3500 < benefit_2026 < 3800  # Full uprated child element
        assert benefit_2027 < benefit_2026  # Reduced due to high income
