# Thiết kế đầy đủ hệ thống IGEP cho suy luận và phân bổ di sản thừa kế

## 1. Tên đề xuất của phương pháp

**Issue-Guided Retrieval and Executable Planning for Vietnamese Inheritance Law Reasoning — IGEP**

Có thể mô tả ngắn gọn phương pháp như sau:

> IGEP là một framework suy luận luật thừa kế có kiểm chứng, trong đó mô hình ngôn ngữ lớn được sử dụng để trích xuất sự kiện, xác định vấn đề pháp lý và sinh kế hoạch thực thi có cấu trúc; việc truy xuất điều luật được hỗ trợ bởi tập enum sinh tự động từ văn bản pháp luật; kết quả phân chia di sản được tính bằng một bộ hàm xác định và được kiểm tra bằng các ràng buộc pháp lý, cấu trúc và số học.

Phiên bản tiếng Anh dùng trong bài báo:

> IGEP is a validator-guided, issue-aware retrieval and executable planning framework for inheritance-law allocation. A large language model extracts a structured case representation, identifies statute-derived legal issues, and produces a constrained execution plan. Relevant statutes are retrieved through hybrid search, while inheritance amounts are computed by a deterministic executor and checked by legal and arithmetic validators.

---

## 2. Mục tiêu nghiên cứu

Bài toán đầu vào là một tình huống thừa kế bằng tiếng Việt, được xây dựng từ hai nhóm nguồn: bản án/quyết định đã công bố và bài tập pháp lý của cơ sở đào tạo luật. Đầu ra mục tiêu là một ánh xạ từ người được hưởng di sản đến số tiền hoặc giá trị tài sản được phân bổ:

```json
{
  "Nguyễn Văn A": 500000000,
  "Nguyễn Thị B": 500000000
}
```

Hệ thống không chỉ cần xác định đúng người được hưởng mà còn phải:

- loại đúng người không đủ điều kiện;
- xác định đúng khối di sản ròng;
- xử lý tài sản chung, tài sản riêng và nghĩa vụ tài sản;
- áp dụng đúng hàng thừa kế, thừa kế thế vị, di chúc và phần bắt buộc;
- bảo đảm tổng số tiền được chia không vượt quá khối di sản;
- cung cấp căn cứ điều luật và dấu vết thực thi.

Vì vậy, đây không nên được mô hình hóa như một bài toán hỏi đáp văn bản thông thường. Cách đặt bài toán phù hợp hơn là:

> **Structured legal reasoning with statute retrieval and exact executable allocation.**

---

## 3. Kiến trúc tổng thể

```text
OFFLINE CONSTRUCTION
────────────────────────────────────────────────────────────
Inheritance statute corpus
        ↓
Statute segmentation and versioning
        ↓
LLM-based legal issue enum induction
        ↓
Enum normalization, deduplication, and freezing
        ↓
Automatic statute annotation
        ↓
Statute database and hybrid retrieval indexes

Generic inheritance operation registry
        ↓
Unit-tested deterministic executor

Published court judgments and legal-education cases
        ↓
Fact sanitization and leakage removal
        ↓
Benchmark cases and gold allocations


ONLINE INFERENCE
────────────────────────────────────────────────────────────
Sanitized inheritance case
        ↓
Global LLM structured extractor
        ↓
Deterministic schema normalization
        ↓
External schema and fact validator
        ↓
Constrained repair or abstention
        ↓
Validated inheritance schema
        ↓
Legal issue profile generation
        ↓
Hybrid statute retrieval
        ↓
Rank fusion and relevance reranking
        ↓
Statute applicability and sufficiency assessment
        ↓
Constrained JSON execution-plan generation
        ↓
Static plan validation
        ↓
Deterministic execution
        ↓
Post-execution legal and arithmetic verification
        ↓
Plan repair and re-execution, or abstention
        ↓
Final heir-to-amount allocation
```

---

# PHẦN I. XÂY DỰNG NGOẠI TUYẾN

## 4. Xây dựng tập văn bản pháp luật

### 4.1. Phạm vi pháp luật

Phạm vi nghiên cứu ban đầu nên được giới hạn theo thiết lập **closed-world**. Hệ thống chỉ xử lý các tình huống mà toàn bộ quy tắc cần thiết nằm trong tập văn bản đã công bố.

Phạm vi tối thiểu nên gồm:

- Bộ luật Dân sự Việt Nam năm 2015, phần thừa kế;
- các điều về tài sản, nghĩa vụ tài sản và xác định di sản;
- các điều cần thiết của Luật Hôn nhân và Gia đình liên quan đến tài sản chung vợ chồng;
- TODO: nghị quyết hướng dẫn, án lệ hoặc văn bản giải thích nếu được đưa vào phạm vi nghiên cứu.

Các case cần quy tắc ngoài corpus phải được gắn trạng thái:

```json
{
  "status": "out_of_scope"
}
```

### 4.2. Đơn vị lập chỉ mục

Đơn vị index nên là điều hoặc khoản, không phải toàn bộ chương luật.

```json
{
  "statute_id": "VN_CC_2015_ART_651_CLAUSE_1",
  "document": "Civil Code 2015",
  "version": "effective_version",
  "article": 651,
  "clause": 1,
  "text": "TODO: nội dung điều luật",
  "effective_from": "TODO",
  "effective_to": null
}
```

Thông tin thời gian hiệu lực cần được lưu để tránh truy xuất nhầm phiên bản điều luật.

---

## 5. Sinh legal issue enum từ luật

### 5.1. Nguyên tắc

Enum không được thiết kế thủ công cho từng điều luật. Thay vào đó, LLM đọc toàn bộ tập văn bản pháp luật và đề xuất một vocabulary nhỏ gồm các vấn đề pháp lý lặp lại.

