"""Experiment registry, prompts, and model-facing schemas for IGEP.

Keep model instructions in this file so experiments can freeze prompts without
mixing them with API, batching, and resume logic in ``run.py``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_SCHEMA_PATH = PROJECT_ROOT / "schema" / "valid.md"


# Competitive systems used in the end-to-end paper table. Oracle inputs are
# diagnostic upper bounds, while component removals are ablations, not baselines.
PAPER_BASELINES = [
    {
        "id": "B0",
        "name": "Monolithic closed-book LLM",
        "description": "Query -> GPT direct allocation; no schema and no retrieval.",
    },
    {
        "id": "B1",
        "name": "LLM + full statute context",
        "description": "Query + the frozen statute corpus -> GPT direct allocation.",
    },
    {
        "id": "B2",
        "name": "BM25 RAG + direct answer",
        "description": "BM25 top-k statutes -> GPT direct allocation.",
    },
    {
        "id": "B3",
        "name": "Dense RAG + direct answer",
        "description": "Voyage dense top-k statutes -> GPT direct allocation.",
    },
    {
        "id": "B4",
        "name": "Hybrid RAG + direct answer",
        "description": "BM25 + Voyage rank fusion -> GPT direct allocation.",
    },
    {
        "id": "B5",
        "name": "Coordinated modular LLM",
        "description": "Extractor -> retrieval -> allocation -> verification LLM roles.",
    },
    {
        "id": "B6",
        "name": "Schema + hybrid RAG + direct answer",
        "description": "Structured facts + hybrid statutes -> GPT direct allocation.",
    },
]

MAIN_METHOD = {
    "id": "M1",
    "name": "Full IGEP",
    "description": (
        "Strict fact extraction + external validation/repair; BM25 + Voyage dense "
        "+ frozen-enum soft signal; applicability filtering; constrained JSON plan; "
        "deterministic executor; post-execution verifier."
    ),
}

DIAGNOSTICS = [
    "Oracle schema + IGEP",
    "Oracle statutes + IGEP",
    "Oracle schema + oracle statutes + planner/executor",
]

ABLATIONS = [
    "Full IGEP without extraction repair",
    "Full IGEP without enum retrieval signal",
    "Full IGEP without applicability filter",
    "Full IGEP with direct answer instead of JSON plan + executor",
]

# These are the extraction variants that can be run now with the current
# 150-case full-schema gold and evaluator.
EXTRACTION_METHODS = {
    "prompt_only": {
        "label": "E1 Prompt-only JSON",
        "structured": False,
        "repair": False,
    },
    "structured": {
        "label": "E2 OpenAI strict structured output",
        "structured": True,
        "repair": False,
    },
    "igep": {
        "label": "M1 IGEP extraction (strict + validator + repair)",
        "structured": True,
        "repair": True,
        "staged": False,
    },
    "staged": {
        "label": "E3 Staged evidence extraction",
        "structured": True,
        "repair": False,
        "staged": True,
    },
}

for _method in EXTRACTION_METHODS.values():
    _method.setdefault("staged", False)


DEFAULT_EXTRACTION_PROMPT = "core_v1"
EXTRACTION_SCHEMA_ADAPTER_VERSION = "openai-strict-v1"

EXTRACTION_PROMPTS = {
    "core_v1": """\
Bạn là bộ trích xuất dữ kiện cho tình huống thừa kế.

Chỉ ghi dữ kiện được nêu trực tiếp, không suy luận pháp lý hoặc kết quả phân chia.
Trích xuất đầy đủ theo schema, giữ nguyên `case_id` và chỉ trả JSON.
""",
    "minimal_v1": """\
Bạn là bộ trích xuất dữ kiện cho tình huống thừa kế.

Yêu cầu:
1. Chỉ ghi dữ kiện được nêu trực tiếp trong đầu vào.
2. Không suy luận tính hợp pháp, điều luật, người được hưởng hoặc kết quả phân chia.
3. Trích xuất đầy đủ theo schema và không tạo bản ghi trùng.
4. Bỏ danh xưng khỏi tên người; dùng nhất quán tên chuẩn hóa cho mọi tham chiếu.
5. `child_of` có hướng người con đến cha hoặc mẹ; quan hệ đối xứng chỉ ghi một lần.
6. Dữ kiện không được nêu dùng giá trị thiếu tương ứng do schema quy định.
7. Giữ nguyên `case_id` và chỉ trả JSON theo schema.
""",
    "consistency_v1": """\
