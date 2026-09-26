# IGEP research roadmap

Tài liệu này theo dõi trạng thái triển khai và thứ tự công việc của IGEP.
Thiết kế kiến trúc chi tiết nằm trong `DESIGN.md`; các claim
chính thức về dữ liệu nằm trong `data/DATASET_CARD.md`.

## 1. Mục tiêu

IGEP hướng tới một hệ thống suy luận và phân bổ di sản thừa kế Việt Nam gồm:

```text
sanitized case
→ structured fact extraction
→ statute retrieval
→ constrained execution plan
→ deterministic allocation
→ legal and arithmetic verification
```

Đầu ra chính là danh sách người nhận và số tiền tương ứng, kèm căn cứ luật,
execution trace và khả năng abstain khi dữ kiện hoặc operation không đủ.

## 2. Nguyên tắc đã chốt

- Benchmark được xử lý theo thiết lập closed-world.
- Runtime input không chứa article labels hoặc reference allocation.
- Court-derived và legal-education cases được báo cáo riêng.
- Kết quả toàn dataset được gọi trung tính là `reference_allocation`.
- Stipulated legal premise phải có metadata và metric exclusion tương ứng.
- LLM dùng để hiểu ngôn ngữ và sinh cấu trúc, không trực tiếp sửa số tiền cuối.
- Retrieval dùng taxonomy như soft signal, không dùng taxonomy làm legal truth.
- Planner chỉ chọn operation từ registry đóng.
- Executor và kiểm tra số học phải xác định, có unit test.
- Khi không đủ dữ kiện hoặc operation, hệ thống phải abstain rõ ràng.

## 3. Trạng thái tổng quan

| Phase | Trạng thái |
|---|---|
| Benchmark foundation | Gần hoàn thành |
| Structured extraction | Có prototype, cần semantic evaluation |
| Statute retrieval | Chưa triển khai đầy đủ |
| Planning and execution | Chưa triển khai |
| End-to-end experiments | Chưa triển khai |
| Paper and release package | Chưa hoàn thành |

## 4. Phase 1 — Benchmark foundation

### 4.1. Đã hoàn thành

- [x] Chuẩn hóa 150 case trong `data/benchmark.csv`.
- [x] Sinh 150 runtime records tại `data/canonical/input.jsonl`.
- [x] Sinh 150 reference records tại `data/canonical/reference.jsonl`.
- [x] Phân loại 129 `court_judgment_derived` cases.
- [x] Phân loại 21 `legal_education_case` cases.
- [x] Phân biệt `court_adjudicated_outcome` và
  `reviewed_educational_answer`.
- [x] Ghi nhận benchmark-level review độc lập bởi bốn reviewer.
- [x] Ghi rõ không thể tái tạo inter-annotator agreement từ repository.
- [x] Audit leakage đối với court finding và legal conclusion trong input.
- [x] Sửa 18 case theo quyết định của tác giả.
- [x] Sửa scenario, timeline và allocation của case 125.
- [x] Thêm `legal_premise_policy` cho stipulated/adjudicated premises.
- [x] Thêm `excluded_module_metrics` cho các subtask có nguy cơ leakage.
- [x] Canonical format validation pass cho 150 case.

### 4.2. Cần hoàn thành trước khi public release

- [x] Loại bỏ format audit và các extraction audit lịch sử đã bị supersede.
- [x] Sinh thống kê phân bố benchmark có thể tái tạo.
- [x] Chốt split `igep-split-v1`: 30 development và 120 held-out test.
- [x] Chạy near-duplicate và family/event overlap audit; không có nhóm bắt
  buộc nào cắt qua hai partition.
- [x] Gắn stable internal source ID; original judgment ID còn được đánh dấu
  thiếu thay vì suy đoán.
- [x] Tạo provenance record cho 150 case và ghi rõ các locator còn thiếu.
- [x] Chốt không public redistribution cho đến khi hoàn tất source-level
  copyright/licensing clearance.
- [x] Tạo SHA-256 manifest và access tier cho các artifact.

