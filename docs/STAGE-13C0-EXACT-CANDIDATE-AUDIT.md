# Stage 13C0 — Exact Candidate-Generation Failure Audit

Status: completed read-only diagnostic. No HNSW setting, corpus, embedding, gold, or production retriever was changed.

## Frozen identity

- Gold: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Embedding parquet: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Corpus: `policy-corpus-v2`, 1,610 unique canonical chunks
- Embedding: `Qwen3-Embedding-0.6B`, 1,024D, unit-normalized

## Query under audit

- Evaluation ID: `stage12a-024`
- Scope: `collateral_appraisal`
- Question: Hồ sơ đăng ký biện pháp bảo đảm được phép nộp bằng những phương thức nào, và có giới hạn nào với đất hoặc tài sản gắn liền với đất?
- Approved gold: `e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9`
- Eligible canonical chunks: **1573** (SHARED plus explicitly authorized SCOPED)

## Exact cosine oracle

- Gold exact rank: **49**
- Gold cosine: `0.715880033`
- Rank-10 cosine: `0.758613239`
- Rank-20 cosine: `0.744822122`
- Gold minus rank-20: `-0.028942089`
- Top-1 exact candidate: `c5d4c2e869b5f102d8d73b1bfe2cb146aca30795dda6d2b07011f984eb00ff2e` — Article 37 (Về đăng ký biện pháp bảo đảm)

### Exact top five

| Rank | Canonical ID | Cosine | Article | Source |
|---:|---|---:|---|---|
| 1 | `c5d4c2e869b5f102d8d73b1bfe2cb146aca30795dda6d2b07011f984eb00ff2e` | 0.795536453 | 37 | Về đăng ký biện pháp bảo đảm |
| 2 | `786c6f996d459d0cb15fde1e8557b5a760c520bc1c33a3fd6f34dd982b0c22f6` | 0.788307409 | 37 | Về đăng ký biện pháp bảo đảm |
| 3 | `1d275a9324a3861f63ef02fd3d84e4e9d6bf6cc44231a21d8379f69ae8169aca` | 0.785473390 | 45 | Về đăng ký biện pháp bảo đảm |
| 4 | `a3d808aa44f60109e597c77871cbe3efca1e9f520623f26846c058510a206bb1` | 0.779457592 | 27 | Về đăng ký biện pháp bảo đảm |
| 5 | `5167c78b217b469cf2ae304b47460309fad37ebaad20eb21cc199bf99d01ccbb` | 0.772040745 | 37 | Về đăng ký biện pháp bảo đảm |

## Unchanged canonical HNSW comparison

- Observed `hnsw.ef_search`: `40` (read-only; unchanged)
- Requested and returned rows: `20`
- Gold HNSW rank: `>20`
- Exact/HNSW top-20 set overlap: `20/20` (100.00%)
- Same-position count: `20/20`
- Exact top-20 IDs missing from HNSW: `0`

## Root-cause classification

**EMBEDDING_CANDIDATE_FAILURE**

The approved gold is not in the HNSW top-20. The exact oracle rank and score determine whether that is semantic under-ranking or ANN omission; no index setting was changed to obtain this comparison.

## Content inspection

### Approved gold

- `e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9` — Về đăng ký biện pháp bảo đảm, Article 13; the approved passage lists online, paper/direct/postal, and email filing methods and qualifies electronic/email methods for land-related assets under specialized law.
- Excerpt: Điều 13. Cách thức nộp hồ sơ đăng ký 1. Hồ sơ đăng ký được nộp theo một trong các cách thức sau đây: a) Qua hệ thống đăng ký trực tuyến; b) Nộp bản giấy trực tiếp hoặc gửi qua dịch vụ bưu chính; c) Qua thư điện tử. 2. Cách thức nộp hồ sơ đăng ký quy định tại điểm a và điểm c khoản 1 Điều này đối với quyền sử dụng đất, tài sản gắn liền với đất, quyền sử dụng khu vực biển, tài sản gắn liền với khu vực biển hoặc đối…

### Exact top-ranked wrong candidates

