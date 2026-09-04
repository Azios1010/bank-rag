# Stage 6 chunking report

## Outcome

Normalized V2 was reused unchanged (`3341` provisions). The chunker now uses
metadata-only hierarchy context (`heading_path`, article/clause/point and a
deterministic occurrence identity), so it never prepends a long article or
clause body to a child fragment. It splits losslessly in this order: paragraph,
Vietnamese legal sentence punctuation, whitespace, then an exact hard boundary;
no emitted chunk may exceed the unchanged `4800` hard limit.

| Measure | Before | After |
| --- | ---: | ---: |
| Emitted chunks | 1,162 | 1,573 |
| Max chunk characters | over 4,800 (47 chunks) | 2,390 |
| Long-unsplittable chunks | 47 | 0 |
| Context-replication duplicate groups | 13 | 0 |
| QC anomalies | 79 | 32 |
| Chunk JSONL disk size | 2,573,814 bytes | 2,732,745 bytes |
| QC JSONL disk size | 23,976 bytes | 12,653 bytes |
| Report JSON disk size | n/a | 381 bytes |

The remaining 32 QC records are intentional classifications: 14 repeated
hierarchy-label groups, five direct article-level points, and 13 groups of
identical legal text that originate in different source provisions. The latter
are retained as `EXACT_DUPLICATE_LEGAL_TEXT`, not treated as chunking defects;
for example, the same documentary requirements are expressly repeated across
separate articles and clauses.

## Hierarchy and orphan decisions

Repeated labels are preserved as genuine consolidated/amendment/annex material
with `hierarchy_instance` ending in a stable `occurrence=N`; nothing is deleted
or deduplicated. This covers the specified sequences at normalized ordinals
01: 200-219; 02: 1960-1969; 03: 2040-2043 and 2064-2067; 05: 2972-2976; and
06: 3208-3216.

All five former orphans have parser-backed direct-article classification rather
than an invented clause: source 01 ordinals 222 (`e`), 223 (`g`), and 224 (`h`)
follow Article 11's article heading; source 03 ordinals 2157 (`a`) and 2158
(`b`) follow Article 14's article heading. They are retained with
`hierarchy_classification=DIRECT_ARTICLE_POINT` and one QC decision apiece.

## 50-chunk stratified human QC

I inspected the listed samples' source, hierarchy, fragment state, size, and
opening legal text during generation. `W` means whole normalized unit and `F`
means a lossless fragment; the sample covers every source, every observed size
band, article/clause/point levels, fragments, repeated labels, and direct
article points. Chunk ID prefixes permit direct lookup in the JSONL.