Enum phải thỏa các yêu cầu:

- đại diện cho một vấn đề pháp lý, điều kiện hoặc phép xử lý tái sử dụng;
- không gắn cứng với một điều luật duy nhất;
- không chứa nội dung quá cụ thể theo từng case;
- có mô tả rõ và từ đồng nghĩa;
- được sinh một lần, chuẩn hóa và freeze trước thực nghiệm.

Ví dụ:

```json
{
  "enum_id": "REPRESENTATION_INHERITANCE",
  "name": "representation inheritance",
  "description": "Inheritance by descendants replacing a predeceased child",
  "category": "heir_identification",
  "synonyms": [
    "thừa kế thế vị",
    "cháu hưởng phần của cha hoặc mẹ đã chết"
  ]
}
```

### 5.2. Nhóm enum dự kiến

```text
succession_mode
heir_identification
heir_eligibility
temporal_status
will_status
estate_scope
estate_obligation
allocation_rule
uncertainty
```

Ví dụ taxonomy:

```json
{
  "succession_mode": [
    "STATUTORY_SUCCESSION",
    "TESTAMENTARY_SUCCESSION",
    "PARTIAL_WILL",
    "INVALID_WILL"
  ],
  "heir_identification": [
    "FIRST_ORDER_HEIR",
    "SECOND_ORDER_HEIR",
    "THIRD_ORDER_HEIR",
    "REPRESENTATION_INHERITANCE",
    "MANDATORY_HEIR",
    "ADOPTED_CHILD",
    "STEPCHILD",
    "UNBORN_CHILD"
  ],
  "heir_eligibility": [
    "DISQUALIFIED_HEIR",
    "RENOUNCED_INHERITANCE",
    "PREDECEASED_HEIR",
    "HEIR_DIED_AFTER_OPENING"
  ],
  "estate_scope": [
    "JOINT_PROPERTY",
    "SEPARATE_PROPERTY",
    "DISPUTED_PROPERTY",
    "ASSET_VALUATION"
  ],
  "estate_obligation": [
    "DEBT_DEDUCTION",
    "FUNERAL_EXPENSE",
    "PROPERTY_OBLIGATION"
  ],
  "allocation_rule": [
    "EQUAL_SHARE",
    "WILL_BASED_ALLOCATION",
    "RESERVED_SHARE",
    "REMAINING_ESTATE_ALLOCATION"
  ]
}
```

### 5.3. Quy trình sinh và freeze enum

```text
Mỗi điều luật
→ LLM sinh candidate enums
→ gom toàn bộ candidate
→ embedding clustering
→ LLM canonicalization
→ loại trùng và chuẩn hóa tên
→ chuyên gia kiểm tra nhẹ
→ freeze vocabulary
```

Enum chỉ là **soft retrieval signal**. Enum không được dùng làm kết luận pháp lý và không phải điều kiện duy nhất để retrieve luật.

---

## 6. Tự động annotate statute database

Sau khi freeze enum list, LLM annotate mỗi điều hoặc khoản bằng đúng vocabulary đó.

```json
{
  "statute_id": "VN_CC_2015_ART_651",
  "text": "TODO: nội dung điều luật",
  "summary": "Quy định về hàng thừa kế và nguyên tắc người cùng hàng được hưởng phần bằng nhau.",
  "enums": [
    "STATUTORY_SUCCESSION",
    "FIRST_ORDER_HEIR",
    "EQUAL_SHARE"
  ],
  "keywords": [
    "hàng thừa kế thứ nhất",
    "vợ chồng cha mẹ con",
    "người cùng hàng"
  ],
  "possible_operations": [
    "select_heirs_by_order",
    "allocate_equal"
  ]
}
```

Các trường `summary`, `enums`, `keywords` và `possible_operations` được sinh tự động bằng prompt cố định. Đây là cách tránh xây law card thủ công hoặc knowledge graph thủ công.

---

## 7. Xây dựng operation registry

### 7.1. Nguyên tắc

Executor không chứa một hàm riêng cho từng điều luật. Thay vào đó, hệ thống dùng một tập phép toán pháp lý tổng quát và có thể tái sử dụng.

Danh sách ban đầu:

```text
select_persons
filter_by_relation
filter_by_life_status
exclude_persons
split_joint_property
subtract_obligations
select_heir_order
allocate_equal
allocate_by_ratio
allocate_by_branch
apply_minimum_share
merge_allocations
normalize_rounding
assert_total_conservation
```

Ví dụ interface:

```python
def allocate_equal(
    estate_amount: Decimal,
    heir_ids: list[str]
) -> dict[str, Decimal]:
    ...
```

### 7.2. Mỗi operation cần có

```json
{
  "operation": "allocate_equal",
  "inputs": {
    "estate_amount": "Decimal",
    "heir_ids": "list[str]"
  },
  "outputs": {
    "allocation": "dict[str, Decimal]"
  },
  "preconditions": [
    "estate_amount >= 0",
    "len(heir_ids) > 0"
  ],
  "postconditions": [
    "sum(allocation.values()) == estate_amount"
  ],
  "failure_codes": [
    "EMPTY_HEIR_SET",
    "NEGATIVE_ESTATE"
  ]
}
```

Toàn bộ operation phải có unit test độc lập.

---

## 8. Xây dựng benchmark từ nguồn tư pháp và giáo dục pháp luật

### 8.1. Dữ liệu đầu vào

Benchmark là tập hỗn hợp. Các case `court_judgment_derived` được biên soạn từ bản án hoặc quyết định đã công bố; các case `legal_education_case` đến từ bài tập của cơ sở đào tạo luật. Mỗi record phải lưu `source_type`, và paper phải báo kết quả theo từng nhóm nguồn bên cạnh kết quả gộp. Không được mô tả các case giáo dục là bản án thực tế hoặc gọi đáp án của chúng là kết quả xét xử.

