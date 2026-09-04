# SME Credit Underwriting Policy

**Document metadata**

- `source_id`: `synthetic-sme-underwriting-v1`
- `version_id`: `synthetic-sme-underwriting-v1.2026-09-01`
- `namespace`: `UNDERWRITING_POLICY`
- `synthetic`: `true`
- `issuer`: Ngân hàng Thương mại Cổ phần Hồng Hà (HHB), a fictional internal organization
- `effective_date`: `2026-09-01`
- `document_version`: `1.0`

## 1. Status and underwriting outcome

This is a complete synthetic internal underwriting policy of Ngân hàng Thương mại Cổ phần Hồng Hà (HHB), a fictional internal organization. `synthetic=true`: its values are not Vietnamese law, are not universal banking requirements, and apply only to this fictional HHB product.

Rule ID: UW-STATUS. Underwriting verifies the product target, identity, ownership, management, industry, purpose, evidence, repayment capacity, and cash-flow fit before recommending an internal grade and approval route.

## 2. Identity, management, and industry assessment

Rule ID: UW-IDENTITY-AND-INDUSTRY. Verify registration, authority, transparent ownership, management continuity, business start date, industry, purpose, and the evidence listed in [[PROD-DOCUMENTS]]. Assess management experience, customer and supplier concentration, industry outlook, and dependence on a single counterparty. An excluded industry or purpose is a hard stop; a material unmitigated management, industry, or concentration weakness prevents standard approval and may result in Grade C or D.

Rule ID: UW-CIC-AND-DEBT. Obtain and date CIC evidence, identify overdue obligations, and reconcile all existing and proposed interest-bearing debt with the debt schedule. Active CIC Group 3 or higher is a hard decline. A resolved Group 2 within 24 months may be one soft exception only when current obligations are clean and [[APR-EXCEPTIONS]] approves it.

## 3. Repayment capacity and financial analysis

Rule ID: UW-REPAYMENT-CAPACITY. Assess repayment from supportable operating cash flow without collateral support. Include all scheduled debt service, including the proposed facility, in DSCR. Use a documented cash-flow bridge and preserve numerator and denominator evidence.

Rule ID: UW-CASH-FLOW. The latest available period must show positive normalized EBITDA and a supportable cash-flow bridge. A one-time net loss may be considered only with documented normalization. Unsupported or recurring negative cash flow is a hard decline; missing statements do not permit an inferred pass.

Rule ID: UW-DSCR. Standard DSCR is >= 1.30, calculated as cash available for debt service divided by scheduled debt service including the proposed facility. DSCR >= 1.15 and < 1.30 may be one soft exception. DSCR < 1.15 is a hard decline and no grade or approval authority may override it.

Rule ID: UW-LEVERAGE. Standard Debt-to-Equity is interest-bearing debt divided by shareholders' equity <= 3.00x, including existing and proposed interest-bearing debt. Debt-to-Equity > 3.00x and <= 4.00x may be one soft exception. Debt-to-Equity > 4.00x is a hard decline.

Rule ID: UW-LIQUIDITY. Standard Current Ratio is >= 1.00x, using current assets and current liabilities from the same reporting period and currency. A Current Ratio >= 0.80x and < 1.00x may be one soft exception with a documented working-capital-cycle explanation. A Current Ratio < 0.80x is a hard decline.

Rule ID: UW-REVENUE-TREND. Standard revenue trend is a decline <= 10% in the latest comparable period. A revenue decline > 10% and <= 20% may be one soft exception when causes and recovery evidence are documented. A decline > 20% is a hard decline for this product unless a new review establishes a different product fit.

## 4. Grades and exception rationale

Rule ID: UW-GRADES. Grade A means all standard metrics comfortably pass and CIC is clean. Grade B means all standard metrics pass at stated minimums. Grade C means exactly one soft exception and otherwise passes. Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded under [[APR-EXCEPTIONS]]. Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3. More than two soft exceptions are not permitted. Grade D or E means decline: D is below an exception floor or has a material unsupported weakness; E is fraud, identity, prohibited-purpose, or severe integrity/compliance concern. No grade or tier may override a hard stop, and approval cannot relabel a grade without documented independent review.

Rule ID: UW-SOFT-EXCEPTIONS. A soft exception may be: operating history of 18–23 months; annual revenue from VND 8 billion to less than VND 10 billion; DSCR >= 1.15 and < 1.30; Debt-to-Equity > 3.00x and <= 4.00x; Current Ratio >= 0.80x and < 1.00x; revenue decline > 10% and <= 20%; or resolved CIC Group 2 within 24 months. One such exception produces Grade C; exactly two produce Grade C-EXCEPTION-2 only on the Tier 4 route stated in [[APR-EXCEPTIONS]]. The report must identify every deviated rule, quantify it, explain root cause and mitigants, and cite supporting evidence for [[APR-EXCEPTIONS]].

Rule ID: UW-HARD-STOPS. Hard declines are active CIC Group 3 or higher; DSCR < 1.15; Debt-to-Equity > 4.00x; Current Ratio < 0.80x; operating history below 18 months; revenue below VND 8 billion; excluded industry or purpose; missing KYC or authority evidence; fraud or intentional misstatement; and unsupported recurring negative cash flow. These map to [[APR-HARD-STOPS]] and cannot be approved as exceptions by any grade or tier.
