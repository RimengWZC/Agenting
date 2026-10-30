# Pilot design: not approved for launch

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
The sponsor-set pilot limit is **assumption: 3 months**.
Pre-register the first decision date, review schedule, early-stop rule, and required follow-up before launch.
Use a statistical method valid for repeated reviews and adaptive allocation.
Stop spending if cost or tracking limits fail. A promising sign-up result alone must not trigger full funding.
If evidence remains weak at the time limit, ask the sponsor about a revised study. Do not extend automatically.
Continue passive outcome tracking only under an approved plan and budget.

## Cost ceiling
The all-inclusive pilot ceiling is **assumption: $300,000**, set by the sponsor.
Reserve the full cost of promised incentives, including payments after the pilot ends.
The pilot is inside **assumption: $2,000,000** total funding.
The remaining maximum is **derived: $2,000,000 - $300,000 = $1,700,000**.
The actual cost is unknown. `pilot_costs.csv` records each missing component.

## Financial rule
The horizon is **assumption: 24 months**, set by the sponsor. The start date needs confirmation.
Compare treatment and control contribution over that horizon, including renewal after the annual contract expires.
Count each incentive and operating cost once. Reconcile discounts already deducted from revenue before subtracting campaign costs.
Estimate treatment contribution before campaign-funded incentives, then deduct the all-inclusive campaign budget once.
Subtract any additional costs outside that budget separately.
Ask finance to reconcile contribution profit with cash payback before approving spend.