Bạn là bộ trích xuất dữ kiện cho tình huống thừa kế.

Yêu cầu:
1. Chỉ ghi dữ kiện được nêu trực tiếp trong đầu vào.
2. Không suy luận tính hợp pháp, điều luật, người được hưởng hoặc kết quả phân chia.
3. Trích xuất đầy đủ theo schema; khi không có dữ kiện, dùng giá trị thiếu do schema quy định.
4. Bỏ danh xưng khỏi tên người và dùng nhất quán tên chuẩn hóa cho mọi tham chiếu.
5. `child_of` có hướng người con đến cha hoặc mẹ; quan hệ đối xứng chỉ ghi một lần.
6. Dùng vị trí cụ thể nhất trong schema và không lặp lại cùng một dữ kiện ở generic event.
7. Trước khi trả kết quả, kiểm tra tham chiếu, chiều quan hệ và bản ghi trùng.
8. Giữ nguyên `case_id` và chỉ trả JSON theo schema.
""",
}

EXTRACTION_SYSTEM_PROMPT = EXTRACTION_PROMPTS[DEFAULT_EXTRACTION_PROMPT]
STAGED_EXTRACTION_VERSION = "staged-evidence-v2"

STAGED_IDENTITY_SYSTEM_PROMPT = """\
Bạn trích xuất sổ thực thể từ một tình huống thừa kế.

Chỉ ghi người, tổ chức và người để lại di sản được nêu trực tiếp.
Dùng một tên chuẩn hóa nhất quán, bỏ danh xưng nhưng không nhập hai người khác nhau.
Chỉ dùng giá trị khác placeholder thiếu khi dữ kiện tương ứng được nói rõ.
Mỗi record phải có ít nhất một trích dẫn nguyên văn ngắn từ đầu vào trong `evidence`.
Không trích xuất quan hệ, tài sản hoặc kết luận pháp lý. Chỉ trả JSON theo schema.
"""

STAGED_RELATIONSHIP_SYSTEM_PROMPT = """\
Bạn trích xuất quan hệ được nêu trực tiếp trong một tình huống thừa kế.

Chỉ dùng tên chuẩn hóa có trong sổ thực thể được cung cấp.
`child_of` có hướng từ người con đến cha hoặc mẹ; quan hệ đối xứng chỉ ghi một lần.
Không tự suy diễn qualifier, trạng thái hoặc thời gian của quan hệ; dùng placeholder
thiếu do schema quy định khi đầu vào không nói rõ.
Mỗi record phải có ít nhất một trích dẫn nguyên văn ngắn từ đầu vào trong `evidence`.
Không suy luận người thừa kế hoặc kết quả phân chia. Chỉ trả JSON theo schema.
"""

STAGED_ESTATE_SYSTEM_PROMPT = """\
Bạn trích xuất các dữ kiện còn lại của một tình huống thừa kế.

Trích xuất di sản, tài sản, nghĩa vụ, di chúc, hành vi thừa kế, hành vi liên quan,
thỏa thuận, sự kiện và nhận định pháp lý được nêu trực tiếp. Dùng nhất quán tên
chuẩn hóa trong sổ thực thể. Không lặp lại quan hệ đã có và không suy luận kết quả
phân chia. Không tự suy diễn quyền sở hữu, trạng thái tài sản hoặc trạng thái phân
chia. `description` của tài sản phải là đoạn trích nguyên văn ngắn nhất đủ nhận
diện tài sản. Không tạo generic event cho dữ kiện đã nằm ở trường cụ thể hơn.
Mỗi record cấp cao nhất phải có ít nhất một trích dẫn nguyên văn ngắn từ đầu vào
trong `evidence`. Chỉ trả JSON theo schema.
"""

EXTRACTION_USER_TEMPLATE = """\
case_id: {case_id}