Phải loại bỏ:

- phần nhận định của tòa có thể tái tạo từ facts còn lại;
- điều luật tòa đã viện dẫn;
- phần quyết định cuối cùng;
- số tiền từng người được nhận;
- câu văn trực tiếp tiết lộ kết luận.

Nếu không kiểm soát leakage, mô hình có thể sao chép đáp án thay vì suy luận.

Nếu một court finding không thể tái tạo từ facts nhưng cần để bài toán có nghiệm
duy nhất, phải chuyển nó thành stipulated premise có metadata rõ ràng. Case đó
không được dùng để chấm subtask suy ra chính premise này. Ví dụ: không chấm
`will_validity` trên case chỉ cung cấp giả định “di chúc không hợp pháp”, và
không chấm định lượng công sức trên case đã cho sẵn tỷ lệ do tòa ấn định.

### 8.2. Gold output

```json
{
  "Nguyễn Văn A": 500000000,
  "Nguyễn Thị B": 500000000
}
```

Answer key phải sử dụng tên người cụ thể, không dùng các vai trò chung như `vợ`, `con 1`, `cháu ruột` nếu có thể gán tên.

### 8.3. Metadata nên lưu

```json
{
  "case_id": "CASE_001",
  "jurisdiction": "Vietnam",
  "source_type": "court_judgment_derived | legal_education_case",
  "court": "TODO: chỉ áp dụng cho court_judgment_derived",
  "decision_year": "TODO",
  "succession_mode": "TODO",
  "has_will": "TODO",
  "complexity_level": "TODO",
  "number_of_persons": "TODO",
  "number_of_assets": "TODO",
  "gold_allocation": {}
}
```

### 8.4. Expert-audited subset

Toàn bộ dataset có thể chỉ cần input và final allocation. Tuy nhiên, ít nhất một subset khoảng 50–100 case hoặc 20% test set nên được annotate sâu:

```text
gold schema
gold applicable statutes
gold legal issue enums
gold excluded persons
gold operation sequence hoặc plan skeleton
```

Subset này cho phép phân tích root cause của lỗi.

---

# PHẦN II. SUY LUẬN TRỰC TUYẾN

## 9. Global LLM structured extractor

### 9.1. Thiết kế cuối cùng

Không chia thành nhiều sub-extractor tuần tự. Một LLM mạnh đọc toàn bộ case và sinh schema đầy đủ trong một lần.

```text
Full case text
→ one strong LLM
→ complete inheritance schema
```

Lý do:

- quan hệ gia đình thường phụ thuộc ngữ cảnh xa;
- trạng thái sống/chết phụ thuộc nhiều câu;
- một lỗi ở sub-extractor có thể kéo theo toàn bộ pipeline sai;
- LLM mạnh có khả năng đọc toàn cục tốt hơn rule nhỏ lẻ.

### 9.2. Trách nhiệm của extractor

Extractor chỉ ghi nhận facts, không được:

- xác định ai cuối cùng được hưởng;
- áp dụng luật;
- tính phần tiền;
- suy ra điều luật;
- tự bổ sung facts không có trong input.

Nếu không chắc, output phải dùng `null`, `unknown` hoặc `disputed`.

### 9.3. Schema đề xuất

```json
{
  "case_id": "CASE_001",
  "decedent": {
    "person_id": "P1",
    "canonical_name": "Nguyễn Văn A",
    "aliases": ["ông A"],
    "death_time": null,
    "evidence_text": "...",
    "evidence_start": 0,
    "evidence_end": 20
  },
  "persons": [
    {
      "person_id": "P2",
      "canonical_name": "Nguyễn Thị B",
      "aliases": ["bà B"],
      "relation_to_decedent": "spouse",
      "living_status_at_opening": "alive",
      "is_potential_heir": true,
      "evidence_text": "...",
      "evidence_start": 25,
      "evidence_end": 55
    }
  ],
  "relationships": [
    {
      "subject": "P2",
      "relation": "spouse_of",
      "object": "P1",
      "evidence_text": "..."
    }
  ],
  "assets": [
    {
      "asset_id": "A1",
      "description": "Quyền sử dụng đất",
      "value": 1200000000,
      "ownership_type": "joint_property",
      "co_owners": ["P1", "P2"],
      "evidence_text": "..."
    }
  ],
  "obligations": [
    {
      "obligation_id": "O1",
      "type": "debt",
      "value": 200000000,
      "evidence_text": "..."
    }
  ],
  "will": {
    "exists": false,
    "validity": "not_applicable",
    "beneficiaries": [],
    "evidence_text": "..."
  },
  "uncertainties": []
}
```

### 9.4. Evidence grounding

Mọi fact quan trọng nên có provenance:

```json
{
  "subject": "P3",
  "relation": "biological_child_of",
  "object": "P1",
  "evidence_text": "Ông A có người con là C",
  "evidence_start": 125,
  "evidence_end": 149,
  "confidence": "high"
}
```

---

## 10. Schema-constrained generation

LLM nên sinh output theo JSON Schema hoặc grammar-constrained decoding.

Structured decoding chỉ bảo đảm output hợp cú pháp. Nó không bảo đảm nội dung đúng. Vì vậy:

```text
Syntactic validity ≠ semantic correctness
```

Schema-constrained decoding phải được kết hợp với normalizer và validator bên ngoài.

---

## 11. Deterministic schema normalizer

Normalizer chỉ chuẩn hóa biểu diễn, không thực hiện suy luận pháp lý.

