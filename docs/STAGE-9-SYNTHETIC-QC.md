# Stage 9 synthetic normalization and chunking QC

Status: complete for the three complete Stage 8 synthetic Markdown policies.

The reusable adapter in `backend/app/services/synthetic_policy_normalization_v2.py`
reads each manifest source in manifest order, applies the frozen NFC/BOM/line-ending
normalization and SHA-256 rule, and emits one closed-schema normalized provision per
complete `Rule ID` section. Markdown has no page locator, so `page_start` and
`page_end` are both `0`; `heading_path` contains the document title and inherited
numbered section. The adapter does not fold, trim, case-transform, or manufacture
retrieval boundaries. `PolicyChunkerV2` is used unchanged by
`backend/scripts/build_synthetic_policy_v2.py`.

## Artifacts and counts

| Artifact | Path | Count |
| --- | --- | ---: |
| Normalized provisions | `dataset/normalized/v2/policy-synthetic-provisions.jsonl` | 37 |
| Chunks | `dataset/chunks/v2/policy-synthetic-chunks.jsonl` | 37 |
| Chunk QC anomalies | `dataset/chunks/v2/policy-synthetic-chunking-qc.jsonl` | 0 |
| Chunk report | `dataset/chunks/v2/policy-synthetic-chunking-report.json` | 1 |

Per-source counts and character lengths (provision and chunk content are identical
because every complete Rule ID section is below the target size):

| Source | Provisions | Chunks | Provision chars | Chunk chars |
| --- | ---: | ---: | ---: | ---: |
| `synthetic-sme-working-capital-v1` | 14 | 14 | 4,857 | 4,857 |
| `synthetic-sme-underwriting-v1` | 12 | 12 | 4,808 | 4,808 |
| `synthetic-credit-approval-v1` | 11 | 11 | 3,687 | 3,687 |

All 37 chunks are non-empty, below the 4,800-character hard limit, metadata-only
context, and carry one source-provision provenance record. No QC anomaly was
manufactured: there are no repeated labels, direct article points, or exact duplicate
legal-text groups in this synthetic set.

## Manual source samples

The following samples were manually inspected against the source Rule ID sections.
Each note confirms that the complete rule context is present, thresholds are not
isolated from their conditions, and exception authority remains in the same chunk.

### `synthetic-sme-working-capital-v1` (first 10 of 14)

`0dfa22f72acb616456e7431b1362a7f80de847ec3f3c53630c887d7876521b71`,
`fdda9f09341a7d3fa905eaf8f7c08e84ebf42e1c3130919836f312e6bb9d14aa`,
`c097149aa99ebd76ad16de38e8c6264407e6f75dc0f52933171b25f5cb31f9de`,
`338978ec37adbbe3d82b9c6ea2378d9a887797ce5b92510fa4496a66547c207b`,
`04e8880282c070a7ba5c0be90dabd5fed33737dfa894267d7435a027d43d3a18`,
`99d4961f132513d92f2b4a60a10acb0b9caf285e71295765d3c0d25d543a3729`,
`c433f3dbc1d6dabf1ced9f39b736a9aeb37bc598ef9a17133909ad10237df42c`,
`90fbcee4f560ae50258f04934d3d0a41a44067084dca297b0e4a168348dda1b8`,
`40cc0096b54df95d426fdf7c249200893e39320e287bce97205a7e751213b465`,
`1a8031690898abfa23f6b7f1203d921878abf324983c15e99f617dd178b51c93`.

Reviewer note: complete Rule ID context retained for every sample; revenue, history,
exposure, tenor, repayment, collateral, CIC, and exception thresholds remain paired
with their authority and hard-stop language.

### `synthetic-sme-underwriting-v1` (first 10 of 12)

`511ec3a07bfc2c5a2839d27bb5c71540ba88ff8418dc81717b1fc14939337525`,
`cacf65f29fb78465914db68e7327d40eb2ef8d8006226785589836130f4bba3d`,
`e2a4618512d93fae606e27380bfb7ee1ea2451f7895e1c66bde3481e048bce9d`,
`282b6cf05cda6c2726ab41b6156cb3be2930ca912d9607cbf4862fcc89e99bac`,
`739a78f5c46e72944da3174d45733326d62b466666c1921a00cf20866e39fe46`,
`091aa50fc0b4c61d328f77a7dce21fb53717691ad6aa9a78cb58bca57798c561`,
`0699b242d383e109e4a7aaba9870038f936c723272d465661fdfa171eedf27d2`,
`b8748f26cc3f390d2b6d1b1c2d9aa436c8b78b8486136361c7f16aed9be0268e`,
`70f267622e10059a611a606e72148dbce2c22386983c8b9be0233f263ffd87e8`,
`6961ba23a2763b4793d9e10c517fb1e7c8ec2d6c52552f65c3bd954ec0c34f02`.

Reviewer note: DSCR, Debt-to-Equity, Current Ratio, revenue trend, grades, soft
exceptions, and hard stops were checked as complete rule statements; no threshold is
isolated and exception authority is retained.

### `synthetic-credit-approval-v1` (first 10 of 11)

`1ad078503e952d4c010471185961e8f00a5580e6ecb80b7b46efff824a9a9f09`,
`db2f2cd6b152e3cee120f38ca38338b0485aaf5e1cca40140423fcd3ace5789d`,
`7b94c1d235374306aa2b1ab6ab9da4a9d8335c288ad88515cc4e85463d30c02e`,
`fc5a76f2eb1b287da7cd0f984130a657fddab05c014755c1394ffc050e8d8461`,
`459549a81e609b0873fef571ec14740da30e756e49fc433b4dae18fed47cffdd`,
`4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d`,
`59aa9152d01a6a9f99183f3e79e6d12e3d69a0e03f00bf50b7876554deecacc9`,
`cfb17cfd26c9d5effd9cf9f16ea99a11aaedfe3295b7372b3a57255e90a4e8bc`,
`6b2a2f24429edf93aae5b14df892c53b5e7783d11324addabbb72efe7a996ddc`,
`917ebf28c65bf84a1883e40449107f1b04763fa062b4dfbc66329d0480b47842`.

Reviewer note: exposure bands, Tier 1–4 authority, maker/checker separation, one- and
two-exception routes, hard stops, validity, and re-approval triggers were manually
checked with their complete conditions retained; thresholds are not isolated.

## Validation and boundary

`backend/scripts/validate_synthetic_policy_v2.py` validates both closed schemas,
manifest synthetic/namespace mapping, normalized content hashes, duplicate IDs/content,
canonical ID recomputation, provenance and complete coverage, hierarchy shape, chunk
limits, report/QC counts, and overlap with frozen real chunk IDs/content. The frozen
real files under `dataset/normalized/v2/policy-sources.json`,
`dataset/normalized/v2/policy-provisions.jsonl`,
`dataset/chunks/v2/policy-legal-chunks.jsonl`,
`dataset/chunks/v2/policy-chunking-qc.jsonl`, and
`dataset/chunks/v2/policy-chunking-report.json` were not changed by Stage 9.
