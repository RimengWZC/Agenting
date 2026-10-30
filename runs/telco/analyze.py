#!/usr/bin/env python3
"""Read-only raw-data audit and gated campaign decision. Run from any directory.

Writes only the named analysis outputs beside this script. Never writes review.md.
No deduplication, imputation, outlier correction, model fit, or experiment is performed.
"""
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
SOURCE = ROOT / 'data/raw/telco_v2.csv'
EXPECTED_BLOB = 'e8c695784970d7d5605f85c377369e9a4a8c3724'
SOURCE_COMMIT = 'dc208b23c8f539fcdb209ff359a51ab768106e8e'


def table(headers, rows):
    def cell(v):
        return str(v).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def save_csv(name, headers, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def save_text(name, text):
    (OUT / name).write_text(text.rstrip() + '\n', encoding='utf-8')


def quantile(values, fraction):
    values = sorted(values)
    pos = (len(values) - 1) * fraction
    low = int(pos)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (pos - low)


def number(v):
    return f'{v:,.2f}'.rstrip('0').rstrip('.') if isinstance(v, float) else f'{v:,}'


def money(v):
    return f'${v:,.0f}'


def font(size):
    return ImageFont.load_default(size=size)


def bars(name, title, subtitle, labels, values, highlight, footnote):
    image = Image.new('RGB', (1400, 620), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.text((55, 38), title, fill='#14252f', font=font(36))
    draw.text((55, 94), subtitle, fill='#485a66', font=font(23))
    left, width = 420, 790
    maximum = max(values) or 1
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 185 + i * 105
        draw.text((55, y + 11), label, fill='#263945', font=font(25))
        draw.rectangle((left, y, left + max(1, int(width * value / maximum)), y + 54),
                       fill='#cf673e' if i in highlight else '#bbc4c9')
        x = left + int(width * value / maximum) + 15
        draw.text((x, y + 10), f'{value:,}', fill='#14252f', font=font(26))
    draw.text((55, 552), footnote, fill='#485a66', font=font(20))
    image.save(OUT / name)


def main():
    raw = SOURCE.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if blob != EXPECTED_BLOB:
        raise SystemExit('Raw file differs from the audited snapshot. Re-scope the analysis before rerunning.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
    rows = list(reader)
    columns = reader.fieldnames
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise SystemExit('Malformed CSV rows. Inspect the source before analysis.')
    n = len(rows)
    groups = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        groups[row['customerID']].append((line, row))
    unique = len(groups)
    duplicates = {key: items for key, items in groups.items() if len(items) > 1}
    conflicts = {key: items for key, items in groups.items()
                 if len({r['Churn'] for _, r in items}) > 1}
    conflict_rows = sum(map(len, conflicts.values()))
    exact_extra = n - len({tuple(r[c] for c in columns) for r in rows})
    other_conflicts = {c: sum(len({r[c] for _, r in items}) > 1 for items in groups.values())
                       for c in columns if c != 'customerID'}
    all_labels = Counter(r['Churn'] for r in rows)
    profile = []
    for c in columns:
        values = [r[c] for r in rows]
        observed = [v for v in values if v.strip()]
        numeric = bool(observed) and all(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', v.strip()) for v in observed)
        parsed = list(map(float, observed)) if numeric else []
        dtype = ('integer' if all(v.is_integer() for v in parsed) else 'decimal') if numeric else 'text'
        profile.append(dict(column=c, inferred_type=dtype, blanks=n-len(observed),
                            empty_strings=sum(v == '' for v in values),
                            whitespace_only=sum(v != '' and not v.strip() for v in values),
                            unique_raw_values=len(set(values)), minimum=min(parsed) if numeric else '',
                            maximum=max(parsed) if numeric else ''))
    charges = [float(r['MonthlyCharges']) for r in rows]
    q1, q3 = quantile(charges, .25), quantile(charges, .75)
    multiplier = 3
    fence = q3 + multiplier * (q3-q1)
    extremes = [(line, r) for line, r in enumerate(rows, 2) if float(r['MonthlyCharges']) > fence]
    missing_total = [(line, r) for line, r in enumerate(rows, 2) if not r['TotalCharges'].strip()]
    missing_offer = [(line, r) for line, r in enumerate(rows, 2) if not r['RetentionOfferAccepted'].strip()]
    offer_counts = Counter((r['RetentionOfferAccepted'] or '[blank]', r['Churn']) for r in rows)
    leakage_match = sum((bool(r['RetentionOfferAccepted'].strip())) == (r['Churn'] == 'Yes') for r in rows)
    internet_fields = ['OnlineSecurity','OnlineBackup','DeviceProtection','TechSupport','StreamingTV','StreamingMovies']
    validation = [
        ['Blank customer IDs', sum(not r['customerID'].strip() for r in rows)],
        ['Churn outside Yes / No', sum(r['Churn'] not in {'Yes','No'} for r in rows)],
        ['SeniorCitizen outside binary categories', sum(r['SeniorCitizen'] not in {'0','1'} for r in rows)],
        ['Contract outside observed term vocabulary', sum(r['Contract'] not in {'Month-to-month','One year','Two year'} for r in rows)],
        ['Negative tenure or charges', sum(any(float(r[c]) < 0 for c in ['tenure','MonthlyCharges','TotalCharges'] if r[c].strip()) for r in rows)],
        ['Phone status inconsistent with multiple-line status', sum((r['MultipleLines']=='No phone service') != (r['PhoneService']=='No') for r in rows)],
        ['Internet status inconsistent with add-on status', sum(any((r[c]=='No internet service') != (r['InternetService']=='No') for c in internet_fields) for r in rows)]]
    contracts = []
    for contract in sorted({r['Contract'] for r in rows}):
        selected = [r for r in rows if r['Contract'] == contract]
        ids = {r['customerID'] for r in selected}
        statuses = Counter('conflict' if key in conflicts else groups[key][0][1]['Churn'] for key in ids)
        contracts.append(dict(contract=contract, raw_rows=len(selected), unique_ids=len(ids),
                              conflict_ids=statuses['conflict'], yes_only_ids=statuses['Yes'], no_only_ids=statuses['No']))
    brief = (ROOT / 'briefs/2m-campaign.md').read_text()
    def amount(pattern):
        return int(re.search(pattern, brief).group(1).replace(',', ''))
    budget = amount(r'full budget is \$([\d,]+)')
    pilot_cap = amount(r'pilot may spend at most \$([\d,]+)')
    target = amount(r'reaches at least \$([\d,]+)')
    horizon = int(re.search(r'projected (\d+)-month', brief).group(1))
    word_numbers = {'three': 3}
    pilot_months = word_numbers[re.search(r'at most (\w+) months', brief).group(1)]
    surplus = target-budget
    buffer = surplus/budget
    mtm = next(x for x in contracts if x['contract'] == 'Month-to-month')
    stats = dict(raw_rows=n, unique_ids=unique, columns=len(columns), raw_bytes=len(raw),
                 duplicate_ids=len(duplicates), conflicting_ids=len(conflicts), conflict_rows=conflict_rows,
                 extra_id_rows=n-unique, exact_duplicate_extra_rows=exact_extra,
                 conflicted_id_share=len(conflicts)/unique, raw_label_counts=dict(all_labels),
                 blanks_total_charges=len(missing_total), blanks_offer=len(missing_offer),
                 missing_total_tenures=sorted({r['tenure'] for _, r in missing_total}),
                 monthly_charge_q1=q1, monthly_charge_q3=q3, extreme_multiplier=multiplier,
                 monthly_charge_fence=fence, monthly_extreme_rows=len(extremes),
                 monthly_extreme_ids=len({r['customerID'] for _, r in extremes}),
                 raw_monthly_min=min(charges), raw_monthly_max=max(charges),
                 offer_missingness_matches_churn=leakage_match, within_id_conflicts=other_conflicts,
                 contract_counts=contracts, budget=budget, pilot_cap=pilot_cap, horizon_months=horizon,
                 pilot_months=pilot_months, gross_target=target, net_target=surplus,
                 profit_buffer=buffer, remaining_budget=budget-pilot_cap,
                 raw_blob=blob, source_commit=SOURCE_COMMIT)
    stats['validation_checks'] = dict(validation)
    (OUT/'metrics.json').write_text(json.dumps(stats, indent=2)+'\n')
    save_csv('profile.csv', list(profile[0]), [list(p.values()) for p in profile])
    save_csv('contract_counts.csv', list(contracts[0]), [list(c.values()) for c in contracts])
    save_csv('validation_checks.csv', ['screen','flagged_rows_data'], validation)
    issue_rows = []
    for key, items in conflicts.items():
        for line, row in items:
            issue_rows.append([line, 'conflicting_customer_label', 'Churn', 'retained; needs dated source'])
    for issue, col, records in [('extreme_monthly_charge', 'MonthlyCharges', extremes),
                                ('blank_total_charge', 'TotalCharges', missing_total),
                                ('blank_offer', 'RetentionOfferAccepted', missing_offer)]:
        for line, row in records:
            issue_rows.append([line, issue, col, 'retained; flagged only'])
    save_csv('row_issues.csv', ['source_csv_line','issue','column','action'], issue_rows)
    issues = [
        dict(column='customerID / Churn', issue=f'{len(conflicts)} IDs have conflicting Churn labels; no dated resolution exists.',
             rows_affected=conflict_rows, action='Retain all rows. Pause customer churn rates and request a source resolution rule.'),
        dict(column='MonthlyCharges', issue='Extreme raw values above the documented quartile screening fence; correctness unknown.',
             rows_affected=len(extremes), action='Flag only. Request billing records and currency confirmation.'),
        dict(column='TotalCharges', issue='Whitespace-only blanks; associated tenure values are reported in metrics.json.',
             rows_affected=len(missing_total), action='Keep blanks. Do not replace them with zero.'),
        dict(column='RetentionOfferAccepted', issue='Missingness matches Churn exactly across all raw rows; availability timing is unknown.',
             rows_affected=n, action='Treat as a leakage risk. Do not use as a pre-outcome predictor or campaign response measure.'),
        dict(column='dates / margins / offer costs / trial assignment', issue='Required history and financial or experimental fields are absent.',
             rows_affected=n, action='Pause spending and financial forecasts. Request the missing inputs.')]
    (OUT/'findings.json').write_text(json.dumps(dict(recommendation='test_first',data_issues=issues,drivers=[]),indent=2)+'\n')
    forecast_rows = [['low','unknown','unknown','unknown','unknown','unknown'],
                     ['mid','unknown','unknown','unknown','unknown','unknown'],
                     ['high','unknown','unknown','unknown','unknown','unknown']]
    save_csv('forecast_scenarios.csv', ['case','eligible_customers','incremental_24m_contribution',
                                      'costs_outside_budget','net_profit','payback_month'], forecast_rows)
    costs = [['Incentives and discounts','unknown','Include all promised incentive costs; count each cost once.'],
             ['Delivery and contact','unknown','Obtain channel quotes.'],
             ['Operations and measurement','unknown','Obtain staffing and tracking costs.'],
             ['Total pilot cost','unknown',f'Must not exceed {pilot_cap}; sponsor-set cap.']]
    save_csv('pilot_costs.csv',['component','cost','basis'],costs)
    bars('customer_conflicts.png', 'Conflicting labels block customer churn rates',
         'Data: unique customer IDs; raw records are retained.',
         ['Consistent Churn label','Conflicting Churn labels'], [unique-len(conflicts),len(conflicts)], {1},
         f'Derived: {len(conflicts):,} / {unique:,} = {len(conflicts)/unique:.2%} of IDs have conflicting labels.')
    bars('offer_missingness.png', 'Offer missingness reveals the recorded churn label',
         'Data: raw rows. Field timing is unknown; do not use this as a predictor.',
         ['Blank offer, Churn No','Filled offer, Churn Yes','Other combinations'],
         [offer_counts[('[blank]','No')], sum(v for (o,c),v in offer_counts.items() if o!='[blank]' and c=='Yes'), n-leakage_match],
         {0,1}, 'Data: complete agreement in this file does not prove when the offer field was recorded.')
    save_text('cleaning_log.md', f'''# Cleaning log

No source rows were removed, changed, or imputed. No cleaned dataset was created.

| Measure | Value | Label |
| --- | --- | --- |
| Rows before inspection | {n:,} | data |
| Rows retained after inspection | {n:,} | data |
| Removed rows | {0:,} | data |
| Changed source cells | {0:,} | data |

CSV parsing and temporary numeric conversion supported diagnostics only. Blank checks include empty strings and whitespace-only cells.
The file's raw values remain intact. No conflicting label was selected or rejected.

`row_issues.csv` lists flagged source lines and issue types. It does not repeat customer IDs or raw values.
A source row can appear under several issues.
The derived fence is Q3 + {multiplier} x (Q3 - Q1) = {fence:.4f}.
The multiplier is an analyst-set screening assumption. It does not establish billing errors.

Raw Git blob: `{blob}`. The script checks this hash before and after analysis.
''')
    pilot = f'''# Pilot design: not approved for launch

## Decision and gates
Recommend `test_first`, with spending paused. Profit, costs, eligibility, and source-label resolution are unknown.
Request finance inputs and dated customer records before launch. Ask the sponsor to approve any conflict-resolution or exclusion rule.
Never select the first duplicate record or assign a conflicting customer to an outcome group.

## Proposed arms
The analysis team proposes these arms. Their terms require sponsor approval.

| Arm | Proposal | Amount | Status |
| --- | --- | --- | --- |
| Control | No campaign offer; continue usual service | Not applicable | Proposed |
| Convenience | Explain annual contract terms; offer no price discount | Unknown delivery cost | Proposed |
| Credit | Offer an annual contract with a one-time credit | Unknown credit amount | Proposed |

Do not claim these offers are feasible until operations confirms terms and finance confirms costs.
Do not treat every month-to-month record as an eligible active customer.
Confirm active status, contact permission, existing offers, and contract eligibility from current records.

## Assignment and measurement
Randomly assign each eligible customer once. Keep a no-offer control group throughout the pilot.
Start with fixed random assignment while checking tracking and response delays.
Consider a multi-armed bandit only after those checks. A bandit changes offer allocation as results arrive.
Keep control allocation fixed. Set minimum offer allocations before launch.
Log customer ID, assignment time, offer, assignment probability, contact, response, and every incurred or promised cost.
Analyze customers by their assigned arm, including customers who ignore the offer.
Record sign-ups, cancellations, churn, service costs, incentive costs, complaints, and contribution over time.
Contribution means revenue less the variable cost of providing service.

## Outcome and sample size
Financial success concerns incremental contribution versus control. Sign-ups alone do not establish profitable retention.
Baseline offer conversion, useful effect size, outcome variance, allocation shares, and follow-up loss are unknown.
Sample size and precision are therefore unknown. Request these inputs and simulate the proposed design before launch.
Ask the sponsor to approve the evidence threshold and the smallest worthwhile effect.

## Timing and stopping
The sponsor-set pilot limit is **assumption: {pilot_months} months**.
Pre-register the first decision date, review schedule, early-stop rule, and required follow-up before launch.
Use a statistical method valid for repeated reviews and adaptive allocation.
Stop spending if cost or tracking limits fail. A promising sign-up result alone must not trigger full funding.
If evidence remains weak at the time limit, ask the sponsor about a revised study. Do not extend automatically.
Continue passive outcome tracking only under an approved plan and budget.

## Cost ceiling
The all-inclusive pilot ceiling is **assumption: {money(pilot_cap)}**, set by the sponsor.
Reserve the full cost of promised incentives, including payments after the pilot ends.
The pilot is inside **assumption: {money(budget)}** total funding.
The remaining maximum is **derived: {money(budget)} - {money(pilot_cap)} = {money(budget-pilot_cap)}**.
The actual cost is unknown. `pilot_costs.csv` records each missing component.

## Financial rule
The horizon is **assumption: {horizon} months**, set by the sponsor. The start date needs confirmation.
Compare treatment and control contribution over that horizon, including renewal after the annual contract expires.
Count each incentive and operating cost once. Reconcile discounts already deducted from revenue before subtracting campaign costs.
Estimate treatment contribution before campaign-funded incentives, then deduct the all-inclusive campaign budget once.
Subtract any additional costs outside that budget separately.
Ask finance to reconcile contribution profit with cash payback before approving spend.
'''
    save_text('pilot_design.md', pilot)
    meanings = {
        'customerID':'Customer identifier; one customer per unique ID under CLAUDE.md.',
        'gender':'Recorded gender; meaning inferred from field name.',
        'SeniorCitizen':'Binary senior status; age rule is unknown.',
        'Partner':'Partner status; definition is not supplied.',
        'Dependents':'Dependent status; definition is not supplied.',
        'tenure':'Length of service; time unit is not documented in this repository.',
        'PhoneService':'Recorded phone service status.',
        'MultipleLines':'Recorded multiple-line phone service status.',
        'InternetService':'Recorded internet service category.',
        'OnlineSecurity':'Recorded online security service status.',
        'OnlineBackup':'Recorded backup service status.',
        'DeviceProtection':'Recorded device protection service status.',
        'TechSupport':'Recorded technical support service status.',
        'StreamingTV':'Recorded television streaming service status.',
        'StreamingMovies':'Recorded movie streaming service status.',
        'Contract':'Recorded contract term; start and renewal dates are unavailable.',
        'PaperlessBilling':'Recorded paperless billing status.',
        'PaymentMethod':'Recorded payment category.',
        'MonthlyCharges':'Recorded monthly charge; currency and billing validity need confirmation.',
        'TotalCharges':'Recorded cumulative charges; currency and coverage need confirmation.',
        'Churn':'Yes means left in the last month, per CLAUDE.md; reference month is unknown.',
        'LoyaltyAppUser':'Recorded app-use flag; definition and timing are unknown.',
        'RetentionOfferAccepted':'Recorded offer-response flag; offer terms and timing are unknown.'}
    dictionary = table(['Column','Meaning','Inferred type','Blanks (data)','Minimum (data)','Maximum (data)'],
                       [[p['column'],meanings[p['column']],p['inferred_type'],p['blanks'],
                         number(p['minimum']) if p['minimum']!='' else 'not applicable',
                         number(p['maximum']) if p['maximum']!='' else 'not applicable'] for p in profile])
    contract_table = table(['Contract','Raw rows (data)','Unique IDs (data)','Yes-only IDs (data)',
                            'No-only IDs (data)','Conflicting IDs (data)'],
                           [[c['contract'],c['raw_rows'],c['unique_ids'],c['yes_only_ids'],c['no_only_ids'],c['conflict_ids']] for c in contracts])
    offer_table = table(['Offer value','Churn No rows (data)','Churn Yes rows (data)'],
                        [[v,offer_counts[(v,'No')],offer_counts[(v,'Yes')]] for v in ['[blank]','No','Yes']])
    issue_table = table(['Issue','Affected rows (data)','Action'],
                        [[i['issue'],i['rows_affected'],i['action']] for i in issues])
    assumptions = table(['Input','Low','Mid','High','Label and owner'],[
        ['Full budget',money(budget),money(budget),money(budget),'assumption; sponsor ceiling'],
        ['Pilot ceiling',money(pilot_cap),money(pilot_cap),money(pilot_cap),'assumption; sponsor ceiling'],
        ['Profit horizon',f'{horizon} months',f'{horizon} months',f'{horizon} months','assumption; sponsor'],
        ['Pilot time limit',f'{pilot_months} months',f'{pilot_months} months',f'{pilot_months} months','assumption; sponsor'],
        ['Profit buffer',f'{buffer:.0%}',f'{buffer:.0%}',f'{buffer:.0%}','derived from sponsor target: (target - budget) / budget'],
        ['Eligible population','unknown','unknown','unknown','needed; operations'],
        ['Incremental contribution per customer','unknown','unknown','unknown','needed; randomized trial and finance'],
        ['Conversion without an offer','unknown','unknown','unknown','needed; randomized control'],
        ['Renewal and later churn','unknown','unknown','unknown','needed; dated history and trial follow-up'],
        ['Offer and operating costs','unknown','unknown','unknown','needed; finance and operations'],
        ['Additional costs outside budget','unknown','unknown','unknown','needed; finance'],
        ['Forecast horizon start','unknown','unknown','unknown','needed; sponsor'],
        ['Outlier multiplier',multiplier,multiplier,multiplier,'assumption; analyst diagnostic screen, not a correction rule']])
    forecasts = table(['Case','Pre-budget incremental profit','Net profit','Payback','Reason'],
                       [[case,'unknown','unknown','unknown','Missing margin, costs, eligible population, and causal response'] for case in ['Low','Mid','High']])
    report = f'''# Campaign funding recommendation

## Summary

**Recommendation: test_first. Pause spending until financial data and customer labels are resolved.**
The current file cannot establish whether the campaign meets the sponsor's profit threshold.
This recommendation does not authorize a pilot launch or full funding.

The source contains **data: {n:,} rows**, **data: {unique:,} customer IDs**, and **data: {len(columns)} columns**.
**Data: {len(conflicts):,} customer IDs** have conflicting churn labels across **data: {conflict_rows:,} rows**.
No dated records identify the correct labels. Customer churn rates and driver rankings remain unknown.

The month-to-month category contains **data: {mtm['unique_ids']:,} IDs**, including **data: {mtm['conflict_ids']:,} conflicted IDs**.
This count includes customers recorded as churned. It is not the current eligible campaign population.
The offer field also reveals the recorded churn label through its missingness.

Full funding is **assumption: {money(budget)}**, including **assumption: {money(pilot_cap)}** for the pilot, both set by the sponsor.
The sponsor requires **assumption: {money(target)}** before that budget over **assumption: {horizon} months**.
Required net profit is **derived: {money(target)} - {money(budget)} = {money(surplus)}**.
Low, mid, and high profit forecasts are all unknown. Margin, complete costs, and campaign response are unavailable.

There is strong evidence for the data limitations. Confidence in campaign profitability cannot be estimated from this file.
Next, request dated source records and finance inputs. Then approve offer terms and the trial design before spending.

## Charts

![Conflicting labels block customer churn rates](customer_conflicts.png)
Conflicting customer labels prevent a defensible customer churn rate under the repository rule.

![Offer missingness reveals the recorded churn label](offer_missingness.png)
The offer field's missingness matches the recorded churn label, so it presents a leakage risk.

## Appendix

### Source, scope, and method
Source: `data/raw/telco_v2.csv` at Git commit `{SOURCE_COMMIT}`.
Raw Git blob: `{blob}`. `analyze.py` verifies the raw file before and after inspection.
The data reference date, collection method, currency, and coverage are unknown.
Field meanings below are inferred from names unless attributed to `CLAUDE.md`.

Read the source as strings. Inspect numeric fields without changing source cells.
Check identifier consistency before any customer churn calculations. No customer churn model or driver ranking was fitted.
No experimental or campaign performance data exists in the supplied file.
The results are an audit and a decision-readiness assessment.

### Data dictionary and profile
Blank counts include empty strings and whitespace-only values. Numeric ranges exclude blanks only for range calculation.
Types describe parseable nonblank values. They are not an asserted business schema.

{dictionary}

### Customer label checks
Counts below preserve every raw record. No conflicting label was selected and no customer was excluded.
All contract values are consistent within each customer ID.

{contract_table}

The conflicting share is **derived: {len(conflicts):,} / {unique:,} = {len(conflicts)/unique:.2%}** of unique IDs.
There are **derived: {n:,} - {unique:,} = {n-unique:,}** extra ID rows.
There are **data: {exact_extra:,}** completely identical extra rows across all columns.
Churn and offer response both differ within every duplicated ID. Other fields agree within those IDs.
The dataset provides no date or source priority to resolve these differences.

Customer churn rates, overall drivers, and within-contract driver directions remain unknown pending an approved resolution rule.
`findings.json` therefore uses an empty drivers list. This does not mean that every variable has no association.

### Missingness and billing checks
The offer-response counts are raw-row diagnostics. They do not measure an offer's treatment effect.

{offer_table}

All **data: {len(missing_total):,}** blank total-charge rows have tenure **data: {', '.join(stats['missing_total_tenures'])}**.
These are whitespace values. Their true charge amounts are unknown.

Q1 and Q3 mark the lower and upper quartiles of sorted raw charges.
The charge screen uses **derived: Q1 = {q1:.4f}** and **derived: Q3 = {q3:.4f}** from all raw rows.
The upper fence is **derived: {q3:.4f} + {multiplier} x ({q3:.4f} - {q1:.4f}) = {fence:.4f}**.
The multiplier is **assumption: {multiplier}**, selected by the analyst for a conservative diagnostic screen.
**Data: {len(extremes):,} rows** exceed that fence. Their billing validity is unknown.
Do not divide charges, cap them, or use them as customer profit without source confirmation.

{issue_table}

These additional screens found the following counts. Category and service rules are analyst checks, pending business confirmation.
A clear screen does not establish overall data quality.

{table(['Screen','Flagged rows (data)'],validation)}

### Cleaning summary
Rows before inspection: **data: {n:,}**. Rows retained: **data: {n:,}**.
Removed rows: **data: {0:,}**. Changed source cells: **data: {0:,}**.
No cleaned dataset was produced. `cleaning_log.md` records this decision.
`row_issues.csv` identifies each flagged source line. Several flags can refer to the same row.

### Financial decision and sensitivity
Contribution means revenue less variable service costs. Monthly charges alone cannot establish this amount.
Let N be the eligible population and d be incremental contribution per assigned customer over the sponsor's horizon.
Measure d before campaign-funded incentives, against the no-offer counterfactual.
Let O be additional costs outside the campaign budget B.

- Pre-budget incremental profit = N x d - O.
- Net incremental profit = N x d - O - B.
- Break-even contribution per customer = (B + O) / N, when N is positive.
- Contribution required for the sponsor's buffer = (target + O) / N, when N is positive.

The target is **assumption: {money(target)}**. B is **assumption: {money(budget)}**. Both come from the sponsor.
The required buffer is **derived: ({money(target)} - {money(budget)}) / {money(budget)} = {buffer:.0%}**.
Count each incentive cost once. Add back campaign discounts already deducted from contribution before subtracting the all-inclusive budget.
Include the pilot in that budget. Do not add it again when evaluating full-campaign economics.
Confirm the horizon start, payment timing, and cash-payback reconciliation with finance.

{forecasts}

These unknown entries are not zero-profit estimates. No supported numerical opportunity range is available.
Vary eligible volume, response, margin, renewal, and costs together after their inputs are obtained.
Do not assume annual contracts produce the churn behavior observed among existing annual-contract customers.

### Assumptions and missing inputs
The scenario labels do not imply measured uncertainty bounds. Sponsor constants remain the same across scenarios.

{assumptions}

### Pilot proposal and costs
The analysis team proposes a no-offer control, a convenience message, and an annual-contract credit offer.
Credit amounts, feasibility, allocation shares, and sample size are unknown. Request sponsor approval before launch.
Randomize at customer level and analyze customers as assigned. Keep the no-offer control throughout the pilot.
Use a bandit only if outcome delays and logging permit sound comparisons.
Do not optimize contract sign-ups alone while claiming to optimize profit.
Record assignment probabilities and apply a method suitable for adaptive assignment and repeated reviews.
The pilot time cap is **assumption: {pilot_months} months**, set by the sponsor.
Early decisions require an approved rule. At the cap, ask the sponsor if the evidence remains inconclusive.
`pilot_design.md` contains the implementation questions and stopping gates.

{table(['Cost component','Amount','Basis'], costs)}

No pilot results were supplied. A pilot results table is therefore not available.
The expected results must include each arm's assigned count, response, contribution, costs, follow-up, and uncertainty.

### Required decisions before dependent work
- Request dated records or an approved rule for conflicting customer labels.
- Obtain customer contribution, complete costs, and current eligibility from finance and operations.
- Approve feasible offer terms, sample size, allocation, evidence thresholds, and stopping rules before launch.
- Pause spending while these inputs remain missing. Do not infer approval from this report.

### Reproduction
From the repository root, run:

```sh
python3 -m pip install -r runs/telco/requirements.txt
python3 runs/telco/analyze.py
```

The script creates the report, charts, profile, issue log, contract counts, scenarios, pilot plan, costs, and findings.
It does not write `review.md`. All source counts and displayed financial arithmetic come from this script.
Financial inputs are sponsor assumptions parsed from the brief. No external financial benchmarks were used.
'''
    save_text('recommendation.md',report)
    if SOURCE.read_bytes() != raw:
        raise RuntimeError('Source bytes changed during analysis.')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