| Input | Output chuẩn hóa |
|---|---|
| `ông Nguyễn Văn A` | `Nguyễn Văn A` |
| `1,2 tỷ đồng` | `1200000000` |
| `vợ` | `spouse` |
| `con ruột` | `biological_child` |
| `đã mất trước ông B` | `dead_before_opening` |
| các alias lặp | cùng một `person_id` |

Normalizer không được:

- bổ sung quan hệ mới;
- thay đổi living status;
- xác định di chúc hợp lệ;
- xác định người thừa kế;
- thay đổi giá trị tiền ngoài việc parse định dạng.

---

## 12. External schema and fact validator

Validator gồm bốn lớp.

### 12.1. Structural validation

```text
JSON hợp lệ
đủ field bắt buộc
person_id duy nhất
mọi reference đều tồn tại
amount và ratio đúng kiểu
enum thuộc frozen vocabulary
```

### 12.2. Evidence grounding validation

```text
Tên người phải có evidence trong input
Số tiền phải có evidence
Tài sản phải có evidence
Quan hệ phải có evidence
Không sinh người hoặc tài sản mới
```

### 12.3. Internal consistency validation

```text
Không vừa alive_at_opening vừa dead_before_opening
Không self-parent hoặc self-spouse
Không có chu trình cha-con bất hợp lý
Không có amount âm
Ngày chết trước/sau không mâu thuẫn
Một tài sản không đồng thời separate và joint nếu không có trạng thái disputed
```

### 12.4. Completeness validation

```text
Không có decedent
Không có estate value khi task yêu cầu monetary allocation
Không rõ quan hệ của người có thể làm thay đổi kết quả
Không rõ thời điểm sống/chết
Không rõ tài sản chung hay riêng khi điều đó làm thay đổi estate mass
```

Ví dụ output lỗi:

```json
{
  "valid": false,
  "errors": [
    {
      "code": "UNKNOWN_PERSON_REFERENCE",
      "location": "relationships[3].object",
      "message": "Person P7 does not exist"
    },
    {
      "code": "MISSING_EVIDENCE",
      "location": "assets[0].value",
      "message": "Asset value has no supporting evidence span"
    }
  ]
}
```

---

## 13. Repair hoặc abstention

Nếu validator fail, LLM nhận:

```json
{
  "original_text": "...",
  "current_schema": {},
  "validator_errors": []
}
```

Repair prompt phải yêu cầu:

- chỉ sửa field bị lỗi;
- không thêm người hoặc số tiền nếu không có evidence;
- dùng `unknown` nếu không chắc;
- không thực hiện legal inference.

Chỉ cho phép một hoặc hai vòng repair.

Trạng thái sau cùng:

```text
pass                → tiếp tục
critical fail       → extraction_failure
ambiguous facts     → under_specified
out-of-domain case  → out_of_scope
```

---

## 14. Legal issue profile generation

Từ validated schema, LLM chọn enum trong frozen vocabulary.

```json
{
  "selected_enums": [
    {
      "enum": "STATUTORY_SUCCESSION",
      "confidence": 0.97,
      "schema_evidence": ["will.exists=false"]
    },
    {
      "enum": "REPRESENTATION_INHERITANCE",
      "confidence": 0.91,
      "schema_evidence": [
        "P3.dead_before_opening=true",
        "P5.child_of=P3"
      ]
    }
  ],
  "retrieval_queries": [
    "thừa kế thế vị khi con của người để lại di sản chết trước",
    "người cùng hàng thừa kế được chia bằng nhau"
  ],
  "expected_operations": [
    "select_heir_order",
    "allocate_by_branch"
  ]
}
```

Legal issue profile gồm:

- enum labels;
- query expansions;
- schema evidence;
- confidence;
- expected operations.

Enum không được dùng làm hard filter duy nhất.

---

## 15. Hybrid statute retrieval

### 15.1. Retrieval channels

```text
Channel A: BM25 over raw statute text
Channel B: dense retrieval over statute embeddings
Channel C: enum overlap
Channel D: LLM-expanded query retrieval
```

Candidate set:

```text
Candidates = union(
    top-k BM25,
    top-k dense,
    top-k enum overlap,
    top-k query expansion
)
```

### 15.2. Rank fusion

Không cộng trực tiếp raw scores vì BM25, cosine similarity và enum overlap không cùng scale.

Dùng Reciprocal Rank Fusion:

```text
RRF(d) = Σ 1 / (k + rank_r(d))
```

### 15.3. Reranking

Sau fusion, giữ top 10–20 điều hoặc khoản rồi rerank bằng cross-encoder hoặc LLM relevance classifier.

```json
{
  "statute_id": "VN_CC_2015_ART_651",
  "relevance": 3,
  "reason": "The case concerns statutory succession and first-order heirs.",
  "supported_issue_enums": [
    "STATUTORY_SUCCESSION",
    "FIRST_ORDER_HEIR"
  ]
}
```

Reranker chỉ đánh giá relevance, không quyết định điều luật chắc chắn áp dụng.

---

## 16. Statute applicability and sufficiency assessment

Phải phân biệt:

```text
Retrieval     = điều luật có liên quan không?
Applicability = điều luật có áp dụng cho facts hiện tại không?
```

Ví dụ:

```json
{
  "statute_id": "VN_CC_2015_ART_652",
  "status": "applicable",
  "conditions_satisfied": [
    "parent died before decedent",
    "descendant is alive at opening"
  ],
  "missing_facts": [],
  "supported_operations": [
    "allocate_by_branch"
  ]
}
```

Hoặc:

```json
{
  "statute_id": "VN_CC_2015_ART_644",
  "status": "conditionally_applicable",
  "conditions_satisfied": [
    "valid will exists"
  ],
  "missing_facts": [
    "age_of_child",
    "working_capacity"
  ]
}
```