- Rank 1, `c5d4c2e869b5f102d8d73b1bfe2cb146aca30795dda6d2b07011f984eb00ff2e`, Article 37: 1. Thông tin về tài sản bảo đảm trong hợp đồng bảo đảm không chỉ có quyền sử dụng đất, tài sản gắn liền với đất mà còn có tài sản khác nhưng trên Phiếu yêu cầu đăng ký chỉ kê khai thông tin về quyền sử dụng đất, tài sản gắn liền với đất.
- Rank 2, `786c6f996d459d0cb15fde1e8557b5a760c520bc1c33a3fd6f34dd982b0c22f6`, Article 37: 2. Thông tin về tài sản bảo đảm trong hợp đồng bảo đảm bao gồm cả quyền sử dụng đất và tài sản gắn liền với đất nhưng trên Phiếu yêu cầu đăng ký chỉ kê khai quyền sử dụng đất hoặc chỉ kê khai tài sản gắn liền với đất thì Văn phòng đăng ký đất đai thực hiện việc đăng ký đối với tài sản được kê khai trên Phiếu yêu cầu đăng ký.
- Rank 3, `1d275a9324a3861f63ef02fd3d84e4e9d6bf6cc44231a21d8379f69ae8169aca`, Article 45: Điều 45. Mô tả tài sản bảo đảm trên Phiếu yêu cầu đăng ký
- Rank 4, `a3d808aa44f60109e597c77871cbe3efca1e9f520623f26846c058510a206bb1`, Article 27: Điều 27. Hồ sơ đăng ký đối với quyền sử dụng đất, tài sản gắn liền với đất đã được chứng nhận quyền sở hữu 1. Phiếu yêu cầu theo Mẫu số 01a tại Phụ lục (01 bản chính). 2. Hợp đồng bảo đảm hoặc hợp đồng bảo đảm có công chứng, chứng thực trong trường hợp Luật Đất đai, Luật Nhà ở, luật khác có liên quan quy định (01 bản chính hoặc 01 bản sao có chứng thực). 3. Giấy chứng nhận (bản gốc), trừ trường hợp quy định tại…
- Rank 5, `5167c78b217b469cf2ae304b47460309fad37ebaad20eb21cc199bf99d01ccbb`, Article 37: 3. Thông tin về tài sản bảo đảm trong hợp đồng bảo đảm và Phiếu yêu cầu đăng ký bao gồm cả quyền sử dụng đất, tài sản gắn liền với đất mà quyền sử dụng đất đủ điều kiện dùng để bảo đảm nhưng tài sản gắn liền với đất thuộc diện phải đăng ký quyền sở hữu theo quy định của pháp luật mà chưa được chứng nhận quyền sở hữu thì Văn phòng đăng ký đất đai thực hiện đăng ký đối với quyền sử dụng đất. Người yêu cầu đăng ký có…

The top wrong passages are from the same security-registration document and share filing/registration terminology, but concern different procedures or articles. This is consistent with semantic under-ranking at article/chunk granularity rather than a scope leak.

## Other frozen @5 misses — exact descriptive ranks

- `stage12a-007`: exact first gold rank `10`
- `stage12a-008`: exact first gold rank `8`
- `stage12a-013`: exact first gold rank `7`

## Method guardrails

- Query vectors came from the canonical llama.cpp adapter with the frozen instruction/template.
- Exact ranking used frozen parquet vectors, cosine, and canonical ID ascending as the tie-break.
- HNSW comparison used the unchanged `public.match_policy_chunks` RPC at `match_count=20`.
- No FTS, hybrid retrieval, reranker, query rewrite, model download, or benchmark metric was used.
- `exact_top50_diagnostic_only` is an offline oracle view; no HNSW top-50 request was made.

## Decision

**EMBEDDING_CANDIDATE_FAILURE** — the approved gold is semantically below the exact top-20 candidate cutoff; investigate candidate-generation alternatives before changing the retained reranker.

OpenCode review status is recorded separately; no verdict is inferred from unavailable reviewer infrastructure.