Tình huống:
{query_text}
"""

REPAIR_SYSTEM_PROMPT = """\
Bạn sửa một JSON trích xuất dữ kiện thừa kế.
Giữ nguyên dữ kiện đúng, chỉ sửa các lỗi validator đã liệt kê.
Không thêm kết luận pháp lý hoặc phân bổ di sản. Chỉ trả về JSON theo schema.
"""

DIRECT_ANSWER_SYSTEM_PROMPT = """\
Bạn giải một tình huống phân chia di sản theo pháp luật Việt Nam.
Chỉ dùng tình huống và văn bản luật được cung cấp. Không bịa điều luật.
Trả kết quả phân bổ theo schema, kèm điều luật thực sự dùng. Nếu thiếu dữ kiện
quyết định hoặc ngoài phạm vi thì chọn trạng thái phù hợp thay vì đoán.
"""

PLAN_SYSTEM_PROMPT = """\
Bạn là legal planner của IGEP. Dùng facts đã kiểm tra và các điều luật đã được
đánh giá applicable để sinh một kế hoạch JSON trên operation registry đóng.
Không tự tính hoặc sửa số tiền cuối cùng; executor sẽ thực hiện phép tính.
Mỗi bước phải nêu đầu vào, căn cứ và phụ thuộc. Chỉ trả JSON theo schema.
"""


def load_gold_schema() -> dict[str, Any]:
    return json.loads(GOLD_SCHEMA_PATH.read_text(encoding="utf-8-sig"))


def openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return an OpenAI Structured Outputs compatible copy.

    The project schema already requires every property and closes all objects
    except ``event.details``. Strict Structured Outputs requires every object to
    use ``additionalProperties=false``. ``details`` is therefore restricted to
    an empty object until its key/value vocabulary is explicitly versioned.
    OpenAI does not accept ``uniqueItems`` for this model/API combination, so
    uniqueness remains an external deterministic-validator constraint.
    """

    result = copy.deepcopy(schema)
    annotations = {
        "$comment",
        "$id",
        "$schema",
        "default",
        "description",
        "examples",
        "readOnly",
        "title",
        "writeOnly",
    }

    def adapt(value: Any, *, name_map: bool = False) -> None:
        if isinstance(value, dict):
            if not name_map:
                for key in annotations:
                    value.pop(key, None)
                value.pop("uniqueItems", None)
                if "const" in value and "type" not in value:
                    const_value = value["const"]
                    if isinstance(const_value, str):
                        value["type"] = "string"
                    elif isinstance(const_value, bool):
                        value["type"] = "boolean"
                    elif isinstance(const_value, int):
                        value["type"] = "integer"
                    elif isinstance(const_value, (int, float)):
                        value["type"] = "number"
                    elif const_value is None:
                        value["type"] = "null"
            for key, child in value.items():
                adapt(child, name_map=key in {"$defs", "properties"})
        elif isinstance(value, list):
            for child in value:
                adapt(child)

    adapt(result)
    details = result["$defs"]["event"]["properties"]["details"]
    details.clear()
    details.update(
        {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
    )
    return result


def assert_openai_strict_schema(schema: dict[str, Any]) -> None:
    """Fail fast when the model-facing schema violates the strict contract."""

    errors: list[str] = []

    def walk(value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            if value.get("type") == "object" or "properties" in value:
                properties = set(value.get("properties", {}))
                required = set(value.get("required", []))
                if value.get("additionalProperties") is not False:
                    errors.append(f"{path}: object is not closed")
                if properties != required:
                    errors.append(f"{path}: properties and required differ")
            if "uniqueItems" in value:
                errors.append(f"{path}: uniqueItems is not accepted by the API")
            for key, child in value.items():
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}/{index}")

    walk(schema)
    if errors:
        raise ValueError("Invalid OpenAI extraction schema: " + "; ".join(errors[:10]))


FULL_SCHEMA = load_gold_schema()
OPENAI_EXTRACTION_SCHEMA = openai_strict_schema(FULL_SCHEMA)
assert_openai_strict_schema(OPENAI_EXTRACTION_SCHEMA)


STAGED_GROUPS = {
    "identity": ("target_decedents", "persons", "organizations"),
    "relationships": ("relationships",),
    "estate": (
        "estates",
        "wills",
        "inheritance_actions",
        "conduct_events",
        "agreements",
        "events",
        "legal_assertions",
    ),
}


def staged_schema(groups: tuple[str, ...]) -> dict[str, Any]:
    """Build a strict partial-schema contract with record-level evidence."""

    properties = {
        "case_id": copy.deepcopy(
            OPENAI_EXTRACTION_SCHEMA["properties"]["case_id"]
        )
    }
    for group in groups:
        properties[group] = copy.deepcopy(
            OPENAI_EXTRACTION_SCHEMA["properties"][group]
        )
    properties["evidence"] = {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["group", "record_index", "quote"],
            "properties": {
                "group": {"type": "string", "enum": list(groups)},
                "record_index": {"type": "integer"},
                "quote": {"type": "string"},
            },
        },
    }
    schema = {
        "$defs": copy.deepcopy(OPENAI_EXTRACTION_SCHEMA["$defs"]),
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", *groups, "evidence"],
        "properties": properties,
    }
    assert_openai_strict_schema(schema)
    return schema


