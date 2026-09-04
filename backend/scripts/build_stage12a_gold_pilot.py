"""Build the evidence-first Stage 12A V2 gold-pilot draft.

The item definitions below are authored from frozen corpus evidence.  This
script never calls retrieval, Supabase, llama.cpp, or an embedding backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.eval.gold_v2 import (
    CanonicalGoldValidator,
    FrozenCorpusV2,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_JSONL = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.draft.jsonl"
OUTPUT_REVIEW = ROOT / "docs/STAGE-12A-GOLD-PILOT-REVIEW.md"
CREATED_AT = "2026-09-03T00:00:00+07:00"


PILOT_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "evaluation_id": "stage12a-001",
        "query": "Một doanh nghiệp có thể được xem xét cho vay khi cần chứng minh những điều kiện cốt lõi nào về tư cách pháp lý, mục đích, phương án sử dụng vốn và khả năng trả nợ?",
        "specialist_scope": "credit",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "1dc0f85ea8e685ea755e0402fe100f824606044d7d5aabb711fca1f915774e0d",
        "evidence_excerpt": "Điều 7. Điều kiện vay vốn Tổ chức tín dụng xem xét, quyết định cho vay khi khách hàng có đủ các điều kiện sau đây: 1. Khách hàng là pháp nhân có năng lực pháp luật dân sự theo quy định của pháp luật. Khách hàng là cá nhân từ đủ 18 tuổi trở lên có năng lực hành vi dân sự đầy đủ theo quy định của pháp luật hoặc từ đủ 15 tuổi đến chưa đủ 18 tuổi không bị mất hoặc hạn chế năng lực hành vi dân sự theo quy định của pháp luật. 2. Nhu cầu vay vốn để sử dụng vào mục đích hợp pháp. 3.13 Có phương án sử dụng vốn khả thi. Điều kiện này không bắt buộc đối với khoản cho vay có mức giá trị nhỏ. 4. Có khả năng tài chính để trả nợ.",
        "rationale": "Đoạn quy định tập hợp các điều kiện nền tảng để tổ chức tín dụng xem xét và quyết định cho vay đối với khách hàng là pháp nhân.",
        "tags": ["credit", "eligibility", "regulation"],
    },
    {
        "evaluation_id": "stage12a-002",
        "query": "Khoản vay có được dùng để mua vàng miếng hay thuộc trường hợp bị loại trừ?",
        "specialist_scope": "credit",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "a5be9a3a14423d608198bcb3d4c3fd5da34a1cb5fb9eca29d861357c7364e27b",
        "rationale": "Đoạn quy định nêu trực tiếp một nhu cầu vốn không được cho vay, phù hợp với câu hỏi về mục đích bị cấm.",
        "tags": ["credit", "prohibited-purpose", "regulation"],
    },
    {
        "evaluation_id": "stage12a-003",
        "query": "Khi thỏa thuận số tiền cho vay, tổ chức tín dụng phải cân nhắc những yếu tố nào từ phương án sử dụng vốn, khách hàng và nguồn vốn của mình?",
        "specialist_scope": "credit",
        "query_type": "CALCULATION_GUIDANCE",
        "chunk_id": "822ee29f7db162578ce65ef9d6a5865a296e2c8fe42ad978a9a11f591a2534dd",
        "rationale": "Đoạn quy định xác định các căn cứ phải dùng khi thỏa thuận mức cho vay, gồm phương án vốn, năng lực tài chính, giới hạn và nguồn vốn.",
        "tags": ["credit", "loan-amount", "regulation"],
    },
    {
        "evaluation_id": "stage12a-004",
        "query": "Một doanh nghiệp cần đáp ứng điều kiện pháp lý và tiêu chí nào để được xác định là doanh nghiệp nhỏ và vừa theo quy định được dẫn chiếu?",
        "specialist_scope": "credit",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "chunk_ids": [
            "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
            "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
        ],
        "evidence_excerpts": {
            "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c": "Điều 2. Đối tượng áp dụng 1. Doanh nghiệp được thành lập, tổ chức và hoạt động theo quy định của pháp luật về doanh nghiệp, đáp ứng các tiêu chí xác định doanh nghiệp nhỏ và vừa theo quy định tại Điều 5 Nghị định này.",
            "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78": "Điều 5. Tiêu chí xác định doanh nghiệp nhỏ và vừa 1. Doanh nghiệp siêu nhỏ trong lĩnh vực nông nghiệp, lâm nghiệp, thủy sản; lĩnh vực công nghiệp và xây dựng sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 10 người và tổng doanh thu của năm không quá 3 tỷ đồng hoặc tổng nguồn vốn của năm không quá 3 tỷ đồng. Doanh nghiệp siêu nhỏ trong lĩnh vực thương mại và dịch vụ sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 10 người và tổng doanh thu của năm không quá 10 tỷ đồng hoặc tổng nguồn vốn của năm không quá 3 tỷ đồng. 2. Doanh nghiệp nhỏ trong lĩnh vực nông nghiệp, lâm nghiệp, thủy sản; lĩnh vực công nghiệp và xây dựng sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 100 người và tổng doanh thu của năm không quá 50 tỷ đồng hoặc tổng nguồn vốn của năm không quá 20 tỷ đồng, nhưng không phải là doanh nghiệp siêu nhỏ theo quy định tại khoản 1 Điều này. Doanh nghiệp nhỏ trong lĩnh vực thương mại và dịch vụ sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 50 người và tổng doanh thu của năm không quá 100 tỷ đồng hoặc tổng nguồn vốn của năm không quá 50 tỷ đồng, nhưng không phải là doanh nghiệp siêu nhỏ theo quy định tại khoản 1 Điều này. 3. Doanh nghiệp vừa trong lĩnh vực nông nghiệp, lâm nghiệp, thủy sản; lĩnh vực công nghiệp và xây dựng sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 200 người và tổng doanh thu của năm không quá 200 tỷ đồng hoặc tổng nguồn vốn của năm không quá 100 tỷ đồng, nhưng không phải là doanh nghiệp siêu nhỏ, doanh nghiệp nhỏ theo quy định tại khoản 1, khoản 2 Điều này. Doanh nghiệp vừa trong lĩnh vực thương mại và dịch vụ sử dụng lao động có tham gia bảo hiểm xã hội bình quân năm không quá 100 người và tổng doanh thu của năm không quá 300 tỷ đồng hoặc tổng nguồn vốn của năm không quá 100 tỷ đồng, nhưng không phải là doanh nghiệp siêu nhỏ, doanh nghiệp nhỏ theo quy định tại khoản 1, khoản 2 Điều này."
        },
        "rationales": {
            "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c": "Điều 2 cung cấp điều kiện pháp lý khái quát và dẫn chiếu đến tiêu chí xác định doanh nghiệp nhỏ và vừa.",
            "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78": "Điều 5 cung cấp trực tiếp các ngưỡng lao động, doanh thu, nguồn vốn và điều kiện loại trừ giữa doanh nghiệp siêu nhỏ, nhỏ và vừa."
        },
        "rationale": "Đoạn quy định xác định doanh nghiệp phải được thành lập, tổ chức, hoạt động hợp pháp và đáp ứng tiêu chí doanh nghiệp nhỏ và vừa.",
        "tags": ["credit", "sme", "regulation"],
    },
    {
        "evaluation_id": "stage12a-005",
        "query": "Trong chính sách sản phẩm vốn lưu động không bảo đảm cho SME, ngưỡng doanh thu chuẩn được xác định ra sao và khoảng ngoại lệ mềm nào được phép xem xét?",
        "specialist_scope": "credit",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "99d4961f132513d92f2b4a60a10acb0b9caf285e71295765d3c0d25d543a3729",
        "rationale": "Quy tắc sản phẩm nêu ngưỡng doanh thu chuẩn, căn cứ thời kỳ đo lường và khoảng ngoại lệ có thể xem xét.",
        "tags": ["credit", "sme", "synthetic", "eligibility"],
    },
    {
        "evaluation_id": "stage12a-006",
        "query": "Một hồ sơ SME có DSCR từ 1,15 đến dưới 1,30 được phân loại thế nào, và mức nào là từ chối cứng?",
        "specialist_scope": "credit",
        "query_type": "CALCULATION_GUIDANCE",
        "chunk_id": "091aa50fc0b4c61d328f77a7dce21fb53717691ad6aa9a78cb58bca57798c561",
        "rationale": "Quy tắc bảo lãnh tín dụng nội bộ định nghĩa ngưỡng DSCR chuẩn, ngoại lệ mềm và sàn từ chối không thể vượt qua.",
        "tags": ["credit", "synthetic", "dscr", "risk"],
    },
    {
        "evaluation_id": "stage12a-007",
        "query": "Trong quy trình phê duyệt khoản vay SME, các vai trò lập hồ sơ, kiểm tra, thách thức rủi ro và phê duyệt phải được phân tách ra sao?",
        "specialist_scope": "credit",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d",
        "rationale": "Đoạn chính sách mô tả kiểm soát maker-checker và yêu cầu người phê duyệt độc lập với người lập đề nghị.",
        "tags": ["credit", "synthetic", "approval-controls"],
    },
    {
        "evaluation_id": "stage12a-008",
        "query": "Ngân hàng cần khai thác dữ liệu khách hàng và CIC để phục vụ những hoạt động quản trị tín dụng và rủi ro nào?",
        "specialist_scope": "risk_management",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17",
        "evidence_excerpt": "Điều 4. Thu thập số liệu, thông tin khách hàng và công nghệ thông tin 1. Ngân hàng, tổ chức tín dụng phi ngân hàng có biện pháp và thường xuyên thực hiện việc thu thập, khai thác thông tin, số liệu về khách hàng, bao gồm cả thông tin từ Trung tâm Thông tin tín dụng quốc gia Việt Nam (CIC), công ty thông tin tín dụng theo quy định của pháp luật để: a) Xây dựng, sửa đổi, bổ sung hệ thống xếp hạng tín dụng nội bộ, quy định nội bộ về cấp tín dụng, quản lý nợ, chính sách dự phòng rủi ro; b) Theo dõi, đánh giá tình hình tài chính, khả năng trả nợ của khách hàng sau khi đã xếp hạng theo hệ thống xếp hạng tín dụng nội bộ, có biện pháp quản lý rủi ro, quản lý chất lượng tín dụng phù hợp; c) Thực hiện tự phân loại nợ, cam kết ngoại bảng theo quy định tại Thông tư này và thực hiện trích lập dự phòng rủi ro và sử dụng dự phòng rủi ro theo quy định tại Nghị định về trích lập dự phòng rủi ro.",
        "rationale": "Đoạn quy định liên kết việc thu thập dữ liệu khách hàng và CIC với xếp hạng, quản lý nợ, dự phòng và theo dõi khả năng trả nợ.",
        "tags": ["risk", "credit-information", "regulation"],
    },
    {
        "evaluation_id": "stage12a-009",
        "query": "Hệ thống xếp hạng tín dụng nội bộ cần được xem xét, đánh giá theo tần suất tối thiểu nào?",
        "specialist_scope": "risk_management",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "96b45a97c58f4c95cce6bf536e7f6f1cade729706e0688a6bbfbe4c9beea5d4b",
        "rationale": "Đoạn quy định đặt ra chu kỳ rà soát tối thiểu đối với hệ thống xếp hạng nội bộ dựa trên dữ liệu.",
        "tags": ["risk", "internal-rating", "regulation"],
    },
    {
        "evaluation_id": "stage12a-010",
        "query": "Khi đánh giá dòng tiền của doanh nghiệp, điều kiện nào khiến hồ sơ bị từ chối vì dòng tiền không được hỗ trợ?",
        "specialist_scope": "risk_management",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "739a78f5c46e72944da3174d45733326d62b466666c1921a00cf20866e39fe46",
        "rationale": "Quy tắc thẩm định nêu yêu cầu về EBITDA chuẩn hóa, cầu nối dòng tiền và cách xử lý dòng tiền âm không được chứng minh.",
        "tags": ["risk", "synthetic", "cash-flow"],
    },
    {
        "evaluation_id": "stage12a-011",
        "query": "Một hồ sơ có hai ngoại lệ mềm phải đáp ứng những điều kiện kiểm soát nào để đi theo tuyến ngoại lệ?",
        "specialist_scope": "risk_management",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "59aa9152d01a6a9f99183f3e79e6d12e3d69a0e03f00bf50b7876554deecacc9",
        "evidence_excerpt": "Rule ID: APR-EXCEPTIONS. A Grade C case has exactly one soft exception and enumerates every deviated rule, evidence, root cause, mitigant, and residual risk. Exactly two soft exceptions are Grade C-EXCEPTION-2 and are eligible only for Tier 4 when every hard stop is absent, total exposure is > VND 3 billion and <= VND 5 billion, Risk and LegalCompliance concur, and the full rationale and mitigants are recorded. Grade C-EXCEPTION-2 is not eligible for Tier 1, Tier 2, or Tier 3. More than two soft exceptions are not permitted. No exception may be hidden through a grade override, and no grade or tier may override a hard stop.",
        "rationale": "Chính sách phê duyệt quy định rõ số lượng ngoại lệ, tuyến thẩm quyền, sự đồng thuận độc lập và hồ sơ lý do/biện pháp giảm thiểu.",
        "tags": ["risk", "synthetic", "exceptions"],
    },
    {
        "evaluation_id": "stage12a-012",
        "query": "Quy định nội bộ của tổ chức tín dụng phải bao quát những nội dung nào về phân loại tài sản, dự phòng, thanh khoản và quản trị rủi ro?",
        "specialist_scope": "risk_management",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "0ed843ba98e3640831d9119cc533d02dc3b8b7739c7c8f35e6ee6687ff004ab0",
        "evidence_excerpt": "2. Tổ chức tín dụng phải ban hành quy định nội bộ về các nội dung sau đây: a) Cấp tín dụng, quản lý khoản cấp tín dụng; b) Phân loại tài sản có, trích lập và sử dụng dự phòng rủi ro; c) Đánh giá chất lượng tài sản có và tuân thủ tỷ lệ an toàn vốn tối thiểu; d) Quản lý thanh khoản, trong đó có thủ tục và giới hạn quản lý thanh khoản; đ) Kiểm soát nội bộ và kiểm toán nội bộ phù hợp với tính chất và quy mô hoạt động của tổ chức tín dụng; e) Hệ thống xếp hạng tín dụng nội bộ đối với tổ chức tín dụng phải xây dựng hệ thống xếp hạng tín dụng nội bộ theo quy định của pháp luật về các tổ chức tín dụng; g) Quản trị rủi ro trong hoạt động của tổ chức tín dụng; h) Phòng, chống rửa tiền; i) Phương án xử lý trường hợp khẩn cấp.",
        "rationale": "Điều khoản luật liệt kê các nhóm nội dung bắt buộc trong quy định nội bộ, bao gồm chất lượng tài sản, dự phòng, thanh khoản và quản trị rủi ro.",
        "tags": ["risk", "internal-controls", "regulation"],
    },
    {
        "evaluation_id": "stage12a-013",
        "query": "Quy định nội bộ về cho vay phải nhận diện và kiểm soát rủi ro trong quá trình cấp tín dụng như thế nào?",
        "specialist_scope": "legal_compliance",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "7bfd8dde82bb3cdee31ad9ae74672ab415a5ac42ba5cd1062ae205f3dcdb9fbf",
        "rationale": "Đoạn quy định yêu cầu nhận diện rủi ro, theo dõi, đánh giá, kiểm soát và chuẩn bị phương án xử lý rủi ro trong quá trình cho vay.",
        "tags": ["legal", "risk-controls", "regulation"],
    },
    {
        "evaluation_id": "stage12a-014",
        "query": "Ngân hàng được cung cấp thông tin khách hàng cho bên khác trong những trường hợp ngoại lệ nào?",
        "specialist_scope": "legal_compliance",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "ccaa99a62c925843df5aa0ed67f502fc49d62702647bfc1c7ae996b59e42e9f4",
        "evidence_excerpt": "3. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài không được cung cấp thông tin khách hàng của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài cho tổ chức, cá nhân khác, trừ trường hợp có yêu cầu của cơ quan nhà nước có thẩm quyền theo quy định của luật hoặc được sự chấp thuận của khách hàng.",
        "rationale": "Điều khoản về bảo mật thông tin xác định nguyên tắc không cung cấp và hai căn cứ ngoại lệ: yêu cầu của cơ quan có thẩm quyền hoặc sự chấp thuận của khách hàng.",
        "tags": ["legal", "confidentiality", "regulation"],
    },
    {
        "evaluation_id": "stage12a-015",
        "query": "Bên bảo đảm bằng tín chấp có những trách nhiệm gì trong việc hỗ trợ người vay, giám sát sử dụng vốn và đôn đốc trả nợ?",
        "specialist_scope": "legal_compliance",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "4d91bf38a04fd7fc9f92d4f1de5874318a8224fb085307e3cbb5a14544bd1062",
        "rationale": "Điều khoản quy định cụ thể trách nhiệm của bên tín chấp trong hỗ trợ, giám sát mục đích sử dụng vốn và đôn đốc nghĩa vụ trả nợ.",
        "tags": ["legal", "guarantee", "regulation"],
    },
    {
        "evaluation_id": "stage12a-016",
        "query": "Cơ quan đăng ký có thể từ chối hồ sơ đăng ký biện pháp bảo đảm khi tài sản đang tranh chấp trong điều kiện nào?",
        "specialist_scope": "legal_compliance",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "36baf9c87d08c9558fc46cf32dd6d3285e72499f338e23a78ec29efe12306276",
        "rationale": "Đoạn quy định giới hạn việc từ chối khi tài sản tranh chấp vào trường hợp cơ quan đăng ký đã nhận được văn bản thụ lý hoặc chứng minh thẩm quyền giải quyết.",
        "tags": ["legal", "security-registration", "regulation"],
    },
    {
        "evaluation_id": "stage12a-017",
        "query": "Những hành vi nào bị cấm để bảo đảm thông tin tín dụng không bị làm sai lệch hoặc cung cấp trái phép?",
        "specialist_scope": "legal_compliance",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "488b1eb76a51610f44dc85023694af8b56f55b1c0b1d16279ac4400d43e81567",
        "rationale": "Điều khoản liệt kê các hành vi cấm liên quan đến bí mật, làm sai lệch, cung cấp sai đối tượng và xâm phạm quyền lợi trong hoạt động thông tin tín dụng.",
        "tags": ["legal", "credit-information", "regulation"],
    },
    {
        "evaluation_id": "stage12a-018",
        "query": "Khách hàng vay có thể được cung cấp thông tin tín dụng của chính mình theo cơ chế nào?",
        "specialist_scope": "customer_relationship",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "88b8b7604c8547cd837abb04a72156813156d744fae6838db67f53db481ed4c2",
        "evidence_excerpt": "4. Khách hàng vay được cung cấp thông tin tín dụng của chính khách hàng vay theo hướng dẫn của CIC.",
        "rationale": "Quy định xác định khách hàng vay được cung cấp thông tin của chính mình theo hướng dẫn của CIC.",
        "tags": ["customer-relationship", "credit-information", "regulation"],
    },
    {
        "evaluation_id": "stage12a-019",
        "query": "Thông tin tiêu cực về khách hàng vay được phép cung cấp trong thời hạn bao lâu và có ngoại lệ nào?",
        "specialist_scope": "customer_relationship",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "0a1f3fcecf06accf8b3285827f9dc894feac10cfa69a1299d6fe55b68bb27c16",
        "rationale": "Đoạn quy định nêu giới hạn năm năm đối với thông tin tiêu cực và ngoại lệ phục vụ yêu cầu của cơ quan quản lý nhà nước.",
        "tags": ["customer-relationship", "credit-information", "regulation"],
    },
    {
        "evaluation_id": "stage12a-020",
        "query": "Khi đề nghị vay vốn, khách hàng phải cung cấp nhóm tài liệu nào để chứng minh điều kiện vay và thông tin người có liên quan?",
        "specialist_scope": "customer_relationship",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "91f496387463579df9fb20ecaeae615386436d672729a3a99d089d0f99ec3b87",
        "rationale": "Điều khoản về hồ sơ đề nghị vay yêu cầu dữ liệu chứng minh điều kiện vay và thông tin về người có liên quan trong các trường hợp quy định.",
        "tags": ["customer-relationship", "loan-application", "regulation"],
    },
    {
        "evaluation_id": "stage12a-021",
        "query": "Hồ sơ xin sản phẩm vốn lưu động SME cần có những nhóm chứng từ nào, và thiếu tài liệu trọng yếu thì xử lý ra sao?",
        "specialist_scope": "customer_relationship",
        "query_type": "ELIGIBILITY_SUPPORT",
        "chunk_id": "61dc9e901fd1c303e9b6969e1037bf5a9a3c1009bb4c3e018a0b242e2294d2ce",
        "evidence_excerpt": "Rule ID: PROD-DOCUMENTS. Required documents are registration and authority evidence; ownership and management information; two completed fiscal-year financial packages where available; latest interim or trailing-12-month data; 12-month bank statements; tax/revenue corroboration; a debt schedule; and a purpose budget with supporting invoices or contracts. Missing or contradictory material evidence is a hold/refer outcome, never an inferred pass.",
        "rationale": "Chính sách sản phẩm liệt kê các nhóm hồ sơ cần thu thập và yêu cầu chuyển trạng thái hold/refer khi thiếu hoặc mâu thuẫn bằng chứng trọng yếu.",
        "tags": ["customer-relationship", "synthetic", "documents"],
    },
    {
        "evaluation_id": "stage12a-022",
        "query": "Việc mô tả tài sản bảo đảm là bất động sản hoặc động sản phải bảo đảm sự phù hợp với tài liệu nào?",
        "specialist_scope": "collateral_appraisal",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "788f3eb83c7f29cd5fc772964418eb5eac409fb59f737bd9f07177372821dc5d",
        "evidence_excerpt": "2. Trường hợp tài sản bảo đảm là bất động sản, động sản mà theo quy định của pháp luật phải đăng ký thì thông tin được mô tả theo thỏa thuận phải phù hợp với thông tin trên Giấy chứng nhận.",
        "rationale": "Quy định về mô tả tài sản yêu cầu thông tin mô tả phù hợp với giấy chứng nhận đối với tài sản phải đăng ký và có yêu cầu riêng cho quyền tài sản.",
        "tags": ["collateral", "description", "regulation"],
    },
    {
        "evaluation_id": "stage12a-023",
        "query": "Có thể dùng riêng quyền sử dụng đất hoặc riêng tài sản gắn liền với đất để bảo đảm nghĩa vụ không?",
        "specialist_scope": "collateral_appraisal",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "dcfbadec798a2c1f4cbf3c650a7faf31d67e54530cc98c3ac271160b15ea3680",
        "rationale": "Đoạn quy định trả lời trực tiếp khả năng tách quyền sử dụng đất và tài sản gắn liền với đất khi dùng để bảo đảm.",
        "tags": ["collateral", "land-rights", "regulation"],
    },
    {
        "evaluation_id": "stage12a-024",
        "query": "Hồ sơ đăng ký biện pháp bảo đảm được phép nộp bằng những phương thức nào, và có giới hạn nào với đất hoặc tài sản gắn liền với đất?",
        "specialist_scope": "collateral_appraisal",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9",
        "evidence_excerpt": "Điều 13. Cách thức nộp hồ sơ đăng ký 1. Hồ sơ đăng ký được nộp theo một trong các cách thức sau đây: a) Qua hệ thống đăng ký trực tuyến; b) Nộp bản giấy trực tiếp hoặc gửi qua dịch vụ bưu chính; c) Qua thư điện tử. 2. Cách thức nộp hồ sơ đăng ký quy định tại điểm a và điểm c khoản 1 Điều này đối với quyền sử dụng đất, tài sản gắn liền với đất, quyền sử dụng khu vực biển, tài sản gắn liền với khu vực biển hoặc đối với tàu bay, tàu biển thực hiện theo quy định của pháp luật về đất đai, về khai thác, sử dụng tài nguyên biển, về hàng không hoặc pháp luật về hàng hải.",
        "rationale": "Điều khoản liệt kê các phương thức nộp hồ sơ và quy định việc áp dụng phương thức điện tử/email cho một số nhóm tài sản theo pháp luật chuyên ngành.",
        "tags": ["collateral", "security-registration", "regulation"],
    },
    {
        "evaluation_id": "stage12a-025",
        "query": "Một nghĩa vụ có thể được bảo đảm bằng nhiều biện pháp hoặc nhiều tài sản không, và khi vi phạm ai chọn biện pháp áp dụng?",
        "specialist_scope": "collateral_appraisal",
        "query_type": "POLICY_LOOKUP",
        "chunk_id": "4b887c1080e4d234196fcbc439c9178a75de692c1e987834cda3d8f99fbda456",
        "rationale": "Điều khoản quy định khả năng dùng nhiều biện pháp hoặc nhiều tài sản và cơ chế lựa chọn khi nghĩa vụ bị vi phạm nếu các bên không có thỏa thuận.",
        "tags": ["collateral", "multiple-security", "regulation"],
    },
)


def build_records(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in PILOT_ITEMS:
        chunk_ids = item.get("chunk_ids", [item["chunk_id"]])
        chunks = [corpus.by_id[chunk_id] for chunk_id in chunk_ids]
        chunk = chunks[0]
        document = corpus.source_identity(chunk["source_id"])
        evidence_excerpts = item.get("evidence_excerpts", {})
        rationales = item.get("rationales", {})
        evidence = [
            corpus.make_evidence(
                chunk_id,
                rationales.get(chunk_id, item["rationale"]),
                excerpt=evidence_excerpts.get(chunk_id, item.get("evidence_excerpt")),
            )
            for chunk_id in chunk_ids
        ]
        records.append(
            {
                "schema_version": "retrieval-gold-v2.0.0",
                "evaluation_id": item["evaluation_id"],
                "query": item["query"],
                "query_type": item["query_type"],
                "specialist_scope": item["specialist_scope"],
                "assessment_date": "2026-09-03",
                "filters": {"corpus_version": "V2", "namespace": document["namespace"]},
                "expected_canonical_chunk_ids": chunk_ids,
                "gold_evidence": evidence,
                "forbidden_version_ids": [],
                "expected_coverage": "SUFFICIENT",
                "tags": ["stage-12a-gold-pilot", *item["tags"]],
                "document": document,
                "visibility": evidence[0]["visibility"],
                "is_synthetic": evidence[0]["is_synthetic"],
                "corpus_identity": corpus.corpus_identity,
                "embedding_identity": corpus.embedding_identity,
                "status": "DRAFT",
                "creation_provenance": {
                    "method": "evidence_first_human_authored_draft",
                    "evidence_source": "dataset/chunks/v2/policy-corpus-v2.jsonl",
                    "retrieval_used": False,
                    "generated_by": "stage12a_gold_pilot_builder",
                    "created_at": CREATED_AT,
                },
                "review": None,
            }
        )
    return records


def write_outputs() -> tuple[int, int]:
    corpus = FrozenCorpusV2()
    records = build_records(corpus)
    validator = CanonicalGoldValidator(corpus)
    for record in records:
        validator.validate_record(record, records[: records.index(record)])
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSONL.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# Stage 12A-R1 — Gold Pilot Review",
        "",
        "This pack is an evidence-first human-review queue for frozen Corpus V2.",
        "No record was generated from retrieval output. Every item remains `DRAFT`; no item is exportable as frozen gold until a human reviewer records `REVIEWED`.",
        "",
        f"- Draft records: **{len(records)}**",
        "- Corpus identity: `policy-corpus-v2`, 1,610 chunks",
        "- Embedding identity: `Qwen3-Embedding-0.6B`, llama.cpp, 1,024 dimensions",
        "",
    ]
    for record in records:
        document = record["document"]
        lines.extend(
            [
                f"## {record['evaluation_id']}",
                "",
                f"**Scope:** `{record['specialist_scope']}`  ",
                f"**Question:** {record['query']}",
                "",
                f"**Expected canonical chunk ID(s):** {', '.join(f'`{chunk_id}`' for chunk_id in record['expected_canonical_chunk_ids'])}  ",
                f"**Primary source:** {document['title']} (`{document['source_id']}` / `{document['version_id']}`)  ",
                f"**Record visibility:** `{record['visibility']}`; **Provenance:** `{document['provenance']}`  ",
                "",
                "**Status:** `DRAFT`",
                "",
            ]
        )
        for index, evidence in enumerate(record["gold_evidence"], start=1):
            evidence_document = corpus.source_identity(evidence["source_id"])
            lines.extend(
                [
                    f"**Evidence {index}:** `{evidence['canonical_chunk_id']}`  ",
                    f"**Source:** {evidence_document['title']} (`{evidence['source_id']}` / `{evidence['version_id']}`)  ",
                    f"**Visibility:** `{evidence['visibility']}`; **Locator:** Article `{evidence['locator']['article']}`, clause `{evidence['locator']['clause']}`, point `{evidence['locator']['point']}`, JSONL line `{evidence['locator']['jsonl_line']}`  ",
                    f"**Evidence:** {evidence['excerpt']}",
                    f"**Rationale:** {evidence['rationale']}",
                    "",
                ]
            )
    OUTPUT_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REVIEW.write_text("\n".join(lines), encoding="utf-8")
    return len(records), 0


if __name__ == "__main__":
    count, reviewed = write_outputs()
    print(f"wrote {count} DRAFT records; REVIEWED={reviewed}")
