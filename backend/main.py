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
    gross_income: float, remaining_debt: float, year: int, years_since_graduation: int
) -> tuple[float, float]:
    # Debt forgiven after 30 years
    if years_since_graduation >= STUDENT_LOAN_FORGIVENESS_YEARS:
        return 0, 0
    if remaining_debt <= 0:
        return 0, 0
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

    FY 2026-27: Phased increase (weighted average ~54.37p)
    FY 2027-28 onwards: Full rate of 57.95p
    """
    if fiscal_year <= 2025:
        # Current frozen rate
        reform_rate = FUEL_DUTY_CURRENT
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
    if gross_income > BASIC_RATE_THRESHOLD:
        savings_allowance = SAVINGS_ALLOWANCE_HIGHER
        dividend_rate = 0.3375
        savings_rate = HIGHER_RATE
    else:
        savings_allowance = SAVINGS_ALLOWANCE_BASIC
        dividend_rate = 0.0875
        savings_rate = BASIC_RATE
    taxable_dividends = max(0, dividends - DIVIDEND_ALLOWANCE)
    taxable_savings = max(0, savings_interest - savings_allowance)
    tax = taxable_dividends * dividend_rate + taxable_savings * savings_rate + property_income * savings_rate
    if increased_tax:
        tax *= 1.05
    return tax


def run_model(inputs: ModelInputs) -> list[dict]:
    # Starting salary is what they earned at age 22 in their graduation year
    # We use this to anchor their earnings profile
    starting_salary = inputs.starting_salary
    graduation_age = 22
    graduation_year = inputs.graduation_year

    # Simulation runs from 2024 onwards
    base_year = 2024
    end_year = 2100
    results = []
    student_loan_debt = inputs.student_loan_debt

    for current_year in range(base_year, end_year + 1):
        # Calculate age based on graduation year
        years_since_graduation = current_year - graduation_year
        age = graduation_age + years_since_graduation

        # Skip if not yet graduated or too old
        if age < graduation_age or age > 100:
            continue

        is_retired = age > inputs.retirement_age

        # Earnings are zero after retirement, plateau at peak before
        if is_retired:
            gross_income = 0
        else:
            base_multiplier = EARNINGS_GROWTH_BY_AGE.get(age, PEAK_EARNINGS_MULTIPLIER)
            additional_growth = (1 + inputs.additional_income_growth_rate) ** years_since_graduation
            gross_income = starting_salary * base_multiplier * additional_growth

        # Simplified: no children modelling
        num_children = 0

        income_tax = calculate_income_tax(gross_income)
        ni = calculate_ni(gross_income)
        student_loan_payment, student_loan_debt = calculate_student_loan(
            gross_income, student_loan_debt, current_year, years_since_graduation
        )
        unearned_tax = calculate_unearned_income_tax(
            inputs.dividends_per_year, inputs.savings_interest_per_year, inputs.property_income_per_year, gross_income
        )

        baseline_net = (gross_income - income_tax - ni - student_loan_payment - unearned_tax
                       - inputs.rail_spending_per_year - inputs.petrol_spending_per_year)

        # Rail fare freeze (2026 only)
        impact_rail_freeze = calculate_rail_impact(inputs.rail_spending_per_year, current_year)

        # Fuel duty reform
        # Note: current_year is calendar year, fiscal year starts April so FY = calendar year for most of year
        fiscal_year = current_year
        impact_fuel_freeze = calculate_fuel_duty_impact(inputs.petrol_spending_per_year, fiscal_year)

        # Threshold freeze extension
        if current_year < 2028:
            impact_threshold_freeze = 0
        else:
            baseline_cpi = get_cumulative_inflation(2028, current_year, use_rpi=False)
            baseline_pa = PERSONAL_ALLOWANCE * baseline_cpi
            baseline_basic = BASIC_RATE_THRESHOLD * baseline_cpi
            baseline_taper = PA_TAPER_THRESHOLD * baseline_cpi

            if current_year < 2030:
                reform_pa = PERSONAL_ALLOWANCE
                reform_basic = BASIC_RATE_THRESHOLD
                reform_taper = PA_TAPER_THRESHOLD
            else:
                reform_cpi = get_cumulative_inflation(2030, current_year, use_rpi=False)
                reform_pa = PERSONAL_ALLOWANCE * reform_cpi
                reform_basic = BASIC_RATE_THRESHOLD * reform_cpi
                reform_taper = PA_TAPER_THRESHOLD * reform_cpi

            if gross_income > baseline_taper:
                baseline_pa_adj = max(0, baseline_pa - (gross_income - baseline_taper) * PA_TAPER_RATE)
            else:
                baseline_pa_adj = baseline_pa
            taxable_baseline = max(0, gross_income - baseline_pa_adj)
            tax_baseline = 0
            if taxable_baseline > 0:
                basic_band = min(taxable_baseline, baseline_basic - baseline_pa)
                tax_baseline += basic_band * BASIC_RATE
                taxable_baseline -= basic_band
            if taxable_baseline > 0:
                tax_baseline += taxable_baseline * HIGHER_RATE

            if gross_income > reform_taper:
                reform_pa_adj = max(0, reform_pa - (gross_income - reform_taper) * PA_TAPER_RATE)
            else:
                reform_pa_adj = reform_pa
            taxable_reform = max(0, gross_income - reform_pa_adj)
            tax_reform = 0
            if taxable_reform > 0:
                basic_band = min(taxable_reform, reform_basic - reform_pa)
                tax_reform += basic_band * BASIC_RATE
                taxable_reform -= basic_band
            if taxable_reform > 0:
                tax_reform += taxable_reform * HIGHER_RATE

            impact_threshold_freeze = tax_baseline - tax_reform

        # Unearned income tax
        unearned_tax_increased = calculate_unearned_income_tax(
            inputs.dividends_per_year, inputs.savings_interest_per_year,
            inputs.property_income_per_year, gross_income, increased_tax=True
        )
        impact_unearned_tax = -(unearned_tax_increased - unearned_tax)

        # Salary sacrifice cap (only applies when working - no salary sacrifice in retirement)
        if is_retired:
            impact_salary_sacrifice_cap = 0
        else:
            impact_salary_sacrifice_cap = -calculate_salary_sacrifice_impact(inputs.salary_sacrifice_per_year, gross_income)

        # Student loan threshold freeze
        if current_year < 2027:
            impact_sl_freeze = 0
        elif student_loan_debt > 0:
            baseline_threshold = STUDENT_LOAN_THRESHOLD_PLAN2 * get_cumulative_inflation(2027, current_year, use_rpi=True)
            if current_year < 2030:
                reform_threshold = STUDENT_LOAN_THRESHOLD_PLAN2
            else:
                reform_threshold = STUDENT_LOAN_THRESHOLD_PLAN2 * get_cumulative_inflation(2030, current_year, use_rpi=True)
            repayment_baseline = max(0, (gross_income - baseline_threshold) * STUDENT_LOAN_RATE) if gross_income > baseline_threshold else 0
            repayment_reform = max(0, (gross_income - reform_threshold) * STUDENT_LOAN_RATE) if gross_income > reform_threshold else 0
            impact_sl_freeze = repayment_baseline - repayment_reform
        else:
            impact_sl_freeze = 0

        results.append({
            "age": age,
            "year": current_year,
            "gross_income": round(gross_income),
            "income_tax": round(income_tax),
            "national_insurance": round(ni),
            "student_loan_payment": round(student_loan_payment),
            "student_loan_debt_remaining": round(student_loan_debt),
            "num_children": num_children,
            "baseline_net_income": round(baseline_net),
            "impact_rail_fare_freeze": round(impact_rail_freeze),
            "impact_fuel_duty_freeze": round(impact_fuel_freeze),
            "impact_threshold_freeze": round(impact_threshold_freeze),
            "impact_unearned_income_tax": round(impact_unearned_tax),
            "impact_salary_sacrifice_cap": round(impact_salary_sacrifice_cap),
            "impact_sl_threshold_freeze": round(impact_sl_freeze),
        })

    return results


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/calculate")
def calculate(inputs: ModelInputs):
    results = run_model(inputs)
    return {"data": results}
