"""Build the Stage 13E1 expanded, evidence-first gold draft.

This builder deliberately has no retrieval or embedding dependency.  The 75
new questions below are hand-authored from explicitly selected frozen corpus
chunks.  The released 25-query pilot is copied byte-for-byte as the seed and
is never rewritten by this script.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
REVIEW_PATH = PROJECT_ROOT / "docs/STAGE-13E-EXPANDED-GOLD-REVIEW.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
ASSESSMENT_DATE = "2026-09-04"
CREATED_AT = "2026-09-04T00:00:00+07:00"


# scope, query_type, question_category, difficulty, source_id, chunk_id,
# question, rationale, additional tags
ITEM_SPECS: list[tuple[str, str, str, str, str, str, str, str, tuple[str, ...]]] = [
    # Credit: 9 real + 4 synthetic = 13 new records.
    (
        "credit", "ELIGIBILITY_SUPPORT", "direct", "EASY",
        "v2-01-86-vbhn-nhnn", "9e09807aa04909fe587454b7b4f1cbe921e102e61cdc5c41b4fc67d2be31fafd",
        "Tổ chức tín dụng có được tự quyết định việc cho vay và từ chối yêu cầu nào của khách hàng?",
        "Đoạn quy định trực tiếp nêu quyền tự chủ, trách nhiệm về quyết định cho vay và quyền từ chối yêu cầu không phù hợp.",
        ("autonomy",),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "multi-condition", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "72a7bd225e92fa731fc15d274322d6c4d0dd9eb548617086f10a78a9fcc8b0da",
        "Khi thỏa thuận khoản vay, khách hàng phải tuân thủ những nguyên tắc cơ bản nào về mục đích sử dụng vốn và nghĩa vụ trả nợ?",
        "Một điều khoản thống nhất quy định sự phù hợp pháp luật, sử dụng vốn đúng cam kết và hoàn trả gốc, lãi, phí đúng hạn.",
        ("lending-principles",),
    ),
    (
        "credit", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-01-86-vbhn-nhnn", "6e4da03b8692ea04b1ce067f23086978a3415d102d305d33f09ec0c70715ff55",
        "Thỏa thuận cho vay và tài liệu tiếng nước ngoài phải được lập hoặc xử lý về ngôn ngữ như thế nào?",
        "Điều khoản quy định ngôn ngữ của thỏa thuận và yêu cầu đối với bản dịch tài liệu nước ngoài khi cơ quan có thẩm quyền yêu cầu.",
        ("loan-agreement", "language"),
    ),
    (
        "credit", "CALCULATION_GUIDANCE", "threshold", "EASY",
        "v2-01-86-vbhn-nhnn", "ca52689c760027aec0d39512b40a3c846e0d5417e06c4bee74b4b80c1fd80c88",
        "Khoản vay được phân loại ngắn hạn, trung hạn và dài hạn theo thời hạn tối đa hoặc khoảng thời gian nào?",
        "Điều 10 đưa ra ba mốc thời hạn rõ ràng để phân biệt các loại cho vay.",
        ("tenor",),
    ),
    (
        "credit", "POLICY_LOOKUP", "distinction", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "1009b017e9829f54c351506fe7866c8f05ef623bdaf5944d2ddaaeb244549a6a",
        "Đồng tiền cho vay và đồng tiền trả nợ được xác định theo nguyên tắc nào, và có thể trả bằng đồng tiền khác hay không?",
        "Điều khoản phân biệt đồng tiền cho vay với đồng tiền trả nợ và nêu điều kiện trả nợ bằng đồng tiền khác.",
        ("currency",),
    ),
    (
        "credit", "CALCULATION_GUIDANCE", "procedural", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "f56c28eac7f0aa3918928954c05c3e3c02adbfe344b5bbfa39fba5f17cc67f28",
        "Thỏa thuận về lãi suất cần thể hiện những thông tin nào về cách xác định và tính lãi?",
        "Đoạn được chọn quy định các thành phần của thỏa thuận lãi suất, gồm mức lãi và phương pháp tính, kể cả quy đổi theo năm khi cần.",
        ("interest",),
    ),
    (
        "credit", "POLICY_LOOKUP", "threshold", "EASY",
        "v2-01-86-vbhn-nhnn", "89d802df285c87a1361ee6a584eaa4b686c4fcb4fa674d2b953984e66be02119",
        "Những loại phí nào có thể được thỏa thuận khi tổ chức tín dụng thực hiện hoạt động cho vay?",
        "Điều 14 liệt kê các nhóm phí liên quan đến khoản vay, bao gồm phí trả trước hạn, hạn mức dự phòng và các loại phí khác theo quy định.",
        ("fees",),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "procedural", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "3b5d373d32f4f75f8ba3b9018190661b2d43e31c3ac57fc5c684a4072a9f9723",
        "Biện pháp bảo đảm tiền vay do ai thỏa thuận và ai chịu trách nhiệm khi khoản vay không áp dụng bảo đảm?",
        "Điều 15 đặt việc áp dụng bảo đảm hoặc không áp dụng trong thỏa thuận, đồng thời phân định trách nhiệm của tổ chức tín dụng.",
        ("security",),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "procedural", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "239da504404561b4f3127a6ae5ae8b69a3420ea22dd0182f2d69776c455ab5a7",
        "Trong thẩm định khoản vay, tổ chức tín dụng có thể sử dụng những nguồn thông tin nào và phải tách bạch khâu thẩm định với quyết định ra sao?",
        "Điều 17 trực tiếp đề cập hệ thống xếp hạng tín dụng nội bộ, CIC, các kênh thông tin khác và yêu cầu tổ chức độc lập hai khâu.",
        ("appraisal",),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "internal-policy", "EASY",
        "synthetic-sme-working-capital-v1", "fdda9f09341a7d3fa905eaf8f7c08e84ebf42e1c3130919836f312e6bb9d14aa",
        "Đối tượng khách hàng mục tiêu của sản phẩm vốn lưu động SME không bảo đảm phải đáp ứng những đặc điểm nền tảng nào?",
        "Quy tắc sản phẩm nêu tình trạng đăng ký, quyền sở hữu minh bạch, hoạt động hợp pháp và nhu cầu vốn lưu động có thể chứng minh.",
        ("synthetic", "product-eligibility"),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "internal-policy", "MEDIUM",
        "synthetic-sme-working-capital-v1", "c097149aa99ebd76ad16de38e8c6264407e6f75dc0f52933171b25f5cb31f9de",
        "Vốn lưu động theo chính sách sản phẩm có thể được dùng cho những nhu cầu vận hành nào và cần chứng minh bằng hồ sơ gì?",
        "Quy tắc liệt kê các nhu cầu vận hành được phép và yêu cầu ngân sách mục đích cùng hóa đơn hoặc hợp đồng hỗ trợ.",
        ("synthetic", "purpose"),
    ),
    (
        "credit", "CALCULATION_GUIDANCE", "threshold", "EASY",
        "synthetic-sme-underwriting-v1", "091aa50fc0b4c61d328f77a7dce21fb53717691ad6aa9a78cb58bca57798c561",
        "Ngưỡng DSCR chuẩn, khoảng ngoại lệ mềm và mức bị từ chối cứng trong thẩm định là bao nhiêu?",
        "Quy tắc UW-DSCR nêu công thức, ngưỡng chuẩn 1,30, khoảng 1,15 đến dưới 1,30 và mức dưới 1,15.",
        ("synthetic", "dscr"),
    ),
    (
        "credit", "ELIGIBILITY_SUPPORT", "internal-policy", "HARD",
        "synthetic-credit-approval-v1", "459549a81e609b0873fef571ec14740da30e756e49fc433b4dae18fed47cffdd",
        "Trường hợp có đúng hai ngoại lệ mềm thì cấp phê duyệt nào được xem xét và phải đáp ứng các điều kiện kiểm soát nào?",
        "Quy tắc Tier 4 tập hợp đúng số ngoại lệ, khoảng tổng dư nợ, việc không có hard stop, đồng thuận độc lập và yêu cầu ghi nhận hồ sơ.",
        ("synthetic", "approval-tier"),
    ),

    # Risk management: 11 real + 4 synthetic = 15 new records.
    (
        "risk_management", "POLICY_LOOKUP", "role", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17",
        "Ngân hàng phải thu thập và khai thác thông tin khách hàng để phục vụ những hoạt động quản trị rủi ro nào?",
        "Điều 4 nối việc thu thập thông tin từ khách hàng, CIC và nguồn hợp pháp với xếp hạng nội bộ, quản lý nợ và chính sách dự phòng.",
        ("credit-information",),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "multi-condition", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "395e0af21b02c1e28c5b77ab5aada1b5c467642d6981dcd1a95310602bff2b62",
        "Một hệ thống xếp hạng tín dụng nội bộ cần bao gồm những nhóm chỉ tiêu và quy trình đánh giá nào?",
        "Đoạn quy định mô tả cả chỉ tiêu tài chính, phi tài chính và quy trình đánh giá khả năng trả nợ trên cơ sở định tính, định lượng.",
        ("internal-rating",),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "distinction", "EASY",
        "v2-03-27-vbhn-nhnn", "a3d9c4cfed50131485a712a8caa5a2c896c09a47ef669da81f98ceaf6cfc85b6",
        "Các mức xếp hạng trong hệ thống xếp hạng tín dụng nội bộ phải phản ánh rủi ro theo chiều hướng nào?",
        "Điểm được chọn yêu cầu các mức xếp hạng tương ứng với mức độ rủi ro từ thấp đến cao.",
        ("internal-rating", "risk-level"),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "role", "EASY",
        "v2-03-27-vbhn-nhnn", "a121373c1059401ad80332f18177f4b699504982e57bd249615de1739ef85f37",
        "Cấp quản lý nào phải phê duyệt việc áp dụng hệ thống xếp hạng tín dụng nội bộ?",
        "Đoạn quy định trực tiếp xác định thẩm quyền phê duyệt của Hội đồng quản trị, Hội đồng thành viên hoặc Tổng giám đốc/Giám đốc tùy loại hình.",
        ("internal-rating", "approval"),
    ),
    (
        "risk_management", "ELIGIBILITY_SUPPORT", "role", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "165a10eba0349fe3d478ef9a74b9e2395ed3c8dab550f50d38eb02195d01f850",
        "Những tổ chức nào bắt buộc phải xây dựng hệ thống xếp hạng tín dụng nội bộ và hệ thống này được sử dụng cho các quyết định nào?",
        "Khoản 3 phân biệt nghĩa vụ của ngân hàng, chi nhánh ngân hàng nước ngoài với tổ chức tín dụng phi ngân hàng và nêu các mục đích sử dụng.",
        ("internal-rating",),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-03-27-vbhn-nhnn", "9fae0dd5446c0d4d80cfbe172a345de541e1bb1fa8a559793e54402e8fd40d85",
        "Trong thời hạn bao lâu sau khi ban hành hoặc sửa đổi hệ thống xếp hạng tín dụng nội bộ phải gửi hồ sơ cho Ngân hàng Nhà nước?",
        "Khoản 4 Điều 5 đặt thời hạn 10 ngày kể từ ngày ban hành hoặc sửa đổi, bổ sung hệ thống.",
        ("internal-rating", "reporting"),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "role", "EASY",
        "v2-03-27-vbhn-nhnn", "3f212b4c7d07d612fc0b95203d562875d9a96e60769ee5d76353d64f80b20714",
        "Tổ chức tín dụng phải ban hành quy định nội bộ về cấp tín dụng, quản lý nợ và dự phòng rủi ro theo những căn cứ nào?",
        "Điều 6 yêu cầu các quy định nội bộ phù hợp với thông tư, nghị định về trích lập dự phòng và pháp luật liên quan.",
        ("internal-policy",),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "consequence", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "97b77dbc674e0906068c9a1204d682722411655d2ff7a25dfaa5a05f045318a8",
        "Quy định nội bộ phải kiểm soát việc tuân thủ những giới hạn và tỷ lệ an toàn nào trong hoạt động?",
        "Điểm được chọn yêu cầu quy định quản lý để bảo đảm tuân thủ các giới hạn và tỷ lệ bảo đảm an toàn của Ngân hàng Nhà nước.",
        ("internal-policy", "prudential-ratios"),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "procedural", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "3e9f616cb4df9720ccae4a91b386f99552665bb5045a3a1254e1223462857329",
        "Quy định về định giá tài sản bảo đảm cần nêu những nguyên tắc và trách nhiệm nào để phục vụ trích lập dự phòng?",
        "Đoạn quy định yêu cầu nêu nguyên tắc, định kỳ, phương pháp, quy trình và trách nhiệm liên quan đến định giá theo giá thị trường.",
        ("collateral", "valuation"),
    ),
    (
        "risk_management", "ELIGIBILITY_SUPPORT", "threshold", "MEDIUM",
        "v2-03-27-vbhn-nhnn", "d60763f0e2492f623c47f61b62b93cf2de3e9cdbb041227f577635f81b3b3a7f",
        "Hệ thống xếp hạng tín dụng nội bộ phải phù hợp với những yếu tố nào và cần có thời gian thử nghiệm tối thiểu bao lâu để phục vụ phân loại nợ định tính?",
        "Điểm a khoản 2 Điều 11 yêu cầu hệ thống phù hợp với hoạt động, đối tượng khách hàng và tính chất rủi ro, đồng thời có thời gian thử nghiệm tối thiểu một năm.",
        ("qualitative-classification", "internal-rating"),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "multi-condition", "HARD",
        "v2-03-27-vbhn-nhnn", "3ca22b44b947c9ce57f7b0a10a52e53e769dcd5f4690e0d11474b4f50b345b34",
        "Mô hình quản lý rủi ro tín dụng cần xác định và đo lường những yếu tố nào khi phân loại nợ?",
        "Điểm được chọn yêu cầu chính sách, mô hình giám sát, phương pháp đo lường rủi ro, khả năng trả nợ, tài sản bảo đảm và quản lý nợ.",
        ("credit-risk",),
    ),
    (
        "risk_management", "ELIGIBILITY_SUPPORT", "internal-policy", "MEDIUM",
        "synthetic-sme-underwriting-v1", "cacf65f29fb78465914db68e7327d40eb2ef8d8006226785589836130f4bba3d",
        "Khâu thẩm định SME phải xác minh những nhóm thông tin nào trước khi đề xuất xếp hạng và tuyến phê duyệt?",
        "Quy tắc thẩm định liệt kê danh tính, sở hữu, quản lý, ngành, mục đích, hồ sơ, khả năng trả nợ và các yếu tố tập trung.",
        ("synthetic", "underwriting"),
    ),
    (
        "risk_management", "POLICY_LOOKUP", "internal-policy", "MEDIUM",
        "synthetic-sme-underwriting-v1", "e2a4618512d93fae606e27380bfb7ee1ea2451f7895e1c66bde3481e048bce9d",
        "Khi rà soát CIC và dư nợ của doanh nghiệp, bộ phận thẩm định phải thực hiện những việc kiểm tra nào?",
        "Quy tắc yêu cầu lấy và ghi ngày chứng cứ CIC, nhận diện nợ quá hạn và đối chiếu toàn bộ nghĩa vụ nợ.",
        ("synthetic", "cic", "debt"),
    ),
    (
        "risk_management", "CALCULATION_GUIDANCE", "threshold", "EASY",
        "synthetic-sme-underwriting-v1", "0699b242d383e109e4a7aaba9870038f936c723272d465661fdfa171eedf27d2",
        "Tỷ lệ nợ trên vốn chủ sở hữu chuẩn, khoảng ngoại lệ mềm và mức từ chối cứng trong chính sách là bao nhiêu?",
        "Quy tắc UW-LEVERAGE nêu rõ mẫu số, việc tính cả dư nợ hiện hữu và đề xuất, cùng ba vùng ngưỡng.",
        ("synthetic", "leverage"),
    ),
    (
        "risk_management", "ELIGIBILITY_SUPPORT", "exception", "HARD",
        "synthetic-credit-approval-v1", "59aa9152d01a6a9f99183f3e79e6d12e3d69a0e03f00bf50b7876554deecacc9",
        "Một hồ sơ Grade C có ngoại lệ mềm phải ghi nhận những nội dung gì, và Grade C-EXCEPTION-2 bị giới hạn ra sao?",
        "Quy tắc phê duyệt yêu cầu nêu ngoại lệ, chứng cứ, nguyên nhân, biện pháp giảm thiểu, rủi ro còn lại và giới hạn tuyến Tier 4.",
        ("synthetic", "exceptions"),
    ),

    # Legal/compliance: 9 source02 + 2 source06 + 4 synthetic = 15 new records.
    (
        "legal_compliance", "POLICY_LOOKUP", "distinction", "EASY",
        "v2-02-100-vbhn-vpqh", "ec3d7284decf237b019ea4cc861a9db511c3b04ba308156578f913f621ec26a9",
        "Các loại tổ chức tín dụng trong nước được tổ chức dưới những hình thức pháp lý nào?",
        "Điều 6 phân biệt hình thức công ty cổ phần, công ty trách nhiệm hữu hạn và hợp tác xã theo từng loại tổ chức.",
        ("legal-form",),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "customer-facing", "MEDIUM",
        "v2-02-100-vbhn-vpqh", "04740a512de500891274f929289034e762e3ed266e6c795d153261d9666f05fc",
        "Tổ chức tín dụng phải công khai và bảo vệ quyền lợi khách hàng trong những nội dung giao dịch nào?",
        "Điều 10 quy định nhiều trách nhiệm trực tiếp với khách hàng, trong đó có bảo hiểm tiền gửi, công khai lãi phí và xử lý tiền gửi.",
        ("customer-protection",),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "role", "MEDIUM",
        "v2-02-100-vbhn-vpqh", "9a0d7836e282df3805ba8936a001028442b771d0a46df6945d8b82e99b509ea9",
        "Người đại diện theo pháp luật của tổ chức tín dụng phải đáp ứng điều kiện cư trú và ủy quyền như thế nào khi vắng mặt?",
        "Điều 11 quy định người đại diện phải cư trú tại Việt Nam và phải ủy quyền bằng văn bản khi vắng mặt.",
        ("legal-representative",),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "role", "MEDIUM",
        "v2-02-100-vbhn-vpqh", "5f25b1e41a0d54e45a7b36650b960a65bff99fc48a358482b75295f2fdd997b1",
        "Khi giao dịch với tổ chức tín dụng, khách hàng phải cung cấp thông tin và chịu trách nhiệm về thông tin đó ra sao?",
        "Khoản 4 Điều 12 yêu cầu thông tin, tài liệu và dữ liệu trung thực, chính xác, đầy đủ, kịp thời và gắn với trách nhiệm của khách hàng.",
        ("customer-information",),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "consequence", "EASY",
        "v2-02-100-vbhn-vpqh", "1c4d9d8498271cb60bc44c0e4621c783bb20388f687d9b630e98a09dea4aff0a",
        "Tổ chức tín dụng phải bảo đảm những yêu cầu nào đối với an toàn dữ liệu và hoạt động liên tục?",
        "Điều 14 trực tiếp yêu cầu an toàn hệ thống thông tin, bảo mật dữ liệu và hoạt động liên tục.",
        ("data-security",),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "consequence", "MEDIUM",
        "v2-02-100-vbhn-vpqh", "2674bf7a078ff0ceb2d74a7fba652d73e2f085093123ba286ef801c388ea7d40",
        "Những nhóm hành vi nào bị nghiêm cấm đối với tổ chức tín dụng và chủ thể không phải tổ chức tín dụng?",
        "Điều 15 là điều khoản cấm, bao quát hoạt động ngoài giấy phép, can thiệp trái pháp luật và cạnh tranh gây hại cho hệ thống.",
        ("prohibition",),
    ),
    (
        "legal_compliance", "ELIGIBILITY_SUPPORT", "threshold", "EASY",
        "v2-02-100-vbhn-vpqh", "da0d6919546dac223a5be5ba23a9acc26b6c8b6ef0f4d08e8eb0ff2da46da21f",
        "Điều kiện về vốn điều lệ tối thiểu khi xin cấp Giấy phép tổ chức tín dụng được quy định thế nào?",
        "Điểm a khoản 1 Điều 29 nêu trực tiếp yêu cầu vốn điều lệ tối thiểu bằng mức vốn pháp định.",
        ("licensing", "capital"),
    ),
    (
        "legal_compliance", "ELIGIBILITY_SUPPORT", "direct", "MEDIUM",
        "v2-02-100-vbhn-vpqh", "ea917efb3c02eea3c24145d0d2edf2d065a9bd31f4922898952e09008c9779a2",
        "Đề án thành lập và phương án kinh doanh phải đáp ứng yêu cầu gì khi xin cấp phép tổ chức tín dụng?",
        "Điểm đ khoản 1 Điều 29 yêu cầu đề án và phương án khả thi, đồng thời không gây ảnh hưởng đến an toàn, ổn định hoặc cạnh tranh.",
        ("licensing", "business-plan"),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "threshold", "EASY",
        "v2-02-100-vbhn-vpqh", "14d689a75e5e7d15027aab6432b1f9f6b88acfc4005093bbbb5734a8e3d4f871",
        "Ngân hàng Nhà nước có thời hạn bao lâu để cấp hoặc từ chối cấp Giấy phép sau khi nhận đủ hồ sơ hợp lệ?",
        "Điều 31 tách thời hạn 180 ngày cho tổ chức tín dụng, chi nhánh ngân hàng nước ngoài và 60 ngày cho văn phòng đại diện.",
        ("licensing", "deadline"),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-06-80-2021-nd-cp", "2533ca7a0a8797990c30c9417057be2a2e7ad60e8de81b196874f23fcdd2d7b5",
        "Lĩnh vực hoạt động của doanh nghiệp nhỏ và vừa được xác định căn cứ vào thông tin nào?",
        "Điều 6 quy định căn cứ là ngành, nghề kinh doanh chính đã đăng ký với cơ quan đăng ký kinh doanh.",
        ("sme", "classification"),
    ),
    (
        "legal_compliance", "CALCULATION_GUIDANCE", "procedural", "MEDIUM",
        "v2-06-80-2021-nd-cp", "d9fa4d73b0e1aaf263c5bea1560d91be0121d783ff746560466ba1fbaae5b508",
        "Tổng nguồn vốn của doanh nghiệp nhỏ và vừa được xác định từ báo cáo nào, và xử lý thế nào nếu doanh nghiệp hoạt động dưới một năm?",
        "Điều 8 chỉ rõ báo cáo tài chính năm trước liền kề và mốc cuối quý liền kề cho doanh nghiệp hoạt động dưới một năm.",
        ("sme", "capital"),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "internal-policy", "MEDIUM",
        "synthetic-sme-working-capital-v1", "338978ec37adbbe3d82b9c6ea2378d9a887797ce5b92510fa4496a66547c207b",
        "Những mục đích sử dụng vốn hoặc ngành nghề nào là hard stop trong chính sách SME vốn lưu động?",
        "Quy tắc loại trừ liệt kê các mục đích đầu tư đầu cơ, trả nợ quá hạn, ngành nghề bị loại và xác định đây là các hard stop.",
        ("synthetic", "hard-stop", "prohibited-purpose"),
    ),
    (
        "legal_compliance", "ELIGIBILITY_SUPPORT", "internal-policy", "HARD",
        "synthetic-sme-underwriting-v1", "bb54d68d09ea0a0da64db105c8507ad5d12b10aced13ecda0551ef9ffa157053",
        "Những tình huống nào bị coi là từ chối cứng và không thể được phê duyệt như một ngoại lệ?",
        "Quy tắc UW-HARD-STOPS nêu đầy đủ các ngưỡng rủi ro, thiếu hồ sơ, gian dối, ngành/mục đích bị loại và dòng tiền âm lặp lại.",
        ("synthetic", "hard-stop"),
    ),
    (
        "legal_compliance", "POLICY_LOOKUP", "role", "EASY",
        "synthetic-credit-approval-v1", "4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d",
        "Trong quy trình phê duyệt tín dụng, vai trò của RM, bộ phận thẩm định, Risk và người phê duyệt được tách biệt như thế nào?",
        "Quy tắc maker-checker mô tả người lập hồ sơ, khâu kiểm tra, phản biện độc lập và yêu cầu người phê duyệt tách khỏi maker.",
        ("synthetic", "maker-checker"),
    ),
    (
        "legal_compliance", "CALCULATION_GUIDANCE", "internal-policy", "EASY",
        "synthetic-credit-approval-v1", "917ebf28c65bf84a1883e40449107f1b04763fa062b4dfbc66329d0480b47842",
        "Phê duyệt tiêu chuẩn và phê duyệt ngoại lệ có thời hạn hiệu lực bao lâu nếu khoản vay chưa giải ngân?",
        "Quy tắc APR-VALIDITY đặt thời hạn 60 ngày cho phê duyệt chuẩn, 30 ngày cho phê duyệt ngoại lệ và yêu cầu phê duyệt lại khi hết hạn.",
        ("synthetic", "validity"),
    ),

    # Customer relationship: 14 real + 2 synthetic = 16 new records.
    (
        "customer_relationship", "POLICY_LOOKUP", "customer-facing", "MEDIUM",
        "v2-01-86-vbhn-nhnn", "dc61f5152d480e1be3b005c5dbe6b1f0a8acbe468c85b08dbceda8fa14a7cde4",
        "Trước khi ký thỏa thuận vay, khách hàng phải được cung cấp những thông tin chủ yếu nào?",
        "Điều 16 liệt kê các thông tin trước hợp đồng như lãi suất, cách tính lãi, phí, điều kiện và biện pháp bảo đảm.",
        ("customer-information",),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-01-86-vbhn-nhnn", "515d0ba7d04e7ad57ffe6994f2638a11a6a170bf1023b260c7aa7eb057d708b3",
        "Khách hàng và tổ chức tín dụng có thể thỏa thuận những cách nào để trả nợ gốc, lãi và trả nợ trước hạn?",
        "Điều 18 nêu trả gốc và lãi theo kỳ riêng hoặc cùng kỳ, đồng thời cho phép thỏa thuận về trả trước hạn.",
        ("repayment",),
    ),
    (
        "customer_relationship", "ELIGIBILITY_SUPPORT", "exception", "HARD",
        "v2-01-86-vbhn-nhnn", "fde373dfe29edf1ae993d7a1ebcc4eed07af589dd1a4ced7ca9414661b8b0908",
        "Khi nào tổ chức tín dụng có thể xem xét cơ cấu lại thời hạn trả nợ cho khách hàng?",
        "Điều 19 gắn việc cơ cấu với đề nghị của khách hàng, khả năng tài chính của tổ chức tín dụng và đánh giá khả năng trả nợ.",
        ("restructuring",),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "consequence", "EASY",
        "v2-01-86-vbhn-nhnn", "10a2f44d90c42f762ef1ef675aa112bd5e1339279b84ec5da34abd83dfda2ca2",
        "Khi nào dư nợ gốc bị chuyển thành nợ quá hạn và thông báo cho khách hàng phải có những thông tin tối thiểu nào?",
        "Điều 20 nêu điều kiện không trả đúng hạn và không được cơ cấu, cùng ba nội dung tối thiểu của thông báo.",
        ("overdue-debt",),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "consequence", "HARD",
        "v2-01-86-vbhn-nhnn", "49e326d4783e6fa8a225a31d8c9d167b23d7684259262d8f5728eae0d62927c0",
        "Những vi phạm nào có thể dẫn đến chấm dứt cho vay hoặc thu hồi nợ trước hạn?",
        "Điều 21 quy định quyền chấm dứt và thu hồi trước hạn trong trường hợp thông tin sai hoặc khách hàng vi phạm thỏa thuận, cùng các hướng xử lý nợ.",
        ("early-termination",),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "direct", "EASY",
        "v2-07-15-2023-tt-nhnn", "1b511053987c46a28a7d877e1ec72d100ef9fee5d3d831edba00a882137a8b10",
        "Cơ sở dữ liệu thông tin tín dụng quốc gia được lập ra để hỗ trợ những hoạt động nào của Nhà nước, tổ chức tín dụng và khách hàng vay?",
        "Điều 4 liệt kê ba mục tiêu: quản lý nhà nước, hỗ trợ kinh doanh của tổ chức cung cấp tín dụng và hỗ trợ khách hàng tiếp cận vốn.",
        ("credit-information",),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "consequence", "MEDIUM",
        "v2-07-15-2023-tt-nhnn", "46c98aee9a9690e685f955c2b51175a280229cc916a8710d3629a2acdd26cbb0",
        "Việc cung cấp thông tin tín dụng cho CIC phải tuân thủ những nguyên tắc nào về dữ liệu và quyền lợi của các bên?",
        "Điều 5 yêu cầu tuân thủ bảo vệ dữ liệu cá nhân, khách quan, không xâm phạm quyền hợp pháp và bảo đảm thông tin chính xác, đầy đủ, kịp thời.",
        ("credit-information", "data-quality"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "consequence", "MEDIUM",
        "v2-07-15-2023-tt-nhnn", "b0acf083b89104474bc9e65b101b6bc1bd7566fc6e8025bfdb0d89d0633b3268",
        "CIC và các tổ chức được cung cấp thông tin tín dụng phải áp dụng những biện pháp nào để bảo vệ và khôi phục dữ liệu?",
        "Điều 6 yêu cầu chống mất mát, truy cập hoặc tiết lộ trái phép và có giải pháp khôi phục dữ liệu, hoạt động khi xảy ra sự cố.",
        ("credit-information", "security"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-07-15-2023-tt-nhnn", "198e64ef61ab853deae852106e730f12697583991614c3ca385c5d0a56a61a84",
        "CIC được phép thu thập thông tin tín dụng từ những nguồn nào?",
        "Điều 8 chỉ rõ thông tin do tổ chức tín dụng, đơn vị thuộc Ngân hàng Nhà nước, cơ quan quản lý và nguồn hợp pháp cung cấp.",
        ("credit-information", "collection"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "procedural", "MEDIUM",
        "v2-07-15-2023-tt-nhnn", "1230bcd9233f1b5d799b19b575975c9203c2d536c9ffb012952cc059396c882b",
        "CIC phải lưu giữ thông tin tín dụng tối thiểu trong bao lâu và xử lý dữ liệu bằng những bước nghiệp vụ nào?",
        "Điều 11 nêu các bước tiếp nhận, chuẩn hóa, làm sạch, ghép nối, cập nhật và thời gian lưu giữ tối thiểu 5 năm.",
        ("credit-information", "retention"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "customer-facing", "EASY",
        "v2-07-15-2023-tt-nhnn", "2c9d41c83adf98dcd0152091e8edb779629a37d77128752313edd11ad7f8ee94",
        "CIC có những quyền và trách nhiệm nào trong việc kiểm tra, giám sát và công khai dịch vụ thông tin tín dụng?",
        "Điều 14 giao cho CIC đầu mối xây dựng hệ thống chỉ tiêu, đôn đốc kiểm tra giám sát và công khai nguyên tắc, phạm vi, quy trình dịch vụ.",
        ("credit-information", "cic"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "role", "MEDIUM",
        "v2-07-15-2023-tt-nhnn", "21e6d15ab5cbaf1c89d289ded68f69104ef6503be1c6e049655d491caaec89e3",
        "Tổ chức tín dụng phải xây dựng hạ tầng, kiểm soát dữ liệu và thực hiện nghĩa vụ thanh toán dịch vụ CIC như thế nào?",
        "Điều 16 quy định hạ tầng dữ liệu, quy định nội bộ, quản lý hệ thống chỉ tiêu và nghĩa vụ thanh toán đúng hạn.",
        ("credit-information", "institution-duty"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "customer-facing", "EASY",
        "v2-07-15-2023-tt-nhnn", "20569490d543947ae89ccd77b49a888ad3406a8d12d449980dfcf139f1cc5f12",
        "Khách hàng vay được khai thác miễn phí thông tin tín dụng về chính mình với tần suất và phạm vi nào?",
        "Điều 18 cho phép khai thác miễn phí một lần trong một năm đối với các nhóm thông tin của chính khách hàng và yêu cầu theo hướng dẫn CIC.",
        ("credit-information", "borrower-rights"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "procedural", "MEDIUM",
        "v2-07-15-2023-tt-nhnn", "5d140fa6e9d6665d6dc8db579b7ff4e934f2cb05f92884356030788e59ef30f6",
        "Nếu tổ chức tín dụng phát hiện dữ liệu tại CIC có sai sót thì phải thông báo và đề nghị điều chỉnh theo cách nào?",
        "Khoản 2 Điều 19 nêu hình thức thông báo qua hệ thống điện tử hoặc văn bản và thời hạn CIC xử lý khi xác minh lỗi thuộc về mình.",
        ("credit-information", "correction"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "internal-policy", "MEDIUM",
        "synthetic-sme-working-capital-v1", "61dc9e901fd1c303e9b6969e1037bf5a9a3c1009bb4c3e018a0b242e2294d2ce",
        "Hồ sơ cho sản phẩm vốn lưu động SME không bảo đảm phải bao gồm những nhóm tài liệu chính nào, và xử lý ra sao nếu thiếu chứng cứ trọng yếu?",
        "Quy tắc sản phẩm liệt kê nhóm hồ sơ định danh, tài chính, ngân hàng, thuế, nợ và mục đích; thiếu hoặc mâu thuẫn trọng yếu phải hold/refer.",
        ("synthetic", "documents"),
    ),
    (
        "customer_relationship", "POLICY_LOOKUP", "internal-policy", "EASY",
        "synthetic-sme-working-capital-v1", "37d51e982dafab7f3052aa1c6c5a8befc584f62e09d974f8cf83376ab83b784a",
        "Khi gia hạn khoản vay theo sản phẩm SME vốn lưu động, doanh nghiệp có được tự động gia hạn hay phải trải qua bước nào?",
        "Quy tắc gia hạn xác định đây là một lần rà soát mới về sản phẩm, thẩm định và phê duyệt, không phải tự động chuyển tiếp.",
        ("synthetic", "renewal"),
    ),

    # Collateral appraisal: 6 source04 + 10 source05 = 16 new real records.
    (
        "collateral_appraisal", "POLICY_LOOKUP", "direct", "MEDIUM",
        "v2-04-21-2021-nd-cp", "706e98b9f3e669b9a891e344046b667c01499fa03c414480ef09404f70736a63",
        "Tài sản hình thành từ quyền bề mặt hoặc quyền hưởng dụng có thể được dùng để bảo đảm trong những trường hợp nào?",
        "Điều 11 xác định tài sản thuộc quyền bề mặt và hoa lợi, lợi tức hoặc tài sản có được từ quyền hưởng dụng có thể dùng để bảo đảm.",
        ("collateral",),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-04-21-2021-nd-cp", "ac99a10ab4e57fc4013fe363131235df356ba5d1bd0adb0fc3c042362c708a58",
        "Giấy tờ có giá, chứng khoán và số dư tiền gửi có thể dùng để bảo đảm với yêu cầu mô tả nào?",
        "Điều 13 cho phép dùng các tài sản này nhưng yêu cầu phần mô tả phù hợp pháp luật về từng loại tài sản và lĩnh vực liên quan.",
        ("collateral", "financial-assets"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "direct", "EASY",
        "v2-04-21-2021-nd-cp", "240447a1cae11affd718c3e814a984d3baac0dafdb997aa2d7ab080838d5b8da",
        "Quyền tài sản nào phát sinh từ hợp đồng có thể được dùng để bảo đảm thực hiện nghĩa vụ?",
        "Điều 14 liệt kê quyền đòi nợ, khoản phải thu, quyền thanh toán, quyền khai thác dự án, quyền cho thuê và các quyền có giá trị bằng tiền.",
        ("collateral", "contract-rights"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "direct", "EASY",
        "v2-04-21-2021-nd-cp", "a76a3cea1b86dbb52993c7f73eec0cfd88c456e31a175e18fdc7bce305feeaad",
        "Cổ phần, phần vốn góp và quyền mua phần vốn góp được dùng làm tài sản bảo đảm trong điều kiện nào?",
        "Điều 15 xác định chủ thể góp vốn có thể dùng các quyền và lợi tức phát sinh để bảo đảm theo pháp luật liên quan và điều lệ.",
        ("collateral", "equity"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "direct", "HARD",
        "v2-04-21-2021-nd-cp", "aebb8c052c311305680ae81015d422df59092fffed51d41270cecece8f50d8ad",
        "Quyền khai thác tài nguyên thiên nhiên và sản phẩm từ quyền đó có thể được sử dụng làm tài sản bảo đảm ra sao?",
        "Điều 16 quy định nhóm quyền khai thác và tài sản, sản phẩm có giá trị bằng tiền được dùng để bảo đảm theo pháp luật liên quan.",
        ("collateral", "natural-resources"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "HARD",
        "v2-04-21-2021-nd-cp", "41923c68f8e47b91bca1491d6d813c783bf53ab052f0ee4816bd0e9397f4506c",
        "Dự án đầu tư và tài sản thuộc dự án có thể được dùng để bảo đảm theo những giới hạn nào?",
        "Điều 18 cho phép dùng dự án không bị cấm chuyển nhượng cùng quyền và tài sản thuộc dự án, đồng thời nêu các điều kiện liên quan.",
        ("collateral", "investment-project"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "MEDIUM",
        "v2-05-2161-vbhn-btp", "fa4f032bdc82782dc88a9cc12f1cdf508aba057da8cea274dd6056ee7baa86f1",
        "Những trường hợp đăng ký biện pháp bảo đảm nào được Nghị định liệt kê, bao gồm đăng ký thay đổi và xóa đăng ký?",
        "Điều 4 liệt kê đăng ký thế chấp, cầm cố, bảo lưu quyền sở hữu, đăng ký theo thỏa thuận và các trường hợp thay đổi, xóa đăng ký.",
        ("security-registration",),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "MEDIUM",
        "v2-05-2161-vbhn-btp", "5676a7e4f20cac99ce3d918a858d43ae50d3524c6edac40048f60ffa97c8dc43",
        "Khi đăng ký đối với quyền sử dụng đất hoặc tài sản gắn liền với đất, nội dung kê khai và giấy tờ phải phù hợp với thông tin nào?",
        "Khoản 3 Điều 5 yêu cầu sự phù hợp với Giấy chứng nhận và thông tin lưu giữ tại cơ quan đăng ký, kèm các ngoại lệ được dẫn chiếu.",
        ("security-registration", "land"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "consequence", "MEDIUM",
        "v2-05-2161-vbhn-btp", "d4ef8036b567e2993e19eb9d15876ae76ec6641cf729a5c649afaebc22629a2d",
        "Thời hạn có hiệu lực của đăng ký biện pháp bảo đảm được tính từ thời điểm nào và dùng để xác định vấn đề gì?",
        "Điểm b khoản 1 Điều 6 xác định khoảng thời gian từ khi đăng ký có hiệu lực đến khi xóa, làm căn cứ xác định hiệu lực đối kháng.",
        ("security-registration", "effectiveness"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "role", "EASY",
        "v2-05-2161-vbhn-btp", "8727155a84ef211878c46027806c79989fac62945d5b3e112ebee732308bc45e",
        "Ai có thể là người yêu cầu đăng ký biện pháp bảo đảm?",
        "Khoản 1 Điều 8 xác định bên nhận bảo đảm, bên bảo đảm và một số chủ thể quản lý tài sản trong trường hợp đặc biệt.",
        ("security-registration", "applicant"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "role", "EASY",
        "v2-05-2161-vbhn-btp", "26bd0fa66942d62fc76275a2ce262c623365a098e8cbf6459fffba105f56f6ad",
        "Người yêu cầu đăng ký có quyền nhận và kiểm tra kết quả đăng ký, cung cấp thông tin như thế nào?",
        "Điểm a khoản 1 Điều 9 ghi nhận quyền nhận kết quả, kiểm tra đối chiếu và yêu cầu cấp bản sao trong trường hợp thuộc thẩm quyền.",
        ("security-registration", "rights"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "role", "EASY",
        "v2-05-2161-vbhn-btp", "41df9d9b1c0ffd2ad69b6af65b88940dad38729b2d25a448c40b20eb31bfd718",
        "Cơ quan nào thực hiện đăng ký và cung cấp thông tin về biện pháp bảo đảm bằng quyền sử dụng đất và tài sản gắn liền với đất?",
        "Khoản 1 Điều 10 giao nhiệm vụ cho Văn phòng đăng ký đất đai và chi nhánh trực thuộc.",
        ("security-registration", "land"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "exception", "MEDIUM",
        "v2-05-2161-vbhn-btp", "d7a8654cb4104ec3a1d95ce811a0d2d619bd800c2b0cc2d844245e236dd06383",
        "Trong trường hợp đăng ký cầm cố, đặt cọc, ký cược hoặc ký quỹ, chữ ký của bên nào là đủ nếu không có thỏa thuận khác?",
        "Điểm c khoản 1 Điều 12 quy định ngoại lệ chỉ cần chữ ký, con dấu nếu có, của bên nhận bảo đảm.",
        ("security-registration", "signature"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-05-2161-vbhn-btp", "8f279fe3b263b4c7e22ecbfd637e0706d81de028d64519fa9bd2b353113366b0",
        "Những biện pháp bảo đảm bằng quyền sử dụng đất nào thuộc trường hợp phải đăng ký?",
        "Điểm a khoản 1 Điều 25 nêu thế chấp quyền sử dụng đất là một trường hợp phải đăng ký tại Văn phòng đăng ký đất đai.",
        ("security-registration", "land"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "exception", "HARD",
        "v2-05-2161-vbhn-btp", "0ae00994d45d376ad388d335c9865ee97b6e509bd12910d0309c9ad5d5c52e26",
        "Những loại tài sản gắn liền với đất hình thành trong tương lai nào thuộc trường hợp đăng ký theo yêu cầu?",
        "Điểm a khoản 2 Điều 25 nêu nhà ở hình thành trong tương lai và tài sản khác gắn liền với đất hình thành trong tương lai.",
        ("security-registration", "future-assets"),
    ),
    (
        "collateral_appraisal", "POLICY_LOOKUP", "procedural", "EASY",
        "v2-05-2161-vbhn-btp", "a3d808aa44f60109e597c77871cbe3efca1e9f520623f26846c058510a206bb1",
        "Hồ sơ đăng ký đối với quyền sử dụng đất và tài sản gắn liền với đất đã được chứng nhận quyền sở hữu gồm những giấy tờ chính nào?",
        "Điều 27 yêu cầu phiếu đăng ký, hợp đồng bảo đảm trong trường hợp luật định và Giấy chứng nhận bản gốc, trừ ngoại lệ được dẫn chiếu.",
        ("security-registration", "land-documents"),
    ),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compact(value: object) -> str:
    return " ".join(str(value).split())


def _display_excerpt(value: str, max_chars: int = 900) -> str:
    compact = _compact(value)
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rsplit(" ", 1)[0] + "…"


def _make_record(corpus: FrozenCorpusV2, number: int, spec: tuple[Any, ...]) -> dict[str, Any]:
    (
        scope,
        query_type,
        category,
        difficulty,
        source_id,
        chunk_id,
        query,
        rationale,
        extra_tags,
    ) = spec
    row = corpus.by_id.get(chunk_id)
    if row is None:
        raise ValueError(f"Selected canonical chunk does not exist: {chunk_id}")
    if row["source_id"] != source_id:
        raise ValueError(f"Chunk {chunk_id} is not from selected source {source_id}")
    source = corpus.source_identity(source_id)
    evidence = corpus.make_evidence(chunk_id, rationale, excerpt=_compact(row["content"]))
    visibility = "SCOPED" if source["synthetic"] else "SHARED"
    namespace = source["namespace"]
    return {
        "schema_version": "retrieval-gold-v2.0.0",
        "evaluation_id": f"stage13e-{number:03d}",
        "query": query,
        "query_type": query_type,
        "question_category": category,
        "difficulty": difficulty,
        "specialist_scope": scope,
        "assessment_date": ASSESSMENT_DATE,
        "filters": {"corpus_version": "V2", "namespace": namespace},
        "expected_canonical_chunk_ids": [chunk_id],
        "gold_evidence": [evidence],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": ["stage-13e-expanded-gold", scope, category, difficulty.casefold(), *extra_tags],
        "document": source,
        "visibility": visibility,
        "is_synthetic": source["synthetic"],
        "corpus_identity": corpus.corpus_identity,
        "embedding_identity": corpus.embedding_identity,
        "status": "DRAFT",
        "creation_provenance": {
            "method": "evidence_first_human_authored_draft",
            "evidence_source": "dataset/chunks/v2/policy-corpus-v2.jsonl",
            "generated_by": "stage13e_expanded_gold_builder",
            "created_at": CREATED_AT,
            "retrieval_used": False,
        },
        "review": None,
    }


def _load_seed_lines() -> list[str]:
    if _sha256(PILOT_PATH) != PILOT_SHA256:
        raise ValueError("Frozen Stage 12A pilot SHA-256 changed; refusing to build")
    lines = [line for line in PILOT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 25:
        raise ValueError(f"Frozen pilot contains {len(lines)} records, expected 25")
    seed = [json.loads(line) for line in lines]
    if any(item.get("status") != "REVIEWED" for item in seed):
        raise ValueError("Frozen pilot seed must contain only REVIEWED records")
    return lines


def _write_review(corpus: FrozenCorpusV2, records: list[dict[str, Any]]) -> None:
    seed_count = 25
    new_records = records[seed_count:]
    scope_counts = Counter(item["specialist_scope"] for item in records)
    provenance_counts = Counter("synthetic" if item["is_synthetic"] else "real_authoritative" for item in records)
    source_counts = Counter(item["document"]["source_id"] for item in records)
    category_counts = Counter(item.get("question_category", "uncategorized") for item in new_records)
    difficulty_counts = Counter(item.get("difficulty", "uncategorized") for item in new_records)
    lines = [
        "# Stage 13E — Expanded Retrieval Gold Review",
        "",
        "## Review scope",
        "",
        "This is an evidence-first human-review pack. The 25 Stage 12A records",
        "are the frozen REVIEWED seed and are referenced, not re-authored here.",
        "The 75 records below are new DRAFT questions derived from frozen Corpus V2",
        "chunks. No retrieval output, embedding ranking, FTS, or reranker was used",
        "to select their evidence. Human reviewers may approve, edit, or reject",
        "each new draft; automated tooling has not promoted any record.",
        "",
        f"- Corpus: `{corpus.corpus_identity['corpus_name']}` / {corpus.corpus_identity['chunk_count']} chunks",
        f"- Frozen seed: 25 REVIEWED records from `dataset/evaluation/retrieval-v2-gold-pilot.jsonl`",
        f"- New drafts: {len(new_records)} (`stage13e-026` through `stage13e-100`)",
        "- Status of every new item: `DRAFT`",
        "",
        "## Draft distribution",
        "",
        f"- By scope: {dict(sorted(scope_counts.items()))}",
        f"- By provenance: {dict(sorted(provenance_counts.items()))}",
        f"- New question categories: {dict(sorted(category_counts.items()))}",
        f"- New difficulty: {dict(sorted(difficulty_counts.items()))}",
        "",
        "## Frozen source coverage",
        "",
        "| Source ID | Records in combined set |",
        "|---|---:|",
    ]
    for source_id, count in sorted(source_counts.items()):
        lines.append(f"| `{source_id}` | {count} |")
    lines.extend(["", "## New DRAFT records", ""])
    for item in new_records:
        evidence = item["gold_evidence"][0]
        locator = evidence["locator"]
        locator_text = ", ".join(
            f"{key}={locator[key]}"
            for key in ("article", "clause", "point", "jsonl_line")
            if locator.get(key) is not None
        )
        lines.extend(
            [
                f"### {item['evaluation_id']}",
                "",
                f"- **Scope:** `{item['specialist_scope']}`",
                f"- **Question:** {item['query']}",
                f"- **Expected canonical chunk ID:** `{evidence['canonical_chunk_id']}`",
                f"- **Source:** {item['document']['title']} (`{item['document']['source_id']}` / `{item['document']['version_id']}`)",
                f"- **Visibility:** `{item['visibility']}`; provenance `{item['document']['provenance']}`",
                f"- **Locator:** {locator_text}; heading `{ ' › '.join(evidence['heading_path']) }`",
                f"- **Question type:** `{item['question_category']}`; **Difficulty:** `{item['difficulty']}`",
                f"- **Evidence:** { _display_excerpt(evidence['excerpt']) }",
                f"- **Rationale:** {evidence['rationale']}",
                "- **Status:** `DRAFT`",
                "",
            ]
        )
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build() -> tuple[list[dict[str, Any]], dict[str, int]]:
    seed_lines = _load_seed_lines()
    corpus = FrozenCorpusV2()
    if len(ITEM_SPECS) != 75:
        raise ValueError(f"Expected 75 new specs, found {len(ITEM_SPECS)}")
    records = [json.loads(line) for line in seed_lines]
    records.extend(_make_record(corpus, number, spec) for number, spec in enumerate(ITEM_SPECS, start=26))
    validator = CanonicalGoldValidator(corpus)
    for line_no, record in enumerate(records, start=1):
        validator.validate_record(record, records[: line_no - 1], line_no)
    statuses = Counter(item["status"] for item in records)
    if statuses != Counter({"REVIEWED": 25, "DRAFT": 75}):
        raise ValueError(f"Unexpected status distribution: {statuses}")
    expected_ids = {f"stage13e-{number:03d}" for number in range(26, 101)}
    actual_ids = {item["evaluation_id"] for item in records[25:]}
    if actual_ids != expected_ids:
        raise ValueError("New evaluation IDs are not exactly stage13e-026..stage13e-100")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        # Preserve the frozen seed lines exactly; only new drafts are serialized here.
        for line in seed_lines:
            handle.write(line + "\n")
        for record in records[25:]:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    _write_review(corpus, records)
    return records, dict(statuses)


if __name__ == "__main__":
    built_records, built_statuses = build()
    print(json.dumps({"records": len(built_records), "statuses": built_statuses, "output": str(OUTPUT_PATH), "review": str(REVIEW_PATH)}, ensure_ascii=False))