STAGED_SCHEMAS = {
    name: staged_schema(groups) for name, groups in STAGED_GROUPS.items()
}


DIRECT_ALLOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "case_id",
        "cited_articles",
        "allocations",
        "undistributed_amount",
        "currency",
        "reason",
    ],
    "properties": {
        "case_id": {"type": "string"},
        "cited_articles": {
            "type": "array",
            "items": {"type": "string"},
        },
        "allocations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "recipient",
                    "amount",
                    "currency",
                    "share_ratio",
                    "basis",
                ],
                "properties": {
                    "recipient": {"type": "string"},
                    "amount": {"type": "integer", "minimum": 0},
                    "currency": {
                        "type": ["string", "null"],
                        "enum": ["VND", "other", None],
                    },
                    "share_ratio": {"type": ["string", "null"]},
                    "basis": {"type": "string"},
                },
            },
        },
        "undistributed_amount": {"type": ["number", "null"]},
        "currency": {
            "type": ["string", "null"],
            "enum": ["VND", "other", None],
        },
        "reason": {"type": ["string", "null"]},
    },
}

DIRECT_ALLOCATION_PROMPT_VERSION = "b0_closed_book_v1"
DIRECT_ALLOCATION_SYSTEM_PROMPT = """\
Bạn giải quyết bài toán phân chia di sản thừa kế Việt Nam từ đầu đến cuối.

Chỉ sử dụng dữ kiện trong tình huống. Không được bịa thêm người, tài sản, ngày,
quan hệ hoặc số tiền. Trả về đúng JSON schema được yêu cầu. `allocations` chỉ
gồm người cuối cùng nhận giá trị và số tiền VND nguyên, không âm. Luôn đưa ra
phương án phân chia trực tiếp tốt nhất từ dữ kiện hiện có, kể cả khi tình huống
khó hoặc thiếu rõ ràng. Không được từ chối, abstain hoặc trả trạng thái thay cho
kết quả phân chia. Không được xem hoặc suy đoán đáp án tham chiếu.
"""


def direct_allocation_user_prompt(case_id: str, query: str) -> str:
    return f"case_id: {case_id}\n\nTình huống:\n{query}\n\nHãy trả kết quả phân chia cuối cùng."


B2_ALLOCATION_PROMPT_VERSION = "b2_bm25_v1"
B2_ALLOCATION_SYSTEM_PROMPT = """\
Bạn giải quyết bài toán phân chia di sản thừa kế Việt Nam từ đầu đến cuối.

Bạn được cung cấp tình huống và các đoạn văn bản luật do BM25 truy xuất. Chỉ sử
dụng dữ kiện trong tình huống; văn bản luật chỉ là căn cứ pháp lý, không phải dữ
kiện vụ việc. Trả về đúng JSON schema được yêu cầu. `allocations` chỉ gồm người
cuối cùng nhận giá trị và số tiền VND nguyên, không âm. Luôn đưa ra phương án
phân chia trực tiếp tốt nhất. Không tạo structured extraction, issue profile,
execution plan, tool call hoặc verifier output. Không được xem hoặc suy đoán đáp
án tham chiếu.
"""


def b2_allocation_user_prompt(
    case_id: str, query: str, retrieved_statutes: list[dict[str, Any]]
) -> str:
    context = "\n\n".join(
        "\n".join(
            [
                f"[STATUTE {rank}] {row['id']}",
                f"Văn bản: {row['metadata'].get('document_title', '')}",
                f"Hiệu lực: {row['metadata'].get('effective_from')} đến "
                f"{row['metadata'].get('effective_to')}",
                row["text"],
            ]
        )
        for rank, row in enumerate(retrieved_statutes, 1)
    )
    return (
        f"case_id: {case_id}\n\n"
        f"Tình huống:\n{query}\n\n"
        f"Văn bản luật BM25 truy xuất:\n{context}\n\n"
        "Hãy trực tiếp trả kết quả phân chia cuối cùng. Trong `cited_articles`, "
        "ghi số điều luật thực sự dùng."
    )


