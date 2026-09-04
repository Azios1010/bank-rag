# Stage 13E — Expanded Retrieval Gold Review

## Review scope

This is an evidence-first human-review pack. The 25 Stage 12A records
are the frozen REVIEWED seed and are referenced, not re-authored here.
The 75 records below are new DRAFT questions derived from frozen Corpus V2
chunks. No retrieval output, embedding ranking, FTS, or reranker was used
to select their evidence. Human reviewers may approve, edit, or reject
each new draft; automated tooling has not promoted any record.

- Corpus: `policy-corpus-v2` / 1610 chunks
- Frozen seed: 25 REVIEWED records from `dataset/evaluation/retrieval-v2-gold-pilot.jsonl`
- New drafts: 75 (`stage13e-026` through `stage13e-100`)
- Status of every new item: `DRAFT`

## Draft distribution

- By scope: {'collateral_appraisal': 20, 'credit': 20, 'customer_relationship': 20, 'legal_compliance': 20, 'risk_management': 20}
- By provenance: {'real_authoritative': 80, 'synthetic': 20}
- New question categories: {'consequence': 8, 'customer-facing': 4, 'direct': 7, 'distinction': 3, 'exception': 4, 'internal-policy': 10, 'multi-condition': 3, 'procedural': 18, 'role': 11, 'threshold': 7}
- New difficulty: {'EASY': 33, 'HARD': 9, 'MEDIUM': 33}

## Frozen source coverage

| Source ID | Records in combined set |
|---|---:|
| `synthetic-credit-approval-v1` | 6 |
| `synthetic-sme-underwriting-v1` | 7 |
| `synthetic-sme-working-capital-v1` | 7 |
| `v2-01-86-vbhn-nhnn` | 19 |
| `v2-02-100-vbhn-vpqh` | 11 |
| `v2-03-27-vbhn-nhnn` | 13 |
| `v2-04-21-2021-nd-cp` | 10 |
| `v2-05-2161-vbhn-btp` | 12 |
| `v2-06-80-2021-nd-cp` | 3 |
| `v2-07-15-2023-tt-nhnn` | 12 |

## New DRAFT records

### stage13e-026

- **Scope:** `credit`
- **Question:** Tổ chức tín dụng có được tự quyết định việc cho vay và từ chối yêu cầu nào của khách hàng?
- **Expected canonical chunk ID:** `9e09807aa04909fe587454b7b4f1cbe921e102e61cdc5c41b4fc67d2be31fafd`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=3, jsonl_line=27; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `direct`; **Difficulty:** `EASY`
- **Evidence:** Điều 3. Quyền tự chủ của tổ chức tín dụng 1. Tổ chức tín dụng có quyền tự chủ trong hoạt động cho vay và tự chịu trách nhiệm về quyết định cho vay của mình. Không tổ chức, cá nhân nào được can thiệp trái pháp luật vào hoạt động cho vay của tổ chức tín dụng. 2. Tổ chức tín dụng có quyền từ chối các yêu cầu của khách hàng không đúng với quy định tại Thông tư này và thỏa thuận cho vay.
- **Rationale:** Đoạn quy định trực tiếp nêu quyền tự chủ, trách nhiệm về quyết định cho vay và quyền từ chối yêu cầu không phù hợp.
- **Status:** `DRAFT`

### stage13e-027

- **Scope:** `credit`
- **Question:** Khi thỏa thuận khoản vay, khách hàng phải tuân thủ những nguyên tắc cơ bản nào về mục đích sử dụng vốn và nghĩa vụ trả nợ?
- **Expected canonical chunk ID:** `72a7bd225e92fa731fc15d274322d6c4d0dd9eb548617086f10a78a9fcc8b0da`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=4, jsonl_line=28; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `multi-condition`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 4. Nguyên tắc cho vay, vay vốn 1. Hoạt động cho vay của tổ chức tín dụng đối với khách hàng được thực hiện theo thỏa thuận giữa tổ chức tín dụng và khách hàng, phù hợp với quy định tại Thông tư này và các quy định của pháp luật có liên quan bao gồm cả pháp luật về bảo vệ môi trường. 2.12 Khách hàng vay vốn tổ chức tín dụng phải đảm bảo sử dụng vốn vay đúng mục đích đã cam kết, hoàn trả nợ gốc, lãi tiền vay, phí đầy đủ, đúng hạn theo thỏa thuận với tổ chức tín dụng.
- **Rationale:** Một điều khoản thống nhất quy định sự phù hợp pháp luật, sử dụng vốn đúng cam kết và hoàn trả gốc, lãi, phí đúng hạn.
- **Status:** `DRAFT`

### stage13e-028

- **Scope:** `credit`
- **Question:** Thỏa thuận cho vay và tài liệu tiếng nước ngoài phải được lập hoặc xử lý về ngôn ngữ như thế nào?
- **Expected canonical chunk ID:** `6e4da03b8692ea04b1ce067f23086978a3415d102d305d33f09ec0c70715ff55`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, jsonl_line=30; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 6. Sử dụng ngôn ngữ 1. Thỏa thuận cho vay được lập bằng tiếng Việt hoặc đồng thời bằng tiếng Việt và tiếng nước ngoài. 2. Đối với các tài liệu khác trong hoạt động cho vay sử dụng tiếng nước ngoài, khi cơ quan có thẩm quyền yêu cầu dịch sang tiếng Việt, thì bản dịch phải có xác nhận của người có thẩm quyền của tổ chức tín dụng hoặc phải được công chứng hoặc chứng thực.
- **Rationale:** Điều khoản quy định ngôn ngữ của thỏa thuận và yêu cầu đối với bản dịch tài liệu nước ngoài khi cơ quan có thẩm quyền yêu cầu.
- **Status:** `DRAFT`

### stage13e-029

- **Scope:** `credit`
- **Question:** Khoản vay được phân loại ngắn hạn, trung hạn và dài hạn theo thời hạn tối đa hoặc khoảng thời gian nào?
- **Expected canonical chunk ID:** `ca52689c760027aec0d39512b40a3c846e0d5417e06c4bee74b4b80c1fd80c88`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=10, jsonl_line=44; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** Điều 10. Loại cho vay Tổ chức tín dụng xem xét quyết định cho khách hàng vay theo các loại cho vay như sau: 1. Cho vay ngắn hạn là các khoản vay có thời hạn cho vay tối đa 01 (một) năm. 2. Cho vay trung hạn là các khoản vay có thời hạn cho vay trên 01 (một) năm và tối đa 05 (năm) năm. 3. Cho vay dài hạn là các khoản vay có thời hạn cho vay trên 05 (năm) năm.
- **Rationale:** Điều 10 đưa ra ba mốc thời hạn rõ ràng để phân biệt các loại cho vay.
- **Status:** `DRAFT`

### stage13e-030

- **Scope:** `credit`
- **Question:** Đồng tiền cho vay và đồng tiền trả nợ được xác định theo nguyên tắc nào, và có thể trả bằng đồng tiền khác hay không?
- **Expected canonical chunk ID:** `1009b017e9829f54c351506fe7866c8f05ef623bdaf5944d2ddaaeb244549a6a`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, jsonl_line=45; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `distinction`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 11. Đồng tiền cho vay, trả nợ 1. Tổ chức tín dụng và khách hàng thỏa thuận về việc cho vay bằng đồng Việt Nam hoặc bằng ngoại tệ phù hợp với quy định tại Thông tư này và quy định của pháp luật có liên quan. 2.21 Đồng tiền trả nợ là đồng tiền cho vay của khoản vay. Trường hợp trả nợ bằng đồng tiền khác, thì thực hiện theo thỏa thuận giữa tổ chức tín dụng và khách hàng phù hợp với quy định của pháp luật liên quan.
- **Rationale:** Điều khoản phân biệt đồng tiền cho vay với đồng tiền trả nợ và nêu điều kiện trả nợ bằng đồng tiền khác.
- **Status:** `DRAFT`

### stage13e-031

- **Scope:** `credit`
- **Question:** Thỏa thuận về lãi suất cần thể hiện những thông tin nào về cách xác định và tính lãi?
- **Expected canonical chunk ID:** `f56c28eac7f0aa3918928954c05c3e3c02adbfe344b5bbfa39fba5f17cc67f28`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=13, clause=3, jsonl_line=54; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** 3. Nội dung thỏa thuận về lãi suất cho vay bao gồm mức lãi suất cho vay và phương pháp tính lãi đối với khoản vay. Trường hợp mức lãi suất cho vay không quy đổi theo tỷ lệ %/năm và/hoặc không áp dụng phương pháp tính lãi theo số dư nợ cho vay thực tế, thời gian duy trì số dư nợ gốc thực tế đó, thì trong thỏa thuận cho vay phải có nội dung về mức lãi suất quy đổi theo tỷ lệ %/năm (một năm là ba trăm sáu mươi lăm ngày) tính theo số dư nợ cho vay thực tế và thời gian duy trì số dư nợ cho vay thực tế đó.
- **Rationale:** Đoạn được chọn quy định các thành phần của thỏa thuận lãi suất, gồm mức lãi và phương pháp tính, kể cả quy đổi theo năm khi cần.
- **Status:** `DRAFT`

### stage13e-032

- **Scope:** `credit`
- **Question:** Những loại phí nào có thể được thỏa thuận khi tổ chức tín dụng thực hiện hoạt động cho vay?
- **Expected canonical chunk ID:** `89d802df285c87a1361ee6a584eaa4b686c4fcb4fa674d2b953984e66be02119`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=14, jsonl_line=60; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** Điều 14. Phí liên quan đến hoạt động cho vay Tổ chức tín dụng và khách hàng thoả thuận về việc thu các khoản phí liên quan đến hoạt động cho vay, gồm: 1. Phí trả nợ trước hạn trong trường hợp khách hàng trả nợ trước hạn. 2. Phí trả cho hạn mức tín dụng dự phòng. 3. Phí thu xếp cho vay hợp vốn. 4.Phí cam kết rút vốn kể từ thời điểm thỏa thuận cho vay có hiệu lực đến ngày giải ngân vốn vay lần đầu. 5. Các loại phí khác liên quan đến hoạt động cho vay được quy định cụ thể tại văn bản quy phạm pháp luật liên quan.
- **Rationale:** Điều 14 liệt kê các nhóm phí liên quan đến khoản vay, bao gồm phí trả trước hạn, hạn mức dự phòng và các loại phí khác theo quy định.
- **Status:** `DRAFT`

### stage13e-033

- **Scope:** `credit`
- **Question:** Biện pháp bảo đảm tiền vay do ai thỏa thuận và ai chịu trách nhiệm khi khoản vay không áp dụng bảo đảm?
- **Expected canonical chunk ID:** `3b5d373d32f4f75f8ba3b9018190661b2d43e31c3ac57fc5c684a4072a9f9723`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=15, jsonl_line=61; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 15. Bảo đảm tiền vay 1. Việc áp dụng biện pháp bảo đảm tiền vay hoặc không áp dụng biện pháp bảo đảm tiền vay do tổ chức tín dụng và khách hàng thoả thuận. Việc thỏa thuận về biện pháp bảo đảm tiền vay của tổ chức tín dụng với khách hàng phù hợp với quy định của pháp luật về biện pháp bảo đảm và pháp luật có liên quan. 2. Tổ chức tín dụng quyết định và chịu trách nhiệm về việc cho vay không áp dụng biện pháp bảo đảm tiền vay. 3. Khách hàng, bên bảo đảm phải phối hợp với tổ chức tín dụng để xử lý tài sản bảo đảm tiền vay khi có căn cứ xử lý theo thỏa thuận cho vay, hợp đồng bảo đảm tiền vay và quy định của pháp luật.
- **Rationale:** Điều 15 đặt việc áp dụng bảo đảm hoặc không áp dụng trong thỏa thuận, đồng thời phân định trách nhiệm của tổ chức tín dụng.
- **Status:** `DRAFT`

### stage13e-034

- **Scope:** `credit`
- **Question:** Trong thẩm định khoản vay, tổ chức tín dụng có thể sử dụng những nguồn thông tin nào và phải tách bạch khâu thẩm định với quyết định ra sao?
- **Expected canonical chunk ID:** `239da504404561b4f3127a6ae5ae8b69a3420ea22dd0182f2d69776c455ab5a7`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=17, jsonl_line=63; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 17. Thẩm định và quyết định cho vay 1. Tổ chức tín dụng thẩm định khả năng đáp ứng các điều kiện vay vốn của khách hàng theo quy định tại Điều 7 Thông tư này để xem xét quyết định cho vay. Trong quá trình thẩm định, tổ chức tín dụng được sử dụng hệ thống xếp hạng tín dụng nội bộ, kết hợp với các thông tin tại Trung tâm Thông tin tín dụng quốc gia Việt Nam, các kênh thông tin khác. 2. Tổ chức tín dụng phải tổ chức xét duyệt cho vay theo nguyên tắc phân định trách nhiệm giữa khâu thẩm định và quyết định cho vay. 3. Trường hợp quyết định không cho vay, tổ chức tín dụng thông báo cho khách hàng lý do khi khách hàng có yêu cầu.
- **Rationale:** Điều 17 trực tiếp đề cập hệ thống xếp hạng tín dụng nội bộ, CIC, các kênh thông tin khác và yêu cầu tổ chức độc lập hai khâu.
- **Status:** `DRAFT`

