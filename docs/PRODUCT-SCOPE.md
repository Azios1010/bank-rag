# Product scope: SME unsecured working-capital pre-screening

## Objective

Help a credit officer decide whether an SME loan application is complete and
ready for manual underwriting. The product extracts facts from submitted
documents, checks explicit eligibility rules, calculates transparent financial
metrics, and links every material conclusion to evidence.

## In scope for the first release

- One borrower segment: registered SMEs and corporate borrowers.
- One facility purpose: short-term working capital for lawful business
  operations.
- Unsecured facilities only. Collateral appraisal is not a decision input in
  this slice.
- A configurable product profile containing currency, amount, tenor and
  internal risk thresholds.
- Document completeness, identity consistency, purpose screening, repayment
  capacity and related-party/exception flags.
- RAG retrieval from versioned public regulations and explicitly labelled
  product-policy documents.
- Hybrid full-text/vector retrieval with reranking and typed evidence packs.
- A human review screen with evidence, calculation inputs, citations, missing
  documents and reviewer feedback.

## Explicit non-goals

- Automatic approval, rejection, pricing, limit setting or disbursement.
- A claim that a public regulation provides a universal DSCR, DTI or risk
  appetite threshold. Such thresholds are product-policy configuration and
  must be supplied by the deploying bank.
- Live CIC, sanctions, tax, registry or core-banking integrations in the public
  demo.
- Training on real customer data, storing customer PII in shared vector
  memory, or exposing case documents in a public corpus.
- OCR quality benchmarking, fraud adjudication and contract generation.
- Full GraphRAG and HyDE enabled by default. These require evaluation evidence
  before entering scope.

## Intended outcomes

The system returns exactly one pre-screening outcome (see
[decision states](DECISION-STATES.md)) and a structured package containing:

- facts and normalized values with source locations;
- calculations with formula, units and input evidence;
- policy findings with source version and citation;
- missing or conflicting information;
- reviewer challenges and unresolved risks;
- an explicit recommendation for the next human action.