### 4.3. Giới hạn claim

Benchmark-level review bao phủ sanitized input, reference articles và reference
allocation. Review này không tự động chứng minh mọi field được sinh khi migrate
sang full schema đã được bốn reviewer kiểm tra độc lập.

Không gọi toàn bộ reference là `court ground truth` hoặc universal legal truth.
Không báo inter-annotator agreement khi không có annotation riêng từng reviewer.

## 5. Phase 2 — Structured extraction

### 5.1. Đã có

- [x] Extraction prompt theo nguyên tắc fact-only.
- [x] Full schema v2.2 và tài liệu mapping.
- [x] Structured-output runner.
- [x] Structural/schema validation không còn lỗi.
- [x] Exact evidence-span validation cho legacy extraction gold.
- [x] Full-schema evaluator và gold self-evaluation tests.
- [x] Pilot cho monolithic và staged extraction.

### 5.2. Cần làm

- [ ] Chốt schema runtime tối thiểu, không mang field chỉ phục vụ gold.
- [ ] Chốt representation cho thời gian và thứ tự tử vong.
- [ ] Chốt evidence span ở cấp atomic fact.
- [ ] Xây expert-reviewed extraction subset trước khi gọi là semantic gold.
- [ ] Review thủ công entity, relationship, estate, will và event fields.
- [ ] Đánh giá hallucination, omission và evidence faithfulness.
- [ ] Đánh giá predicted schema so với oracle schema.
- [ ] Báo extraction performance theo source group và complexity group.

### 5.3. Exit criteria

- Expert-reviewed subset có protocol và provenance rõ.
- Không có entity hoặc amount không được input/evidence hỗ trợ.
- Structural validity không được dùng thay cho semantic correctness.
- Module metrics, confidence interval và error taxonomy được báo cáo.

## 6. Phase 3 — Statute corpus and retrieval

### 6.1. Corpus

- [ ] Chốt phạm vi Bộ luật Dân sự và luật liên quan.
- [x] Xác định phiên bản luật áp dụng cho 213 lần mở thừa kế.
- [x] Chuẩn hóa bốn văn bản lõi theo điều, khoản và điểm.
- [x] Lưu effective date và source URL chính thức cho bốn văn bản lõi.
- [x] Loại 13 opening trước 10/09/1990 khỏi retrieval evaluation cho đến khi
  hoàn thiện composite historical corpus.

### 6.2. Taxonomy annotation

- [x] Có taxonomy frozen v1.0.0.
- [x] Có bản abridged cho runtime/retrieval.
- [ ] Ghi lại đầy đủ quy trình LLM-assisted và manual review của taxonomy.
- [ ] Map taxonomy vào từng statute unit bằng prompt cố định.
- [ ] Kiểm tra consistency và coverage của statute annotations.
- [ ] Version statute annotations và lưu checksum taxonomy nguồn.

### 6.3. Retrieval implementation

- [ ] Xây BM25 baseline.
- [ ] Xây dense retrieval baseline.
- [ ] Xây enum-overlap retrieval.
- [ ] Triển khai query expansion từ validated schema.
- [ ] Triển khai reciprocal rank fusion.
- [ ] Triển khai reranker.
- [ ] Tách relevance khỏi applicability và sufficiency.
- [ ] Đánh giá Recall@k, MRR và nDCG.

## 7. Phase 4 — Planning and deterministic execution

### 7.1. Operation registry

- [ ] Chốt vocabulary operation tối thiểu.
- [ ] Định nghĩa input/output contract cho từng operation.
- [ ] Gắn legal basis và precondition cho operation pháp lý.
- [ ] Viết unit test cho tài sản chung, nghĩa vụ và di sản ròng.
- [ ] Viết unit test cho hàng thừa kế và thế vị.
- [ ] Viết unit test cho di chúc và mandatory share.
- [ ] Viết unit test cho nhiều thời điểm mở thừa kế.
- [ ] Định nghĩa `unsupported_operation` rõ ràng.

### 7.2. Plan and executor