Không được sử dụng quy tắc:

```text
Không retrieve được luật → thiếu dữ kiện
```

Các trạng thái phải tách rõ:

```text
processable
under_specified
extraction_failure
retrieval_failure
out_of_scope
unsupported_operation
```

---

## 17. JSON execution plan generation

Planner nhận ba đầu vào:

```text
validated schema
+ applicable statutes
+ operation registry
```

Planner không được sinh Python tự do. Planner chỉ sinh JSON plan có dependency.

```json
{
  "plan_id": "PLAN_001",
  "steps": [
    {
      "step_id": "S1",
      "operation": "split_joint_property",
      "depends_on": [],
      "inputs": {
        "asset_ids": ["A1"],
        "surviving_spouse_id": "P2"
      },
      "legal_basis": ["TODO: relevant provision"],
      "output": "estate_after_property_split"
    },
    {
      "step_id": "S2",
      "operation": "subtract_obligations",
      "depends_on": ["S1"],
      "inputs": {
        "estate": "$S1.estate",
        "obligation_ids": ["O1"]
      },
      "legal_basis": ["VN_CC_2015_ART_658"],
      "output": "net_estate"
    },
    {
      "step_id": "S3",
      "operation": "select_heir_order",
      "depends_on": [],
      "inputs": {
        "persons": "$schema.persons",
        "order": 1
      },
      "legal_basis": ["VN_CC_2015_ART_651"],
      "output": "candidate_heirs"
    },
    {
      "step_id": "S4",
      "operation": "allocate_by_branch",
      "depends_on": ["S2", "S3"],
      "inputs": {
        "estate": "$S2.net_estate",
        "heirs": "$S3.candidate_heirs"
      },
      "legal_basis": [
        "VN_CC_2015_ART_651",
        "VN_CC_2015_ART_652"
      ],
      "output": "allocation"
    }
  ]
}
```

Ưu điểm:

- không cho LLM thực hiện phép tính số học trực tiếp;
- không cho LLM chạy code tùy ý;
- dễ validate;
- dễ trace từng bước;
- dễ ablation và error analysis.

---

## 18. Static plan validator

Trước khi execute, plan phải qua validator.

### 18.1. Structural checks

```text
Mọi operation có trong registry
Mọi input tồn tại
Mọi dependency tồn tại
Không có cycle
Không sử dụng output trước khi được tạo
Không ghi đè output trái phép
```

### 18.2. Legal grounding checks

```text
Legal basis nằm trong applicable statute set
Không dùng điều luật đã bị đánh dấu irrelevant
Mỗi operation phải có legal basis khi cần
```

### 18.3. Semantic preconditions

```text
allocate_equal yêu cầu non-empty heir set
split_joint_property yêu cầu ownership_type=joint
apply_minimum_share yêu cầu valid will
allocate_by_branch yêu cầu branch structure
subtract_obligations yêu cầu estate đã được xác định
```

Nếu fail, planner được sửa plan một lần bằng explicit validator feedback.

---

## 19. Deterministic executor

Executor sử dụng:

- `Decimal` cho tiền;
- `Fraction` cho tỷ lệ;
- deterministic rounding policy;
- immutable intermediate state;
- execution trace.

Ví dụ trace:

```json
{
  "step_id": "S2",
  "operation": "subtract_obligations",
  "input_estate": 1200000000,
  "deducted": 200000000,
  "output_estate": 1000000000
}
```

Executor không được:

- gọi LLM;
- tự retrieve luật;
- suy diễn relationship;
- thêm người;
- sửa schema;
- thực thi arbitrary code do LLM tạo.

---

## 20. Post-execution verifier

### 20.1. Arithmetic verification

```text
Mọi amount không âm
Tổng share bằng 1 hoặc có phần dư được giải thích
Tổng phân bổ không vượt net estate
Rounding residual được xử lý
```

### 20.2. Entity verification

```text
Mọi người trong output tồn tại trong schema
Không có excluded person
Không có alias trùng
Không bỏ sót người đã được plan chọn
```

### 20.3. Legal consistency verification

```text
Không chọn hàng sau khi hàng trước còn người đủ điều kiện
Áp dụng đúng thừa kế thế vị
Tài sản chung và nghĩa vụ được xử lý trước allocation
Reserved share được áp dụng khi đủ điều kiện
Mọi bước có căn cứ pháp lý phù hợp
```

Nếu verifier fail:

```text
verifier error
→ planner sửa JSON plan
→ execute lại
```

Không cho LLM sửa trực tiếp số tiền cuối cùng.

Nếu lần hai vẫn fail:

```json
{
  "status": "verification_failure"
}
```

---

## 21. Final output

Output nội bộ:

```json
{
  "status": "success",
  "net_estate": 1000000000,
  "allocations": [
    {
      "person_id": "P2",
      "name": "Nguyễn Văn A",
      "share": "1/2",
      "amount": 500000000,
      "legal_basis": ["VN_CC_2015_ART_651"]
    },
    {
      "person_id": "P3",
      "name": "Nguyễn Thị B",
      "share": "1/2",
      "amount": 500000000,
      "legal_basis": ["VN_CC_2015_ART_651"]
    }
  ],
  "total_allocated": 1000000000,
  "verification": {
    "total_conservation": true,
    "entity_consistency": true,
    "legal_consistency": true
  }
}
```

Output benchmark:

```json
{
  "Nguyễn Văn A": 500000000,
  "Nguyễn Thị B": 500000000
}
```

---

# PHẦN III. THỰC NGHIỆM

## 22. Baseline và phương pháp chính đã chốt

Mọi nhánh sinh dùng cùng họ model `gpt-5-mini` và cùng decoding budget để phép
so sánh không bị nhiễu bởi năng lực model khác nhau.