### stage13e-035

- **Scope:** `credit`
- **Question:** Đối tượng khách hàng mục tiêu của sản phẩm vốn lưu động SME không bảo đảm phải đáp ứng những đặc điểm nền tảng nào?
- **Expected canonical chunk ID:** `fdda9f09341a7d3fa905eaf8f7c08e84ebf42e1c3130919836f312e6bb9d14aa`
- **Source:** SME Unsecured Working Capital Product Policy (`synthetic-sme-working-capital-v1` / `synthetic-sme-working-capital-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=PROD-TARGET, jsonl_line=1575; heading `SME Unsecured Working Capital Product Policy › ## 2. Target customer and ordinary use`
- **Question type:** `internal-policy`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: PROD-TARGET. The target customer is a registered Vietnamese SME business with transparent ownership, lawful operating activity, and a demonstrated working-capital need. The relationship manager must identify the legal entity, beneficial ownership, management, business history, and operating cycle; underwriting verification is governed by [[UW-IDENTITY-AND-INDUSTRY]].
- **Rationale:** Quy tắc sản phẩm nêu tình trạng đăng ký, quyền sở hữu minh bạch, hoạt động hợp pháp và nhu cầu vốn lưu động có thể chứng minh.
- **Status:** `DRAFT`

### stage13e-036

- **Scope:** `credit`
- **Question:** Vốn lưu động theo chính sách sản phẩm có thể được dùng cho những nhu cầu vận hành nào và cần chứng minh bằng hồ sơ gì?
- **Expected canonical chunk ID:** `c097149aa99ebd76ad16de38e8c6264407e6f75dc0f52933171b25f5cb31f9de`
- **Source:** SME Unsecured Working Capital Product Policy (`synthetic-sme-working-capital-v1` / `synthetic-sme-working-capital-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=PROD-PURPOSE, jsonl_line=1576; heading `SME Unsecured Working Capital Product Policy › ## 2. Target customer and ordinary use`
- **Question type:** `internal-policy`; **Difficulty:** `MEDIUM`
- **Evidence:** Rule ID: PROD-PURPOSE. Permitted purposes are inventory, trade receivables, payroll, rent, utilities, and ordinary operating expenses tied to the borrower's business cycle. A proposed use must be evidenced by a purpose budget and supporting invoices or contracts, then tested against cash flow under [[UW-CASH-FLOW]].
- **Rationale:** Quy tắc liệt kê các nhu cầu vận hành được phép và yêu cầu ngân sách mục đích cùng hóa đơn hoặc hợp đồng hỗ trợ.
- **Status:** `DRAFT`

### stage13e-037

- **Scope:** `credit`
- **Question:** Ngưỡng DSCR chuẩn, khoảng ngoại lệ mềm và mức bị từ chối cứng trong thẩm định là bao nhiêu?
- **Expected canonical chunk ID:** `091aa50fc0b4c61d328f77a7dce21fb53717691ad6aa9a78cb58bca57798c561`
- **Source:** SME Credit Underwriting Policy (`synthetic-sme-underwriting-v1` / `synthetic-sme-underwriting-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=UW-DSCR, jsonl_line=1593; heading `SME Credit Underwriting Policy › ## 3. Repayment capacity and financial analysis`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: UW-DSCR. Standard DSCR is >= 1.30, calculated as cash available for debt service divided by scheduled debt service including the proposed facility. DSCR >= 1.15 and < 1.30 may be one soft exception. DSCR < 1.15 is a hard decline and no grade or approval authority may override it.
- **Rationale:** Quy tắc UW-DSCR nêu công thức, ngưỡng chuẩn 1,30, khoảng 1,15 đến dưới 1,30 và mức dưới 1,15.
- **Status:** `DRAFT`

### stage13e-038

- **Scope:** `credit`
- **Question:** Trường hợp có đúng hai ngoại lệ mềm thì cấp phê duyệt nào được xem xét và phải đáp ứng các điều kiện kiểm soát nào?
- **Expected canonical chunk ID:** `459549a81e609b0873fef571ec14740da30e756e49fc433b4dae18fed47cffdd`
- **Source:** Credit Approval & Exception Policy (`synthetic-credit-approval-v1` / `synthetic-credit-approval-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=APR-TIER-4, jsonl_line=1604; heading `Credit Approval & Exception Policy › ## 2. Approval authority`
- **Question type:** `internal-policy`; **Difficulty:** `HARD`
- **Evidence:** Rule ID: APR-TIER-4. Tier 4 Credit Committee/UBTD may approve a single-exception Grade C case with total exposure above VND 3 billion and up to VND 5 billion. It may approve a Grade C-EXCEPTION-2 case only when exactly two soft exceptions apply, every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded.
- **Rationale:** Quy tắc Tier 4 tập hợp đúng số ngoại lệ, khoảng tổng dư nợ, việc không có hard stop, đồng thuận độc lập và yêu cầu ghi nhận hồ sơ.
- **Status:** `DRAFT`

### stage13e-039

- **Scope:** `risk_management`
- **Question:** Ngân hàng phải thu thập và khai thác thông tin khách hàng để phục vụ những hoạt động quản trị rủi ro nào?
- **Expected canonical chunk ID:** `db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=4, jsonl_line=840; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 4. Thu thập số liệu, thông tin khách hàng và công nghệ thông tin 1. Ngân hàng, tổ chức tín dụng phi ngân hàng có biện pháp và thường xuyên thực hiện việc thu thập, khai thác thông tin, số liệu về khách hàng, bao gồm cả thông tin từ Trung tâm Thông tin tín dụng quốc gia Việt Nam (CIC), công ty thông tin tín dụng theo quy định của pháp luật để: a) Xây dựng, sửa đổi, bổ sung hệ thống xếp hạng tín dụng nội bộ, quy định nội bộ về cấp tín dụng, quản lý nợ, chính sách dự phòng rủi ro; b) Theo dõi, đánh giá tình hình tài chính, khả năng trả nợ của khách hàng sau khi đã xếp hạng theo hệ thống xếp hạng tín dụng nội bộ, có biện pháp quản lý rủi ro, quản lý chất lượng tín dụng phù hợp; c) Thực hiện tự phân loại nợ, cam kết ngoại bảng theo quy định tại Thông tư này và thực hiện trích lập dự phòng rủi ro và sử dụng dự phòng rủi ro theo quy định tại Nghị định về trích lập dự phòng rủi ro. 2. Ngân…
- **Rationale:** Điều 4 nối việc thu thập thông tin từ khách hàng, CIC và nguồn hợp pháp với xếp hạng nội bộ, quản lý nợ và chính sách dự phòng.
- **Status:** `DRAFT`

### stage13e-040

- **Scope:** `risk_management`
- **Question:** Một hệ thống xếp hạng tín dụng nội bộ cần bao gồm những nhóm chỉ tiêu và quy trình đánh giá nào?
- **Expected canonical chunk ID:** `395e0af21b02c1e28c5b77ab5aada1b5c467642d6981dcd1a95310602bff2b62`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=1, point=a, jsonl_line=843; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `multi-condition`; **Difficulty:** `MEDIUM`
- **Evidence:** a) Các bộ chỉ tiêu tài chính và phi tài chính, các quy trình đánh giá khả năng trả nợ, thanh toán của khách hàng trên cơ sở định tính và định lượng về mặt tài chính, tình hình kinh doanh, quản trị, uy tín của khách hàng, kể cả khách hàng là đối tượng bị hạn chế cấp tín dụng; các thông tin về người có liên quan của khách hàng là đối tượng bị hạn chế cấp tín dụng;
- **Rationale:** Đoạn quy định mô tả cả chỉ tiêu tài chính, phi tài chính và quy trình đánh giá khả năng trả nợ trên cơ sở định tính, định lượng.
- **Status:** `DRAFT`

### stage13e-041

- **Scope:** `risk_management`
- **Question:** Các mức xếp hạng trong hệ thống xếp hạng tín dụng nội bộ phải phản ánh rủi ro theo chiều hướng nào?
- **Expected canonical chunk ID:** `a3d9c4cfed50131485a712a8caa5a2c896c09a47ef669da81f98ceaf6cfc85b6`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=2, point=c, jsonl_line=848; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `distinction`; **Difficulty:** `EASY`
- **Evidence:** c) Có quy định các mức xếp hạng tương ứng với mức độ rủi ro từ thấp đến cao;
- **Rationale:** Điểm được chọn yêu cầu các mức xếp hạng tương ứng với mức độ rủi ro từ thấp đến cao.
- **Status:** `DRAFT`

### stage13e-042

- **Scope:** `risk_management`
- **Question:** Cấp quản lý nào phải phê duyệt việc áp dụng hệ thống xếp hạng tín dụng nội bộ?
- **Expected canonical chunk ID:** `a121373c1059401ad80332f18177f4b699504982e57bd249615de1739ef85f37`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=2, point=d, jsonl_line=849; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** d) Được Hội đồng quản trị, Hội đồng thành viên (đối với ngân hàng thương mại, tổ chức tín dụng phi ngân hàng), Tổng giám đốc hoặc Giám đốc (đối với chi nhánh ngân hàng nước ngoài) phê duyệt áp dụng.
- **Rationale:** Đoạn quy định trực tiếp xác định thẩm quyền phê duyệt của Hội đồng quản trị, Hội đồng thành viên hoặc Tổng giám đốc/Giám đốc tùy loại hình.
- **Status:** `DRAFT`

### stage13e-043

- **Scope:** `risk_management`
- **Question:** Những tổ chức nào bắt buộc phải xây dựng hệ thống xếp hạng tín dụng nội bộ và hệ thống này được sử dụng cho các quyết định nào?
- **Expected canonical chunk ID:** `165a10eba0349fe3d478ef9a74b9e2395ed3c8dab550f50d38eb02195d01f850`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=3, jsonl_line=850; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `MEDIUM`
- **Evidence:** 3. Ngân hàng thương mại, chi nhánh ngân hàng nước ngoài phải xây dựng hệ thống xếp hạng tín dụng nội bộ để xếp hạng khách hàng theo định kỳ và khi cần thiết, làm cơ sở cho việc xét duyệt cấp tín dụng, quản lý chất lượng tín dụng, xây dựng chính sách dự phòng rủi ro phù hợp với phạm vi hoạt động, đối tượng khách hàng và tình hình thực tế của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài. Tổ chức tín dụng phi ngân hàng không bắt buộc phải có hệ thống xếp hạng tín dụng nội bộ. Trường hợp tổ chức tín dụng phi ngân hàng xây dựng hệ thống xếp hạng tín dụng nội bộ thì phải đáp ứng các quy định tại Thông tư này.
- **Rationale:** Khoản 3 phân biệt nghĩa vụ của ngân hàng, chi nhánh ngân hàng nước ngoài với tổ chức tín dụng phi ngân hàng và nêu các mục đích sử dụng.
- **Status:** `DRAFT`

### stage13e-044

- **Scope:** `risk_management`
- **Question:** Trong thời hạn bao lâu sau khi ban hành hoặc sửa đổi hệ thống xếp hạng tín dụng nội bộ phải gửi hồ sơ cho Ngân hàng Nhà nước?
- **Expected canonical chunk ID:** `9fae0dd5446c0d4d80cfbe172a345de541e1bb1fa8a559793e54402e8fd40d85`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=4, jsonl_line=851; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** 4. Trong thời hạn 10 (mười) ngày kể từ ngày ban hành, sửa đổi, bổ sung hệ thống xếp hạng tín dụng nội bộ, ngân hàng, tổ chức tín dụng phi ngân hàng phải gửi trực tiếp hoặc qua dịch vụ bưu chính hoặc phương tiện điện tử cho Ngân hàng Nhà nước theo quy định tại khoản 5 Điều này các văn bản sau:
- **Rationale:** Khoản 4 Điều 5 đặt thời hạn 10 ngày kể từ ngày ban hành hoặc sửa đổi, bổ sung hệ thống.
- **Status:** `DRAFT`

### stage13e-045

- **Scope:** `risk_management`
- **Question:** Tổ chức tín dụng phải ban hành quy định nội bộ về cấp tín dụng, quản lý nợ và dự phòng rủi ro theo những căn cứ nào?
- **Expected canonical chunk ID:** `3f212b4c7d07d612fc0b95203d562875d9a96e60769ee5d76353d64f80b20714`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, clause=1, jsonl_line=857; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** 1. Ngân hàng, tổ chức tín dụng phi ngân hàng phải ban hành quy định nội bộ về cấp tín dụng, quản lý nợ, chính sách dự phòng rủi ro phù hợp với quy định tại Thông tư này, Nghị định về trích lập dự phòng rủi ro và các quy định pháp luật khác có liên quan.
- **Rationale:** Điều 6 yêu cầu các quy định nội bộ phù hợp với thông tư, nghị định về trích lập dự phòng và pháp luật liên quan.
- **Status:** `DRAFT`

### stage13e-046

- **Scope:** `risk_management`
- **Question:** Quy định nội bộ phải kiểm soát việc tuân thủ những giới hạn và tỷ lệ an toàn nào trong hoạt động?
- **Expected canonical chunk ID:** `97b77dbc674e0906068c9a1204d682722411655d2ff7a25dfaa5a05f045318a8`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, clause=2, point=d, jsonl_line=862; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `MEDIUM`
- **Evidence:** d) Có quy định về quản lý nhằm đảm bảo tuân thủ quy định của Ngân hàng Nhà nước về các giới hạn, tỷ lệ đảm bảo an toàn trong hoạt động của ngân hàng, tổ chức tín dụng phi ngân hàng; 2 Khoản này được sửa đổi theo quy định tại Điều 1 của Thông tư số 37/2025/TT-NHNN sửa đổi, bổ sung một số điều của Thông tư số 31/2024/TT-NHNN của Thống đốc Ngân hàng Nhà nước Việt Nam quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài, có hiệu lực kể từ ngày 15/12/2025.
- **Rationale:** Điểm được chọn yêu cầu quy định quản lý để bảo đảm tuân thủ các giới hạn và tỷ lệ bảo đảm an toàn của Ngân hàng Nhà nước.
- **Status:** `DRAFT`

### stage13e-047

- **Scope:** `risk_management`
- **Question:** Quy định về định giá tài sản bảo đảm cần nêu những nguyên tắc và trách nhiệm nào để phục vụ trích lập dự phòng?
- **Expected canonical chunk ID:** `3e9f616cb4df9720ccae4a91b386f99552665bb5045a3a1254e1223462857329`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, clause=2, point=h, jsonl_line=866; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** h) Có quy định về định giá tài sản bảo đảm, bao gồm nguyên tắc, định kỳ, phương pháp, quy trình và trách nhiệm của từng đơn vị, cá nhân có liên quan đến việc định giá tài sản bảo đảm theo quy định của pháp luật để đảm bảo giá trị tài sản bảo đảm phù hợp với giá trị thị trường khi tính số tiền trích lập dự phòng cụ thể theo quy định tại Nghị định về trích lập dự phòng rủi ro;
- **Rationale:** Đoạn quy định yêu cầu nêu nguyên tắc, định kỳ, phương pháp, quy trình và trách nhiệm liên quan đến định giá theo giá thị trường.
- **Status:** `DRAFT`

### stage13e-048

- **Scope:** `risk_management`
- **Question:** Hệ thống xếp hạng tín dụng nội bộ phải phù hợp với những yếu tố nào và cần có thời gian thử nghiệm tối thiểu bao lâu để phục vụ phân loại nợ định tính?
- **Expected canonical chunk ID:** `d60763f0e2492f623c47f61b62b93cf2de3e9cdbb041227f577635f81b3b3a7f`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, clause=2, point=a, jsonl_line=929; heading `Chương II › Mục 1 PHÂN LOẠI NỢ VÀ CAM KẾT NGOẠI BẢNG`
- **Question type:** `threshold`; **Difficulty:** `MEDIUM`
- **Evidence:** a) Có Hệ thống xếp hạng tín dụng nội bộ phù hợp với hoạt động kinh doanh, đối tượng khách hàng, tính chất rủi ro của khoản nợ và có thời gian thử nghiệm tối thiểu 01 (một) năm;
- **Rationale:** Điểm a khoản 2 Điều 11 yêu cầu hệ thống phù hợp với hoạt động, đối tượng khách hàng và tính chất rủi ro, đồng thời có thời gian thử nghiệm tối thiểu một năm.
- **Status:** `DRAFT`

### stage13e-049

- **Scope:** `risk_management`
- **Question:** Mô hình quản lý rủi ro tín dụng cần xác định và đo lường những yếu tố nào khi phân loại nợ?
- **Expected canonical chunk ID:** `3ca22b44b947c9ce57f7b0a10a52e53e769dcd5f4690e0d11474b4f50b345b34`
- **Source:** Quy định về phân loại tài sản có trong hoạt động của ngân hàng thương mại, tổ chức tín dụng phi ngân hàng, chi nhánh ngân hàng nước ngoài (`v2-03-27-vbhn-nhnn` / `v2-03-27-vbhn-nhnn-2025-11-21-5ced19467135`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, clause=2, point=c, jsonl_line=931; heading `Chương II › Mục 1 PHÂN LOẠI NỢ VÀ CAM KẾT NGOẠI BẢNG`
- **Question type:** `multi-condition`; **Difficulty:** `HARD`
- **Evidence:** c) Có chính sách quản lý rủi ro tín dụng, mô hình giám sát rủi ro tín dụng, phương pháp xác định, đo lường rủi ro tín dụng (trong đó bao gồm cách thức đánh giá về khả năng trả nợ của khách hàng theo hợp đồng tín dụng, tài sản bảo đảm, khả năng thu hồi nợ) và quản lý nợ;
- **Rationale:** Điểm được chọn yêu cầu chính sách, mô hình giám sát, phương pháp đo lường rủi ro, khả năng trả nợ, tài sản bảo đảm và quản lý nợ.
- **Status:** `DRAFT`

### stage13e-050

- **Scope:** `risk_management`
- **Question:** Khâu thẩm định SME phải xác minh những nhóm thông tin nào trước khi đề xuất xếp hạng và tuyến phê duyệt?
- **Expected canonical chunk ID:** `cacf65f29fb78465914db68e7327d40eb2ef8d8006226785589836130f4bba3d`
- **Source:** SME Credit Underwriting Policy (`synthetic-sme-underwriting-v1` / `synthetic-sme-underwriting-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=UW-IDENTITY-AND-INDUSTRY, jsonl_line=1589; heading `SME Credit Underwriting Policy › ## 2. Identity, management, and industry assessment`
- **Question type:** `internal-policy`; **Difficulty:** `MEDIUM`
- **Evidence:** Rule ID: UW-IDENTITY-AND-INDUSTRY. Verify registration, authority, transparent ownership, management continuity, business start date, industry, purpose, and the evidence listed in [[PROD-DOCUMENTS]]. Assess management experience, customer and supplier concentration, industry outlook, and dependence on a single counterparty. An excluded industry or purpose is a hard stop; a material unmitigated management, industry, or concentration weakness prevents standard approval and may result in Grade C or D.
- **Rationale:** Quy tắc thẩm định liệt kê danh tính, sở hữu, quản lý, ngành, mục đích, hồ sơ, khả năng trả nợ và các yếu tố tập trung.
- **Status:** `DRAFT`

### stage13e-051

- **Scope:** `risk_management`
- **Question:** Khi rà soát CIC và dư nợ của doanh nghiệp, bộ phận thẩm định phải thực hiện những việc kiểm tra nào?
- **Expected canonical chunk ID:** `e2a4618512d93fae606e27380bfb7ee1ea2451f7895e1c66bde3481e048bce9d`
- **Source:** SME Credit Underwriting Policy (`synthetic-sme-underwriting-v1` / `synthetic-sme-underwriting-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=UW-CIC-AND-DEBT, jsonl_line=1590; heading `SME Credit Underwriting Policy › ## 2. Identity, management, and industry assessment`
- **Question type:** `internal-policy`; **Difficulty:** `MEDIUM`
- **Evidence:** Rule ID: UW-CIC-AND-DEBT. Obtain and date CIC evidence, identify overdue obligations, and reconcile all existing and proposed interest-bearing debt with the debt schedule. Active CIC Group 3 or higher is a hard decline. A resolved Group 2 within 24 months may be one soft exception only when current obligations are clean and [[APR-EXCEPTIONS]] approves it.
- **Rationale:** Quy tắc yêu cầu lấy và ghi ngày chứng cứ CIC, nhận diện nợ quá hạn và đối chiếu toàn bộ nghĩa vụ nợ.
- **Status:** `DRAFT`

### stage13e-052

- **Scope:** `risk_management`
- **Question:** Tỷ lệ nợ trên vốn chủ sở hữu chuẩn, khoảng ngoại lệ mềm và mức từ chối cứng trong chính sách là bao nhiêu?
- **Expected canonical chunk ID:** `0699b242d383e109e4a7aaba9870038f936c723272d465661fdfa171eedf27d2`
- **Source:** SME Credit Underwriting Policy (`synthetic-sme-underwriting-v1` / `synthetic-sme-underwriting-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=UW-LEVERAGE, jsonl_line=1594; heading `SME Credit Underwriting Policy › ## 3. Repayment capacity and financial analysis`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: UW-LEVERAGE. Standard Debt-to-Equity is interest-bearing debt divided by shareholders' equity <= 3.00x, including existing and proposed interest-bearing debt. Debt-to-Equity > 3.00x and <= 4.00x may be one soft exception. Debt-to-Equity > 4.00x is a hard decline.
- **Rationale:** Quy tắc UW-LEVERAGE nêu rõ mẫu số, việc tính cả dư nợ hiện hữu và đề xuất, cùng ba vùng ngưỡng.
- **Status:** `DRAFT`

### stage13e-053

- **Scope:** `risk_management`
- **Question:** Một hồ sơ Grade C có ngoại lệ mềm phải ghi nhận những nội dung gì, và Grade C-EXCEPTION-2 bị giới hạn ra sao?
- **Expected canonical chunk ID:** `59aa9152d01a6a9f99183f3e79e6d12e3d69a0e03f00bf50b7876554deecacc9`
- **Source:** Credit Approval & Exception Policy (`synthetic-credit-approval-v1` / `synthetic-credit-approval-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=APR-EXCEPTIONS, jsonl_line=1606; heading `Credit Approval & Exception Policy › ## 3. Maker, checker, challenge, and exceptions`
- **Question type:** `exception`; **Difficulty:** `HARD`
- **Evidence:** Rule ID: APR-EXCEPTIONS. A Grade C case has exactly one soft exception and enumerates every deviated rule, evidence, root cause, mitigant, and residual risk. Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded. Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3. More than two soft exceptions are not permitted. No exception may be hidden through a grade override, and no grade or tier may override a hard stop.
- **Rationale:** Quy tắc phê duyệt yêu cầu nêu ngoại lệ, chứng cứ, nguyên nhân, biện pháp giảm thiểu, rủi ro còn lại và giới hạn tuyến Tier 4.
- **Status:** `DRAFT`

### stage13e-054

- **Scope:** `legal_compliance`
- **Question:** Các loại tổ chức tín dụng trong nước được tổ chức dưới những hình thức pháp lý nào?
- **Expected canonical chunk ID:** `ec3d7284decf237b019ea4cc861a9db511c3b04ba308156578f913f621ec26a9`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, jsonl_line=210; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `distinction`; **Difficulty:** `EASY`
- **Evidence:** Điều 6. Hình thức pháp lý của tổ chức tín dụng 1. Ngân hàng thương mại trong nước được thành lập, tổ chức dưới hình thức công ty cổ phần, trừ trường hợp quy định tại khoản 2 Điều này và trường hợp thực hiện phương án chuyển giao bắt buộc được phê duyệt. 2. Ngân hàng thương mại nhà nước được thành lập, tổ chức dưới hình thức công ty trách nhiệm hữu hạn một thành viên do Nhà nước nắm giữ 100% vốn điều lệ. 3. Tổ chức tín dụng phi ngân hàng trong nước được thành lập, tổ chức dưới hình thức công ty cổ phần, công ty trách nhiệm hữu hạn. 4. Tổ chức tín dụng liên doanh, tổ chức tín dụng 100% vốn nước ngoài được thành lập, tổ chức dưới hình thức công ty trách nhiệm hữu hạn. 5. Ngân hàng hợp tác xã, quỹ tín dụng nhân dân được thành lập, tổ chức dưới hình thức hợp tác xã. 6. Tổ chức tài chính vi mô được thành lập, tổ chức dưới hình thức công ty trách nhiệm hữu hạn.
- **Rationale:** Điều 6 phân biệt hình thức công ty cổ phần, công ty trách nhiệm hữu hạn và hợp tác xã theo từng loại tổ chức.
- **Status:** `DRAFT`

### stage13e-055

- **Scope:** `legal_compliance`
- **Question:** Tổ chức tín dụng phải công khai và bảo vệ quyền lợi khách hàng trong những nội dung giao dịch nào?
- **Expected canonical chunk ID:** `04740a512de500891274f929289034e762e3ed266e6c795d153261d9666f05fc`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=10, jsonl_line=214; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `customer-facing`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 10. Trách nhiệm của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài trong việc bảo vệ quyền lợi của khách hàng 1. Tham gia bảo hiểm tiền gửi, quỹ bảo đảm an toàn hệ thống quỹ tín dụng nhân dân theo quy định của pháp luật và công bố công khai việc tham gia bảo hiểm tiền gửi tại trụ sở chính và chi nhánh. 2. Tạo thuận lợi cho khách hàng gửi và rút tiền, bảo đảm thanh toán đủ, đúng hạn tiền gốc, lãi của khoản tiền gửi theo thỏa thuận phù hợp với quy định của pháp luật. 3. Từ chối việc điều tra, phong tỏa, cầm giữ, trích chuyển tiền gửi của khách hàng, trừ trường hợp có yêu cầu của cơ quan nhà nước có thẩm quyền theo quy định của luật hoặc được sự chấp thuận của khách hàng. 4. Công bố công khai lãi suất tiền gửi, phí dịch vụ, quyền, nghĩa vụ của khách hàng đối với từng loại sản phẩm, dịch vụ đang cung ứng. 5. Công bố công khai thời gian giao dịch chính thức. Trường hợp ngừng giao dịch…
- **Rationale:** Điều 10 quy định nhiều trách nhiệm trực tiếp với khách hàng, trong đó có bảo hiểm tiền gửi, công khai lãi phí và xử lý tiền gửi.
- **Status:** `DRAFT`

### stage13e-056

- **Scope:** `legal_compliance`
- **Question:** Người đại diện theo pháp luật của tổ chức tín dụng phải đáp ứng điều kiện cư trú và ủy quyền như thế nào khi vắng mặt?
- **Expected canonical chunk ID:** `9a0d7836e282df3805ba8936a001028442b771d0a46df6945d8b82e99b509ea9`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, jsonl_line=215; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 11. Người đại diện theo pháp luật của tổ chức tín dụng 1. Người đại diện theo pháp luật của tổ chức tín dụng được quy định tại Điều lệ của tổ chức tín dụng và phải là một trong những người sau đây: a) Chủ tịch Hội đồng quản trị hoặc Chủ tịch Hội đồng thành viên của tổ chức tín dụng; b) Tổng giám đốc (Giám đốc) của tổ chức tín dụng. 2. Người đại diện theo pháp luật của tổ chức tín dụng phải cư trú tại Việt Nam, trường hợp vắng mặt ở Việt Nam phải ủy quyền bằng văn bản cho người khác là người quản lý, người điều hành tổ chức tín dụng đang cư trú tại Việt Nam để thực hiện quyền, nghĩa vụ của người đại diện theo pháp luật của tổ chức tín dụng. 3. Tổ chức tín dụng phải thông báo cho Ngân hàng Nhà nước về người đại diện theo pháp luật của tổ chức tín dụng trong thời hạn 10 ngày kể từ ngày bầu, bổ nhiệm chức danh đảm nhiệm người đại diện theo pháp luật theo quy định tại Điều lệ của tổ…
- **Rationale:** Điều 11 quy định người đại diện phải cư trú tại Việt Nam và phải ủy quyền bằng văn bản khi vắng mặt.
- **Status:** `DRAFT`

### stage13e-057

- **Scope:** `legal_compliance`
- **Question:** Khi giao dịch với tổ chức tín dụng, khách hàng phải cung cấp thông tin và chịu trách nhiệm về thông tin đó ra sao?
- **Expected canonical chunk ID:** `5f25b1e41a0d54e45a7b36650b960a65bff99fc48a358482b75295f2fdd997b1`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=12, jsonl_line=216; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 12. Cung cấp thông tin 1. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài cung cấp cho chủ tài khoản thông tin về giao dịch và số dư trên tài khoản của chủ tài khoản theo thỏa thuận với chủ tài khoản. 2. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài có trách nhiệm báo cáo Ngân hàng Nhà nước thông tin liên quan đến hoạt động kinh doanh và được Ngân hàng Nhà nước cung cấp thông tin của khách hàng có quan hệ tín dụng với tổ chức tín dụng, chi nhánh ngân hàng nước ngoài theo quy định của Thống đốc Ngân hàng Nhà nước. 3. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài được trao đổi với nhau thông tin về hoạt động của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài. 4. Khi thực hiện giao dịch với tổ chức tín dụng, chi nhánh ngân hàng nước ngoài, khách hàng có trách nhiệm cung cấp thông tin, tài liệu, dữ liệu trung thực, chính xác, đầy đủ, kịp thời và phải chịu trách nhiệm về việc…
- **Rationale:** Khoản 4 Điều 12 yêu cầu thông tin, tài liệu và dữ liệu trung thực, chính xác, đầy đủ, kịp thời và gắn với trách nhiệm của khách hàng.
- **Status:** `DRAFT`

### stage13e-058

- **Scope:** `legal_compliance`
- **Question:** Tổ chức tín dụng phải bảo đảm những yêu cầu nào đối với an toàn dữ liệu và hoạt động liên tục?
- **Expected canonical chunk ID:** `1c4d9d8498271cb60bc44c0e4621c783bb20388f687d9b630e98a09dea4aff0a`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=14, jsonl_line=218; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `EASY`
- **Evidence:** Điều 14. An toàn dữ liệu và bảo đảm hoạt động liên tục Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài phải bảo đảm an toàn hệ thống thông tin, bảo mật dữ liệu và hoạt động liên tục theo quy định của Thống đốc Ngân hàng Nhà nước và quy định khác của pháp luật có liên quan.
- **Rationale:** Điều 14 trực tiếp yêu cầu an toàn hệ thống thông tin, bảo mật dữ liệu và hoạt động liên tục.
- **Status:** `DRAFT`

### stage13e-059

- **Scope:** `legal_compliance`
- **Question:** Những nhóm hành vi nào bị nghiêm cấm đối với tổ chức tín dụng và chủ thể không phải tổ chức tín dụng?
- **Expected canonical chunk ID:** `2674bf7a078ff0ceb2d74a7fba652d73e2f085093123ba286ef801c388ea7d40`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=15, jsonl_line=219; heading `Chương I NHỮNG QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 15. Hành vi bị nghiêm cấm 1. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài thực hiện hoạt động ngân hàng, hoạt động kinh doanh khác ngoài hoạt động ghi trong Giấy phép được Ngân hàng Nhà nước cấp cho tổ chức tín dụng, chi nhánh ngân hàng nước ngoài. 2. Tổ chức, cá nhân không phải là tổ chức tín dụng, chi nhánh ngân hàng nước ngoài thực hiện hoạt động ngân hàng, trừ giao dịch ký quỹ, giao dịch mua bán lại chứng khoán của công ty chứng khoán. 3. Tổ chức, cá nhân can thiệp trái pháp luật vào hoạt động ngân hàng, hoạt động kinh doanh khác của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài. 4. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài thực hiện hành vi hạn chế cạnh tranh hoặc hành vi cạnh tranh không lành mạnh có nguy cơ gây tổn hại hoặc gây tổn hại đến việc thực hiện chính sách tiền tệ quốc gia, an toàn của hệ thống tổ chức tín dụng, lợi ích của Nhà nước, quyền và lợi ích…
- **Rationale:** Điều 15 là điều khoản cấm, bao quát hoạt động ngoài giấy phép, can thiệp trái pháp luật và cạnh tranh gây hại cho hệ thống.
- **Status:** `DRAFT`

### stage13e-060

- **Scope:** `legal_compliance`
- **Question:** Điều kiện về vốn điều lệ tối thiểu khi xin cấp Giấy phép tổ chức tín dụng được quy định thế nào?
- **Expected canonical chunk ID:** `da0d6919546dac223a5be5ba23a9acc26b6c8b6ef0f4d08e8eb0ff2da46da21f`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=29, clause=1, point=a, jsonl_line=235; heading `Chương III GIẤY PHÉP`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** a) Có vốn điều lệ tối thiểu bằng mức vốn pháp định;
- **Rationale:** Điểm a khoản 1 Điều 29 nêu trực tiếp yêu cầu vốn điều lệ tối thiểu bằng mức vốn pháp định.
- **Status:** `DRAFT`

### stage13e-061

- **Scope:** `legal_compliance`
- **Question:** Đề án thành lập và phương án kinh doanh phải đáp ứng yêu cầu gì khi xin cấp phép tổ chức tín dụng?
- **Expected canonical chunk ID:** `ea917efb3c02eea3c24145d0d2edf2d065a9bd31f4922898952e09008c9779a2`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=29, clause=1, point=đ, jsonl_line=239; heading `Chương III GIẤY PHÉP`
- **Question type:** `direct`; **Difficulty:** `MEDIUM`
- **Evidence:** đ) Đề án thành lập, phương án kinh doanh khả thi, bảo đảm không gây ảnh hưởng đến sự an toàn, ổn định của hệ thống tổ chức tín dụng, không tạo ra sự độc quyền hoặc hạn chế cạnh tranh hoặc cạnh tranh không lành mạnh trong hệ thống tổ chức tín dụng.
- **Rationale:** Điểm đ khoản 1 Điều 29 yêu cầu đề án và phương án khả thi, đồng thời không gây ảnh hưởng đến an toàn, ổn định hoặc cạnh tranh.
- **Status:** `DRAFT`

### stage13e-062

- **Scope:** `legal_compliance`
- **Question:** Ngân hàng Nhà nước có thời hạn bao lâu để cấp hoặc từ chối cấp Giấy phép sau khi nhận đủ hồ sơ hợp lệ?
- **Expected canonical chunk ID:** `14d689a75e5e7d15027aab6432b1f9f6b88acfc4005093bbbb5734a8e3d4f871`
- **Source:** Luật Các tổ chức tín dụng (`v2-02-100-vbhn-vpqh` / `v2-02-100-vbhn-vpqh-2026-04-22-584568fa5972`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=31, jsonl_line=257; heading `Chương III GIẤY PHÉP`
- **Question type:** `threshold`; **Difficulty:** `EASY`
- **Evidence:** Điều 31. Thời hạn cấp Giấy phép 1. Trong thời hạn 180 ngày kể từ ngày nhận đủ hồ sơ hợp lệ, Ngân hàng Nhà nước cấp Giấy phép hoặc từ chối cấp Giấy phép thành lập và hoạt động của tổ chức tín dụng, Giấy phép thành lập chi nhánh ngân hàng nước ngoài. 2. Trong thời hạn 60 ngày kể từ ngày nhận đủ hồ sơ hợp lệ, Ngân hàng Nhà nước cấp Giấy phép hoặc từ chối cấp Giấy phép thành lập văn phòng đại diện nước ngoài. 3. Trường hợp từ chối cấp Giấy phép, Ngân hàng Nhà nước phải thông báo bằng văn bản và nêu rõ lý do.
- **Rationale:** Điều 31 tách thời hạn 180 ngày cho tổ chức tín dụng, chi nhánh ngân hàng nước ngoài và 60 ngày cho văn phòng đại diện.
- **Status:** `DRAFT`

### stage13e-063

- **Scope:** `legal_compliance`
- **Question:** Lĩnh vực hoạt động của doanh nghiệp nhỏ và vừa được xác định căn cứ vào thông tin nào?
- **Expected canonical chunk ID:** `2533ca7a0a8797990c30c9417057be2a2e7ad60e8de81b196874f23fcdd2d7b5`
- **Source:** Quy định chi tiết và hướng dẫn thi hành một số điều của Luật Hỗ trợ doanh nghiệp nhỏ và vừa (`v2-06-80-2021-nd-cp` / `v2-06-80-2021-nd-cp-2021-08-26-20a1d22961e9`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, jsonl_line=1411; heading `Chương II TIÊU CHÍ XÁC ĐỊNH DOANH NGHIỆP NHỎ VÀ VỪA`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 6. Xác định lĩnh vực hoạt động của doanh nghiệp nhỏ và vừa Lĩnh vực hoạt động của doanh nghiệp nhỏ và vừa được xác định căn cứ vào ngành, nghề kinh doanh chính mà doanh nghiệp đã đăng ký với cơ quan đăng ký kinh doanh.
- **Rationale:** Điều 6 quy định căn cứ là ngành, nghề kinh doanh chính đã đăng ký với cơ quan đăng ký kinh doanh.
- **Status:** `DRAFT`

### stage13e-064

- **Scope:** `legal_compliance`
- **Question:** Tổng nguồn vốn của doanh nghiệp nhỏ và vừa được xác định từ báo cáo nào, và xử lý thế nào nếu doanh nghiệp hoạt động dưới một năm?
- **Expected canonical chunk ID:** `d9fa4d73b0e1aaf263c5bea1560d91be0121d783ff746560466ba1fbaae5b508`
- **Source:** Quy định chi tiết và hướng dẫn thi hành một số điều của Luật Hỗ trợ doanh nghiệp nhỏ và vừa (`v2-06-80-2021-nd-cp` / `v2-06-80-2021-nd-cp-2021-08-26-20a1d22961e9`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=8, jsonl_line=1413; heading `Chương II TIÊU CHÍ XÁC ĐỊNH DOANH NGHIỆP NHỎ VÀ VỪA`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 8. Xác định tổng nguồn vốn của doanh nghiệp nhỏ và vừa 1. Tổng nguồn vốn của năm được xác định trong bảng cân đối kế toán thể hiện trên Báo cáo tài chính của năm trước liền kề mà doanh nghiệp nộp cho cơ quan quản lý thuế. Tổng nguồn vốn của năm được xác định tại thời điểm cuối năm. 2. Trường hợp doanh nghiệp hoạt động dưới 01 năm, tổng nguồn vốn được xác định trong bảng cân đối kế toán của doanh nghiệp tại thời điểm cuối quý liền kề thời điểm doanh nghiệp đăng ký hưởng nội dung hỗ trợ.
- **Rationale:** Điều 8 chỉ rõ báo cáo tài chính năm trước liền kề và mốc cuối quý liền kề cho doanh nghiệp hoạt động dưới một năm.
- **Status:** `DRAFT`

### stage13e-065

- **Scope:** `legal_compliance`
- **Question:** Những mục đích sử dụng vốn hoặc ngành nghề nào là hard stop trong chính sách SME vốn lưu động?
- **Expected canonical chunk ID:** `338978ec37adbbe3d82b9c6ea2378d9a887797ce5b92510fa4496a66547c207b`
- **Source:** SME Unsecured Working Capital Product Policy (`synthetic-sme-working-capital-v1` / `synthetic-sme-working-capital-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=PROD-EXCLUSIONS, jsonl_line=1577; heading `SME Unsecured Working Capital Product Policy › ## 2. Target customer and ordinary use`
- **Question type:** `internal-policy`; **Difficulty:** `MEDIUM`
- **Evidence:** Rule ID: PROD-EXCLUSIONS. Capital expenditure, real-estate or securities speculation, crypto-asset trading, owner distributions, repayment of overdue debt, and any purpose rejected by legal/compliance review are prohibited. Gambling, unlicensed financial intermediation, weapons trafficking, adult-content operations, crypto-asset speculation, and speculative real-estate trading are excluded industries. These are hard stops and cannot be waived under [[APR-HARD-STOPS]].
- **Rationale:** Quy tắc loại trừ liệt kê các mục đích đầu tư đầu cơ, trả nợ quá hạn, ngành nghề bị loại và xác định đây là các hard stop.
- **Status:** `DRAFT`

### stage13e-066

- **Scope:** `legal_compliance`
- **Question:** Những tình huống nào bị coi là từ chối cứng và không thể được phê duyệt như một ngoại lệ?
- **Expected canonical chunk ID:** `bb54d68d09ea0a0da64db105c8507ad5d12b10aced13ecda0551ef9ffa157053`
- **Source:** SME Credit Underwriting Policy (`synthetic-sme-underwriting-v1` / `synthetic-sme-underwriting-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=UW-HARD-STOPS, jsonl_line=1599; heading `SME Credit Underwriting Policy › ## 4. Grades and exception rationale`
- **Question type:** `internal-policy`; **Difficulty:** `HARD`
- **Evidence:** Rule ID: UW-HARD-STOPS. Hard declines are active CIC Group 3 or higher; DSCR < 1.15; Debt-to-Equity > 4.00x; Current Ratio < 0.80x; operating history below 18 months; revenue below VND 8 billion; excluded industry or purpose; missing KYC or authority evidence; fraud or intentional misstatement; and unsupported recurring negative cash flow. These map to [[APR-HARD-STOPS]] and cannot be approved as exceptions by any grade or tier.
- **Rationale:** Quy tắc UW-HARD-STOPS nêu đầy đủ các ngưỡng rủi ro, thiếu hồ sơ, gian dối, ngành/mục đích bị loại và dòng tiền âm lặp lại.
- **Status:** `DRAFT`

### stage13e-067

- **Scope:** `legal_compliance`
- **Question:** Trong quy trình phê duyệt tín dụng, vai trò của RM, bộ phận thẩm định, Risk và người phê duyệt được tách biệt như thế nào?
- **Expected canonical chunk ID:** `4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d`
- **Source:** Credit Approval & Exception Policy (`synthetic-credit-approval-v1` / `synthetic-credit-approval-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=APR-MAKER-CHECKER, jsonl_line=1605; heading `Credit Approval & Exception Policy › ## 3. Maker, checker, challenge, and exceptions`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: APR-MAKER-CHECKER. The RM or business unit prepares the request as maker. Credit Underwriting checks analysis. Risk independently challenges material risk. The approver is separate from the maker. Product documentation and underwriting rationale must be complete before approval.
- **Rationale:** Quy tắc maker-checker mô tả người lập hồ sơ, khâu kiểm tra, phản biện độc lập và yêu cầu người phê duyệt tách khỏi maker.
- **Status:** `DRAFT`

### stage13e-068

- **Scope:** `legal_compliance`
- **Question:** Phê duyệt tiêu chuẩn và phê duyệt ngoại lệ có thời hạn hiệu lực bao lâu nếu khoản vay chưa giải ngân?
- **Expected canonical chunk ID:** `917ebf28c65bf84a1883e40449107f1b04763fa062b4dfbc66329d0480b47842`
- **Source:** Credit Approval & Exception Policy (`synthetic-credit-approval-v1` / `synthetic-credit-approval-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=APR-VALIDITY, jsonl_line=1609; heading `Credit Approval & Exception Policy › ## 4. Approval controls, expiry, and re-approval`
- **Question type:** `internal-policy`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: APR-VALIDITY. A standard approval expires after 60 calendar days if undisbursed. An exception approval expires after 30 calendar days. Expired requests require re-approval.
- **Rationale:** Quy tắc APR-VALIDITY đặt thời hạn 60 ngày cho phê duyệt chuẩn, 30 ngày cho phê duyệt ngoại lệ và yêu cầu phê duyệt lại khi hết hạn.
- **Status:** `DRAFT`

### stage13e-069

- **Scope:** `customer_relationship`
- **Question:** Trước khi ký thỏa thuận vay, khách hàng phải được cung cấp những thông tin chủ yếu nào?
- **Expected canonical chunk ID:** `dc61f5152d480e1be3b005c5dbe6b1f0a8acbe468c85b08dbceda8fa14a7cde4`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=16, jsonl_line=62; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `customer-facing`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 16. Cung cấp thông tin 1. Tổ chức tín dụng có trách nhiệm cung cấp cho khách hàng đầy đủ các thông tin trước khi xác lập thỏa thuận cho vay: Lãi suất cho vay; nguyên tắc và các yếu tố xác định, thời điểm xác định lãi suất cho vay đối với trường hợp áp dụng lãi suất cho vay có điều chỉnh; lãi suất áp dụng đối với dư nợ gốc bị quá hạn; lãi suất áp dụng đối với lãi chậm trả; phương pháp tính lãi tiền vay; loại phí và mức phí áp dụng đối với khoản vay; các tiêu chí xác định khách hàng vay vốn theo lãi suất cho vay quy định tại khoản 2 Điều 13 Thông tư này. 2.23 Khách hàng có trách nhiệm cung cấp thông tin, tài liệu, dữ liệu cho tổ chức tín dụng trung thực, chính xác, đầy đủ, kịp thời và phải chịu trách nhiệm về việc cung cấp thông tin, tài liệu, dữ liệu đó: a) Các thông tin, tài liệu, dữ liệu quy định tại khoản 1 Điều 9 Thông tư này; b) Báo cáo việc sử dụng vốn vay và cung cấp thông…
- **Rationale:** Điều 16 liệt kê các thông tin trước hợp đồng như lãi suất, cách tính lãi, phí, điều kiện và biện pháp bảo đảm.
- **Status:** `DRAFT`

### stage13e-070

- **Scope:** `customer_relationship`
- **Question:** Khách hàng và tổ chức tín dụng có thể thỏa thuận những cách nào để trả nợ gốc, lãi và trả nợ trước hạn?
- **Expected canonical chunk ID:** `515d0ba7d04e7ad57ffe6994f2638a11a6a170bf1023b260c7aa7eb057d708b3`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=18, jsonl_line=64; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 18. Trả nợ gốc và lãi tiền vay 1. Tổ chức tín dụng và khách hàng thoả thuận về kỳ hạn trả nợ gốc và lãi tiền vay như sau: a) Trả nợ gốc, lãi tiền vay theo kỳ hạn riêng; b) Trả nợ gốc và lãi tiền vay trong cùng một kỳ hạn. 2. Tổ chức tín dụng và khách hàng thoả thuận về việc trả nợ trước hạn. 23 Khoản này được sửa đổi theo quy định tại khoản 5 Điều 1 của Thông tư số 12/2024/TT-NHNN sửa đổi, bổ sung một số điều của Thông tư số 39/2016/TT-NHNN ngày 30 tháng 12 năm 2016 của Thống đốc Ngân hàng Nhà nước Việt Nam quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng, có hiệu lực kể từ ngày 01/7/2024. 3. Trường hợp khách hàng không có khả năng trả nợ đúng hạn một phần hoặc toàn bộ nợ gốc và/hoặc lãi tiền vay, tổ chức tín dụng xem xét chấp thuận cơ cấu lại thời hạn trả nợ theo quy định tại Điều 19 hoặc chuyển nợ quá hạn theo quy định tại Điều…
- **Rationale:** Điều 18 nêu trả gốc và lãi theo kỳ riêng hoặc cùng kỳ, đồng thời cho phép thỏa thuận về trả trước hạn.
- **Status:** `DRAFT`

### stage13e-071

- **Scope:** `customer_relationship`
- **Question:** Khi nào tổ chức tín dụng có thể xem xét cơ cấu lại thời hạn trả nợ cho khách hàng?
- **Expected canonical chunk ID:** `fde373dfe29edf1ae993d7a1ebcc4eed07af589dd1a4ced7ca9414661b8b0908`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=19, jsonl_line=65; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `exception`; **Difficulty:** `HARD`
- **Evidence:** Điều 19. Cơ cấu lại thời hạn trả nợ Tổ chức tín dụng xem xét quyết định việc cơ cấu lại thời hạn trả nợ trên cơ sở đề nghị của khách hàng, khả năng tài chính của tổ chức tín dụng và kết quả đánh giá khả năng trả nợ của khách hàng, như sau: 1. Khách hàng không có khả năng trả nợ đúng kỳ hạn nợ gốc và/hoặc lãi tiền vay và được tổ chức tín dụng đánh giá là có khả năng trả đầy đủ nợ gốc và/hoặc lãi tiền vay theo kỳ hạn trả nợ được điều chỉnh, thì tổ chức tín dụng xem xét điều chỉnh kỳ hạn trả nợ gốc và/hoặc lãi tiền vay đó phù hợp với nguồn trả nợ của khách hàng; thời hạn cho vay không thay đổi. 2. Khách hàng không có khả năng trả hết nợ gốc và/hoặc lãi tiền vay đúng thời hạn cho vay đã thoả thuận và được tổ chức tín dụng đánh giá là có khả năng trả đầy đủ nợ gốc và/hoặc lãi tiền vay trong một khoảng thời gian nhất định sau thời hạn cho vay, thì tổ chức tín dụng xem xét cho gia hạn nợ với…
- **Rationale:** Điều 19 gắn việc cơ cấu với đề nghị của khách hàng, khả năng tài chính của tổ chức tín dụng và đánh giá khả năng trả nợ.
- **Status:** `DRAFT`

### stage13e-072

- **Scope:** `customer_relationship`
- **Question:** Khi nào dư nợ gốc bị chuyển thành nợ quá hạn và thông báo cho khách hàng phải có những thông tin tối thiểu nào?
- **Expected canonical chunk ID:** `10a2f44d90c42f762ef1ef675aa112bd5e1339279b84ec5da34abd83dfda2ca2`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=20, jsonl_line=66; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `EASY`
- **Evidence:** Điều 20. Nợ quá hạn Tổ chức tín dụng chuyển nợ quá hạn đối với số dư nợ gốc mà khách hàng không trả được nợ đúng hạn theo thỏa thuận và không được tổ chức tín dụng chấp thuận cơ cấu lại thời hạn trả nợ; thông báo cho khách hàng về việc chuyển nợ quá hạn. Nội dung thông báo tối thiểu bao gồm số dư nợ gốc bị quá hạn, thời điểm chuyển nợ quá hạn và lãi suất áp dụng đối với dư nợ gốc bị quá hạn.
- **Rationale:** Điều 20 nêu điều kiện không trả đúng hạn và không được cơ cấu, cùng ba nội dung tối thiểu của thông báo.
- **Status:** `DRAFT`

### stage13e-073

- **Scope:** `customer_relationship`
- **Question:** Những vi phạm nào có thể dẫn đến chấm dứt cho vay hoặc thu hồi nợ trước hạn?
- **Expected canonical chunk ID:** `49e326d4783e6fa8a225a31d8c9d167b23d7684259262d8f5728eae0d62927c0`
- **Source:** Quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng (`v2-01-86-vbhn-nhnn` / `v2-01-86-vbhn-nhnn-2026-06-30-92f9c4e45252`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=21, jsonl_line=67; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `HARD`
- **Evidence:** Điều 21. Chấm dứt cho vay, xử lý nợ, miễn, giảm lãi tiền vay, phí 24 Khoản này được sửa đổi theo quy định tại Điều 4 của Thông tư số 29/2026/TT- NHNN sửa đổi, bổ sung một số điều của Thông tư số 39/2016/TT-NHNN quy định về hoạt động cho vay của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài đối với khách hàng, có hiệu lực kể từ ngày 15/08/2026. 1. Tổ chức tín dụng có quyền chấm dứt cho vay, thu hồi nợ trước hạn theo nội dung đã thỏa thuận khi phát hiện khách hàng cung cấp thông tin sai sự thật, vi phạm quy định trong thỏa thuận cho vayvà/hoặc hợp đồng bảo đảm tiền vay. Khi thực hiện chấm dứt cho vay, thu hồi nợ trước hạn theo thỏa thuận trong thỏa thuận cho vay, tổ chức tín dụng phải thông báo cho khách hàng về việc chấm dứt cho vay, thu hồi nợ trước hạn. Nội dung thông báo tối thiểu bao gồm thời điểm chấm dứt cho vay, thu hồi nợ trước hạn, số dư nợ gốc bị thu hồi trước hạn; thời hạn…
- **Rationale:** Điều 21 quy định quyền chấm dứt và thu hồi trước hạn trong trường hợp thông tin sai hoặc khách hàng vi phạm thỏa thuận, cùng các hướng xử lý nợ.
- **Status:** `DRAFT`

### stage13e-074

- **Scope:** `customer_relationship`
- **Question:** Cơ sở dữ liệu thông tin tín dụng quốc gia được lập ra để hỗ trợ những hoạt động nào của Nhà nước, tổ chức tín dụng và khách hàng vay?
- **Expected canonical chunk ID:** `1b511053987c46a28a7d877e1ec72d100ef9fee5d3d831edba00a882137a8b10`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=4, jsonl_line=1545; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `direct`; **Difficulty:** `EASY`
- **Evidence:** Điều 4. Mục đích của hoạt động thông tin tín dụng Hoạt động thông tin tín dụng nhằm tạo lập Cơ sở dữ liệu thông tin tín dụng quốc gia để: 1. Ngân hàng Nhà nước thực hiện chức năng quản lý nhà nước trong lĩnh vực tiền tệ, ngân hàng. 2. Hỗ trợ tổ chức tín dụng, tổ chức tự nguyện trong hoạt động kinh doanh. 3. Hỗ trợ khách hàng vay tiếp cận nguồn vốn tín dụng đáp ứng nhu cầu đời sống, kinh tế, xã hội theo quy định của pháp luật. 4. Hỗ trợ tổ chức khác tiếp cận thông tin tín dụng theo quy định của pháp luật.
- **Rationale:** Điều 4 liệt kê ba mục tiêu: quản lý nhà nước, hỗ trợ kinh doanh của tổ chức cung cấp tín dụng và hỗ trợ khách hàng tiếp cận vốn.
- **Status:** `DRAFT`

### stage13e-075

- **Scope:** `customer_relationship`
- **Question:** Việc cung cấp thông tin tín dụng cho CIC phải tuân thủ những nguyên tắc nào về dữ liệu và quyền lợi của các bên?
- **Expected canonical chunk ID:** `46c98aee9a9690e685f955c2b51175a280229cc916a8710d3629a2acdd26cbb0`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, jsonl_line=1546; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 5. Nguyên tắc hoạt động thông tin tín dụng 1. Tuân thủ quy định của pháp luật về bảo vệ dữ liệu cá nhân và các quy định pháp luật khác có liên quan. 2. Đảm bảo tính khách quan và không ảnh hưởng đến quyền, lợi ích hợp pháp của các tổ chức, cá nhân có liên quan. 3. Đảm bảo chính xác, trung thực, đầy đủ, kịp thời đối với thông tin tín dụng cung cấp cho CIC quy định tại Điều 8, Điều 9, Điều 10 Thông tư này.
- **Rationale:** Điều 5 yêu cầu tuân thủ bảo vệ dữ liệu cá nhân, khách quan, không xâm phạm quyền hợp pháp và bảo đảm thông tin chính xác, đầy đủ, kịp thời.
- **Status:** `DRAFT`

### stage13e-076

- **Scope:** `customer_relationship`
- **Question:** CIC và các tổ chức được cung cấp thông tin tín dụng phải áp dụng những biện pháp nào để bảo vệ và khôi phục dữ liệu?
- **Expected canonical chunk ID:** `b0acf083b89104474bc9e65b101b6bc1bd7566fc6e8025bfdb0d89d0633b3268`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, jsonl_line=1547; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 6. An toàn, bảo mật thông tin tín dụng CIC, tổ chức tín dụng, tổ chức tự nguyện, tổ chức khác được cung cấp thông tin tín dụng phải: 1. Có biện pháp bảo vệ thông tin tín dụng để chống lại mất mát, truy cập, sử dụng hoặc tiết lộ trái phép. 2. Có giải pháp khôi phục dữ liệu trong trường hợp dữ liệu bị lỗi, bị mất, bị hỏng và phương án khôi phục hoạt động sau khi dữ liệu bị lỗi, bị mất, bị hỏng. 3. Đảm bảo an toàn, bảo mật thông tin tín dụng theo quy định tại Thông tư này và các quy định khác của pháp luật về an toàn, bảo mật thông tin.
- **Rationale:** Điều 6 yêu cầu chống mất mát, truy cập hoặc tiết lộ trái phép và có giải pháp khôi phục dữ liệu, hoạt động khi xảy ra sự cố.
- **Status:** `DRAFT`

### stage13e-077

- **Scope:** `customer_relationship`
- **Question:** CIC được phép thu thập thông tin tín dụng từ những nguồn nào?
- **Expected canonical chunk ID:** `198e64ef61ab853deae852106e730f12697583991614c3ca385c5d0a56a61a84`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=8, jsonl_line=1549; heading `Chương II HOẠT ĐỘNG THÔNG TIN TÍN DỤNG`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 8. Thu thập thông tin CIC được thu thập: 1. Thông tin tín dụng do tổ chức tín dụng, tổ chức tự nguyện cung cấp theo quy định tại Thông tư này. 2. Thông tin từ các đơn vị thuộc Ngân hàng Nhà nước theo quy định của Ngân hàng Nhà nước và các quy định liên quan khác của pháp luật. 3. Thông tin từ các cơ quan quản lý nhà nước, các nguồn thông tin hợp pháp khác theo quy định của pháp luật.
- **Rationale:** Điều 8 chỉ rõ thông tin do tổ chức tín dụng, đơn vị thuộc Ngân hàng Nhà nước, cơ quan quản lý và nguồn hợp pháp cung cấp.
- **Status:** `DRAFT`

### stage13e-078

- **Scope:** `customer_relationship`
- **Question:** CIC phải lưu giữ thông tin tín dụng tối thiểu trong bao lâu và xử lý dữ liệu bằng những bước nghiệp vụ nào?
- **Expected canonical chunk ID:** `1230bcd9233f1b5d799b19b575975c9203c2d536c9ffb012952cc059396c882b`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, jsonl_line=1552; heading `Chương II HOẠT ĐỘNG THÔNG TIN TÍN DỤNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 11. Xử lý, lưu giữ thông tin tín dụng 1. CIC sử dụng các giải pháp công nghệ, kỹ thuật về nghiệp vụ tiếp nhận, chuẩn hóa, làm sạch, ghép nối và cập nhật để xử lý thông tin tín dụng của Cơ sở dữ liệu thông tin tín dụng quốc gia. 2. Thông tin tín dụng được lưu giữ tại CIC trong thời gian tối thiểu 05 năm kể từ ngày phát sinh. 3. Việc xử lý, lưu giữ thông tin tín dụng phải bảo đảm tính toàn vẹn, đầy đủ, không bị sai lệch thông tin và khai thác, chiết xuất được theo nhu cầu của CIC.
- **Rationale:** Điều 11 nêu các bước tiếp nhận, chuẩn hóa, làm sạch, ghép nối, cập nhật và thời gian lưu giữ tối thiểu 5 năm.
- **Status:** `DRAFT`

### stage13e-079

- **Scope:** `customer_relationship`
- **Question:** CIC có những quyền và trách nhiệm nào trong việc kiểm tra, giám sát và công khai dịch vụ thông tin tín dụng?
- **Expected canonical chunk ID:** `2c9d41c83adf98dcd0152091e8edb779629a37d77128752313edd11ad7f8ee94`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=14, jsonl_line=1555; heading `Chương III QUYỀN VÀ NGHĨA VỤ CỦA TỔ CHỨC, CÁ NHÂN TRONG HOẠT ĐỘNG THÔNG TIN TÍN DỤNG`
- **Question type:** `customer-facing`; **Difficulty:** `EASY`
- **Evidence:** Điều 14. Quyền và nghĩa vụ của CIC 1. Đầu mối xây dựng, trình Thống đốc Ngân hàng Nhà nước ban hành Quyết định về Hệ thống chỉ tiêu thông tin tín dụng. 2. Đôn đốc, kiểm tra, giám sát việc cung cấp thông tin tín dụng của tổ chức tín dụng và việc thực hiện hoạt động thông tin tín dụng của tổ chức tự nguyện theo hợp đồng ký kết với CIC. 3. Công khai các nguyên tắc, phạm vi sử dụng dịch vụ thông tin tín dụng, quy trình khai thác và sử dụng dịch vụ thông tin tín dụng, giá dịch vụ thông tin tín dụng. 4. Tạo lập sản phẩm thông tin tín dụng để cung cấp theo đề nghị của các đơn vị thuộc Ngân hàng Nhà nước theo quy định tại khoản 1 Điều 12 Thông tư này. 5. Hỗ trợ đào tạo cán bộ về nghiệp vụ thông tin tín dụng theo nhu cầu của tổ chức tín dụng, tổ chức tự nguyện. 6. Tổ chức cung cấp dịch vụ thông tin tín dụng theo mô hình đơn vị sự nghiệp công lập và thực hiện cơ chế tự chủ tài chính theo quy định…
- **Rationale:** Điều 14 giao cho CIC đầu mối xây dựng hệ thống chỉ tiêu, đôn đốc kiểm tra giám sát và công khai nguyên tắc, phạm vi, quy trình dịch vụ.
- **Status:** `DRAFT`

### stage13e-080

- **Scope:** `customer_relationship`
- **Question:** Tổ chức tín dụng phải xây dựng hạ tầng, kiểm soát dữ liệu và thực hiện nghĩa vụ thanh toán dịch vụ CIC như thế nào?
- **Expected canonical chunk ID:** `21e6d15ab5cbaf1c89d289ded68f69104ef6503be1c6e049655d491caaec89e3`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=16, jsonl_line=1557; heading `Chương III QUYỀN VÀ NGHĨA VỤ CỦA TỔ CHỨC, CÁ NHÂN TRONG HOẠT ĐỘNG THÔNG TIN TÍN DỤNG`
- **Question type:** `role`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 16. Quyền và nghĩa vụ của tổ chức tín dụng 1. Thiết lập cơ sở hạ tầng thông tin đáp ứng yêu cầu tạo lập dữ liệu, kiểm soát dữ liệu cung cấp cho CIC; ban hành các quy định nội bộ và quản lý hệ thống chỉ tiêu thông tin tín dụng trong toàn hệ thống. 2. Thanh toán đầy đủ, đúng hạn tiền khai thác, sử dụng dịch vụ thông tin tín dụng theo hợp đồng ký kết với CIC. 3. Cử cán bộ, nhân viên tham gia các khóa đào tạo nghiệp vụ thông tin tín dụng do CIC tổ chức hoặc phối hợp tổ chức. 4. Thực hiện các quyền, nghĩa vụ khác theo thỏa thuận với CIC và quy định liên quan của pháp luật.
- **Rationale:** Điều 16 quy định hạ tầng dữ liệu, quy định nội bộ, quản lý hệ thống chỉ tiêu và nghĩa vụ thanh toán đúng hạn.
- **Status:** `DRAFT`

### stage13e-081

- **Scope:** `customer_relationship`
- **Question:** Khách hàng vay được khai thác miễn phí thông tin tín dụng về chính mình với tần suất và phạm vi nào?
- **Expected canonical chunk ID:** `20569490d543947ae89ccd77b49a888ad3406a8d12d449980dfcf139f1cc5f12`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=18, jsonl_line=1559; heading `Chương III QUYỀN VÀ NGHĨA VỤ CỦA TỔ CHỨC, CÁ NHÂN TRONG HOẠT ĐỘNG THÔNG TIN TÍN DỤNG`
- **Question type:** `customer-facing`; **Difficulty:** `EASY`
- **Evidence:** Điều 18. Quyền và nghĩa vụ của khách hàng vay 1. Được khai thác miễn phí đối với thông tin tín dụng về chính khách hàng vay quy định tại điểm a, c, d, đ, e, h khoản 1 Điều 9 và khoản 4 Điều 12 Thông tư này một lần trong một năm. 2. Sử dụng sản phẩm thông tin tín dụng về chính khách hàng vay theo hướng dẫn của CIC. 3. Thanh toán đầy đủ, đúng hạn tiền khai thác, sử dụng dịch vụ thông tin tín dụng theo quy định của CIC. 4. Thực hiện các quyền, nghĩa vụ khác theo quy định của CIC và quy định liên quan của pháp luật.
- **Rationale:** Điều 18 cho phép khai thác miễn phí một lần trong một năm đối với các nhóm thông tin của chính khách hàng và yêu cầu theo hướng dẫn CIC.
- **Status:** `DRAFT`

### stage13e-082

- **Scope:** `customer_relationship`
- **Question:** Nếu tổ chức tín dụng phát hiện dữ liệu tại CIC có sai sót thì phải thông báo và đề nghị điều chỉnh theo cách nào?
- **Expected canonical chunk ID:** `5d140fa6e9d6665d6dc8db579b7ff4e934f2cb05f92884356030788e59ef30f6`
- **Source:** Quy định về hoạt động thông tin tín dụng của Ngân hàng Nhà nước Việt Nam (`v2-07-15-2023-tt-nhnn` / `v2-07-15-2023-tt-nhnn-2023-12-05-5de19f587bf4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=19, clause=2, jsonl_line=1564; heading `Chương IV ĐIỀU CHỈNH DỮ LIỆU SAI SÓT VÀ XỬ LÝ VI PHẠM`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** 2. Trường hợp tổ chức tín dụng, tổ chức tự nguyện phát hiện dữ liệu tại CIC có sai sót, tổ chức tín dụng, tổ chức tự nguyện thông báo qua hệ thống điện tử hoặc gửi bằng văn bản đề nghị CIC điều chỉnh. Nếu CIC xác minh sai sót do CIC, trong thời hạn 03 ngày làm việc kể từ ngày xác minh sai sót, CIC thực hiện điều chỉnh dữ liệu theo yêu cầu.
- **Rationale:** Khoản 2 Điều 19 nêu hình thức thông báo qua hệ thống điện tử hoặc văn bản và thời hạn CIC xử lý khi xác minh lỗi thuộc về mình.
- **Status:** `DRAFT`

### stage13e-083

- **Scope:** `customer_relationship`
- **Question:** Hồ sơ cho sản phẩm vốn lưu động SME không bảo đảm phải bao gồm những nhóm tài liệu chính nào, và xử lý ra sao nếu thiếu chứng cứ trọng yếu?
- **Expected canonical chunk ID:** `61dc9e901fd1c303e9b6969e1037bf5a9a3c1009bb4c3e018a0b242e2294d2ce`
- **Source:** SME Unsecured Working Capital Product Policy (`synthetic-sme-working-capital-v1` / `synthetic-sme-working-capital-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=PROD-DOCUMENTS, jsonl_line=1584; heading `SME Unsecured Working Capital Product Policy › ## 4. Evidence, CIC, and renewal`
- **Question type:** `internal-policy`; **Difficulty:** `MEDIUM`
- **Evidence:** Rule ID: PROD-DOCUMENTS. Required documents are registration and authority evidence; ownership and management information; two completed fiscal-year financial packages where available; latest interim or trailing-12-month data; 12-month bank statements; tax/revenue corroboration; a debt schedule; and a purpose budget with supporting invoices or contracts. Missing or contradictory material evidence is a hold/refer outcome, never an inferred pass.
- **Rationale:** Quy tắc sản phẩm liệt kê nhóm hồ sơ định danh, tài chính, ngân hàng, thuế, nợ và mục đích; thiếu hoặc mâu thuẫn trọng yếu phải hold/refer.
- **Status:** `DRAFT`

### stage13e-084

- **Scope:** `customer_relationship`
- **Question:** Khi gia hạn khoản vay theo sản phẩm SME vốn lưu động, doanh nghiệp có được tự động gia hạn hay phải trải qua bước nào?
- **Expected canonical chunk ID:** `37d51e982dafab7f3052aa1c6c5a8befc584f62e09d974f8cf83376ab83b784a`
- **Source:** SME Unsecured Working Capital Product Policy (`synthetic-sme-working-capital-v1` / `synthetic-sme-working-capital-v1.2026-09-01`)
- **Visibility:** `SCOPED`; provenance `synthetic`
- **Locator:** article=PROD-RENEWAL, jsonl_line=1586; heading `SME Unsecured Working Capital Product Policy › ## 4. Evidence, CIC, and renewal`
- **Question type:** `internal-policy`; **Difficulty:** `EASY`
- **Evidence:** Rule ID: PROD-RENEWAL. At renewal, the borrower must undergo a new product, underwriting, and approval review. Any material change or expiry follows [[APR-REAPPROVAL]]; the product does not automatically roll over.
- **Rationale:** Quy tắc gia hạn xác định đây là một lần rà soát mới về sản phẩm, thẩm định và phê duyệt, không phải tự động chuyển tiếp.
- **Status:** `DRAFT`

### stage13e-085

- **Scope:** `collateral_appraisal`
- **Question:** Tài sản hình thành từ quyền bề mặt hoặc quyền hưởng dụng có thể được dùng để bảo đảm trong những trường hợp nào?
- **Expected canonical chunk ID:** `706e98b9f3e669b9a891e344046b667c01499fa03c414480ef09404f70736a63`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=11, jsonl_line=968; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `direct`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 11. Tài sản được tạo lập từ quyền bề mặt, quyền hưởng dụng 1. Tài sản thuộc sở hữu của chủ thể quyền bề mặt quy định tại khoản 2 Điều 271 của Bộ luật Dân sự được dùng để bảo đảm thực hiện nghĩa vụ. Trường hợp tài sản quy định tại khoản này là tài sản gắn liền với đất thì áp dụng quy định tại khoản 1 và khoản 2 Điều 9, các khoản 1, 2 và 3 Điều 10 Nghị định này. 2. Hoa lợi, lợi tức hoặc tài sản khác có được từ việc khai thác, sử dụng tài sản là đối tượng của quyền hưởng dụng được dùng để bảo đảm thực hiện nghĩa vụ.
- **Rationale:** Điều 11 xác định tài sản thuộc quyền bề mặt và hoa lợi, lợi tức hoặc tài sản có được từ quyền hưởng dụng có thể dùng để bảo đảm.
- **Status:** `DRAFT`

### stage13e-086

- **Scope:** `collateral_appraisal`
- **Question:** Giấy tờ có giá, chứng khoán và số dư tiền gửi có thể dùng để bảo đảm với yêu cầu mô tả nào?
- **Expected canonical chunk ID:** `ac99a10ab4e57fc4013fe363131235df356ba5d1bd0adb0fc3c042362c708a58`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=13, jsonl_line=970; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 13. Giấy tờ có giá, chứng khoán, số dư tiền gửi Giấy tờ có giá, chứng khoán, số dư tiền gửi tại tổ chức tín dụng, chi nhánh ngân hàng nước ngoài được dùng để bảo đảm thực hiện nghĩa vụ nhưng việc mô tả tài sản bảo đảm phải phù hợp với quy định của pháp luật về giấy tờ có giá, chứng khoán, ngân hàng.
- **Rationale:** Điều 13 cho phép dùng các tài sản này nhưng yêu cầu phần mô tả phù hợp pháp luật về từng loại tài sản và lĩnh vực liên quan.
- **Status:** `DRAFT`

### stage13e-087

- **Scope:** `collateral_appraisal`
- **Question:** Quyền tài sản nào phát sinh từ hợp đồng có thể được dùng để bảo đảm thực hiện nghĩa vụ?
- **Expected canonical chunk ID:** `240447a1cae11affd718c3e814a984d3baac0dafdb997aa2d7ab080838d5b8da`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=14, jsonl_line=971; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `direct`; **Difficulty:** `EASY`
- **Evidence:** Điều 14. Quyền tài sản phát sinh từ hợp đồng Bên có quyền trong hợp đồng được dùng quyền đòi nợ, các khoản phải thu, quyền yêu cầu thanh toán khác; quyền khai thác, quản lý dự án đầu tư; quyền cho thuê, cho thuê lại; quyền hưởng hoa lợi, lợi tức, lợi ích khác trị giá được bằng tiền hình thành từ hợp đồng; quyền được bồi thường thiệt hại; quyền khác trị giá được bằng tiền phát sinh từ hợp đồng để bảo đảm thực hiện nghĩa vụ.
- **Rationale:** Điều 14 liệt kê quyền đòi nợ, khoản phải thu, quyền thanh toán, quyền khai thác dự án, quyền cho thuê và các quyền có giá trị bằng tiền.
- **Status:** `DRAFT`

### stage13e-088

- **Scope:** `collateral_appraisal`
- **Question:** Cổ phần, phần vốn góp và quyền mua phần vốn góp được dùng làm tài sản bảo đảm trong điều kiện nào?
- **Expected canonical chunk ID:** `a76a3cea1b86dbb52993c7f73eec0cfd88c456e31a175e18fdc7bce305feeaad`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=15, jsonl_line=972; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `direct`; **Difficulty:** `EASY`
- **Evidence:** Điều 15. Tài sản hình thành từ việc góp vốn Chủ thể góp vốn được dùng cổ phần, phần vốn góp, quyền mua phần vốn góp hoặc lợi tức phát sinh từ cổ phần, phần vốn góp trong pháp nhân thương mại, pháp nhân phi thương mại là doanh nghiệp xã hội để bảo đảm thực hiện nghĩa vụ theo quy định của pháp luật liên quan và điều lệ của pháp nhân (nếu có).
- **Rationale:** Điều 15 xác định chủ thể góp vốn có thể dùng các quyền và lợi tức phát sinh để bảo đảm theo pháp luật liên quan và điều lệ.
- **Status:** `DRAFT`

### stage13e-089

- **Scope:** `collateral_appraisal`
- **Question:** Quyền khai thác tài nguyên thiên nhiên và sản phẩm từ quyền đó có thể được sử dụng làm tài sản bảo đảm ra sao?
- **Expected canonical chunk ID:** `aebb8c052c311305680ae81015d422df59092fffed51d41270cecece8f50d8ad`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=16, jsonl_line=973; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `direct`; **Difficulty:** `HARD`
- **Evidence:** Điều 16. Quyền khai thác tài nguyên thiên nhiên Chủ thể có quyền khai thác tài nguyên thiên nhiên theo quy định của pháp luật liên quan được dùng quyền khai thác khoáng sản; sản phẩm của rừng tự nhiên, trừ động vật; hải sản tự nhiên, bao gồm động vật và thực vật biển; tài nguyên nước, bao gồm nước mặt, nước biển và nước dưới đất, trừ nước thiên nhiên dùng cho nông nghiệp, lâm nghiệp, ngư nghiệp, diêm nghiệp; yến sào thiên nhiên; quyền khai thác tài nguyên thiên nhiên khác trị giá được bằng tiền để bảo đảm thực hiện nghĩa vụ. Việc dùng quyền khai thác khoáng sản, quyền khai thác tài nguyên thiên nhiên khác để bảo đảm thực hiện nghĩa vụ quy định tại Điều này phải phù hợp với quy định của pháp luật về khoáng sản, pháp luật về tài nguyên thiên nhiên khác.
- **Rationale:** Điều 16 quy định nhóm quyền khai thác và tài sản, sản phẩm có giá trị bằng tiền được dùng để bảo đảm theo pháp luật liên quan.
- **Status:** `DRAFT`

### stage13e-090

- **Scope:** `collateral_appraisal`
- **Question:** Dự án đầu tư và tài sản thuộc dự án có thể được dùng để bảo đảm theo những giới hạn nào?
- **Expected canonical chunk ID:** `41923c68f8e47b91bca1491d6d813c783bf53ab052f0ee4816bd0e9397f4506c`
- **Source:** Quy định thi hành Bộ luật Dân sự về bảo đảm thực hiện nghĩa vụ (`v2-04-21-2021-nd-cp` / `v2-04-21-2021-nd-cp-2021-03-19-83c5805f1fa4`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=18, jsonl_line=975; heading `Chương II TÀI SẢN BẢO ĐẢM`
- **Question type:** `procedural`; **Difficulty:** `HARD`
- **Evidence:** Điều 18. Dự án đầu tư, tài sản thuộc dự án đầu tư Chủ đầu tư được dùng dự án đầu tư mà Luật Đầu tư, luật khác liên quan không cấm chuyển nhượng để bảo đảm thực hiện nghĩa vụ. Chủ đầu tư có thể dùng toàn bộ dự án đầu tư, quyền tài sản của mình về khai thác, quản lý dự án đầu tư và quyền tài sản khác hoặc tài sản khác thuộc dự án đầu tư để bảo đảm thực hiện nghĩa vụ. Trường hợp dự án đầu tư dùng để bảo đảm thực hiện nghĩa vụ là dự án xây dựng nhà ở, dự án xây dựng công trình không phải là nhà ở, dự án khác mà theo quy định của pháp luật liên quan phải có Giấy chứng nhận, Quyết định của cơ quan nhà nước có thẩm quyền hoặc căn cứ pháp lý khác thì việc mô tả trong hợp đồng bảo đảm phải thể hiện được căn cứ pháp lý này.
- **Rationale:** Điều 18 cho phép dùng dự án không bị cấm chuyển nhượng cùng quyền và tài sản thuộc dự án, đồng thời nêu các điều kiện liên quan.
- **Status:** `DRAFT`

### stage13e-091

- **Scope:** `collateral_appraisal`
- **Question:** Những trường hợp đăng ký biện pháp bảo đảm nào được Nghị định liệt kê, bao gồm đăng ký thay đổi và xóa đăng ký?
- **Expected canonical chunk ID:** `fa4f032bdc82782dc88a9cc12f1cdf508aba057da8cea274dd6056ee7baa86f1`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=4, jsonl_line=1050; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** Điều 4. Các trường hợp đăng ký 1. Các trường hợp đăng ký bao gồm: a) Đăng ký thế chấp tài sản, cầm cố tài sản, bảo lưu quyền sở hữu theo quy định của Bộ luật Dân sự, luật khác liên quan; b) Đăng ký theo thỏa thuận giữa bên bảo đảm và bên nhận bảo đảm hoặc theo yêu cầu của bên nhận bảo đảm, trừ cầm giữ tài sản; c) Đăng ký thông báo xử lý tài sản bảo đảm trong trường hợp một tài sản được dùng để bảo đảm thực hiện nhiều nghĩa vụ mà có nhiều bên cùng nhận bảo đảm hoặc trong trường hợp bên bảo đảm và bên nhận bảo đảm có thỏa thuận; d) Đăng ký thay đổi nội dung đã được đăng ký (sau đây gọi là đăng ký thay đổi); xóa đăng ký nội dung đã được đăng ký (sau đây gọi là xóa đăng ký) đối với trường hợp quy định tại các điểm a, b và c khoản này. 2. Việc đăng ký được thực hiện tại cơ quan có thẩm quyền đăng ký quy định tại Điều 10 Nghị định này.
- **Rationale:** Điều 4 liệt kê đăng ký thế chấp, cầm cố, bảo lưu quyền sở hữu, đăng ký theo thỏa thuận và các trường hợp thay đổi, xóa đăng ký.
- **Status:** `DRAFT`

### stage13e-092

- **Scope:** `collateral_appraisal`
- **Question:** Khi đăng ký đối với quyền sử dụng đất hoặc tài sản gắn liền với đất, nội dung kê khai và giấy tờ phải phù hợp với thông tin nào?
- **Expected canonical chunk ID:** `5676a7e4f20cac99ce3d918a858d43ae50d3524c6edac40048f60ffa97c8dc43`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=5, clause=3, jsonl_line=1054; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `procedural`; **Difficulty:** `MEDIUM`
- **Evidence:** 3. Việc đăng ký đối với quyền sử dụng đất, tài sản gắn liền với đất; quyền sử dụng khu vực biển, tài sản gắn liền với khu vực biển hoặc đối với tàu bay, tàu biển phải đảm bảo nội dung được kê khai và các giấy tờ trong hồ sơ đăng ký phù hợp với thông tin trên Giấy chứng nhận, thông tin được lưu giữ tại cơ quan đăng ký, trừ trường hợp tài sản được quy định tại khoản 5 Điều này, khoản 1, khoản 3 Điều 36 và Điều 37 Nghị định này.
- **Rationale:** Khoản 3 Điều 5 yêu cầu sự phù hợp với Giấy chứng nhận và thông tin lưu giữ tại cơ quan đăng ký, kèm các ngoại lệ được dẫn chiếu.
- **Status:** `DRAFT`

### stage13e-093

- **Scope:** `collateral_appraisal`
- **Question:** Thời hạn có hiệu lực của đăng ký biện pháp bảo đảm được tính từ thời điểm nào và dùng để xác định vấn đề gì?
- **Expected canonical chunk ID:** `d4ef8036b567e2993e19eb9d15876ae76ec6641cf729a5c649afaebc22629a2d`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=6, clause=1, point=b, jsonl_line=1059; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `consequence`; **Difficulty:** `MEDIUM`
- **Evidence:** b) Thời hạn có hiệu lực của đăng ký được tính từ thời điểm có hiệu lực của đăng ký đến thời điểm xóa đăng ký. Thời hạn có hiệu lực của đăng ký là căn cứ để xác định thời hạn có hiệu lực đối kháng của biện pháp bảo đảm với người thứ ba theo quy định của Bộ luật Dân sự, trừ trường hợp xác định hiệu lực đối kháng không chấm dứt quy định tại khoản 2 Điều này và trường hợp đăng ký thông báo xử lý tài sản bảo đảm quy định tại khoản 4 Điều này;
- **Rationale:** Điểm b khoản 1 Điều 6 xác định khoảng thời gian từ khi đăng ký có hiệu lực đến khi xóa, làm căn cứ xác định hiệu lực đối kháng.
- **Status:** `DRAFT`

### stage13e-094

- **Scope:** `collateral_appraisal`
- **Question:** Ai có thể là người yêu cầu đăng ký biện pháp bảo đảm?
- **Expected canonical chunk ID:** `8727155a84ef211878c46027806c79989fac62945d5b3e112ebee732308bc45e`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=8, clause=1, jsonl_line=1073; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** 1. Người yêu cầu đăng ký bao gồm bên nhận bảo đảm, bên bảo đảm; Quản tài viên; doanh nghiệp quản lý, thanh lý tài sản trong trường hợp doanh nghiệp, hợp tác xã mất khả năng thanh toán cho người khác vay tài sản nhưng không thực hiện việc đăng ký (sau đây gọi là doanh nghiệp quản lý, thanh lý tài sản).
- **Rationale:** Khoản 1 Điều 8 xác định bên nhận bảo đảm, bên bảo đảm và một số chủ thể quản lý tài sản trong trường hợp đặc biệt.
- **Status:** `DRAFT`

### stage13e-095

- **Scope:** `collateral_appraisal`
- **Question:** Người yêu cầu đăng ký có quyền nhận và kiểm tra kết quả đăng ký, cung cấp thông tin như thế nào?
- **Expected canonical chunk ID:** `26bd0fa66942d62fc76275a2ce262c623365a098e8cbf6459fffba105f56f6ad`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=9, clause=1, point=a, jsonl_line=1083; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** a) Nhận kết quả đăng ký, kết quả cung cấp thông tin; kiểm tra, đối chiếu 9 Khoản này được sửa đổi, bổ sung theo quy định tại khoản 4 Điều 11 của Nghị định số 18/2026/NĐ- CP sửa đổi, bổ sung một số nghị định để cắt giảm, đơn giản hóa thủ tục hành chính, điều kiện kinh doanh thuộc phạm vi quản lý của Bộ Tư pháp, có hiệu lực kể từ ngày 15 tháng 01 năm 2026. thông tin được đăng ký, được cung cấp; đề nghị cơ quan đăng ký quy định tại10 khoản 3 hoặc khoản 5 Điều 10 Nghị định này cấp bản sao văn bản chứng nhận đăng ký đối với trường hợp đăng ký thuộc thẩm quyền của cơ quan này;
- **Rationale:** Điểm a khoản 1 Điều 9 ghi nhận quyền nhận kết quả, kiểm tra đối chiếu và yêu cầu cấp bản sao trong trường hợp thuộc thẩm quyền.
- **Status:** `DRAFT`

### stage13e-096

- **Scope:** `collateral_appraisal`
- **Question:** Cơ quan nào thực hiện đăng ký và cung cấp thông tin về biện pháp bảo đảm bằng quyền sử dụng đất và tài sản gắn liền với đất?
- **Expected canonical chunk ID:** `41df9d9b1c0ffd2ad69b6af65b88940dad38729b2d25a448c40b20eb31bfd718`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=10, clause=1, jsonl_line=1097; heading `Chương I QUY ĐỊNH CHUNG`
- **Question type:** `role`; **Difficulty:** `EASY`
- **Evidence:** 1. Văn phòng đăng ký đất đai trực thuộc Sở Nông nghiệp và Môi trường11, Chi nhánh của Văn phòng đăng ký đất đai (sau đây gọi là Văn phòng đăng ký đất đai) thực hiện đăng ký, cung cấp thông tin về biện pháp bảo đảm bằng quyền sử dụng đất, tài sản gắn liền với đất quy định tại Điều 25 Nghị định này.
- **Rationale:** Khoản 1 Điều 10 giao nhiệm vụ cho Văn phòng đăng ký đất đai và chi nhánh trực thuộc.
- **Status:** `DRAFT`

### stage13e-097

- **Scope:** `collateral_appraisal`
- **Question:** Trong trường hợp đăng ký cầm cố, đặt cọc, ký cược hoặc ký quỹ, chữ ký của bên nào là đủ nếu không có thỏa thuận khác?
- **Expected canonical chunk ID:** `d7a8654cb4104ec3a1d95ce811a0d2d619bd800c2b0cc2d844245e236dd06383`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=12, clause=1, point=c, jsonl_line=1110; heading `Chương II › Mục 1 THỦ TỤC CHUNG`
- **Question type:** `exception`; **Difficulty:** `MEDIUM`
- **Evidence:** c) Đăng ký cầm cố tài sản, đặt cọc, ký cược hoặc ký quỹ trong trường hợp pháp luật về bảo đảm thực hiện nghĩa vụ có quy định hoặc có thỏa thuận trong hợp đồng bảo đảm thì chỉ cần có chữ ký, con dấu (nếu có) của bên nhận bảo đảm, trừ trường hợp có thỏa thuận khác trong hợp đồng bảo đảm;
- **Rationale:** Điểm c khoản 1 Điều 12 quy định ngoại lệ chỉ cần chữ ký, con dấu nếu có, của bên nhận bảo đảm.
- **Status:** `DRAFT`

