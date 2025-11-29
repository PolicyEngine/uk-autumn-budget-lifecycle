const { chromium } = require('playwright');

const PROD_API_URL = 'https://uk-autumn-budget-lifecycle-578039519715.europe-west1.run.app';
const FRONTEND_URL = 'https://uk-autumn-budget-lifecycle.vercel.app/';

// Default parameters matching the frontend sliders exactly
const DEFAULT_PARAMS = {
    current_age: 22,
    current_salary: 30000,
    retirement_age: 67,
    life_expectancy: 85,
    student_loan_debt: 45000,
    salary_sacrifice_per_year: 2000,
    rail_spending_per_year: 2000,
    petrol_spending_per_year: 500,
    dividends_per_year: 500,
    savings_interest_per_year: 500,
    property_income_per_year: 0
};

// Reforms to track
const REFORM_KEYS = [
    'impact_rail_fare_freeze',
    'impact_fuel_duty_freeze',
    'impact_threshold_freeze',
    'impact_unearned_income_tax',
    'impact_salary_sacrifice_cap',
    'impact_sl_threshold_freeze'
];

// CPI forecasts matching the frontend exactly
const CPI_FORECASTS = {2024: 0.0233, 2025: 0.0318, 2026: 0.0193, 2027: 0.0200, 2028: 0.0200, 2029: 0.0200};
const CPI_LONG_TERM = 0.0200;

// Calculate cumulative inflation matching the frontend's formula exactly
function getCumulativeInflation(targetYear) {
    if (targetYear <= 2025) return 1.0;
    let factor = 1.0;
    for (let y = 2025; y < targetYear; y++) {
        const rate = CPI_FORECASTS[y] || CPI_LONG_TERM;
        factor *= (1 + rate);
    }
    return factor;
}

// Calculate net lifetime impact from API data with real terms adjustment
function calculateNetImpactFromAPI(data, showRealTerms = true) {
    let total = 0;
    for (const row of data) {
        const deflator = showRealTerms ? getCumulativeInflation(row.year) : 1;
        for (const key of REFORM_KEYS) {
            const nominal = row[key] || 0;
            total += nominal / deflator;
        }
    }
    return total;
}

async function main() {
    console.log('=== Frontend/API Consistency Test ===\n');

    // Step 1: Set up browser with interceptor FIRST
    console.log('1. Setting up browser with API interception...');
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    let interceptedData = null;
    await page.route('**/calculate', async route => {
        const response = await route.fetch();
        const body = await response.json();
        interceptedData = body.data;
        await route.fulfill({ response, json: body });
    });

    // Step 2: Load frontend (interceptor captures the API call)
    console.log('2. Loading frontend...');
    await page.goto(FRONTEND_URL);
    await page.waitForTimeout(5000);

    console.log(`   Intercepted ${interceptedData?.length} rows from API`);
    console.log(`   First year rail fare freeze: ${interceptedData?.[0]?.impact_rail_fare_freeze}`);

    // Step 3: Calculate expected value from intercepted data
    console.log('\n3. Calculating expected net lifetime impact...');
    const expectedTotal = calculateNetImpactFromAPI(interceptedData, true);
    console.log(`   My calculation (real terms): ${expectedTotal >= 0 ? '+' : '-'}£${Math.abs(Math.round(expectedTotal)).toLocaleString()}`);

    // Step 4: Get the displayed value
    console.log('\n4. Reading displayed value from DOM...');
    const displayedValue = await page.$eval('.summary-item.highlighted .summary-value', el => el.textContent);
    const displayedNum = parseFloat(displayedValue.replace(/[£,+]/g, '').replace('−', '-'));
    console.log(`   DOM displays: ${displayedValue}`);

    // Step 5: Get the frontend's own calculation
    console.log('\n5. Getting frontend\'s internal calculation...');
    const frontendCalc = await page.evaluate(() => {
        const data = getDisplayData();
        const totals = {};
        reforms.forEach(r => totals[r.key] = d3.sum(data, d => d[r.key]));
        const netTotal = d3.sum(Object.values(totals));
        return {
            netTotal,
            currentDataLength: currentData.length,
            showRealTerms: showRealTerms,
            firstYearRail: currentData[0]?.impact_rail_fare_freeze
        };
    });
    console.log(`   Frontend calculates: ${frontendCalc.netTotal >= 0 ? '+' : '-'}£${Math.abs(Math.round(frontendCalc.netTotal)).toLocaleString()}`);
    console.log(`   showRealTerms: ${frontendCalc.showRealTerms}`);
    console.log(`   currentData first year rail: ${frontendCalc.firstYearRail}`);

    // Step 6: Compare
    console.log('\n=== COMPARISON ===');
    console.log(`Intercepted API data (year 2026 rail): ${interceptedData?.[0]?.impact_rail_fare_freeze}`);
    console.log(`Frontend currentData (year 2026 rail): ${frontendCalc.firstYearRail}`);
    console.log('');
    console.log(`My calculation from intercepted data: ${expectedTotal >= 0 ? '+' : '-'}£${Math.abs(Math.round(expectedTotal)).toLocaleString()}`);
    console.log(`Frontend's internal calculation:      ${frontendCalc.netTotal >= 0 ? '+' : '-'}£${Math.abs(Math.round(frontendCalc.netTotal)).toLocaleString()}`);
    console.log(`DOM displayed value:                  ${displayedValue}`);

    const myVsDOM = Math.abs(Math.round(expectedTotal) - displayedNum);
    const frontendVsDOM = Math.abs(Math.round(frontendCalc.netTotal) - displayedNum);

    console.log('');
    if (myVsDOM === 0 && frontendVsDOM === 0) {
        console.log('✅ PASS: All values match!');
    } else {
        console.log(`❌ FAIL:`);
        if (myVsDOM !== 0) {
            console.log(`   My calculation differs from DOM by £${myVsDOM}`);
        }
        if (frontendVsDOM !== 0) {
            console.log(`   Frontend calculation differs from DOM by £${frontendVsDOM}`);
        }
        if (interceptedData?.[0]?.impact_rail_fare_freeze !== frontendCalc.firstYearRail) {
            console.log(`   API data doesn't match currentData!`);
        }
    }

    await browser.close();
}

main().catch(console.error);
