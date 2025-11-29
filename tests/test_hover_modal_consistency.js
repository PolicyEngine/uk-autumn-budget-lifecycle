const { chromium } = require('playwright');

// Change to 'http://localhost:8080/index.html' to test local, or keep production URL
const FRONTEND_URL = process.env.LOCAL_TEST ? 'http://localhost:8080/index.html' : 'https://uk-autumn-budget-lifecycle.vercel.app/';

async function main() {
    console.log('=== Hover vs Modal Consistency Test ===\n');
    console.log('Testing age 85 (year 2088) - threshold freeze values\n');

    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    // Intercept API to get the raw data
    let apiData = null;
    await page.route('**/calculate', async route => {
        const response = await route.fetch();
        const body = await response.json();
        apiData = body.data;
        await route.fulfill({ response, json: body });
    });

    await page.goto(FRONTEND_URL);
    await page.waitForTimeout(5000);

    // Find the row for age 85 (year 2088)
    const age85Row = apiData.find(d => d.age === 85);
    console.log('=== RAW API DATA for Age 85 ===');
    console.log(`Year: ${age85Row.year}`);
    console.log(`gross_income: ${age85Row.gross_income}`);
    console.log(`impact_threshold_freeze (API): ${age85Row.impact_threshold_freeze}`);
    console.log(`baseline_pa: ${age85Row.baseline_pa}`);
    console.log(`reform_pa: ${age85Row.reform_pa}`);
    console.log(`baseline_basic_threshold: ${age85Row.baseline_basic_threshold}`);
    console.log(`reform_basic_threshold: ${age85Row.reform_basic_threshold}`);
    console.log(`baseline_additional_threshold: ${age85Row.baseline_additional_threshold}`);
    console.log(`reform_additional_threshold: ${age85Row.reform_additional_threshold}`);
    console.log('');

    // Get what the hover tooltip shows (from getDisplayData)
    const hoverData = await page.evaluate(() => {
        const data = getDisplayData();
        const row = data.find(d => d.age === 85);
        return {
            impact_threshold_freeze: row.impact_threshold_freeze,
            gross_income: row.gross_income,
            showRealTerms: showRealTerms
        };
    });
    console.log('=== HOVER TOOLTIP DATA (getDisplayData - deflated) ===');
    console.log(`impact_threshold_freeze: £${hoverData.impact_threshold_freeze.toFixed(2)}`);
    console.log(`gross_income: £${hoverData.gross_income.toFixed(2)}`);
    console.log(`showRealTerms: ${hoverData.showRealTerms}`);
    console.log('');

    // Get what the modal calculates using the EXACT same logic as the frontend
    const modalCalc = await page.evaluate(() => {
        const row = currentData.find(d => d.age === 85);
        const income = row.gross_income;
        const year = row.year;

        // This is EXACTLY how the modal calculates tax bands (from renderTaxDetailChart)
        const calcEffectivePA = (pa, taperThreshold) => {
            if (income > taperThreshold) {
                const reduction = Math.min(pa, (income - taperThreshold) * 0.5);
                return Math.max(0, pa - reduction);
            }
            return pa;
        };

        const baselineEffectivePA = calcEffectivePA(row.baseline_pa, row.baseline_taper_threshold);
        const reformEffectivePA = calcEffectivePA(row.reform_pa, row.reform_taper_threshold);

        // Note: The basic rate band width is (basicThreshold - nominalPA), NOT (basicThreshold - effectivePA)
        // This matches how HMRC calculates tax: the band sizes are fixed, only taxable income changes
        const calcBands = (effectivePA, nominalPA, basicThreshold, additionalThreshold) => {
            let remaining = income;
            const taxFree = Math.min(remaining, effectivePA);
            remaining -= taxFree;
            const basicBand = Math.max(0, Math.min(remaining, basicThreshold - nominalPA));
            remaining -= basicBand;
            const higherBand = Math.max(0, Math.min(remaining, additionalThreshold - basicThreshold));
            remaining -= higherBand;
            const additionalBand = Math.max(0, remaining);
            const tax = basicBand * 0.20 + higherBand * 0.40 + additionalBand * 0.45;
            return { taxFree, basicBand, higherBand, additionalBand, tax };
        };

        const baselineBands = calcBands(baselineEffectivePA, row.baseline_pa, row.baseline_basic_threshold, row.baseline_additional_threshold);
        const reformBands = calcBands(reformEffectivePA, row.reform_pa, row.reform_basic_threshold, row.reform_additional_threshold);

        // Tax difference (baseline - reform, positive = you SAVE money, matching API convention)
        const taxDiffNominal = baselineBands.tax - reformBands.tax;

        // Apply real terms if toggle is on
        const deflator = getCumulativeInflation(year);
        const taxDiffReal = taxDiffNominal / deflator;

        return {
            income: income,
            year: year,
            baseline_pa: row.baseline_pa,
            reform_pa: row.reform_pa,
            baseline_basic_threshold: row.baseline_basic_threshold,
            reform_basic_threshold: row.reform_basic_threshold,
            baselineEffectivePA: baselineEffectivePA,
            reformEffectivePA: reformEffectivePA,
            baselineTax: baselineBands.tax,
            reformTax: reformBands.tax,
            taxDiffNominal: taxDiffNominal,
            taxDiffReal: taxDiffReal,
            deflator: deflator,
            showRealTerms: showRealTerms
        };
    });

    console.log('=== MODAL TAX CALCULATION (replicating frontend logic) ===');
    console.log(`income (nominal): £${modalCalc.income.toFixed(2)}`);
    console.log(`year: ${modalCalc.year}`);
    console.log(`baseline_pa: £${modalCalc.baseline_pa.toFixed(2)}`);
    console.log(`reform_pa: £${modalCalc.reform_pa.toFixed(2)}`);
    console.log(`baseline_effective_PA (after taper): £${modalCalc.baselineEffectivePA.toFixed(2)}`);
    console.log(`reform_effective_PA (after taper): £${modalCalc.reformEffectivePA.toFixed(2)}`);
    console.log(`baseline_tax: £${modalCalc.baselineTax.toFixed(2)}`);
    console.log(`reform_tax: £${modalCalc.reformTax.toFixed(2)}`);
    console.log(`tax_diff (nominal): £${modalCalc.taxDiffNominal.toFixed(2)}`);
    console.log(`tax_diff (real 2025 £): £${modalCalc.taxDiffReal.toFixed(2)}`);
    console.log(`deflator: ${modalCalc.deflator.toFixed(4)}`);
    console.log('');

    // Calculate what API says in real terms
    const apiImpactReal = age85Row.impact_threshold_freeze / modalCalc.deflator;

    console.log('=== COMPARISON ===');
    console.log(`API "impact_threshold_freeze" (nominal): £${age85Row.impact_threshold_freeze}`);
    console.log(`API "impact_threshold_freeze" (real):    £${apiImpactReal.toFixed(2)}`);
    console.log(`Hover tooltip shows:                     £${hoverData.impact_threshold_freeze.toFixed(0)} (from API, deflated)`);
    console.log('');
    console.log(`Modal calculates tax diff (nominal):     £${modalCalc.taxDiffNominal.toFixed(0)}`);
    console.log(`Modal calculates tax diff (real):        £${modalCalc.taxDiffReal.toFixed(0)}`);
    console.log('');

    const hoverRounded = Math.round(hoverData.impact_threshold_freeze);
    const apiRealRounded = Math.round(apiImpactReal);
    const modalNominalRounded = Math.round(modalCalc.taxDiffNominal);
    const modalRealRounded = Math.round(modalCalc.taxDiffReal);

    console.log('=== DIAGNOSIS ===');
    if (hoverRounded !== modalRealRounded) {
        console.log(`❌ FAIL: Hover (£${hoverRounded}) != Modal (£${modalRealRounded})`);
        console.log('');
        console.log('The hover tooltip shows the API\'s pre-calculated impact_threshold_freeze.');
        console.log('The modal recalculates tax using the threshold parameters.');
        console.log('');
        console.log('Possible causes:');
        console.log('1. API calculates impact differently than frontend');
        console.log('2. Frontend modal uses different thresholds than API');
        console.log('3. Tax calculation formula differs');
        console.log('');
        console.log(`Difference: £${Math.abs(hoverRounded - modalRealRounded)}`);

        // Extra check: is the modal showing nominal when it should show real?
        if (Math.abs(hoverRounded - modalNominalRounded) < Math.abs(hoverRounded - modalRealRounded)) {
            console.log('');
            console.log('HINT: Modal nominal value is CLOSER to hover value!');
            console.log(`Modal nominal (£${modalNominalRounded}) vs Hover (£${hoverRounded})`);
            console.log('This suggests the modal may not be applying real-terms conversion correctly.');
        }
    } else {
        console.log('✅ PASS: Hover and modal values match!');
    }

    await browser.close();
}

main().catch(console.error);