| # | Source | Chars / band | Level | State | Classification | Hierarchy | ID prefix |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | v2-01-86-vbhn-nhnn | 486 / 0-499 | article | W | NORMAL | a1 | 4004d98bc682 |
| 2 | v2-01-86-vbhn-nhnn | 129 / 0-499 | clause | W | NORMAL | a2/c2 | 8e605cc1b2a1 |
| 3 | v2-01-86-vbhn-nhnn | 24 / 0-499 | point | W | NORMAL | a2/c2/pa | 318aadfca163 |
| 4 | v2-01-86-vbhn-nhnn | 2152 / 1500-2399 | clause | F | NORMAL | a22/c2 | 024b0a315d4d |
| 5 | v2-02-100-vbhn-vpqh | 609 / 500-1499 | article | W | NORMAL | a1 | a044a27efdcb |
| 6 | v2-02-100-vbhn-vpqh | 216 / 0-499 | clause | W | NORMAL | a4/c1 | 5f74c255fc5f |
| 7 | v2-02-100-vbhn-vpqh | 173 / 0-499 | point | W | NORMAL | a4/c9/pa | ca4edd5ef6ad |
| 8 | v2-03-27-vbhn-nhnn | 26 / 0-499 | article | W | NORMAL | a1 | 2528bb1cd000 |
| 9 | v2-03-27-vbhn-nhnn | 222 / 0-499 | clause | W | NORMAL | a1/c1 | a26a6f64d8e7 |
| 10 | v2-03-27-vbhn-nhnn | 11 / 0-499 | point | W | NORMAL | a1/c1/pa | 1f359fc5b0f7 |
| 11 | v2-04-21-2021-nd-cp | 246 / 0-499 | article | W | NORMAL | a1 | f78c9eb1a954 |
| 12 | v2-04-21-2021-nd-cp | 184 / 0-499 | clause | W | NORMAL | a21/c1 | 2f25c483b8df |
| 13 | v2-04-21-2021-nd-cp | 150 / 0-499 | point | W | NORMAL | a21/c1/pa | d6db717bdba1 |
| 14 | v2-05-2161-vbhn-btp | 615 / 500-1499 | article | W | NORMAL | a1 | e29172a810b4 |
| 15 | v2-05-2161-vbhn-btp | 337 / 0-499 | clause | W | NORMAL | a3/c1 | 4744a1e70dc0 |
| 16 | v2-05-2161-vbhn-btp | 70 / 0-499 | point | W | NORMAL | a3/c3/pb | 2121740eb5c0 |
| 17 | v2-05-2161-vbhn-btp | 2178 / 1500-2399 | clause | F | NORMAL | a10/c6 | ac48787dd10c |
| 18 | v2-06-80-2021-nd-cp | 676 / 500-1499 | article | W | NORMAL | a1 | 9e01288d5809 |
| 19 | v2-06-80-2021-nd-cp | 447 / 0-499 | clause | W | NORMAL | a3/c1 | 7efc3654ce5e |
| 20 | v2-06-80-2021-nd-cp | 660 / 500-1499 | point | W | NORMAL | a13/c1/pa | fa1ad0caec40 |
| 21 | v2-07-15-2023-tt-nhnn | 251 / 0-499 | article | W | NORMAL | a1 | 78b1333d7a4c |
| 22 | v2-07-15-2023-tt-nhnn | 276 / 0-499 | clause | W | NORMAL | a3/c1 | e82c2c9b82de |
| 23 | v2-07-15-2023-tt-nhnn | 149 / 0-499 | point | W | NORMAL | a3/c8/pa | 28d0f16a96a8 |
| 24 | v2-01-86-vbhn-nhnn | 359 / 0-499 | article | W | NORMAL | a2 | 6c7391afd9d6 |
| 25 | v2-01-86-vbhn-nhnn | 679 / 500-1499 | point | W | NORMAL | a2/c2/pe | 2a6a5e3f25d6 |
| 26 | v2-01-86-vbhn-nhnn | 1549 / 1500-2399 | point | W | NORMAL | a2/c11/pb | 2f0230810bd7 |
| 27 | v2-03-27-vbhn-nhnn | 452 / 0-499 | point | W | REPEATED | a5/c4/pa | 418b575fe372 |
| 28 | v2-03-27-vbhn-nhnn | 255 / 0-499 | point | W | DIRECT ARTICLE | a14/pa | aa9cb1f17721 |
| 29 | v2-01-86-vbhn-nhnn | 2390 / 1500-2399 | point | F | NORMAL | a22/c2/pđ | 7bfd8dde82bb |
| 30 | v2-02-100-vbhn-vpqh | 2385 / 1500-2399 | article | W | NORMAL | a209 | 59fcadebd352 |
| 31 | v2-04-21-2021-nd-cp | 2385 / 1500-2399 | article | W | NORMAL | a52 | 66b82e031117 |
| 32 | v2-03-27-vbhn-nhnn | 2380 / 1500-2399 | article | W | NORMAL | a3 | 103fd9ad7a77 |
| 33 | v2-02-100-vbhn-vpqh | 2364 / 1500-2399 | article | W | NORMAL | a171 | d108a1b76093 |
| 34 | v2-02-100-vbhn-vpqh | 2354 / 1500-2399 | article | W | NORMAL | a167 | f297e62db4e6 |
| 35 | v2-01-86-vbhn-nhnn | 2343 / 1500-2399 | article | W | NORMAL | a9 | 91f496387463 |
| 36 | v2-05-2161-vbhn-btp | 2340 / 1500-2399 | clause | W | NORMAL | a5/c4 | 0e5dd69e3d49 |
| 37 | v2-05-2161-vbhn-btp | 2332 / 1500-2399 | point | F | NORMAL | a21/c2/pa | 7cdecc5df6bd |
| 38 | v2-02-100-vbhn-vpqh | 2329 / 1500-2399 | article | W | NORMAL | a49 | ee8519c24ee1 |
| 39 | v2-02-100-vbhn-vpqh | 2318 / 1500-2399 | article | W | NORMAL | a102 | 958e40edd538 |
| 40 | v2-02-100-vbhn-vpqh | 2264 / 1500-2399 | article | W | NORMAL | a39 | 82f4b5ca4449 |
| 41 | v2-02-100-vbhn-vpqh | 2264 / 1500-2399 | article | W | NORMAL | a48 | 754cefcd3910 |
| 42 | v2-02-100-vbhn-vpqh | 2243 / 1500-2399 | article | W | NORMAL | a34 | 3327dbfa0c74 |
| 43 | v2-01-86-vbhn-nhnn | 2226 / 1500-2399 | clause | F | NORMAL | a22/c2 | 9ff81d891e7b |
| 44 | v2-04-21-2021-nd-cp | 2221 / 1500-2399 | article | W | NORMAL | a3 | b815f622a42c |
| 45 | v2-02-100-vbhn-vpqh | 2209 / 1500-2399 | article | W | NORMAL | a134 | bce027e58803 |
| 46 | v2-02-100-vbhn-vpqh | 2208 / 1500-2399 | article | W | NORMAL | a174 | eed0168f9613 |
| 47 | v2-05-2161-vbhn-btp | 2206 / 1500-2399 | article | W | NORMAL | a57 | 123356748e2d |
| 48 | v2-02-100-vbhn-vpqh | 2204 / 1500-2399 | article | W | NORMAL | a188 | e92b0c6b09f5 |
| 49 | v2-02-100-vbhn-vpqh | 2196 / 1500-2399 | article | W | NORMAL | a183 | 68f3e9fbd2b4 |
| 50 | v2-01-86-vbhn-nhnn | 2154 / 1500-2399 | article | W | NORMAL | a5 | a98035544540 |

## Verification

Ran once after the single in-place chunk/QC regeneration:

```text
python -m pytest backend/tests/test_policy_chunking_v2.py backend/tests/test_validate_policy_chunks_v2.py -q
# 12 passed
python backend/scripts/validate_policy_chunks_v2.py
# All validations passed.
python -m pytest backend/tests -q --basetemp .pytest-stage6
# 80 passed, 2 skipped, 1 warning
```

The validator now verifies strict length, exact fragment provenance, every
normalized provision's coverage, schema conformance, deterministic IDs, and
duplicate-legal-text QC reconciliation.

The full-suite warning is the existing unregistered `integration` pytest mark.
