## Output Schema v2.2 — Compact Name-Based Specification

### 1. Mục tiêu

Schema này là contract chuẩn cho bước trích xuất dữ kiện trực tiếp từ tình
huống thừa kế.

Benchmark bảo đảm tên chuẩn của mỗi người là duy nhất trong từng case. Vì vậy:

```text
Người và tổ chức
→ tham chiếu bằng tên chuẩn

Tài sản, di chúc, nghĩa vụ, sự kiện và thỏa thuận
→ tham chiếu bằng ID kỹ thuật
```

Kết quả cuối cùng của benchmark phải dùng đúng `persons[].name` hoặc
`organizations[].name` làm key.

Schema này được thiết kế để:

- đủ tín hiệu cho taxonomy thừa kế frozen;
- ngắn hơn bản v2.1 đầy đủ;
- tránh tạo hơn hai mươi top-level array;
- không buộc extractor đưa ra kết luận pháp lý;
- phù hợp với runtime LLM và deterministic executor.

---

## 2. Nguyên tắc trích xuất

Extractor chỉ ghi nhận dữ kiện được nêu trực tiếp.

Extractor không được:

- tự xác định người có quyền hưởng di sản;
- tự xác định di chúc hợp pháp hoặc không hợp pháp;
- tự tính phần tài sản của người chết trong tài sản chung;
- tự tính phần thừa kế;
- tự kết luận một khoản nợ, từ chối nhận di sản hoặc thỏa thuận là hợp lệ;
- tự chọn enum hoặc điều luật;
- tự tạo phân chia chưa được nêu trong đầu vào;
- dùng alias hoặc vai trò chung thay cho tên chuẩn.

Các kết luận pháp lý được xử lý sau:

```text
raw case
→ fact-only extractor
→ schema signal compiler
→ frozen enum selector
→ statute retrieval
→ applicability filter
→ execution plan
→ deterministic executor
→ final formatter
```

---

## 3. Cấu trúc tổng quát

```json
{
  "schema_version": "2.2.0",
  "case_id": null,

  "target_decedents": [],
  "persons": [],
  "organizations": [],
  "relationships": [],

  "estates": [],
  "wills": [],

  "inheritance_actions": [],
  "conduct_events": [],
  "agreements": [],
  "events": [],

  "legal_assertions": []
}
```

Mọi top-level array phải xuất hiện. Array không liên quan để `[]`.

---

## 4. Quy ước chung

### 4.1. Tên chuẩn

Mọi người phải xuất hiện trong `persons`.

```json
{
  "name": "Nguyễn Văn An",
  "aliases": ["ông An"]
}
```

Mọi reference đến người phải dùng chính xác:

```text
Nguyễn Văn An
```

Không dùng:

```text
ông An
người cha
người con
P1
```

Mọi tổ chức được reference phải xuất hiện trong `organizations`.

### 4.2. ID kỹ thuật

```text
E1, E2, ...       estate
A1, A2, ...       asset
O1, O2, ...       obligation
W1, W2, ...       will
D1, D2, ...       disposition
IA1, IA2, ...     inheritance action
CE1, CE2, ...     conduct event
AG1, AG2, ...     agreement
EVT1, EVT2, ...   generic event
LA1, LA2, ...     legal assertion
```

Mỗi ID phải duy nhất trong namespace tương ứng.

### 4.3. Thời gian

Chỉ dùng:

```text
YYYY
YYYY-MM
YYYY-MM-DD
null
```

Không tự thêm ngày hoặc tháng.

### 4.4. Trạng thái fact

Khi cần mô tả một dữ kiện được nêu, phủ nhận hoặc tranh chấp:

```text
stated_true
stated_false
disputed
not_mentioned
```

### 4.5. Giá trị không được nêu

- Trường đơn dùng `null`, `unknown` hoặc `not_mentioned`.
- Danh sách dùng `[]`.
- Object con không liên quan có thể dùng `null`.
- Không sinh hàng loạt trường suy đoán.

---

# 5. Các trường chi tiết

## 5.1. `target_decedents`

Danh sách tên người có di sản được yêu cầu giải quyết trong câu hỏi cuối.

```json
{
  "target_decedents": [
    "Nguyễn Văn An"
  ]
}
```

