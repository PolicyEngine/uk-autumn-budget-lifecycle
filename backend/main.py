"""FastAPI backend for lifetime tax model."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Lifetime tax model")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inflation forecasts
# Source: OBR Economic and Fiscal Outlook, November 2025
# https://obr.uk/efo/economic-and-fiscal-outlook-november-2025/
# All values from OBR EFO detailed forecast tables (Table 1.7)
# Long-term assumptions from OBR's long-run equilibrium projections
CPI_FORECASTS = {
    2024: 0.0233, 2025: 0.0318, 2026: 0.0193, 2027: 0.0200, 2028: 0.0200, 2029: 0.0200,
}
CPI_LONG_TERM = 0.0200

RPI_FORECASTS = {
    2024: 0.0331, 2025: 0.0416, 2026: 0.0308, 2027: 0.0300, 2028: 0.0283, 2029: 0.0283,
}
RPI_LONG_TERM = 0.0239

# Policy parameters
PERSONAL_ALLOWANCE = 12_570
BASIC_RATE_THRESHOLD = 50_270
HIGHER_RATE_THRESHOLD = 125_140
BASIC_RATE = 0.20
HIGHER_RATE = 0.40
ADDITIONAL_RATE = 0.45
PA_TAPER_THRESHOLD = 100_000
PA_TAPER_RATE = 0.50

NI_PRIMARY_THRESHOLD = 12_570
NI_UPPER_EARNINGS_LIMIT = 50_270
NI_MAIN_RATE = 0.08
NI_HIGHER_RATE = 0.02
EMPLOYER_NI_RATE = 0.15  # From April 2025

STUDENT_LOAN_THRESHOLD_PLAN2 = 27_295
STUDENT_LOAN_RATE = 0.09
STUDENT_LOAN_FORGIVENESS_YEARS = 30

# Fuel duty rates (£ per litre) - calendar year averages
# Source: PolicyEngine-UK implementation and fuel-duty-freeze-2025 report
# https://policyengine.org/uk/research/fuel-duty-freeze-2025
#
# Baseline (without Autumn Budget): 5p cut ends Mar 2026, rate returns to 57.95p,
# then RPI uprating from April 2026 (4.1% in 2026-27, 3.2% in 2027-28, 2.9% thereafter)
#
# Reform (Autumn Budget): Freeze at 52.95p until Sep 2026, staggered reversal to 57.95p
# by Mar 2027, then same RPI uprating from April 2027
#
# Using calendar year averages (as per policyengine-uk methodology) to match how
# PolicyEngine calculates annual impacts. This ensures consistent treatment.

# Baseline rates by calendar year (counterfactual: 5p cut ends Mar 2026)
# Pre-AB: 5p cut expires Mar 2026, returns to 57.95p, then RPI uprating from Apr 2026
FUEL_DUTY_BASELINE = {
    2025: 0.5295,  # 5p cut still in effect (same as reform)
    # 2026 avg: Jan-Mar at 52.95p (91 days), Apr-Dec at 60.33p (275 days)
    # 60.33p = 57.95p * 1.041 (RPI uprating)
    2026: (0.5295 * 91 + 0.6033 * 275) / 366,  # ~0.5849
    # 2027 avg: Jan-Mar at 60.33p (90 days), Apr-Dec at 62.26p (275 days)
    # 62.26p = 60.33p * 1.032 (RPI uprating)
    2027: (0.6033 * 90 + 0.6226 * 275) / 365,  # ~0.6179
    # 2028 avg: Jan-Mar at 62.26p (91 days), Apr-Dec at 64.06p (275 days)
    2028: (0.6226 * 91 + 0.6406 * 275) / 366,  # ~0.6361
    # 2029 avg: Jan-Mar at 64.06p (90 days), Apr-Dec at 65.92p (275 days)
    2029: (0.6406 * 90 + 0.6592 * 275) / 365,  # ~0.6546
}

# Reform rates by calendar year (Autumn Budget policy)
# From policyengine-uk/parameters/gov/hmrc/fuel_duty/petrol_and_diesel.yaml
FUEL_DUTY_REFORM = {
    2025: 0.5295,  # 5p cut extended (same as baseline)
    2026: 0.5345,  # Calendar year avg with staggered increases
    2027: 0.5902,  # Calendar year avg transitioning to RPI uprating
    2028: 0.6111,  # RPI uprating from 2027
    2029: 0.6290,  # RPI uprating continues
}

# Long-term RPI growth rate for projecting beyond 2029
FUEL_DUTY_RPI_LONG_TERM = 0.029  # 2.9% per OBR projections

AVG_PETROL_PRICE_PER_LITRE = 1.40

SALARY_SACRIFICE_CAP = 2_000

DIVIDEND_ALLOWANCE = 500
SAVINGS_ALLOWANCE_BASIC = 1_000
SAVINGS_ALLOWANCE_HIGHER = 500

# State pension forecasts (full new state pension, annual amounts)
# Source: OBR Economic and Fiscal Outlook, November 2025
# https://media.quilter.com/search/state-pension-just-15p-shy-of-breaching-tax-allowances-in-2026-forecasts-obr/
# OBR projects the triple lock directly, so we use their forecasts
STATE_PENSION_FORECASTS = {
    2024: 11541.90,   # £221.20/week * 52.14
    2025: 12016.75,   # 4.1% triple lock increase
    2026: 12569.85,   # 4.6% triple lock increase (15p shy of PA!)
    2027: 12885.50,   # 2.5% triple lock minimum
}
# Long-term triple lock growth rate
# OBR FSR 2024: triple lock averages 0.53pp above earnings growth historically
# OBR long-term assumptions: 2% productivity + 2% inflation = ~4% nominal earnings
# Triple lock = max(CPI, earnings, 2.5%) averages ~4.5% over long term
# Source: https://obr.uk/frs/fiscal-risks-and-sustainability-july-2025/
STATE_PENSION_LONG_TERM_GROWTH = 0.04  # Conservative estimate (CPI target + productivity)
STATE_PENSION_AGE = 67

# Universal Credit child element parameters
# Source: policyengine-uk parameters for 2025-26
# https://github.com/PolicyEngine/policyengine-uk/tree/main/policyengine_uk/parameters/gov/dwp/universal_credit/elements/child
#
# Note: UC benefit uprating is not automatic - it requires an annual decision by the
# Secretary of State. However, in practice UC amounts have been consistently uprated
# by CPI each year (September CPI, effective from April). We assume this continues.
UC_CHILD_ELEMENT_ANNUAL_2025 = 3513.72  # £292.81/month * 12
UC_CHILD_ELEMENT_MAX_AGE = 18  # Children up to age 18 (or 19 if in approved education)
UC_TWO_CHILD_LIMIT_END_YEAR = 2026  # Autumn Budget 2025 removes limit from April 2026
UC_TWO_CHILD_LIMIT = 2  # Number of children covered before limit kicks in

# UC income tapering parameters
# Source: policyengine-uk parameters for 2025-26
# https://github.com/PolicyEngine/policyengine-uk/tree/main/policyengine_uk/parameters/gov/dwp/universal_credit/means_test
#
# UC is reduced by the taper rate for every £1 of net earnings above the work allowance.
# If earnings are high enough, UC can be tapered to zero.
UC_TAPER_RATE = 0.55  # 55% taper on net earnings above work allowance
UC_WORK_ALLOWANCE_WITH_HOUSING_2025 = 404 * 12  # £404/month = £4,848/year
UC_WORK_ALLOWANCE_NO_HOUSING_2025 = 673 * 12  # £673/month = £8,076/year


def calculate_uc_child_element_impact(
    num_children: int,
    children_ages: list[int],
    year: int,
    net_earnings: float = 0.0,
    has_housing_element: bool = True,
) -> float:
    """Calculate the impact of removing the two-child limit on UC child element.

    The Autumn Budget 2025 abolishes the two-child limit from April 2026.
    This function calculates how much additional UC child element a family gains,
    accounting for UC income tapering.

    UC is means-tested: benefits are reduced by 55% for each £1 of net earnings
    above the work allowance. If income is high enough, UC can taper to zero.

    Args:
        num_children: Total number of children in household
        children_ages: List of ages for each child
        year: Tax year (e.g., 2025 for 2025-26)
        net_earnings: Annual net earnings (after tax/NI) for UC taper calculation
        has_housing_element: Whether household receives UC housing element (affects work allowance)

    Returns:
        Annual impact in £ (positive = benefit from limit removal)
        Returns 0 for families with 2 or fewer eligible children
        Returns reduced amount if income tapers the benefit
    """
    if num_children == 0 or len(children_ages) == 0:
        return 0.0

    # Filter to eligible children (under 19)
    # UC rules: children under 16, or under 20 if in approved education
    # Simplified: we use age < 19 as the cutoff
    eligible_children = sum(1 for age in children_ages if age < UC_CHILD_ELEMENT_MAX_AGE + 1)

    # No impact if 2 or fewer eligible children
    if eligible_children <= UC_TWO_CHILD_LIMIT:
        return 0.0

    # Impact = additional children beyond 2 * annual child element amount
    additional_children = eligible_children - UC_TWO_CHILD_LIMIT

    # Get the uprated child element and work allowance for the target year
    # UC benefits and thresholds are uprated by CPI each April
    if year <= 2025:
        child_element = UC_CHILD_ELEMENT_ANNUAL_2025
        work_allowance = UC_WORK_ALLOWANCE_WITH_HOUSING_2025 if has_housing_element else UC_WORK_ALLOWANCE_NO_HOUSING_2025
    else:
        # Apply CPI uprating from 2025 to target year
        cpi_factor = get_cumulative_inflation(2025, year, use_rpi=False)
        child_element = UC_CHILD_ELEMENT_ANNUAL_2025 * cpi_factor
        base_allowance = UC_WORK_ALLOWANCE_WITH_HOUSING_2025 if has_housing_element else UC_WORK_ALLOWANCE_NO_HOUSING_2025
        work_allowance = base_allowance * cpi_factor

    # Calculate maximum child element impact (before tapering)
    max_impact = additional_children * child_element

    # Apply UC taper if earnings are above work allowance
    # The taper reduces UC by 55p for every £1 of net earnings above the work allowance
    if net_earnings > work_allowance:
        taper_reduction = (net_earnings - work_allowance) * UC_TAPER_RATE
        # The additional child element from limit abolition is tapered like other UC
        impact_after_taper = max(0.0, max_impact - taper_reduction)
        return impact_after_taper

    return max_impact


# Earnings growth plateaus at peak (no decline approaching retirement)
EARNINGS_GROWTH_BY_AGE = {
    22: 1.00, 23: 1.05, 24: 1.10, 25: 1.16, 26: 1.22, 27: 1.28, 28: 1.35,
    29: 1.42, 30: 1.50, 31: 1.55, 32: 1.60, 33: 1.65, 34: 1.70, 35: 1.75,
    36: 1.80, 37: 1.84, 38: 1.88, 39: 1.92, 40: 1.96, 41: 2.00, 42: 2.03,
    43: 2.06, 44: 2.09, 45: 2.12, 46: 2.14, 47: 2.16, 48: 2.18, 49: 2.19,
    50: 2.20,
}
PEAK_EARNINGS_MULTIPLIER = 2.20  # Plateau from age 50 onwards


class ModelInputs(BaseModel):
    current_age: int = 30
    current_salary: float = 40_000  # 2025 values
    retirement_age: int = 67
    life_expectancy: int = 85
    student_loan_debt: float = 50_000
    salary_sacrifice_per_year: float = 5_000
    rail_spending_per_year: float = 2_000
    dividends_per_year: float = 2_000
    savings_interest_per_year: float = 1_500
    property_income_per_year: float = 3_000
    petrol_spending_per_year: float = 1_500
    additional_income_growth_rate: float = 0.01
    # Children ages in 2025 (for two-child limit impact calculation)
    children_ages: list[int] = []


def get_cpi(year: int) -> float:
    return CPI_FORECASTS.get(year, CPI_LONG_TERM)


def get_rpi(year: int) -> float:
    return RPI_FORECASTS.get(year, RPI_LONG_TERM)


def get_cumulative_inflation(base_year: int, target_year: int, use_rpi: bool = False) -> float:
    factor = 1.0
    for y in range(base_year, target_year):
        rate = get_rpi(y) if use_rpi else get_cpi(y)
        factor *= (1 + rate)
    return factor


def get_state_pension(year: int) -> float:
    """Get state pension for a given year using OBR forecasts.

    Uses OBR's direct state pension projections where available,
    then extrapolates with 2.5% growth (triple lock floor) beyond forecast horizon.
    """
    if year in STATE_PENSION_FORECASTS:
        return STATE_PENSION_FORECASTS[year]

    # Beyond forecast horizon: grow from last known year at triple lock floor
    last_forecast_year = max(STATE_PENSION_FORECASTS.keys())
    pension = STATE_PENSION_FORECASTS[last_forecast_year]
    for _ in range(last_forecast_year, year):
        pension *= (1 + STATE_PENSION_LONG_TERM_GROWTH)
    return pension




def calculate_income_tax(gross_income: float) -> float:
    if gross_income > PA_TAPER_THRESHOLD:
        reduction = min(PERSONAL_ALLOWANCE, (gross_income - PA_TAPER_THRESHOLD) * PA_TAPER_RATE)
        pa = PERSONAL_ALLOWANCE - reduction
    else:
        pa = PERSONAL_ALLOWANCE

    taxable = max(0, gross_income - pa)
    tax = 0
    if taxable > 0:
        basic_band = min(taxable, BASIC_RATE_THRESHOLD - PERSONAL_ALLOWANCE)
        tax += basic_band * BASIC_RATE
        taxable -= basic_band
    if taxable > 0:
        higher_band = min(taxable, HIGHER_RATE_THRESHOLD - BASIC_RATE_THRESHOLD)
        tax += higher_band * HIGHER_RATE
        taxable -= higher_band
    if taxable > 0:
        tax += taxable * ADDITIONAL_RATE
    return tax


def calculate_ni(gross_income: float) -> float:
    if gross_income <= NI_PRIMARY_THRESHOLD:
        return 0
    ni = 0
    if gross_income > NI_PRIMARY_THRESHOLD:
        main_band = min(gross_income - NI_PRIMARY_THRESHOLD, NI_UPPER_EARNINGS_LIMIT - NI_PRIMARY_THRESHOLD)
        ni += main_band * NI_MAIN_RATE
    if gross_income > NI_UPPER_EARNINGS_LIMIT:
        ni += (gross_income - NI_UPPER_EARNINGS_LIMIT) * NI_HIGHER_RATE
    return ni


def calculate_student_loan(
    gross_income: float, remaining_debt: float, year: int, years_since_graduation: int,
    threshold: float = None
) -> tuple[float, float]:
    """Calculate student loan repayment and new debt balance.

    Args:
        gross_income: Annual gross income
        remaining_debt: Debt balance at start of year
        year: Calendar year
        years_since_graduation: Years since graduation (for 30-year forgiveness)
        threshold: Repayment threshold (defaults to STUDENT_LOAN_THRESHOLD_PLAN2)

    Returns:
        Tuple of (repayment amount, new debt balance after interest)
    """
    # Debt forgiven after 30 years
    if years_since_graduation >= STUDENT_LOAN_FORGIVENESS_YEARS:
        return 0, 0
    if remaining_debt <= 0:
        return 0, 0
    if threshold is None:
        threshold = STUDENT_LOAN_THRESHOLD_PLAN2
    rpi = get_rpi(year)
    interest_rate = min(rpi + 0.03, 0.071)
    if gross_income <= threshold:
        new_debt = remaining_debt * (1 + interest_rate)
        return 0, new_debt
    repayment = (gross_income - threshold) * STUDENT_LOAN_RATE
    repayment = min(repayment, remaining_debt)
    remaining_after_payment = remaining_debt - repayment
    new_debt = remaining_after_payment * (1 + interest_rate)
    return repayment, max(0, new_debt)


def get_fuel_duty_rate(year: int, is_reform: bool) -> float:
    """Get fuel duty rate for a given year.

    Args:
        year: Calendar year
        is_reform: True for Autumn Budget reform rates, False for baseline

    Returns:
        Fuel duty rate in £ per litre
    """
    rates = FUEL_DUTY_REFORM if is_reform else FUEL_DUTY_BASELINE

    if year in rates:
        return rates[year]

    # For years beyond 2029, extrapolate with RPI growth
    last_year = max(rates.keys())
    last_rate = rates[last_year]
    years_ahead = year - last_year
    return last_rate * ((1 + FUEL_DUTY_RPI_LONG_TERM) ** years_ahead)


def calculate_fuel_duty_impact(petrol_spending: float, year: int) -> float:
    """Calculate savings from fuel duty freeze/reform vs baseline (counterfactual).

    The Autumn Budget extends the 5p cut with staggered reversal. Without the Budget,
    the 5p cut would have ended in March 2026, returning rates to 57.95p with RPI
    uprating from April 2026.

    Impact = what you'd pay under baseline - what you pay under reform
    Positive value = savings (lower fuel costs)

    Args:
        petrol_spending: Annual petrol spending in £
        year: Calendar year

    Returns:
        Annual savings from the policy (positive = benefit)
    """
    if year < 2026:
        # No difference before policy diverges
        return 0

    baseline_rate = get_fuel_duty_rate(year, is_reform=False)
    reform_rate = get_fuel_duty_rate(year, is_reform=True)

    # Fuel duty is embedded in the petrol price
    # Savings = (baseline_rate - reform_rate) * litres consumed
    # litres = petrol_spending / price_per_litre
    litres = petrol_spending / AVG_PETROL_PRICE_PER_LITRE

    return (baseline_rate - reform_rate) * litres


def calculate_rail_impact(rail_spending_base: float, current_year: int, base_year: int = 2024) -> float:
    """Calculate savings from rail fare freeze in 2026.

    Rail fares normally increase by RPI + 1% annually.
    The 2026 freeze means fares stay at 2025 levels for one year.
    After 2026, fares resume normal increases but from the lower frozen base.

    Args:
        rail_spending_base: Annual rail spending in base_year prices
        current_year: Year to calculate for
        base_year: Year the spending input is denominated in

    Returns:
        Savings (positive = benefit) from the freeze policy
    """
    if current_year < 2026:
        return 0

    # Rail fares increase by RPI + 1% annually
    RAIL_MARKUP = 0.01  # 1% above RPI

    # Calculate cumulative fare index from base year to current year
    # Pre-AB (no freeze): fares increase every year by RPI + 1%
    # Post-AB (freeze): fares frozen in 2026, then resume increases

    def get_fare_index(target_year: int, freeze_2026: bool) -> float:
        """Get cumulative fare index from base_year to target_year."""
        index = 1.0
        for y in range(base_year, target_year):
            if freeze_2026 and y == 2025:
                # In 2026, fares don't increase (frozen at 2025 level)
                continue
            rpi = get_rpi(y)
            index *= (1 + rpi + RAIL_MARKUP)
        return index

    # Pre-AB: fares would have increased in 2026
    preAB_index = get_fare_index(current_year, freeze_2026=False)
    # Post-AB: fares frozen in 2026
    postAB_index = get_fare_index(current_year, freeze_2026=True)

    # Spending in current year
    preAB_spending = rail_spending_base * preAB_index
    postAB_spending = rail_spending_base * postAB_index

    # Savings = what you would have spent - what you actually spend
    return preAB_spending - postAB_spending


def calculate_salary_sacrifice_impact(salary_sacrifice: float, gross_income: float) -> float:
    """Calculate impact of salary sacrifice cap.

    Under the reform, employee and employer NICs are charged on pension contributions
    above the cap. This is a cost to the employee (reduced take-home or pension value).
    """
    excess = max(0, salary_sacrifice - SALARY_SACRIFICE_CAP)
    if excess == 0:
        return 0
    # Employee NI rate depends on income level
    employee_ni_rate = NI_MAIN_RATE if gross_income <= NI_UPPER_EARNINGS_LIMIT else NI_HIGHER_RATE
    # Total NICs charged on excess pension contribution
    return excess * (employee_ni_rate + EMPLOYER_NI_RATE)


def calculate_unearned_income_tax(dividends: float, savings_interest: float, property_income: float,
                                   gross_income: float, increased_tax: bool = False) -> float:
    """Calculate tax on unearned income (dividends, savings, property).

    Personal allowance is applied first to earned income, then any remaining
    allowance reduces unearned income. Order of taxation: savings interest,
    then dividends, then property income.
    """
    # Calculate remaining personal allowance after earned income
    remaining_pa = max(0, PERSONAL_ALLOWANCE - gross_income)

    # Total unearned income
    total_unearned = dividends + savings_interest + property_income

    # If personal allowance covers all unearned income, no tax
    if remaining_pa >= total_unearned:
        return 0.0

    # Determine tax rates based on total income (earned + unearned)
    total_income = gross_income + total_unearned
    if total_income > BASIC_RATE_THRESHOLD:
        savings_allowance = SAVINGS_ALLOWANCE_HIGHER
        dividend_rate = 0.3375
        savings_rate = HIGHER_RATE
    else:
        savings_allowance = SAVINGS_ALLOWANCE_BASIC
        dividend_rate = 0.0875
        savings_rate = BASIC_RATE

    # Apply remaining PA to unearned income (savings first, then dividends, then property)
    # Reduce each income type by the PA used
    pa_used = 0

    # Savings interest (taxed first, benefits from starting rate band)
    savings_after_pa = max(0, savings_interest - max(0, remaining_pa - pa_used))
    pa_used += min(savings_interest, max(0, remaining_pa - pa_used))
    taxable_savings = max(0, savings_after_pa - savings_allowance)

    # Dividends (taxed next)
    dividends_after_pa = max(0, dividends - max(0, remaining_pa - pa_used))
    pa_used += min(dividends, max(0, remaining_pa - pa_used))
    taxable_dividends = max(0, dividends_after_pa - DIVIDEND_ALLOWANCE)

    # Property income (taxed last)
    property_after_pa = max(0, property_income - max(0, remaining_pa - pa_used))
    taxable_property = property_after_pa

    tax = taxable_dividends * dividend_rate + taxable_savings * savings_rate + taxable_property * savings_rate
    if increased_tax:
        tax *= 1.05
    return tax


def calculate_scenario(
    gross_income: float,
    current_year: int,
    years_since_graduation: int,
    remaining_debt: float,
    freeze_end_year: int,
) -> dict:
    """Calculate all tax/benefit values for a single policy scenario.

    Args:
        gross_income: Annual gross income
        current_year: Calendar year
        years_since_graduation: Years since graduation
        remaining_debt: Student loan debt at start of year
        freeze_end_year: Year when threshold freeze ends (2028 for baseline, 2031 for reform)

    Returns:
        Dict with all calculated values for this scenario
    """
    # Calculate income tax thresholds
    if current_year < 2028:
        # Before any freeze would have ended
        pa = PERSONAL_ALLOWANCE
        basic_threshold = BASIC_RATE_THRESHOLD
        additional_threshold = HIGHER_RATE_THRESHOLD
    elif current_year < freeze_end_year:
        # Still frozen under this scenario
        pa = PERSONAL_ALLOWANCE
        basic_threshold = BASIC_RATE_THRESHOLD
        additional_threshold = HIGHER_RATE_THRESHOLD
    else:
        # Freeze has ended, CPI uprating applies
        cpi_factor = get_cumulative_inflation(freeze_end_year, current_year, use_rpi=False)
        pa = PERSONAL_ALLOWANCE * cpi_factor
        basic_threshold = BASIC_RATE_THRESHOLD * cpi_factor
        additional_threshold = HIGHER_RATE_THRESHOLD * cpi_factor

    # PA taper threshold is NEVER uprated (fixed at £100k since 2009)
    taper_threshold = PA_TAPER_THRESHOLD

    # Calculate effective PA after taper
    if gross_income > taper_threshold:
        effective_pa = max(0, pa - (gross_income - taper_threshold) * PA_TAPER_RATE)
    else:
        effective_pa = pa

    # Calculate income tax
    taxable = max(0, gross_income - effective_pa)
    income_tax = 0
    if taxable > 0:
        basic_band = min(taxable, basic_threshold - pa)
        income_tax += basic_band * BASIC_RATE
        taxable -= basic_band
    if taxable > 0:
        higher_band = min(taxable, additional_threshold - basic_threshold)
        income_tax += higher_band * HIGHER_RATE
        taxable -= higher_band
    if taxable > 0:
        income_tax += taxable * ADDITIONAL_RATE

    # Student loan threshold: frozen until 2027, then RPI uprating resumes
    # For baseline: freeze ends 2027 (RPI uprating from then)
    # For reform: additional freeze to 2030, then RPI uprating
    sl_freeze_end = 2027 if freeze_end_year == 2028 else 2030
    if current_year < 2027:
        sl_threshold = STUDENT_LOAN_THRESHOLD_PLAN2
    elif current_year < sl_freeze_end:
        # Still frozen
        sl_threshold = STUDENT_LOAN_THRESHOLD_PLAN2
    else:
        sl_threshold = STUDENT_LOAN_THRESHOLD_PLAN2 * get_cumulative_inflation(sl_freeze_end, current_year, use_rpi=True)

    # Calculate student loan payment and new debt
    sl_payment, new_debt = calculate_student_loan(
        gross_income, remaining_debt, current_year, years_since_graduation, sl_threshold
    )

    return {
        "pa": pa,
        "basic_threshold": basic_threshold,
        "taper_threshold": taper_threshold,
        "additional_threshold": additional_threshold,
        "effective_pa": effective_pa,
        "income_tax": income_tax,
        "sl_threshold": sl_threshold,
        "sl_payment": sl_payment,
        "sl_debt": new_debt,
    }


def run_model(inputs: ModelInputs) -> list[dict]:
    # Current salary is the 2025 value at current_age
    current_salary = inputs.current_salary
    current_age = inputs.current_age
    input_year = 2025  # All inputs are in 2025 values

    # Calculate what starting salary (at age 22) would be to produce current salary at current age
    current_age_multiplier = EARNINGS_GROWTH_BY_AGE.get(current_age, PEAK_EARNINGS_MULTIPLIER)
    base_multiplier_22 = EARNINGS_GROWTH_BY_AGE.get(22, 1.0)
    starting_salary = current_salary / current_age_multiplier * base_multiplier_22

    # Derive graduation year from current age (assume graduated at 22)
    graduation_age = 22
    graduation_year = input_year - (current_age - graduation_age)

    # Simulation runs from 2026 onwards (when Autumn Budget policies take effect)
    base_year = 2026
    # End year is when person reaches life expectancy
    end_year = input_year + (inputs.life_expectancy - current_age)
    results = []

    # Track two separate debt paths: baseline (Pre-AB) and reform (Post-AB)
    baseline_debt = inputs.student_loan_debt
    reform_debt = inputs.student_loan_debt

    for current_year in range(base_year, end_year + 1):
        years_since_graduation = current_year - graduation_year
        age = graduation_age + years_since_graduation

        if age < current_age or age > inputs.life_expectancy:
            continue

        is_retired = age > inputs.retirement_age

        # Calculate gross income (employment income + state pension if retired)
        if is_retired:
            employment_income = 0
            state_pension = get_state_pension(current_year)
            gross_income = state_pension
        else:
            base_multiplier = EARNINGS_GROWTH_BY_AGE.get(age, PEAK_EARNINGS_MULTIPLIER)
            additional_growth = (1 + inputs.additional_income_growth_rate) ** years_since_graduation
            employment_income = starting_salary * base_multiplier * additional_growth
            state_pension = 0
            gross_income = employment_income

        # Calculate both scenarios using the unified function
        baseline = calculate_scenario(gross_income, current_year, years_since_graduation, baseline_debt, freeze_end_year=2028)
        reform = calculate_scenario(gross_income, current_year, years_since_graduation, reform_debt, freeze_end_year=2031)

        # Update debt trackers
        baseline_debt = baseline["sl_debt"]
        reform_debt = reform["sl_debt"]

        # Standard calculations (same for both scenarios)
        ni = calculate_ni(gross_income)

        # Uprate unearned income with CPI from base year (maintains real value)
        unearned_cpi_factor = get_cumulative_inflation(base_year, current_year, use_rpi=False)
        dividends = inputs.dividends_per_year * unearned_cpi_factor
        savings_interest = inputs.savings_interest_per_year * unearned_cpi_factor
        property_income = inputs.property_income_per_year * unearned_cpi_factor

        unearned_tax = calculate_unearned_income_tax(
            dividends, savings_interest, property_income, gross_income
        )

        # Net income uses reform values (what actually happens post-AB)
        baseline_net = (gross_income - reform["income_tax"] - ni - reform["sl_payment"] - unearned_tax
                       - inputs.rail_spending_per_year - inputs.petrol_spending_per_year)

        # Calculate policy impacts
        impact_rail_freeze = calculate_rail_impact(inputs.rail_spending_per_year, current_year)
        impact_fuel_freeze = calculate_fuel_duty_impact(inputs.petrol_spending_per_year, current_year)

        # Threshold freeze impact: difference in income tax between scenarios
        impact_threshold_freeze = round(baseline["income_tax"] - reform["income_tax"]) if current_year >= 2028 else 0

        # Student loan impact: difference in repayments
        if current_year >= 2027 and (baseline_debt > 0 or reform_debt > 0):
            impact_sl_freeze = baseline["sl_payment"] - reform["sl_payment"]
        else:
            impact_sl_freeze = 0

        # Unearned income tax increase (using uprated values)
        unearned_tax_increased = calculate_unearned_income_tax(
            dividends, savings_interest, property_income, gross_income, increased_tax=True
        )
        impact_unearned_tax = -(unearned_tax_increased - unearned_tax)

        # Salary sacrifice cap (takes effect April 2029)
        # Salary sacrifice grows with CPI to maintain real value
        salary_sacrifice = inputs.salary_sacrifice_per_year * unearned_cpi_factor
        if current_year >= 2029 and not is_retired:
            impact_salary_sacrifice_cap = -calculate_salary_sacrifice_impact(salary_sacrifice, gross_income)
        else:
            impact_salary_sacrifice_cap = 0

        # Two-child limit abolition impact (takes effect April 2026)
        # Calculate children ages for this year (they age each year from 2025)
        years_from_input = current_year - input_year
        children_ages_this_year = [age_2025 + years_from_input for age_2025 in inputs.children_ages]
        num_children = len(children_ages_this_year)

        # Only calculate impact if there are children and we're in 2026+ (when limit is abolished)
        if num_children > 0 and current_year >= UC_TWO_CHILD_LIMIT_END_YEAR:
            # Calculate net earnings for UC taper (employment income minus tax and NI)
            # Note: UC taper applies to net earnings from employment, not total income
            net_earnings_for_uc = max(0, employment_income - reform["income_tax"] - ni)
            impact_two_child_limit = calculate_uc_child_element_impact(
                num_children, children_ages_this_year, current_year,
                net_earnings=net_earnings_for_uc,
                has_housing_element=True,  # Conservative assumption (lower work allowance)
            )
        else:
            impact_two_child_limit = 0

        results.append({
            "age": age,
            "year": current_year,
            "gross_income": round(gross_income),
            "employment_income": round(employment_income),
            "state_pension": round(state_pension),
            "income_tax": round(reform["income_tax"]),
            "national_insurance": round(ni),
            "student_loan_payment": round(reform["sl_payment"]),
            "student_loan_debt_remaining": round(reform_debt),
            "num_children": num_children,
            "baseline_net_income": round(baseline_net),
            "impact_rail_fare_freeze": round(impact_rail_freeze),
            "impact_fuel_duty_freeze": round(impact_fuel_freeze),
            "impact_threshold_freeze": round(impact_threshold_freeze),
            "impact_unearned_income_tax": round(impact_unearned_tax),
            "impact_salary_sacrifice_cap": round(impact_salary_sacrifice_cap),
            "impact_sl_threshold_freeze": round(impact_sl_freeze),
            "impact_two_child_limit": round(impact_two_child_limit),
            # Baseline scenario thresholds
            "baseline_pa": round(baseline["pa"]),
            "baseline_basic_threshold": round(baseline["basic_threshold"]),
            "baseline_taper_threshold": round(baseline["taper_threshold"]),
            "baseline_additional_threshold": round(baseline["additional_threshold"]),
            # Reform scenario thresholds
            "reform_pa": round(reform["pa"]),
            "reform_basic_threshold": round(reform["basic_threshold"]),
            "reform_taper_threshold": round(reform["taper_threshold"]),
            "reform_additional_threshold": round(reform["additional_threshold"]),
            # Student loan details for both scenarios
            "baseline_sl_debt": round(baseline["sl_debt"]),
            "reform_sl_debt": round(reform_debt),
            "baseline_sl_payment": round(baseline["sl_payment"]),
            "reform_sl_payment": round(reform["sl_payment"]),
            "baseline_sl_threshold": round(baseline["sl_threshold"]),
            "reform_sl_threshold": round(reform["sl_threshold"]),
        })

    return results


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/calculate")
def calculate(inputs: ModelInputs):
    results = run_model(inputs)
    return {"data": results}
