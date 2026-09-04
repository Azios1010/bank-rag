# Credit Approval & Exception Policy

**Document metadata**

- `source_id`: `synthetic-credit-approval-v1`
- `version_id`: `synthetic-credit-approval-v1.2026-09-01`
- `namespace`: `UNDERWRITING_POLICY`
- `synthetic`: `true`
- `issuer`: Ngân hàng Thương mại Cổ phần Hồng Hà (HHB), a fictional internal organization
- `effective_date`: `2026-09-01`
- `document_version`: `1.0`

## 1. Status and exposure calculation

This is a complete synthetic internal approval policy of Ngân hàng Thương mại Cổ phần Hồng Hà (HHB), a fictional internal organization. `synthetic=true`: its values are not Vietnamese law, are not universal banking requirements, and apply only to fictional HHB internal decisions.

Rule ID: APR-EXPOSURE. Total exposure equals the proposed facility plus existing HHB funded and committed credit obligations plus applicable guarantees and contingent obligations included by HHB policy. The product cap and all approval tiers use this total exposure, not only the new draw. Amounts above VND 5 billion are outside the SME unsecured working-capital product.

## 2. Approval authority

Rule ID: APR-TIER-1. Tier 1 Credit Officer may approve total exposure greater than VND 0 and up to VND 1 billion only for Grade A/B, all-standard, no-exception cases.

Rule ID: APR-TIER-2. Tier 2 Branch Credit Committee may approve total exposure above VND 1 billion and up to VND 3 billion only for Grade A/B, all-standard, no-exception cases. Independent Risk review is required.

Rule ID: APR-TIER-3. Tier 3 Head Office Credit Committee may approve total exposure above VND 3 billion and up to VND 5 billion for Grade A/B, all-standard cases. It may also approve a single-exception Grade C case with total exposure up to VND 3 billion, subject to underwriting, Risk, LegalCompliance, and recorded rationale.

Rule ID: APR-TIER-4. Tier 4 Credit Committee/UBTD may approve a single-exception Grade C case with total exposure above VND 3 billion and up to VND 5 billion. It may approve a Grade C-EXCEPTION-2 case only when exactly two soft exceptions apply, every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded.

## 3. Maker, checker, challenge, and exceptions

Rule ID: APR-MAKER-CHECKER. The RM or business unit prepares the request as maker. Credit Underwriting checks analysis. Risk independently challenges material risk. The approver is separate from the maker. Product documentation and underwriting rationale must be complete before approval.

Rule ID: APR-EXCEPTIONS. A Grade C case has exactly one soft exception and enumerates every deviated rule, evidence, root cause, mitigant, and residual risk. Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded. Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3. More than two soft exceptions are not permitted. No exception may be hidden through a grade override, and no grade or tier may override a hard stop.

Rule ID: APR-HARD-STOPS. No grade or tier may override missing KYC or authority evidence, fraud or intentional misstatement, excluded industry or purpose, active CIC Group 3 or higher, DSCR < 1.15, Debt-to-Equity > 4.00x, Current Ratio < 0.80x, operating history below 18 months, revenue below VND 8 billion, or unsupported recurring negative cash flow. Collateral cannot substitute for a hard stop because the product is collateral-free under [[PROD-COLLATERAL]].

## 4. Approval controls, expiry, and re-approval

Rule ID: APR-OVERRIDES. A standard Grade A/B approval route applies only when all standard requirements in [[UW-GRADES]] pass. An independent review may correct an incorrectly evidenced grade, but may not disguise an exception or override a hard stop.

Rule ID: APR-VALIDITY. A standard approval expires after 60 calendar days if undisbursed. An exception approval expires after 30 calendar days. Expired requests require re-approval.

Rule ID: APR-REAPPROVAL. Re-approval is required when requested amount or total exposure rises by more than 10%; purpose or tenor changes; ownership or control changes; a new overdue or CIC adverse event occurs; DSCR falls by more than 10%; a material financial restatement occurs; or approval expires. Renewal under [[PROD-RENEWAL]] is a new review and follows this rule.