Người chết trong tình huống nhưng không phải đối tượng cần chia di sản chỉ xuất
hiện trong `persons`, `relationships` hoặc `events`.

---

## 5.2. `persons`

```json
{
  "name": "Nguyễn Văn An",
  "aliases": ["ông An"],

  "life_status": "deceased",
  "death_time": "2024",

  "birth_time": null,
  "conception_time": null,
  "birth_status": "unknown",

  "age": null,
  "age_status": "unknown",
  "working_capacity": "unknown",

  "awareness_state": "unknown",
  "literacy_status": "unknown",
  "physical_limitation": null,

  "last_residence": "Hà Nội"
}
```

`life_status`:

```text
alive
deceased
unknown
```

`birth_status`:

```text
born_alive
stillborn
unborn
unknown
```

`age_status`:

```text
minor
adult
unknown
```

`working_capacity`:

```text
able_to_work
unable_to_work
limited_working_capacity
unknown
```

`awareness_state`:

```text
aware
impaired
unaware
disputed
unknown
```

`literacy_status`:

```text
literate
illiterate
unknown
```

Chỉ ghi `minor`, `adult`, `unable_to_work`, `illiterate` hoặc trạng thái tương
tự khi văn bản trực tiếp nêu. Nếu chỉ có tuổi cụ thể thì lưu `age`, còn
`age_status` để `unknown`.

---

## 5.3. `organizations`

```json
{
  "name": "Công ty ABC",
  "organization_type": "enterprise",
  "existence_status": "existing",
  "termination_time": null
}
```

`organization_type`:

```text
court
enterprise
state_authority
notary_office
commune_committee
hospital
detention_facility
charitable_organization
other
```

`existence_status`:

```text
existing
not_existing
dissolved
terminated
disputed
unknown
```

---

## 5.4. `relationships`

```json
{
  "subject": "Nguyễn Văn Bình",
  "relation": "child_of",
  "object": "Nguyễn Văn An",

  "qualifiers": ["biological"],

  "relationship_status": "active",
  "start_time": null,
  "end_time": null,

  "mutual_care": "not_mentioned"
}
```

`relation`:

```text
spouse_of
child_of
sibling_of
grandchild_of
great_grandchild_of
grandparent_of
great_grandparent_of
aunt_uncle_of
niece_nephew_of
stepparent_of
other_relative_of
```

Quan hệ cha mẹ - con luôn ưu tiên ghi:

```text
người con → child_of → cha hoặc mẹ
```

`qualifiers`:

```text
legal_marriage
not_legally_recognized
biological
adopted_legal
adopted_not_legally_recognized
outside_marriage
step_relationship
full_sibling
half_sibling
not_mentioned
```

Một quan hệ có thể có nhiều qualifier.

`relationship_status`:

```text
active
ended
disputed
unknown
```

`mutual_care`:

```text
stated
absent
disputed
not_mentioned
```

---

# 6. Di sản

## 6.1. `estates`

```json
{
  "estate_id": "E1",
  "decedent": "Nguyễn Văn An",
  "opening_place": "Hà Nội",

  "assets": [],
  "obligations": [],
  "estate_roles": [],

  "distribution_status": "undivided"
}
```

`distribution_status`:

```text
undivided
partially_distributed
fully_distributed
unknown
```

### 6.1.1. Assets

```json
{
  "asset_id": "A1",
  "asset_type": "house",
  "description": "Căn nhà tại Hà Nội",

  "value": 2400000000,
  "currency": "VND",
  "valuation_time": "2024",

  "ownership_type": "marital_common_property",

  "owners": [
    {
      "holder_type": "person",
      "holder": "Nguyễn Văn An",
      "stated_share_ratio": "1/2"
    }
  ],

  "status": "existing"
}
```

`asset_type`:

```text
cash
house
apartment
land_use_right
vehicle
savings_deposit
gold_jewelry
securities
business_capital
receivable
other
```

`ownership_type`:

```text
separate_property
marital_common_property
joint_property
sole_property
unknown
```

`status`:

```text
existing
partially_existing
sold
transferred
destroyed
recovered
unknown
```

Không tự tính tỷ lệ thuộc di sản. Chỉ ghi `stated_share_ratio` khi đầu vào nêu
trực tiếp.

