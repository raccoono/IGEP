# IGEP extraction prompt — core v1

Runtime source of truth:

```text
scripts/igep_specs.py
EXTRACTION_PROMPTS["core_v1"]
```

Model:

```text
gpt-5-mini
```

System prompt:

```text
Bạn là bộ trích xuất dữ kiện cho tình huống thừa kế.

Chỉ ghi dữ kiện được nêu trực tiếp, không suy luận pháp lý hoặc kết quả phân chia.
Trích xuất đầy đủ theo schema, giữ nguyên `case_id` và chỉ trả JSON.
```

User template:

```text
case_id: {case_id}

Tình huống:
{query_text}
```

Output contract:

- Full schema: `schema/valid.md`, version `2.2.0`.
- OpenAI adapter: `openai-strict-v1`.
- All objects are closed and all properties are required.
- `uniqueItems` remains an external validator rule because it is not accepted
  by the Structured Outputs endpoint used in this experiment.
- No benchmark example, answer, statute, named person, monetary value, or
  case-specific rule is included in the prompt.

Default decoding configuration:

```text
OPENAI_MODEL=gpt-5-mini
OPENAI_REASONING_EFFORT=low
OPENAI_MAX_OUTPUT_TOKENS=6000
OPENAI_TIMEOUT_SECONDS=120
OPENAI_ATTEMPTS=2
```

Selection:

- Frozen after the development prompt study; future experiment runs must record
  the selected prompt ID and decoding configuration in their run manifest.
- Development IDs were selected without reading gold labels.
- `core_v1` achieved the highest content, item, and structure F1 both on the
  eight-case development split and on the three-case completed intersection.
- This pilot selects the prompt only; final paper results must be reported on
  the frozen full evaluation population.