- [ ] Chốt JSON plan schema.
- [ ] Chặn free-form code execution từ planner.
- [ ] Xây static validator cho reference, dependency và ratio.
- [ ] Xây deterministic executor dùng exact decimal/rational arithmetic.
- [ ] Sinh execution trace theo từng operation.
- [ ] Kiểm tra total conservation và non-negative allocation.
- [ ] Xây legal consistency verifier.
- [ ] Xây repair/re-execution policy có giới hạn.
- [ ] Xây abstention output có reason code.

### 7.3. Exit criteria

- Mỗi operation có test và precondition.
- Executor cho cùng plan phải luôn cho cùng kết quả.
- Không cho LLM trực tiếp ghi đè allocation sau execution.
- Unsupported cases được báo cáo trong coverage, không bị tính như thành công.

## 8. Phase 5 — Experiments

### 8.1. Baselines

- [ ] B0 monolithic end-to-end LLM allocation (closed-book).
- [ ] B0 monolithic end-to-end LLM allocation with fixed RAG.
- [ ] B1 coordinated modular LLM pipeline with extractor, retrieval,
  allocation and verification roles.
- [ ] BM25 RAG plus direct generation.
- [ ] Hybrid RAG plus direct generation.
- [ ] Structured schema plus direct generation.
- [ ] JSON plan plus executor without taxonomy.
- [ ] Full IGEP.
- [ ] Oracle schema plus oracle statutes upper bound.

### 8.2. Ablations

- [ ] Không taxonomy signal.
- [ ] Không dense retrieval.
- [ ] Không applicability filter.
- [ ] Không extraction validator.
- [ ] Không plan validator.
- [ ] Không final verifier.
- [ ] Predicted schema so với oracle schema.

### 8.3. Metrics

- Retrieval: Recall@k, MRR và nDCG.
- Extraction: entity/relationship/event F1 và evidence faithfulness.
- Planning: plan validity, operation accuracy và dependency accuracy.
- Allocation: heir F1, amount accuracy, total conservation và case exact match.
- Reliability: coverage, accuracy at coverage, critical-error rate và abstention.
- Báo cáo riêng cho court-derived và educational subsets.
- Báo cáo confidence interval hoặc paired significance test phù hợp.

## 9. Phase 6 — Paper and release

- [ ] Thực hiện systematic literature search trước khi chốt novelty claim.
- [ ] Xác minh toàn bộ bibliographic metadata và DOI.
- [ ] Viết data statement và limitations section.
- [ ] Mô tả chính xác review scope và stipulated-premise protocol.
- [ ] Công bố model, prompt và inference parameters.
- [ ] Công bố environment/dependency lock file.
- [ ] Công bố seed, split manifest và evaluation commands.
- [ ] Tạo reproducibility table cho mọi kết quả trong paper.
- [ ] Chuẩn bị release artifact không chứa secret hoặc dữ liệu hạn chế.

## 10. Thứ tự công việc tiếp theo

1. Dọn mâu thuẫn giữa audit legacy và canonical documentation.
2. Hoàn thiện benchmark statistics, provenance, licensing và split audit.
3. Chọn và expert-review extraction subset.
4. Chốt statute corpus có version và effective dates.
5. Xây retrieval baselines trước khi triển khai planner.
6. Chốt operation registry và test executor độc lập với LLM.
7. Tích hợp planner, verifier và abstention.
8. Chạy baselines, ablations, oracle experiments và error analysis.

## 11. Definition of done

IGEP chỉ được xem là sẵn sàng nộp bài khi:

- benchmark release có provenance, licensing và split audit;
- mọi claim review khớp với artifact có trong repository;
- extraction gold dùng để chấm semantic fields đã được review phù hợp;
- statute corpus có version và nguồn chính thức;
- retrieval, planning và execution có baseline cùng ablation;
- allocation được executor kiểm tra bảo toàn tổng;
- unsupported cases và abstention được báo cáo minh bạch;
- kết quả có thể tái lập từ manifest và command được công bố;
- novelty claim đã được đối chiếu bằng literature review có hệ thống.