| ID | Hệ thống cạnh tranh | Mục tiêu |
|---|---|---|
| B1 | Direct LLM | Query → allocation trực tiếp; không schema, không retrieval |
| B2 | LLM + Full Statute Context | Đưa frozen statute corpus vào context, không retrieval |
| B3 | BM25 RAG + Direct Answer | Baseline sparse retrieval |
| B4 | Dense RAG + Direct Answer | Baseline `voyage-4-large` dense retrieval |
| B5 | Hybrid RAG + Direct Answer | BM25 + dense rank fusion, chưa có structured executor |
| B6 | Schema + Hybrid RAG + Direct Answer | Đo đóng góp của structured facts trước khi thêm planner/executor |
| M1 | Full IGEP | Structured extraction + validation/repair + hybrid/enum retrieval + applicability + JSON plan + deterministic executor + verifier |

Các cấu hình sau là **diagnostic upper bound**, không được báo như baseline cạnh
tranh: Oracle Schema + IGEP; Oracle Statutes + IGEP; Oracle Schema + Oracle
Statutes + Planner/Executor.

`JSON Plan + Executor, No Enum` và `Free-form Python Generation` chỉ dùng như
ablation/diagnostic nếu ngân sách cho phép; không đặt vào bảng baseline chính.

---

## 23. Ablation study

| Ablation | Câu hỏi nghiên cứu |
|---|---|
| Không normalizer | Normalization có giảm lỗi alias và money không? |
| Không extraction validator | Validator có tăng schema correctness không? |
| Không evidence grounding | Evidence constraint có giảm hallucination không? |
| Không enum | Enum có cải thiện statute recall không? |
| Enum làm hard filter | Hard filtering có gây retrieval miss không? |
| Không query expansion | Query expansion có đóng góp không? |
| Không dense retrieval | Dense channel đóng góp bao nhiêu? |
| Không reranker | Reranking có giảm luật nhiễu không? |
| Không applicability filter | Luật không áp dụng ảnh hưởng planner thế nào? |
| Free-form code | JSON plan có đáng tin cậy hơn arbitrary code không? |
| Không plan validator | Valid plan rate thay đổi thế nào? |
| Không final verifier | Có bao nhiêu lỗi pháp lý và số học lọt ra ngoài? |
| Không abstention | Accuracy và critical error rate thay đổi thế nào? |

---

## 24. Hệ metric

### 24.1. Extraction metrics

```text
Person-F1
Relation-F1
Life-status accuracy
Money exact accuracy
Asset-F1
Obligation-F1
Will-status accuracy
Evidence grounding rate
Schema-valid rate
Validator-pass rate
```

### 24.2. Enum và retrieval metrics

```text
Enum micro-F1
Enum macro-F1
Article Recall@5
Article Recall@10
MRR
nDCG@10
Applicable-law precision
Applicable-law recall
```

### 24.3. Planning metrics

```text
Valid plan rate
Executable plan rate
Operation precision
Operation recall
Dependency accuracy
Operation order accuracy
Legal-basis accuracy
```

### 24.4. Final allocation metrics

```text
Heir-F1
Excluded-person F1
Share accuracy
Amount exact accuracy
Amount accuracy under tolerance
Total conservation
Legal consistency
Case exact match
```

### 24.5. Reliability metrics

```text
Coverage
Accuracy at coverage
Critical error rate
Abstention precision
Abstention recall
```

---

## 25. Bảng kết quả dự kiến

### 25.1. Extraction results

| Method | Person-F1 | Relation-F1 | Money Acc. | Life Status Acc. | Schema Valid | Evidence Rate |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only | TODO | TODO | TODO | TODO | TODO | TODO |
| LLM + Normalizer | TODO | TODO | TODO | TODO | TODO | TODO |
| LLM + Normalizer + Validator | TODO | TODO | TODO | TODO | TODO | TODO |
| Full extractor + Repair | TODO | TODO | TODO | TODO | TODO | TODO |

### 25.2. Retrieval results

| Retrieval Method | Recall@5 | Recall@10 | MRR | nDCG@10 | Applicable-law Recall |
|---|---:|---:|---:|---:|---:|
| BM25 | TODO | TODO | TODO | TODO | TODO |
| Dense | TODO | TODO | TODO | TODO | TODO |
| Enum Only | TODO | TODO | TODO | TODO | TODO |
| BM25 + Dense | TODO | TODO | TODO | TODO | TODO |
| BM25 + Dense + Enum | TODO | TODO | TODO | TODO | TODO |
| Full Hybrid + Query Expansion + Reranker | TODO | TODO | TODO | TODO | TODO |

### 25.3. Planning results

| Method | Valid Plan Rate | Executable Rate | Operation F1 | Order Acc. | Legal-basis Acc. |
|---|---:|---:|---:|---:|---:|
| Free-form Python | TODO | TODO | TODO | TODO | TODO |
| JSON Plan, No Validator | TODO | TODO | TODO | TODO | TODO |
| JSON Plan + Static Validator | TODO | TODO | TODO | TODO | TODO |
| Full IGEP Planner | TODO | TODO | TODO | TODO | TODO |

### 25.4. End-to-end results

| Method | Heir-F1 | Share Acc. | Amount Acc. | Total Conservation | Legal Consistency | Case EM |
|---|---:|---:|---:|---:|---:|---:|
| LLM Direct | TODO | TODO | TODO | TODO | TODO | TODO |
| LLM + BM25 RAG | TODO | TODO | TODO | TODO | TODO | TODO |
| LLM + Hybrid RAG | TODO | TODO | TODO | TODO | TODO | TODO |
| Schema + RAG + Direct Answer | TODO | TODO | TODO | TODO | TODO | TODO |
| Free-form Python Generation | TODO | TODO | TODO | TODO | TODO | TODO |
| JSON Plan + Executor, No Enum | TODO | TODO | TODO | TODO | TODO | TODO |
| Full IGEP | TODO | TODO | TODO | TODO | TODO | TODO |
| Oracle Schema + Oracle Laws | TODO | TODO | TODO | TODO | TODO | TODO |