### stage13e-098

- **Scope:** `collateral_appraisal`
- **Question:** Những biện pháp bảo đảm bằng quyền sử dụng đất nào thuộc trường hợp phải đăng ký?
- **Expected canonical chunk ID:** `8f279fe3b263b4c7e22ecbfd637e0706d81de028d64519fa9bd2b353113366b0`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=25, clause=1, point=a, jsonl_line=1194; heading `Chương II › Mục 2 THỦ TỤC ĐĂNG KÝ BIỆN PHÁP BẢO ĐẢM BẰNG QUYỀN SỬ DỤNG ĐẤT, TÀI SẢN GẮN LIỀN VỚI ĐẤT`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** a) Thế chấp quyền sử dụng đất;
- **Rationale:** Điểm a khoản 1 Điều 25 nêu thế chấp quyền sử dụng đất là một trường hợp phải đăng ký tại Văn phòng đăng ký đất đai.
- **Status:** `DRAFT`

### stage13e-099

- **Scope:** `collateral_appraisal`
- **Question:** Những loại tài sản gắn liền với đất hình thành trong tương lai nào thuộc trường hợp đăng ký theo yêu cầu?
- **Expected canonical chunk ID:** `0ae00994d45d376ad388d335c9865ee97b6e509bd12910d0309c9ad5d5c52e26`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=25, clause=2, point=a, jsonl_line=1199; heading `Chương II › Mục 2 THỦ TỤC ĐĂNG KÝ BIỆN PHÁP BẢO ĐẢM BẰNG QUYỀN SỬ DỤNG ĐẤT, TÀI SẢN GẮN LIỀN VỚI ĐẤT`
- **Question type:** `exception`; **Difficulty:** `HARD`
- **Evidence:** a) Thế chấp nhà ở hình thành trong tương lai, tài sản khác gắn liền với đất hình thành trong tương lai; b)24 Thế chấp tài sản gắn liền với đất không thuộc trường hợp đăng ký tài sản gắn liền với đất theo quy định của pháp luật về đất đai hoặc thuộc trường hợp đăng ký tài sản gắn liền với đất theo quy định của pháp luật về đất đai mà không phải là nhà ở nhưng chưa được đăng ký quyền sở hữu theo yêu cầu, trừ 24 Điểm này được sửa đổi, bổ sung theo quy định tại khoản 7 Điều 11 của Nghị định số 18/2026/NĐ- CP sửa đổi, bổ sung một số nghị định để cắt giảm, đơn giản hóa thủ tục hành chính, điều kiện kinh doanh thuộc phạm vi quản lý của Bộ Tư pháp, có hiệu lực kể từ ngày 15 tháng 01 năm 2026. trường hợp quy định tại khoản 9 Điều này;
- **Rationale:** Điểm a khoản 2 Điều 25 nêu nhà ở hình thành trong tương lai và tài sản khác gắn liền với đất hình thành trong tương lai.
- **Status:** `DRAFT`