B4_ALLOCATION_PROMPT_VERSION = "b4_hybrid_v1"
B4_ALLOCATION_SYSTEM_PROMPT = """\
Bạn giải quyết bài toán phân chia di sản thừa kế Việt Nam từ đầu đến cuối.

Bạn được cung cấp tình huống và các đoạn văn bản luật do truy xuất hybrid BM25
và dense cung cấp. Chỉ sử dụng dữ kiện trong tình huống; văn bản luật chỉ là căn
cứ pháp lý, không phải dữ kiện vụ việc. Trả về đúng JSON schema được yêu cầu.
`allocations` chỉ gồm người cuối cùng nhận giá trị và số tiền VND nguyên, không
âm. Luôn đưa ra phương án phân chia trực tiếp tốt nhất. Không tạo structured
extraction, issue profile, execution plan, tool call hoặc verifier output. Không
được xem hoặc suy đoán đáp án tham chiếu.
"""


def b4_allocation_user_prompt(
    case_id: str, query: str, retrieved_statutes: list[dict[str, Any]]
) -> str:
    """Use the B2 direct-allocation structure with fused statute context."""
    context = "\n\n".join(
        "\n".join(
            [
                f"[STATUTE {rank}] {row['id']}",
                f"Văn bản: {row['metadata'].get('document_title', '')}",
                f"Hiệu lực: {row['metadata'].get('effective_from')} đến "
                f"{row['metadata'].get('effective_to')}",
                row["text"],
            ]
        )
        for rank, row in enumerate(retrieved_statutes, 1)
    )
    return (
        f"case_id: {case_id}\n\n"
        f"Tình huống:\n{query}\n\n"
        f"Văn bản luật hybrid truy xuất:\n{context}\n\n"
        "Hãy trực tiếp trả kết quả phân chia cuối cùng. Trong `cited_articles`, "
        "ghi số điều luật thực sự dùng."
    )


B5_PROMPT_VERSION = "b5_modular_v1"
B5_MODULE_ORDER = [
    "structured_case_extraction",
    "inheritance_issue_analysis",
    "statute_aware_reasoning",
    "coordinated_final_allocation",
]

B5_EXTRACTION_SYSTEM_PROMPT = """\
Bạn là module trích xuất dữ kiện của baseline B5. Chỉ ghi dữ kiện được nêu rõ
trong tình huống: người, quan hệ, cái chết/mở thừa kế, tài sản, nghĩa vụ, di
chúc, tặng cho, chuyển giao và ngày tháng. Không suy luận người thừa kế, điều
luật hoặc kết quả chia. Ghi rõ thông tin thiếu hay không chắc chắn. Chỉ trả JSON
đúng schema.
"""

B5_ISSUE_SYSTEM_PROMPT = """\
Bạn là module phân tích vấn đề thừa kế của baseline B5. Dùng tình huống, dữ kiện
đã trích xuất và văn bản luật truy xuất để xác định các vấn đề pháp lý được dữ
kiện kích hoạt. Giải thích liên kết dữ kiện-vấn đề. Không đưa ra kết quả phân bổ
cuối cùng. Không tạo execution plan hay gọi công cụ. Chỉ trả JSON đúng schema.
"""

B5_REASONING_SYSTEM_PROMPT = """\
Bạn là module lập luận pháp luật của baseline B5. Dùng dữ kiện có cấu trúc, phân
tích vấn đề và văn bản luật truy xuất để trình bày các bước lập luận, điều luật,
phép tính và trạng thái thừa kế trung gian. Đánh dấu rõ giả định và điểm chưa
giải quyết. Không trả output allocation cuối cùng, không tạo executable plan,
không dùng deterministic executor và không tự kiểm chứng/sửa lại. Chỉ trả JSON
đúng schema.
"""

B5_ALLOCATION_SYSTEM_PROMPT = """\
Bạn là module phân bổ cuối cùng của baseline B5. Phối hợp tình huống gốc, dữ kiện
có cấu trúc, phân tích vấn đề và lập luận pháp luật đã cung cấp để trực tiếp trả
kết quả phân chia cuối cùng theo đúng allocation schema. Không tạo thêm module,
không verifier, không repair, không abstain và không suy đoán đáp án tham chiếu.
"""