### 25.5. Reliability results

| Method | Coverage | Accuracy at Coverage | Critical Error Rate | Abstention Precision |
|---|---:|---:|---:|---:|
| LLM Direct | TODO | TODO | TODO | TODO |
| Hybrid RAG | TODO | TODO | TODO | TODO |
| Full IGEP | TODO | TODO | TODO | TODO |

---

## 26. Error taxonomy

```text
E1  Fact extraction omission
E2  Fact extraction hallucination
E3  Alias/coreference error
E4  Temporal-status error
E5  Money normalization error
E6  Missing issue enum
E7  Retrieval miss
E8  Irrelevant statute retained
E9  Applicable statute rejected
E10 Missing-fact misclassification
E11 Invalid JSON plan
E12 Wrong operation
E13 Wrong dependency/order
E14 Unsupported operation
E15 Execution error
E16 Arithmetic inconsistency
E17 Legal consistency violation
E18 Incorrect abstention
E19 Failure to abstain
```

Mỗi failed case nên được gán **first causal error**, không gán toàn bộ lỗi downstream.

Ví dụ:

```text
Extractor bỏ sót một người
→ planner chọn sai heirs
→ allocation sai
```

Root cause phải là `E1`, không phải planning error.

---

# PHẦN IV. CÂU HỎI NGHIÊN CỨU

## 27. Research questions

**RQ1.** LLM-based global structured extraction kết hợp normalization và deterministic validation có giảm hallucination và tăng tính hợp lệ của schema so với LLM-only hay không?

**RQ2.** Statute-derived legal issue enums có cải thiện khả năng truy xuất điều luật so với BM25 và dense retrieval hay không?

**RQ3.** JSON execution planning kết hợp deterministic executor có cải thiện độ chính xác số tiền và total conservation so với direct answer và free-form code generation hay không?

**RQ4.** Applicability filtering và post-execution verification đóng góp như thế nào vào legal consistency và critical error rate?

**RQ5.** Hệ thống có thể xác định đúng các case thiếu dữ kiện và abstain thay vì tạo kết quả không đáng tin cậy hay không?

---

# PHẦN V. ĐÓNG GÓP DỰ KIẾN

## 28. Contributions

1. **Inheritance-law allocation benchmark.** Một benchmark tiếng Việt kết hợp tình huống được biên soạn từ bản án thừa kế đã công bố và bài tập của cơ sở đào tạo luật, với đầu vào là facts đã làm sạch và đầu ra là phân bổ di sản có cấu trúc.

2. **Validator-guided structured extraction.** Một extractor LLM đọc toàn cục, được ràng buộc bởi JSON schema, normalization, evidence grounding và deterministic validation.

3. **Statute-derived legal issue vocabulary.** Một vocabulary enum được sinh từ corpus pháp luật và sử dụng như soft retrieval signal, tránh xây knowledge graph hoặc law card thủ công.

4. **Hybrid statute retrieval.** Một cơ chế retrieval kết hợp BM25, dense search, enum overlap, query expansion, rank fusion và reranking.

5. **Constrained executable legal planning.** LLM sinh JSON plan trên operation registry thay vì trả kết quả trực tiếp hoặc sinh Python tự do.

6. **Deterministic allocation and verification.** Kết quả tiền được tính bằng executor xác định và kiểm tra bằng legal, structural và arithmetic validators.

7. **Multi-level evaluation.** Đánh giá riêng extraction, retrieval, planning, execution, final allocation và abstention để phân tích error propagation.

---

# PHẦN VI. ĐỊNH VỊ SO VỚI NGHIÊN CỨU TRƯỚC

## 29. Khoảng trống nghiên cứu

Các hệ thống Vietnamese Civil Code QA trước đây chủ yếu truy xuất citation rồi sinh câu trả lời văn bản. Chúng chưa giải quyết bài toán phân bổ thừa kế có output định lượng và chưa tách reasoning khỏi exact computation.

Các phương pháp legal case retrieval dựa trên graph hoặc text–graph fusion tập trung vào tìm án tương tự, không thực hiện xác định khối di sản và chia tiền.

Các framework Program-aided hoặc Program-of-Thought cho thấy lợi ích của việc tách ngôn ngữ tự nhiên khỏi computation, nhưng thường cho phép sinh code tự do. IGEP thay thế arbitrary code bằng một operation registry được kiểm thử và JSON execution plan có validator.

Khoảng trống chính:

> Chưa có framework được biết đến cho luật thừa kế Việt Nam kết hợp structured fact extraction, statute-derived issue retrieval, constrained executable planning, deterministic monetary allocation và multi-level legal verification trên một benchmark hỗn hợp từ nguồn tư pháp và giáo dục pháp luật. Claim này phải được kiểm tra lại bằng systematic literature search trước khi submit.

---

# PHẦN VII. NGUYÊN TẮC THIẾT KẾ CUỐI CÙNG

## 30. Các quyết định đã chốt

```text
LLM-first extraction
Không chia thành nhiều sub-extractor tuần tự
Schema-constrained output
Deterministic normalization
External validation
Explicit repair hoặc abstention
Enum sinh từ luật và được freeze
Enum chỉ là soft retrieval signal
Hybrid retrieval thay vì enum-only retrieval
Applicability tách khỏi relevance
JSON plan thay vì Python tự do
Deterministic executor
Static plan validator
Post-execution verifier
Không sửa trực tiếp số tiền bằng LLM
```

