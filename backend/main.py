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

# Fuel duty rates (per litre)
# Current rate: 52.95p (frozen with 5p cut)
# Reform for FY 2026-27: extend 5p cut to Aug 2026, then +1p Sep, +2p Dec, +2p Mar
# Weighted average for FY 2026-27: (5*52.95 + 3*53.95 + 3*55.95 + 1*57.95) / 12 = 54.37p
FUEL_DUTY_CURRENT = 0.5295
FUEL_DUTY_FY_2026_27 = (5 * 0.5295 + 3 * 0.5395 + 3 * 0.5595 + 1 * 0.5795) / 12  # ~0.5437
FUEL_DUTY_UNFROZEN = 0.58
AVG_PETROL_PRICE_PER_LITRE = 1.40

SALARY_SACRIFICE_CAP = 2_000

DIVIDEND_ALLOWANCE = 500
SAVINGS_ALLOWANCE_BASIC = 1_000
SAVINGS_ALLOWANCE_HIGHER = 500

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
    starting_salary: float = 30_000
    graduation_year: int = 2024
    retirement_age: int = 67
    student_loan_debt: float = 50_000
    salary_sacrifice_per_year: float = 5_000
    rail_spending_per_year: float = 2_000
    dividends_per_year: float = 2_000
    savings_interest_per_year: float = 1_500
    property_income_per_year: float = 3_000
    petrol_spending_per_year: float = 1_500
    additional_income_growth_rate: float = 0.01


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


def calculate_fuel_duty_impact(petrol_spending: float, fiscal_year: int) -> float:
    """Calculate impact of fuel duty freeze/reform vs unfrozen baseline.

    Policy takes effect from 2026 (FY 2026-27).
    FY 2026-27: Phased increase (weighted average ~54.37p)
    FY 2027-28 onwards: Full rate of 57.95p
    """
    if fiscal_year < 2026:
        # No impact before policy takes effect
        return 0
    elif fiscal_year == 2026:
        # FY 2026-27: weighted average of phased increases
        reform_rate = FUEL_DUTY_FY_2026_27
    else:
        # FY 2027-28 onwards: 57.95p (52.95 + 5p of increases)
        reform_rate = 0.5795

    return petrol_spending * (FUEL_DUTY_UNFROZEN - reform_rate) / AVG_PETROL_PRICE_PER_LITRE


def calculate_rail_impact(rail_spending: float, current_year: int) -> float:
    if current_year < 2026:
        return 0
    rpi_2025 = get_rpi(2025)
    return rail_spending * rpi_2025


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
    # Starting salary is what they earned at age 22 in their graduation year
    starting_salary = inputs.starting_salary
    graduation_age = 22
    graduation_year = inputs.graduation_year

    # Simulation runs from 2026 onwards (when Autumn Budget policies take effect)
    base_year = 2026
    end_year = 2100
    results = []

    # Track two separate debt paths: baseline (Pre-AB) and reform (Post-AB)
    baseline_debt = inputs.student_loan_debt
    reform_debt = inputs.student_loan_debt

    for current_year in range(base_year, end_year + 1):
        years_since_graduation = current_year - graduation_year
        age = graduation_age + years_since_graduation

        if age < graduation_age or age > 100:
            continue

        is_retired = age > inputs.retirement_age

        # Calculate gross income
        if is_retired:
            gross_income = 0
        else:
            base_multiplier = EARNINGS_GROWTH_BY_AGE.get(age, PEAK_EARNINGS_MULTIPLIER)
            additional_growth = (1 + inputs.additional_income_growth_rate) ** years_since_graduation
            gross_income = starting_salary * base_multiplier * additional_growth

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
        if current_year >= 2029 and not is_retired:
            impact_salary_sacrifice_cap = -calculate_salary_sacrifice_impact(inputs.salary_sacrifice_per_year, gross_income)
        else:
            impact_salary_sacrifice_cap = 0

        results.append({
            "age": age,
            "year": current_year,
            "gross_income": round(gross_income),
            "income_tax": round(reform["income_tax"]),
            "national_insurance": round(ni),
            "student_loan_payment": round(reform["sl_payment"]),
            "student_loan_debt_remaining": round(reform_debt),
            "num_children": 0,
            "baseline_net_income": round(baseline_net),
            "impact_rail_fare_freeze": round(impact_rail_freeze),
            "impact_fuel_duty_freeze": round(impact_fuel_freeze),
            "impact_threshold_freeze": round(impact_threshold_freeze),
            "impact_unearned_income_tax": round(impact_unearned_tax),
            "impact_salary_sacrifice_cap": round(impact_salary_sacrifice_cap),
            "impact_sl_threshold_freeze": round(impact_sl_freeze),
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