def _b5_statute_context(retrieved_statutes: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        "\n".join([
            f"[STATUTE {rank}] {row['id']}",
            f"Văn bản: {row['metadata'].get('document_title', '')}",
            f"Hiệu lực: {row['metadata'].get('effective_from')} đến {row['metadata'].get('effective_to')}",
            row["text"],
        ])
        for rank, row in enumerate(retrieved_statutes, 1)
    )


def b5_extraction_user_prompt(case_id: str, query: str) -> str:
    return f"case_id: {case_id}\n\nTình huống:\n{query}\n\nHãy trích xuất dữ kiện được hỗ trợ trực tiếp."


def b5_issue_user_prompt(
    case_id: str, query: str, extraction: dict[str, Any],
    retrieved_statutes: list[dict[str, Any]],
) -> str:
    return (
        f"case_id: {case_id}\n\nTình huống:\n{query}\n\n"
        f"Dữ kiện có cấu trúc:\n{json.dumps(extraction, ensure_ascii=False)}\n\n"
        f"Văn bản luật B4 hybrid truy xuất:\n{_b5_statute_context(retrieved_statutes)}\n\n"
        "Hãy phân tích vấn đề pháp lý; không phân bổ cuối cùng."
    )


def b5_reasoning_user_prompt(
    case_id: str, extraction: dict[str, Any], issues: dict[str, Any],
    retrieved_statutes: list[dict[str, Any]],
) -> str:
    return (
        f"case_id: {case_id}\n\n"
        f"Dữ kiện có cấu trúc:\n{json.dumps(extraction, ensure_ascii=False)}\n\n"
        f"Phân tích vấn đề:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"Văn bản luật B4 hybrid truy xuất:\n{_b5_statute_context(retrieved_statutes)}\n\n"
        "Hãy lập luận và tính toán trung gian; không trả allocation cuối cùng."
    )


def b5_allocation_user_prompt(
    case_id: str, query: str, extraction: dict[str, Any],
    issues: dict[str, Any], reasoning: dict[str, Any],
) -> str:
    return (
        f"case_id: {case_id}\n\nTình huống gốc:\n{query}\n\n"
        f"Dữ kiện có cấu trúc:\n{json.dumps(extraction, ensure_ascii=False)}\n\n"
        f"Phân tích vấn đề:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"Lập luận pháp luật:\n{json.dumps(reasoning, ensure_ascii=False)}\n\n"
        "Hãy trả kết quả phân chia cuối cùng theo allocation schema."
    )


_NULLABLE_STRING = {"type": ["string", "null"]}
_NULLABLE_INTEGER = {"type": ["integer", "null"]}

B5_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["case_id", "persons", "relationships", "succession_openings", "assets", "obligations", "wills_gifts_transfers", "explicit_uncertainties"],
    "properties": {
        "case_id": {"type": "string"},
        "persons": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["name", "stated_role", "death_date"], "properties": {
                "name": {"type": "string"}, "stated_role": {"type": "string"}, "death_date": _NULLABLE_STRING}}},
        "relationships": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["person_a", "relationship", "person_b", "details"], "properties": {
                "person_a": {"type": "string"}, "relationship": {"type": "string"}, "person_b": {"type": "string"}, "details": {"type": "string"}}}},
        "succession_openings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["decedent", "date", "details"], "properties": {
                "decedent": {"type": "string"}, "date": _NULLABLE_STRING, "details": {"type": "string"}}}},
        "assets": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["description", "value_vnd", "stated_ownership"], "properties": {
                "description": {"type": "string"}, "value_vnd": _NULLABLE_INTEGER, "stated_ownership": {"type": "string"}}}},
        "obligations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["description", "amount_vnd"], "properties": {
                "description": {"type": "string"}, "amount_vnd": _NULLABLE_INTEGER}}},
        "wills_gifts_transfers": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["kind", "actor", "beneficiary", "date", "details"], "properties": {
                "kind": {"type": "string"}, "actor": {"type": "string"}, "beneficiary": _NULLABLE_STRING,
                "date": _NULLABLE_STRING, "details": {"type": "string"}}}},
        "explicit_uncertainties": {"type": "array", "items": {"type": "string"}},
    },
}