### stage13e-100

- **Scope:** `collateral_appraisal`
- **Question:** Hồ sơ đăng ký đối với quyền sử dụng đất và tài sản gắn liền với đất đã được chứng nhận quyền sở hữu gồm những giấy tờ chính nào?
- **Expected canonical chunk ID:** `a3d808aa44f60109e597c77871cbe3efca1e9f520623f26846c058510a206bb1`
- **Source:** Về đăng ký biện pháp bảo đảm (`v2-05-2161-vbhn-btp` / `v2-05-2161-vbhn-btp-2026-04-07-9a6298b60a4a`)
- **Visibility:** `SHARED`; provenance `real_authoritative`
- **Locator:** article=27, jsonl_line=1228; heading `Chương II › Mục 2 THỦ TỤC ĐĂNG KÝ BIỆN PHÁP BẢO ĐẢM BẰNG QUYỀN SỬ DỤNG ĐẤT, TÀI SẢN GẮN LIỀN VỚI ĐẤT`
- **Question type:** `procedural`; **Difficulty:** `EASY`
- **Evidence:** Điều 27. Hồ sơ đăng ký đối với quyền sử dụng đất, tài sản gắn liền với đất đã được chứng nhận quyền sở hữu 1. Phiếu yêu cầu theo Mẫu số 01a tại Phụ lục (01 bản chính). 2. Hợp đồng bảo đảm hoặc hợp đồng bảo đảm có công chứng, chứng thực trong trường hợp Luật Đất đai, Luật Nhà ở, luật khác có liên quan quy định (01 bản chính hoặc 01 bản sao có chứng thực). 3. Giấy chứng nhận (bản gốc), trừ trường hợp quy định tại khoản 2 Điều 35 Nghị định này.
- **Rationale:** Điều 27 yêu cầu phiếu đăng ký, hợp đồng bảo đảm trong trường hợp luật định và Giấy chứng nhận bản gốc, trừ ngoại lệ được dẫn chiếu.
- **Status:** `DRAFT`