### 6.1.2. Obligations

```json
{
  "obligation_id": "O1",

  "obligation_type": "debt",

  "creditor_type": "person",
  "creditor": "Trần Văn Cường",

  "amount": 300000000,
  "currency": "VND",

  "decedent_liability_ratio": null,
  "secured_asset_ids": []
}
```

`obligation_type`:

```text
funeral_expense
unpaid_maintenance
estate_preservation_cost
dependent_support
labor_wage
compensation
tax_or_fee
debt
secured_debt
fine
other
```

Không có trường `validity`.

### 6.1.3. Estate roles

```json
{
  "role": "estate_manager",
  "holder_type": "person",
  "holder": "Nguyễn Văn Bình",

  "appointment_basis": "will",
  "status": "active"
}
```

`role`:

```text
estate_manager
estate_distributor
will_custodian
will_publisher
worship_property_manager
```

`appointment_basis`:

```text
will
heir_agreement
current_possession
state_authority
not_mentioned
other
```

`status`:

```text
active
ended
refused
disputed
unknown
```

---

# 7. Di chúc

## 7.1. `wills`

```json
{
  "will_id": "W1",
  "testator": "Nguyễn Văn An",
  "date": "2022",

  "medium": "written",
  "execution_method": "handwritten",

  "authentication": {
    "type": "notarized",
    "place": "Văn phòng công chứng Minh Tâm",
    "certifier": "Phạm Văn Dũng",
    "time": "2022"
  },

  "witnesses": [],

  "will_facts": null,

  "relations_to_other_wills": [],
  "dispositions": []
}
```

`medium`:

```text
written
oral
unknown
other
```

`execution_method`:

```text
handwritten
typed
written_by_other
oral_declaration
unknown
other
```

### 7.1.1. Authentication

```json
{
  "type": "notarized",
  "place": "Văn phòng công chứng Minh Tâm",
  "certifier": "Phạm Văn Dũng",
  "time": "2022"
}
```

`type`:

```text
none
notarized
certified
special_equivalent
unknown
```

Object dùng `null` khi hoàn toàn không liên quan.

### 7.1.2. Will facts

`will_facts` chứa các dữ kiện hình thức hiếm nhưng cần cho taxonomy.

```json
{
  "testator_signed": "stated_true",
  "testator_fingerprinted": "not_mentioned",
  "signed_before_witnesses": "not_mentioned",
  "witnesses_signed": "not_mentioned",

  "witness_count": 2,

  "life_threatening_context": "not_mentioned",
  "unable_to_make_written_will": "not_mentioned",
  "recorded_immediately": "not_mentioned",
  "record_time": null,
  "signature_certification_time": null,
  "testator_alive_after_three_months": "not_mentioned",
  "testator_aware_after_three_months": "not_mentioned",

  "has_execution_date": "stated_true",
  "has_testator_identity": "stated_true",
  "has_beneficiary_identity": "stated_true",
  "has_asset_description": "stated_true",
  "contains_abbreviation_or_symbol": "stated_false",

  "pages_numbered": "stated_true",
  "signed_each_page": "stated_true",
  "has_erasure_or_correction": "stated_false",
  "corrections_countersigned": "not_mentioned",

  "document_status": "available",
  "content_completeness": "complete",
  "ambiguous_content": "stated_false",

  "special_context": null
}
```

`document_status`:

```text
available
lost
damaged
recovered
destroyed
unknown
```

`content_completeness`:

```text
complete
partial
unreadable
unknown
```

`special_context` có thể là:

```text
active_duty_military
ship
aircraft
hospital
remote_research
overseas
detention
imprisonment
administrative_facility
other
null
```

### 7.1.3. Quan hệ giữa các di chúc

```json
{
  "relation": "replaces",
  "other_will_id": "W2",
  "affected_asset_ids": ["A1"]
}
```

`relation`:

```text
amends
supplements
replaces
revokes
partially_revokes
conflicts_with
```

### 7.1.4. Dispositions

```json
{
  "disposition_id": "D1",
  "disposition_type": "appoint_heir",

  "recipient_type": "person",
  "recipient": "Nguyễn Văn Bình",

  "manager_type": null,
  "manager": null,

  "affected_persons": [],

  "scope": "share_ratio",
  "asset_ids": [],
  "share_ratio": "1/2",
  "amount": null,
  "currency": null,

  "condition": null,
  "appointed_role": null
}
```