B5_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["case_id", "succession_modes", "succession_order", "will_issues", "representation_issues", "mandatory_share_issues", "estate_issues", "obligation_issues", "multi_stage_issues", "other_issues", "fact_issue_links", "unresolved_ambiguities"],
    "properties": {
        "case_id": {"type": "string"},
        **{field: {"type": "array", "items": {"type": "string"}} for field in [
            "succession_modes", "succession_order", "will_issues", "representation_issues",
            "mandatory_share_issues", "estate_issues", "obligation_issues", "multi_stage_issues",
            "other_issues", "unresolved_ambiguities"]},
        "fact_issue_links": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["fact", "issue", "explanation"], "properties": {
                "fact": {"type": "string"}, "issue": {"type": "string"}, "explanation": {"type": "string"}}}},
    },
}

B5_REASONING_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["case_id", "applicable_statutes", "reasoning_steps", "intermediate_calculations", "intermediate_succession_states", "assumptions", "unresolved_ambiguities"],
    "properties": {
        "case_id": {"type": "string"},
        "applicable_statutes": {"type": "array", "items": {"type": "string"}},
        "reasoning_steps": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["step", "facts", "statutes", "conclusion"], "properties": {
                "step": {"type": "integer"}, "facts": {"type": "array", "items": {"type": "string"}},
                "statutes": {"type": "array", "items": {"type": "string"}}, "conclusion": {"type": "string"}}}},
        "intermediate_calculations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["description", "expression", "result_vnd"], "properties": {
                "description": {"type": "string"}, "expression": {"type": "string"}, "result_vnd": _NULLABLE_INTEGER}}},
        "intermediate_succession_states": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["opening", "decedent", "state"], "properties": {
                "opening": {"type": "integer"}, "decedent": {"type": "string"}, "state": {"type": "string"}}}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "unresolved_ambiguities": {"type": "array", "items": {"type": "string"}},
    },
}


APPLICABILITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["case_id", "decisions"],
    "properties": {
        "case_id": {"type": "string"},
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "statute_id",
                    "applicable",
                    "fact_evidence",
                    "reason",
                ],
                "properties": {
                    "statute_id": {"type": "string"},
                    "applicable": {"type": "boolean"},
                    "fact_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


PLAN_OPERATIONS = [
    "split_common_property",
    "identify_estate",
    "pay_obligation",
    "apply_will",
    "reserve_compulsory_share",
    "identify_intestate_heirs",
    "apply_representation",
    "exclude_unworthy_heir",
    "redistribute_lapsed_share",
    "transfer_inheritance_share",
    "compensate_in_kind",
    "preserve_worship_property",
]

EXECUTION_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["case_id", "status", "steps", "reason"],
    "properties": {
        "case_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["processable", "under_specified", "unsupported_operation"],
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "step_id",
                    "operation",
                    "estate_id",
                    "asset_id",
                    "person",
                    "recipient",
                    "amount",
                    "ratio",
                    "depends_on",
                    "legal_basis",
                    "note",
                ],
                "properties": {
                    "step_id": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "enum": PLAN_OPERATIONS,
                    },
                    "estate_id": {"type": ["string", "null"]},
                    "asset_id": {"type": ["string", "null"]},
                    "person": {"type": ["string", "null"]},
                    "recipient": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "null"]},
                    "ratio": {"type": ["string", "null"]},
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "legal_basis": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "note": {"type": ["string", "null"]},
                },
            },
        },
        "reason": {"type": ["string", "null"]},
    },
}


def raw_schema_instruction() -> str:
    """Schema text used only by the prompt-only baseline."""

    return (
        "\nJSON phải tuân theo contract sau (API không cưỡng chế schema ở baseline này):\n"
        + json.dumps(OPENAI_EXTRACTION_SCHEMA, ensure_ascii=False, separators=(",", ":"))
    )


def extraction_user_prompt(case_id: str, query_text: str) -> str:
    return EXTRACTION_USER_TEMPLATE.format(
        case_id=case_id,
        query_text=query_text.strip(),
    )


def repair_user_prompt(
    case_id: str,
    query_text: str,
    previous: dict[str, Any],
    errors: list[str],
) -> str:
    return (
        extraction_user_prompt(case_id, query_text)
        + "\n\nJSON cần sửa:\n"
        + json.dumps(previous, ensure_ascii=False)
        + "\n\nLỗi validator:\n- "
        + "\n- ".join(errors[:50])
    )
