# Underwriting rules

Rules are split into two classes so that a demo threshold cannot be mistaken
for a statutory requirement.

## Regulatory hard gates

These are evidence-backed checks derived from the applicable law/regulation:

- borrower and purpose information is present and internally consistent;
- the declared purpose is lawful and not on the configured excluded-purpose
  list;
- the case contains the records required by the selected product profile;
- data processing has an appropriate consent/legal basis.

The legal source and effective version must be attached to each hard-gate
finding.

## Product-policy checks (configurable)

The deploying institution supplies these values. The repository may ship a
synthetic profile for tests, for example:

```yaml
currency: VND
max_amount: 5000000000
max_tenor_months: 12
minimum_dscr: 1.20
maximum_debt_to_equity: 3.50
```

These numbers are illustrative only. They are not universal Vietnamese
banking rules and must not be used for a real credit decision.

## Calculation contract

- `DSCR = cash available for debt service / scheduled debt service`
- `DebtToEquity = total interest-bearing debt / shareholders' equity`
- `CurrentRatio = current assets / current liabilities`

Each numerator and denominator must reference fact IDs, period, currency and
normalization steps. Division by zero, mixed periods or mixed currencies
produce `REFER_TO_CREDIT_OFFICER`.