## 31. Công thức tóm tắt

```text
LLM hiểu ngữ nghĩa
+ retrieval cung cấp căn cứ luật
+ deterministic components tính toán và kiểm tra
= hệ thống suy luận thừa kế có thể truy nguyên và đánh giá
```

Thiết kế tránh hai cực đoan:

```text
Pure LLM
→ linh hoạt nhưng khó tin cậy, khó truy nguyên và dễ sai số

Pure hand-coded rule system
→ chính xác cục bộ nhưng tốn công, khó mở rộng và khó xử lý ngôn ngữ tự nhiên
```

Kiến trúc phù hợp nhất:

> **LLM-first extraction, externally validated; enum-assisted but not enum-dependent retrieval; constrained planning; deterministic execution; explicit abstention.**

---

# 32. Tài liệu cần cite trong bài

Danh sách dưới đây là khung citation ban đầu. Thông tin BibTeX đầy đủ cần được kiểm tra lại trước khi submit.

1. Tran, Q.-D. L. and Nguyen, H.-M. H. *A Hybrid Approach to Enhancing Contextual Information for Vietnam Civil Code Question-Answering*. KSII Transactions on Internet and Information Systems, 2025. DOI: 10.3837/tiis.2025.01.005.

2. Chu, Q. and Chen, X. *A Multi-modal Graph-BERT Framework for Intelligent Legal Case Retrieval*. KSII Transactions on Internet and Information Systems, 2026. DOI: 10.3837/tiis.2026.05.003.

3. Lewis et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS, 2020.

4. Karpukhin et al. *Dense Passage Retrieval for Open-Domain Question Answering*. EMNLP, 2020.

5. Robertson and Zaragoza. *The Probabilistic Relevance Framework: BM25 and Beyond*. Foundations and Trends in Information Retrieval, 2009.

6. Gao et al. *PAL: Program-aided Language Models*. 2022.

7. Chen et al. *Program of Thoughts Prompting: Disentangling Computation from Reasoning for Numerical Reasoning Tasks*. 2022.

8. Wang et al. *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR, 2023.

9. Yao et al. *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR, 2023.

10. TODO: MAWARITH benchmark paper and recent inheritance reasoning systems; verify bibliographic metadata before final submission.

---

# 33. Checklist triển khai

## Dataset

- [ ] Chốt phạm vi pháp luật.
- [ ] Xây statute corpus theo điều/khoản.
- [ ] Làm sạch facts từ bản án và case giáo dục pháp luật.
- [ ] Loại court reasoning có thể tái tạo và final decision khỏi input; đánh dấu
  stipulated premise cho finding cần thiết nhưng không thể tái tạo.
- [ ] Chuẩn hóa tên người trong answer key.
- [x] Ghi nhận review độc lập cho toàn bộ 150 case ở cấp benchmark bởi bốn reviewer.
- [ ] Lưu reviewer-specific annotations/disagreement log để tính agreement có thể tái lập.
- [ ] Xác nhận riêng các field được tạo bởi full-schema migration nếu dùng chúng như expert gold.

## Enum và retrieval

- [ ] Sinh candidate enums từ corpus luật.
- [ ] Cluster và chuẩn hóa enum.
- [ ] Freeze vocabulary.
- [ ] Auto-annotate từng statute.
- [ ] Build BM25 index.
- [ ] Build dense index.
- [ ] Implement enum overlap.
- [ ] Implement query expansion.
- [ ] Implement RRF.
- [ ] Implement reranker.

## Extraction

- [ ] Chốt JSON schema.
- [ ] Viết extraction prompt.
- [ ] Thêm evidence span.
- [ ] Implement normalizer.
- [ ] Implement structural validator.
- [ ] Implement evidence validator.
- [ ] Implement consistency validator.
- [ ] Implement repair and abstention.

## Planning và execution

- [ ] Chốt operation registry.
- [ ] Viết unit tests cho từng operation.
- [ ] Chốt JSON plan schema.
- [ ] Implement static plan validator.
- [ ] Implement deterministic executor.
- [ ] Implement execution trace.
- [ ] Implement final verifier.

## Experiments

- [ ] Implement tất cả baseline.
- [ ] Chạy module-level evaluation.
- [ ] Chạy end-to-end evaluation.
- [ ] Chạy ablation.
- [ ] Phân tích root cause lỗi.
- [ ] Báo coverage và critical error rate.

---

# 34. Kết luận thiết kế

IGEP được xây dựng trên nguyên tắc không để một thành phần duy nhất nắm toàn bộ quyền quyết định. LLM đảm nhiệm phần hiểu ngôn ngữ và sinh biểu diễn có cấu trúc. Retrieval cung cấp nguồn luật chính thức. Applicability module đánh giá điều kiện áp dụng. Planner chọn các phép xử lý từ một vocabulary đóng. Executor thực hiện phép tính xác định. Validator và verifier ngăn các lỗi cấu trúc, pháp lý và số học trước khi xuất kết quả.

Điểm khoa học mạnh nhất của nghiên cứu không nằm ở số lượng agent mà nằm ở sự kết hợp giữa:

- benchmark thừa kế hỗn hợp từ nguồn tư pháp và giáo dục pháp luật;
- global structured extraction có kiểm chứng;
- statute-derived legal issue vocabulary;
- hybrid statute retrieval;
- constrained JSON planning;
- deterministic monetary allocation;
- explicit verification và abstention;
- multi-level evaluation của error propagation.

Đây là bộ khung được đề xuất để triển khai hệ thống, thực hiện thí nghiệm và viết bản journal paper hoàn chỉnh.