`disposition_type`:

```text
appoint_heir
bequest
worship_property
disinheritance
impose_obligation
appoint_estate_manager
appoint_estate_distributor
appoint_will_custodian
appoint_will_publisher
other
```

`scope`:

```text
entire_estate
specific_asset
specific_amount
share_ratio
remainder
entire_inheritance_right
other
```

Không cần trường `disinherited_persons` riêng. Truất quyền được biểu diễn bằng:

```json
{
  "disposition_type": "disinheritance",
  "affected_persons": ["Nguyễn Văn Bình"],
  "scope": "entire_inheritance_right"
}
```

---

# 8. Hành động, hành vi và thỏa thuận

## 8.1. `inheritance_actions`

```json
{
  "action_id": "IA1",

  "person": "Nguyễn Văn Bình",
  "related_decedent": "Nguyễn Văn An",

  "action": "renunciation",
  "time": "2024",
  "form": "written",

  "notified_parties": ["Trần Thị Hoa"],
  "stated_purpose": null
}
```

`action`:

```text
renunciation
acceptance
request_distribution
request_postponement
request_redistribution
other
```

Không có trường `validity`.

## 8.2. `conduct_events`

```json
{
  "conduct_event_id": "CE1",

  "actor": "Nguyễn Văn Bình",
  "target": "Nguyễn Văn An",

  "conduct_type": "intentional_harm_to_decedent",

  "conviction_status": "convicted",

  "purpose_to_obtain_inheritance": "not_mentioned",
  "decedent_knew_conduct": "stated_true",
  "decedent_still_granted_by_will": "stated_true"
}
```

`conduct_type`:

```text
intentional_harm_to_decedent
serious_abuse
serious_failure_of_support
intentional_harm_to_other_heir
deception_in_will_making
coercion_in_will_making
obstruction_of_will_making
will_forgery
will_alteration
will_destruction
will_concealment
other
```

`conviction_status`:

```text
convicted
not_convicted
alleged
disputed
unknown
```

Không tự kết luận người đó mất quyền hưởng.

## 8.3. `agreements`

```json
{
  "agreement_id": "AG1",

  "agreement_type": "distribution_method",
  "participants": [
    "Nguyễn Văn Bình",
    "Trần Thị Hoa"
  ],

  "form": "written",
  "time": "2024",

  "asset_ids": ["A1"],
  "terms": "Bình nhận nhà và thanh toán phần chênh lệch cho Hoa"
}
```

`agreement_type`:

```text
estate_manager_appointment
estate_distributor_appointment
distribution_method
asset_valuation
in_kind_recipient
distribution_postponement
manager_rights_and_duties
manager_remuneration
other
```

Không tự kết luận thỏa thuận có hiệu lực.

---

# 9. Generic events

`events` gom các sự kiện hiếm để tránh tạo nhiều top-level array.

```json
{
  "event_id": "EVT1",

  "event_type": "divorce_filed",

  "person": "Nguyễn Văn An",
  "related_person": "Trần Thị Hoa",

  "related_estate_id": null,
  "related_asset_id": null,
  "related_will_id": null,

  "time": "2023",

  "temporal_relation": "not_applicable",

  "details": {
    "description": "Đơn ly hôn đã được nộp nhưng chưa có bản án có hiệu lực"
  }
}
```

`event_type`:

```text
declared_missing
declared_dead
death_order
divorce_filed
divorce_decision_issued
divorce_effective
marriage_ended
remarriage
common_property_divided
adoption_started
adoption_ended
asset_sold
asset_transferred
asset_destroyed
asset_recovered
asset_income_generated
will_lost
will_damaged
will_recovered
will_deposited
will_delivered
will_published
will_translated
claim_filed
estate_distributed
distribution_postponed
postponement_extended
new_heir_discovered
heir_right_rejected
refund_requested
compensation_paid
other
```

`temporal_relation`:

```text
before
after
same_time
order_indeterminable
not_applicable
```

Ví dụ chết cùng thời điểm:

```json
{
  "event_id": "EVT2",
  "event_type": "death_order",
  "person": "Nguyễn Văn An",
  "related_person": "Nguyễn Văn Bình",
  "time": null,
  "temporal_relation": "same_time",
  "details": {}
}
```

`details` chỉ chứa dữ kiện trực tiếp không phù hợp với các trường chuẩn.

---

# 10. Legal assertions

Dùng khi văn bản trực tiếp đưa ra nhận định pháp lý.

```json
{
  "assertion_id": "LA1",

  "subject_type": "will",
  "subject_ref": "W1",

  "assertion": "valid",
  "asserted_by": "court_finding",

  "asserting_party_type": "organization",
  "asserting_party": "Tòa án nhân dân huyện X"
}
```

`subject_type`:

```text
person
organization
relationship
asset
obligation
will
inheritance_action
conduct_event
agreement
distribution
other
```

`asserted_by`:

```text
narrative
party_claim
party_denial
party_agreement
court_finding
official_document
other
```

Không tự tạo assertion. Assertion cũng không thay thế bước applicability filter.

---

# 11. Schema hoàn chỉnh

```json
{
  "schema_version": "2.2.0",
  "case_id": "string | null",

  "target_decedents": ["string"],

  "persons": [
    {
      "name": "string",
      "aliases": ["string"],

      "life_status": "alive | deceased | unknown",
      "death_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",

      "birth_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "conception_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "birth_status": "born_alive | stillborn | unborn | unknown",

      "age": "integer | null",
      "age_status": "minor | adult | unknown",
      "working_capacity": "able_to_work | unable_to_work | limited_working_capacity | unknown",

      "awareness_state": "aware | impaired | unaware | disputed | unknown",
      "literacy_status": "literate | illiterate | unknown",
      "physical_limitation": "string | null",

      "last_residence": "string | null"
    }
  ],

  "organizations": [
    {
      "name": "string",
      "organization_type": "court | enterprise | state_authority | notary_office | commune_committee | hospital | detention_facility | charitable_organization | other",
      "existence_status": "existing | not_existing | dissolved | terminated | disputed | unknown",
      "termination_time": "YYYY | YYYY-MM | YYYY-MM-DD | null"
    }
  ],

  "relationships": [
    {
      "subject": "string",
      "relation": "spouse_of | child_of | sibling_of | grandchild_of | great_grandchild_of | grandparent_of | great_grandparent_of | aunt_uncle_of | niece_nephew_of | stepparent_of | other_relative_of",
      "object": "string",

      "qualifiers": [
        "legal_marriage | not_legally_recognized | biological | adopted_legal | adopted_not_legally_recognized | outside_marriage | step_relationship | full_sibling | half_sibling | not_mentioned"
      ],

      "relationship_status": "active | ended | disputed | unknown",
      "start_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "end_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",

      "mutual_care": "stated | absent | disputed | not_mentioned"
    }
  ],

  "estates": [
    {
      "estate_id": "E1",
      "decedent": "string",
      "opening_place": "string | null",

      "assets": [
        {
          "asset_id": "A1",
          "asset_type": "cash | house | apartment | land_use_right | vehicle | savings_deposit | gold_jewelry | securities | business_capital | receivable | other",
          "description": "string",

          "value": "integer | number | null",
          "currency": "VND | other | null",
          "valuation_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",

          "ownership_type": "separate_property | marital_common_property | joint_property | sole_property | unknown",

          "owners": [
            {
              "holder_type": "person | organization",
              "holder": "string",
              "stated_share_ratio": "fraction | null"
            }
          ],

          "status": "existing | partially_existing | sold | transferred | destroyed | recovered | unknown"
        }
      ],

      "obligations": [
        {
          "obligation_id": "O1",
          "obligation_type": "funeral_expense | unpaid_maintenance | estate_preservation_cost | dependent_support | labor_wage | compensation | tax_or_fee | debt | secured_debt | fine | other",

          "creditor_type": "person | organization | unknown",
          "creditor": "string | null",

          "amount": "integer | number | null",
          "currency": "VND | other | null",

          "decedent_liability_ratio": "fraction | null",
          "secured_asset_ids": ["A1"]
        }
      ],

      "estate_roles": [
        {
          "role": "estate_manager | estate_distributor | will_custodian | will_publisher | worship_property_manager",
          "holder_type": "person | organization",
          "holder": "string",
          "appointment_basis": "will | heir_agreement | current_possession | state_authority | not_mentioned | other",
          "status": "active | ended | refused | disputed | unknown"
        }
      ],

      "distribution_status": "undivided | partially_distributed | fully_distributed | unknown"
    }
  ],

  "wills": [
    {
      "will_id": "W1",
      "testator": "string",
      "date": "YYYY | YYYY-MM | YYYY-MM-DD | null",

      "medium": "written | oral | unknown | other",
      "execution_method": "handwritten | typed | written_by_other | oral_declaration | unknown | other",

      "authentication": {
        "type": "none | notarized | certified | special_equivalent | unknown",
        "place": "string | null",
        "certifier": "string | null",
        "time": "YYYY | YYYY-MM | YYYY-MM-DD | null"
      },

      "witnesses": ["string"],

      "will_facts": {
        "testator_signed": "stated_true | stated_false | disputed | not_mentioned",
        "testator_fingerprinted": "stated_true | stated_false | disputed | not_mentioned",
        "signed_before_witnesses": "stated_true | stated_false | disputed | not_mentioned",
        "witnesses_signed": "stated_true | stated_false | disputed | not_mentioned",

        "witness_count": "integer | null",

        "life_threatening_context": "stated_true | stated_false | disputed | not_mentioned",
        "unable_to_make_written_will": "stated_true | stated_false | disputed | not_mentioned",
        "recorded_immediately": "stated_true | stated_false | disputed | not_mentioned",
        "record_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
        "signature_certification_time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
        "testator_alive_after_three_months": "stated_true | stated_false | disputed | not_mentioned",
        "testator_aware_after_three_months": "stated_true | stated_false | disputed | not_mentioned",

        "has_execution_date": "stated_true | stated_false | disputed | not_mentioned",
        "has_testator_identity": "stated_true | stated_false | disputed | not_mentioned",
        "has_beneficiary_identity": "stated_true | stated_false | disputed | not_mentioned",
        "has_asset_description": "stated_true | stated_false | disputed | not_mentioned",
        "contains_abbreviation_or_symbol": "stated_true | stated_false | disputed | not_mentioned",

        "pages_numbered": "stated_true | stated_false | disputed | not_mentioned",
        "signed_each_page": "stated_true | stated_false | disputed | not_mentioned",
        "has_erasure_or_correction": "stated_true | stated_false | disputed | not_mentioned",
        "corrections_countersigned": "stated_true | stated_false | disputed | not_mentioned",

        "document_status": "available | lost | damaged | recovered | destroyed | unknown",
        "content_completeness": "complete | partial | unreadable | unknown",
        "ambiguous_content": "stated_true | stated_false | disputed | not_mentioned",

        "special_context": "active_duty_military | ship | aircraft | hospital | remote_research | overseas | detention | imprisonment | administrative_facility | other | null"
      },

      "relations_to_other_wills": [
        {
          "relation": "amends | supplements | replaces | revokes | partially_revokes | conflicts_with",
          "other_will_id": "W2",
          "affected_asset_ids": ["A1"]
        }
      ],

      "dispositions": [
        {
          "disposition_id": "D1",
          "disposition_type": "appoint_heir | bequest | worship_property | disinheritance | impose_obligation | appoint_estate_manager | appoint_estate_distributor | appoint_will_custodian | appoint_will_publisher | other",

          "recipient_type": "person | organization | null",
          "recipient": "string | null",

          "manager_type": "person | organization | null",
          "manager": "string | null",

          "affected_persons": ["string"],

          "scope": "entire_estate | specific_asset | specific_amount | share_ratio | remainder | entire_inheritance_right | other",
          "asset_ids": ["A1"],
          "share_ratio": "fraction | null",
          "amount": "integer | number | null",
          "currency": "VND | other | null",

          "condition": "string | null",
          "appointed_role": "string | null"
        }
      ]
    }
  ],

  "inheritance_actions": [
    {
      "action_id": "IA1",
      "person": "string",
      "related_decedent": "string",
      "action": "renunciation | acceptance | request_distribution | request_postponement | request_redistribution | other",
      "time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "form": "written | oral | unknown | other",
      "notified_parties": ["string"],
      "stated_purpose": "string | null"
    }
  ],

  "conduct_events": [
    {
      "conduct_event_id": "CE1",
      "actor": "string",
      "target": "string | null",
      "conduct_type": "intentional_harm_to_decedent | serious_abuse | serious_failure_of_support | intentional_harm_to_other_heir | deception_in_will_making | coercion_in_will_making | obstruction_of_will_making | will_forgery | will_alteration | will_destruction | will_concealment | other",
      "conviction_status": "convicted | not_convicted | alleged | disputed | unknown",
      "purpose_to_obtain_inheritance": "stated_true | stated_false | disputed | not_mentioned",
      "decedent_knew_conduct": "stated_true | stated_false | disputed | not_mentioned",
      "decedent_still_granted_by_will": "stated_true | stated_false | disputed | not_mentioned"
    }
  ],

  "agreements": [
    {
      "agreement_id": "AG1",
      "agreement_type": "estate_manager_appointment | estate_distributor_appointment | distribution_method | asset_valuation | in_kind_recipient | distribution_postponement | manager_rights_and_duties | manager_remuneration | other",
      "participants": ["string"],
      "form": "written | oral | unknown | other",
      "time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "asset_ids": ["A1"],
      "terms": "string | null"
    }
  ],

  "events": [
    {
      "event_id": "EVT1",
      "event_type": "declared_missing | declared_dead | death_order | divorce_filed | divorce_decision_issued | divorce_effective | marriage_ended | remarriage | common_property_divided | adoption_started | adoption_ended | asset_sold | asset_transferred | asset_destroyed | asset_recovered | asset_income_generated | will_lost | will_damaged | will_recovered | will_deposited | will_delivered | will_published | will_translated | claim_filed | estate_distributed | distribution_postponed | postponement_extended | new_heir_discovered | heir_right_rejected | refund_requested | compensation_paid | other",

      "person": "string | null",
      "related_person": "string | null",

      "related_estate_id": "E1 | null",
      "related_asset_id": "A1 | null",
      "related_will_id": "W1 | null",

      "time": "YYYY | YYYY-MM | YYYY-MM-DD | null",
      "temporal_relation": "before | after | same_time | order_indeterminable | not_applicable",

      "details": {}
    }
  ],

  "legal_assertions": [
    {
      "assertion_id": "LA1",
      "subject_type": "person | organization | relationship | asset | obligation | will | inheritance_action | conduct_event | agreement | distribution | other",
      "subject_ref": "string",
      "assertion": "string",
      "asserted_by": "narrative | party_claim | party_denial | party_agreement | court_finding | official_document | other",
      "asserting_party_type": "person | organization | null",
      "asserting_party": "string | null"
    }
  ]
}
```

