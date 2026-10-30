# Brief: $2M month-to-month contract campaign

## Decision
Decide whether to fund a campaign that moves month-to-month customers to one-year contracts.

The full budget is $2,000,000, including the pilot. The pilot may spend at most $300,000, including all incentives, delivery, operations, and measurement.

Approve full funding only if projected 24-month incremental contribution profit reaches at least $2,400,000 before the $2,000,000 campaign budget. This leaves at least $400,000 after that budget. These amounts and the 24-month horizon are decision assumptions set by the sponsor.

Start with a randomized pilot. Run it for at most three months, or stop earlier under an approved early-decision rule. The pilot can support a forecast; it cannot directly observe 24 months of profit.

## Questions to answer
1. Which month-to-month customers can receive an offer?
2. Which feasible offers increase one-year contract sign-ups compared with no offer?
3. Does each offer reduce churn and increase contribution profit after its discount and service costs?
4. How many customers would switch without an offer?
5. Which offer, if any, can meet the 24-month profit threshold at full scale?
6. How sensitive is the decision to conversion, churn, margin, renewal, and cost assumptions?

## Data checks before modeling
- Profile the raw file as required by `CLAUDE.md`. Keep `data/raw/` unchanged.
- Check one record and one consistent `Churn` label per `customerID`. Request dated source records for conflicts.
- Check blanks, invalid values, extreme charges, date coverage, and contract definitions.
- Check whether `RetentionOfferAccepted` or other fields reveal `Churn` after the outcome.
- Obtain customer-level monthly revenue, contribution costs, contract changes, churn dates, and prior offers.
- Obtain offer costs, contact costs, delivery costs, eligibility rules, and other campaign exposure.
- Confirm that customers can be assigned at random and tracked for 24 months.
- Record every approved data change or excluded row in `cleaning_log.md`.

## Analysis plan
1. Define eligibility, outcomes, observation windows, and the no-offer comparison group before launch.
2. Estimate pilot size and precision. Do not launch if the pilot cannot answer the funding question.
3. Have the analysis team propose feasible offer arms and their full costs. Obtain sponsor approval before launch.
4. Randomly assign eligible customers. Keep a no-offer control group throughout the pilot.
5. Consider adaptive allocation among offer arms only when a useful outcome arrives soon enough.
6. Log each assignment, offer, contact, response, cost, time, and assignment probability.
7. Predefine checks and an early-stop rule that remains valid after repeated reviews.
8. Estimate each offer's incremental conversion, churn, and contribution profit against control.
9. Forecast 24-month results for the full eligible population. Include customers who would switch without an offer.
10. Show low, mid, and high forecasts. State every assumption and the break-even conversion or margin.
11. Recommend `fund`, `do_not_fund`, or `test_first` against the stated profit threshold.

Adaptive assignment can make ordinary comparisons unreliable when assignment probabilities or outcomes vary over time. Use a method designed for adaptive data, or use fixed random assignment.

## Stop and ask the sponsor
- Pause before any pilot spend if customer contribution profit or complete offer costs remain unavailable.
- Pause if conflicting customer records cannot be resolved or safely excluded under an approved rule.
- Ask for approval of eligibility, offer arms, the randomization design, and the early-stop rule before launch.
- Pause if the $300,000 pilot cap may be exceeded or tracking fails.
- Ask before changing the 24-month profit threshold, budget, outcome, or analysis plan.
- At three months, or at a valid early decision point, ask for the full-funding decision.
- If evidence cannot support a 24-month forecast, recommend `test_first` and state what is missing.

## Deliver
Write all analysis outputs to `runs/telco/`, as required by `CLAUDE.md`.

- `recommendation.md`: decision, evidence, 24-month low/mid/high profit, uncertainty, risks, and next step.
- Charts as PNG files, embedded in `recommendation.md`.
- `cleaning_log.md`: every change or exclusion and its reason.
- `findings.json`: the required format from `CLAUDE.md`.
- Reproducible code and a run command for all reported numbers.
- A pilot design and cost table before launch; a pilot results table after observation.

## Method notes
Adaptive experiments need recorded assignment probabilities for sound comparison. Delayed outcomes make both learning and inference harder.

- [Confidence intervals for policy evaluation in adaptive experiments](https://pmc.ncbi.nlm.nih.gov/articles/PMC8054003/)
- [Statistical inference on multi-armed bandits with delayed feedback](https://proceedings.mlr.press/v202/shi23g.html)