---

# 12. Trường không thuộc extractor output

Không thêm:

```text
selected_enums
applicable_laws
legal_issues
eligible_heirs
invalid_heirs
valid_will
invalid_will
net_estate_value
inheritance_shares
final_allocations
```

Enum selector có output riêng.

---

# 13. Final output benchmark

```json
{
  "Nguyễn Văn Bình": 800000000,
  "Trần Thị Hoa": 800000000
}
```

Không dùng ID, alias hoặc vai trò chung. Nếu người nhận là tổ chức, phải dùng
đúng `organizations[].name`.

---

# 14. Validation rules

1. `persons[].name` duy nhất trong case.
2. `organizations[].name` duy nhất trong case.
3. Mọi reference đến người tồn tại trong `persons`.
4. Mọi reference đến tổ chức tồn tại trong `organizations`.
5. Mọi `target_decedents` tồn tại trong `persons`.
6. Alias không được dùng làm reference chính.
7. ID kỹ thuật đúng pattern và duy nhất.
8. Mọi ID reference trỏ đến object tồn tại.
9. Không có trường `validity` trong will, obligation hoặc inheritance action.
10. Không tự sinh kết luận pháp lý.
11. Mọi key final allocation thuộc hợp của `persons[].name` và
    `organizations[].name`.
12. Tổ chức có thể xuất hiện trong final allocation khi là chủ nợ, bên nhận di
    tặng hoặc bên nhận hợp pháp khác.
