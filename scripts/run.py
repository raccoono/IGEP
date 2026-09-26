"""Small, resumable runner for IGEP model experiments.

Available now:
  * B0 monolithic closed-book final-allocation baseline;
  * extraction baselines and IGEP extraction on the 150-case benchmark;
  * Voyage statute-corpus indexing and dense search.

The statute corpus, applicability evaluator, operation registry, and executor
must be frozen before the end-to-end M1 experiment is enabled.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from build_gold import graph_validation_errors, validate_instance
from igep_specs import (
    ABLATIONS,
    DIAGNOSTICS,
    DEFAULT_EXTRACTION_PROMPT,
    DIRECT_ALLOCATION_PROMPT_VERSION,
    DIRECT_ALLOCATION_SCHEMA,
    DIRECT_ALLOCATION_SYSTEM_PROMPT,
    EXTRACTION_METHODS,
    EXTRACTION_PROMPTS,
    EXTRACTION_SCHEMA_ADAPTER_VERSION,
    FULL_SCHEMA,
    MAIN_METHOD,
    OPENAI_EXTRACTION_SCHEMA,
    PAPER_BASELINES,
    REPAIR_SYSTEM_PROMPT,
    STAGED_ESTATE_SYSTEM_PROMPT,
    STAGED_EXTRACTION_VERSION,
    STAGED_GROUPS,
    STAGED_IDENTITY_SYSTEM_PROMPT,
    STAGED_RELATIONSHIP_SYSTEM_PROMPT,
    STAGED_SCHEMAS,
    extraction_user_prompt,
    direct_allocation_user_prompt,
    raw_schema_instruction,
    repair_user_prompt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "canonical" / "input.jsonl"
DEFAULT_RUN_DIR = PROJECT_ROOT / "data" / "runs"
DEFAULT_SPLIT_MANIFEST = PROJECT_ROOT / "data" / "release" / "split.csv"
B0_DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
B0_DEFAULT_REASONING_EFFORT = "low"
B0_DEFAULT_MAX_OUTPUT_TOKENS = 6000
B0_DEFAULT_TIMEOUT_SECONDS = 120
B0_DEFAULT_ATTEMPTS = 2


def b0_config() -> dict[str, Any]:
    """Return the explicit, traceable B0 inference configuration."""
    return {
        "model": env("B0_MODEL", B0_DEFAULT_MODEL),
        "reasoning_effort": env(
            "B0_REASONING_EFFORT", B0_DEFAULT_REASONING_EFFORT
        ),
        "max_output_tokens": int(
            env("B0_MAX_OUTPUT_TOKENS", str(B0_DEFAULT_MAX_OUTPUT_TOKENS))
        ),
        # The selected reasoning model/API configuration does not expose a
        # project-approved temperature control. Do not send an unsupported
        # parameter; record the omission explicitly in traces.
        "temperature": None,
        "timeout_seconds": int(
            env("B0_TIMEOUT_SECONDS", str(B0_DEFAULT_TIMEOUT_SECONDS))
        ),
        "attempts": int(env("B0_ATTEMPTS", str(B0_DEFAULT_ATTEMPTS))),
        "prompt_version": DIRECT_ALLOCATION_PROMPT_VERSION,
    }


def split_case_ids(path: Path, split: str) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            str(row["case_id"])
            for row in csv.DictReader(handle)
            if row["split"] == split
        }


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing {name}. Fill it in {PROJECT_ROOT / '.env'}")
    return value or ""


def post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = 180,
    attempts: int = 4,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code not in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
            last_error = f"HTTP {exc.code}: {detail}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(2**attempt)
    raise RuntimeError(last_error)


def response_text(response: dict[str, Any]) -> str:
    if response.get("status") == "incomplete":
        raise RuntimeError(f"Incomplete OpenAI response: {response.get('incomplete_details')}")
    parts: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise RuntimeError(f"Model refusal: {content.get('refusal')}")
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    if not parts:
        raise RuntimeError("OpenAI response contained no output_text")
    return "".join(parts)


def extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        first_newline = candidate.find("\n")
        candidate = candidate[first_newline + 1 :]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model output must be one JSON object")
    return value


def openai_call(
    system_prompt: str,
    user_prompt: str,
    *,
    structured: bool,
    output_schema: dict[str, Any] | None = None,
    schema_name: str = "igep_extraction_v2_2_minimal",
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
    timeout_seconds: int | None = None,
    attempts: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_model = model or env("OPENAI_MODEL", "gpt-5-mini")
    payload: dict[str, Any] = {
        "model": selected_model,
        "store": False,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "reasoning": {
            "effort": reasoning_effort
            or env("OPENAI_REASONING_EFFORT", "low"),
        },
        "max_output_tokens": max_output_tokens
        if max_output_tokens is not None
        else int(env("OPENAI_MAX_OUTPUT_TOKENS", "6000")),
    }
    if structured:
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": output_schema or OPENAI_EXTRACTION_SCHEMA,
            }
        }
    response = post_json(
        env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/responses",
        env("OPENAI_API_KEY", required=True),
        payload,
        timeout=timeout_seconds
        if timeout_seconds is not None
        else int(env("OPENAI_TIMEOUT_SECONDS", "120")),
        attempts=attempts
        if attempts is not None
        else int(env("OPENAI_ATTEMPTS", "2")),
    )
    return extract_json(response_text(response)), response


def voyage_embed(texts: list[str], input_type: str) -> tuple[list[list[float]], int]:
    payload = {
        "model": env("VOYAGE_MODEL", "voyage-4-large"),
        "input": texts,
        "input_type": input_type,
        "truncation": False,
        "output_dimension": int(env("VOYAGE_OUTPUT_DIMENSION", "1024")),
        "output_dtype": "float",
    }
    response = post_json(
        env("VOYAGE_BASE_URL", "https://api.voyageai.com/v1").rstrip("/")
        + "/embeddings",
        env("VOYAGE_API_KEY", required=True),
        payload,
    )
    ordered = sorted(response["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in ordered], response.get("usage", {}).get(
        "total_tokens", 0
    )


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if text.startswith("["):
        records = json.loads(text)
    else:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(records, list) or not all(isinstance(x, dict) for x in records):
        raise ValueError(f"{path} must contain a JSON array or JSONL objects")
    return records


def normalized_case(record: dict[str, Any]) -> tuple[str, str]:
    case_id = record.get("case_id", record.get("Case_ID"))
    query = record.get("query_text", record.get("User_Query"))
    if case_id is None or not isinstance(query, str):
        raise ValueError("Each input needs case_id/Case_ID and query_text/User_Query")
    return str(case_id), query


def normalize_evidence_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def accent_insensitive_token(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")


def recover_source_name(name: str, query: str) -> str:
    candidate_tokens = re.findall(r"\w+", name, flags=re.UNICODE)
    if not candidate_tokens:
        return name
    query_tokens = list(re.finditer(r"\w+", query, flags=re.UNICODE))
    width = len(candidate_tokens)
    target = [accent_insensitive_token(token) for token in candidate_tokens]
    matches: list[str] = []
    for start in range(len(query_tokens) - width + 1):
        window = query_tokens[start : start + width]
        normalized = [
            accent_insensitive_token(token.group()) for token in window
        ]
        if normalized == target:
            matches.append(" ".join(token.group() for token in window))
    distinct = list(dict.fromkeys(matches))
    return distinct[0] if len(distinct) == 1 else name


def replace_exact_strings(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: replace_exact_strings(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [replace_exact_strings(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def canonicalize_staged_prediction(
    prediction: dict[str, Any],
    query: str,
) -> dict[str, Any]:
    entity_names = [
        *prediction.get("target_decedents", []),
        *[
            item.get("name")
            for group in ("persons", "organizations")
            for item in prediction.get(group, [])
            if isinstance(item, dict)
        ],
    ]
    replacements = {
        name: recovered
        for name in entity_names
        if isinstance(name, str)
        and (recovered := recover_source_name(name, query)) != name
    }
    result = replace_exact_strings(prediction, replacements)
    for relationship in result.get("relationships", []):
        if isinstance(relationship, dict):
            relationship["qualifiers"] = [
                qualifier
                for qualifier in relationship.get("qualifiers", [])
                if qualifier != "not_mentioned"
            ]
    return result


def stage_validation_errors(
    stage: str,
    value: dict[str, Any],
    query: str,
) -> list[str]:
    schema = STAGED_SCHEMAS[stage]
    errors = [
        f"{stage}: {error}"
        for error in validate_instance(value, schema, schema)
    ]
    if errors:
        return errors

    normalized_query = normalize_evidence_text(query)
    covered: set[tuple[str, int]] = set()
    for index, evidence in enumerate(value["evidence"]):
        group = evidence["group"]
        record_index = evidence["record_index"]
        quote = normalize_evidence_text(evidence["quote"])
        if record_index < 0 or record_index >= len(value[group]):
            errors.append(
                f"{stage}: evidence[{index}] has invalid {group}[{record_index}]"
            )
            continue
        covered.add((group, record_index))
        if not quote or quote not in normalized_query:
            errors.append(
                f"{stage}: evidence[{index}] is not an exact input quote"
            )

    for group in STAGED_GROUPS[stage]:
        for record_index in range(len(value[group])):
            if (group, record_index) not in covered:
                errors.append(
                    f"{stage}: {group}[{record_index}] has no evidence"
                )
    return errors


def merge_numeric_dicts(values: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for value in values:
        for key, item in value.items():
            if isinstance(item, (int, float)):
                result[key] = result.get(key, 0) + item
            elif isinstance(item, dict):
                prior = result.get(key)
                nested = prior if isinstance(prior, dict) else {}
                result[key] = merge_numeric_dicts([nested, item])
    return result


def staged_context(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_decedents": identity["target_decedents"],
        "persons": [item["name"] for item in identity["persons"]],
        "organizations": [item["name"] for item in identity["organizations"]],
    }


def run_staged_extraction(
    case_id: str,
    query: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    stages: list[dict[str, Any]] = []
    evidence_errors: list[str] = []
    base_prompt = extraction_user_prompt(case_id, query)

    identity, identity_response = openai_call(
        STAGED_IDENTITY_SYSTEM_PROMPT,
        base_prompt,
        structured=True,
        output_schema=STAGED_SCHEMAS["identity"],
        schema_name="igep_staged_identity_v1",
    )
    identity["case_id"] = case_id
    identity_errors = stage_validation_errors("identity", identity, query)
    if any("has no evidence" not in error and "exact input quote" not in error for error in identity_errors):
        raise RuntimeError("; ".join(identity_errors[:20]))
    evidence_errors.extend(identity_errors)
    stages.append(
        {
            "stage": "identity",
            "response_id": identity_response.get("id"),
            "usage": identity_response.get("usage"),
            "evidence": identity.get("evidence", []),
            "evidence_errors": identity_errors,
        }
    )

    entity_ledger = staged_context(identity)
    relationship_prompt = (
        base_prompt
        + "\n\nSổ thực thể đã khóa:\n"
        + json.dumps(entity_ledger, ensure_ascii=False, separators=(",", ":"))
    )
    relationships, relationship_response = openai_call(
        STAGED_RELATIONSHIP_SYSTEM_PROMPT,
        relationship_prompt,
        structured=True,
        output_schema=STAGED_SCHEMAS["relationships"],
        schema_name="igep_staged_relationships_v1",
    )
    relationships["case_id"] = case_id
    relationship_errors = stage_validation_errors(
        "relationships", relationships, query
    )
    if any("has no evidence" not in error and "exact input quote" not in error for error in relationship_errors):
        raise RuntimeError("; ".join(relationship_errors[:20]))
    evidence_errors.extend(relationship_errors)
    stages.append(
        {
            "stage": "relationships",
            "response_id": relationship_response.get("id"),
            "usage": relationship_response.get("usage"),
            "evidence": relationships.get("evidence", []),
            "evidence_errors": relationship_errors,
        }
    )

    remaining_prompt = (
        base_prompt
        + "\n\nSổ thực thể đã khóa:\n"
        + json.dumps(entity_ledger, ensure_ascii=False, separators=(",", ":"))
        + "\n\nQuan hệ đã trích xuất; không lặp lại ở generic event:\n"
        + json.dumps(
            relationships["relationships"],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    remaining, remaining_response = openai_call(
        STAGED_ESTATE_SYSTEM_PROMPT,
        remaining_prompt,
        structured=True,
        output_schema=STAGED_SCHEMAS["estate"],
        schema_name="igep_staged_estate_v1",
    )
    remaining["case_id"] = case_id
    remaining_errors = stage_validation_errors("estate", remaining, query)
    if any("has no evidence" not in error and "exact input quote" not in error for error in remaining_errors):
        raise RuntimeError("; ".join(remaining_errors[:20]))
    evidence_errors.extend(remaining_errors)
    stages.append(
        {
            "stage": "estate",
            "response_id": remaining_response.get("id"),
            "usage": remaining_response.get("usage"),
            "evidence": remaining.get("evidence", []),
            "evidence_errors": remaining_errors,
        }
    )

    prediction: dict[str, Any] = {
        "schema_version": "2.2.0",
        "case_id": case_id,
    }
    for group in STAGED_GROUPS["identity"]:
        prediction[group] = identity[group]
    prediction["relationships"] = relationships["relationships"]
    for group in STAGED_GROUPS["estate"]:
        prediction[group] = remaining[group]
    prediction = canonicalize_staged_prediction(prediction, query)

    usage = merge_numeric_dicts(
        [
            response.get("usage", {})
            for response in (
                identity_response,
                relationship_response,
                remaining_response,
            )
            if isinstance(response.get("usage"), dict)
        ]
    )
    response_summary = {
        "id": None,
        "usage": usage,
        "_stages": stages,
    }
    return prediction, response_summary, evidence_errors


def validation_errors(prediction: dict[str, Any]) -> list[str]:
    errors = validate_instance(prediction, FULL_SCHEMA, FULL_SCHEMA)
    if not errors:
        errors.extend(graph_validation_errors(prediction))
    return errors


def existing_case_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(record.get("case_id"))
        for record in load_records(path)
        if record.get("case_id") is not None
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def trace_record(
    case_id: str,
    method: str,
    prompt_version: str,
    started: float,
    *,
    response: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    evidence_errors: list[str] | None = None,
    repairs: int = 0,
    exception: Exception | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "method": method,
        "model": env("OPENAI_MODEL", "gpt-5-mini"),
        "prompt_version": prompt_version,
        "schema_adapter_version": EXTRACTION_SCHEMA_ADAPTER_VERSION,
        "response_id": response.get("id") if response else None,
        "usage": response.get("usage") if response else None,
        "stages": response.get("_stages") if response else None,
        "validation_errors": errors or [],
        "evidence_errors": evidence_errors or [],
        "repair_count": repairs,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "error": str(exception) if exception else None,
    }


def b0_trace_record(
    case_id: str,
    split: str,
    started: float,
    config: dict[str, Any],
    *,
    response: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    exception: Exception | None = None,
) -> dict[str, Any]:
    """Small B0-specific trace containing the frozen experiment settings."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "split": split,
        "method": "b0",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "max_output_tokens": config["max_output_tokens"],
        "temperature": config["temperature"],
        "timeout_seconds": config["timeout_seconds"],
        "attempt_count": config["attempts"],
        "retry_count": max(config["attempts"] - 1, 0),
        "prompt_version": config["prompt_version"],
        "response_id": response.get("id") if response else None,
        "usage": response.get("usage") if response else None,
        "structural_validation_errors": errors or [],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "error": str(exception) if exception else None,
    }


def run_extract(args: argparse.Namespace) -> None:
    method = EXTRACTION_METHODS[args.method]
    system_prompt = EXTRACTION_PROMPTS[args.prompt_version]
    experiment_version = (
        STAGED_EXTRACTION_VERSION if method["staged"] else args.prompt_version
    )
    output = args.output or DEFAULT_RUN_DIR / (
        f"extraction_{args.method}_{experiment_version}.jsonl"
    )
    trace = args.trace or output.with_name(output.stem + ".trace.jsonl")
    records = load_records(args.input)
    if args.split == "test" and not args.allow_held_out_test:
        raise ValueError(
            "Held-out test access is locked. Freeze the complete method first, "
            "then pass --allow-held-out-test explicitly."
        )
    allowed = split_case_ids(args.split_manifest, args.split)
    records = [r for r in records if normalized_case(r)[0] in allowed]
    if args.case_id:
        wanted = set(args.case_id)
        records = [r for r in records if normalized_case(r)[0] in wanted]
    if args.limit is not None:
        records = records[: args.limit]

    if args.dry_run:
        if not records:
            raise RuntimeError("No matching input records")
        case_id, query = normalized_case(records[0])
        print(
            json.dumps(
                {
                    "method": args.method,
                    "label": method["label"],
                    "model": env("OPENAI_MODEL", "gpt-5-mini"),
                    "prompt_version": experiment_version,
                    "schema_adapter_version": EXTRACTION_SCHEMA_ADAPTER_VERSION,
                    "structured": method["structured"],
                    "repair": method["repair"],
                    "staged": method["staged"],
                    "case_id": case_id,
                    "user_prompt": extraction_user_prompt(case_id, query),
                    "system_prompt": (
                        system_prompt if not method["staged"] else None
                    ),
                    "stage_prompts": (
                        {
                            "identity": STAGED_IDENTITY_SYSTEM_PROMPT,
                            "relationships": STAGED_RELATIONSHIP_SYSTEM_PROMPT,
                            "estate": STAGED_ESTATE_SYSTEM_PROMPT,
                        }
                        if method["staged"]
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    env("OPENAI_API_KEY", required=True)
    completed = existing_case_ids(output) if args.resume else set()
    selected = [
        record
        for record in records
        if normalized_case(record)[0] not in completed
    ]
    print(
        f"{method['label']}: {len(selected)} pending / {len(records)} selected; "
        f"output={output}"
    )
    for index, record in enumerate(selected, 1):
        case_id, query = normalized_case(record)
        started = time.perf_counter()
        response: dict[str, Any] | None = None
        evidence_errors: list[str] = []
        try:
            if method["staged"]:
                prediction, response, evidence_errors = run_staged_extraction(
                    case_id, query
                )
            else:
                user_prompt = extraction_user_prompt(case_id, query)
                if not method["structured"]:
                    user_prompt += raw_schema_instruction()
                prediction, response = openai_call(
                    system_prompt,
                    user_prompt,
                    structured=bool(method["structured"]),
                )
            # case_id and schema version are deterministic protocol fields, not
            # semantic predictions.
            prediction["case_id"] = case_id
            prediction["schema_version"] = "2.2.0"
            errors = validation_errors(prediction)
            repairs = 0
            while method["repair"] and errors and repairs < args.max_repairs:
                repairs += 1
                prediction, response = openai_call(
                    REPAIR_SYSTEM_PROMPT,
                    repair_user_prompt(case_id, query, prediction, errors),
                    structured=True,
                )
                prediction["case_id"] = case_id
                prediction["schema_version"] = "2.2.0"
                errors = validation_errors(prediction)
            append_jsonl(output, prediction)
            append_jsonl(
                trace,
                trace_record(
                    case_id,
                    args.method,
                    experiment_version,
                    started,
                    response=response,
                    errors=errors,
                    evidence_errors=evidence_errors,
                    repairs=repairs,
                ),
            )
            print(
                f"[{index}/{len(selected)}] case {case_id}: "
                f"{len(errors)} validation errors, {repairs} repairs"
            )
        except Exception as exc:
            append_jsonl(
                trace,
                trace_record(
                    case_id,
                    args.method,
                    experiment_version,
                    started,
                    response=response,
                    evidence_errors=evidence_errors,
                    exception=exc,
                ),
            )
            print(f"[{index}/{len(selected)}] case {case_id}: ERROR {exc}", file=sys.stderr)


def run_allocate(args: argparse.Namespace) -> None:
    """Run the frozen B0 monolithic closed-book allocation baseline."""
    output = args.output or DEFAULT_RUN_DIR / "allocation_dev_b0.jsonl"
    trace = args.trace or output.with_name(output.stem + ".trace.jsonl")
    config = b0_config()
    records = load_records(args.input)
    if args.split == "test" and not args.allow_held_out_test:
        raise ValueError(
            "Held-out test access is locked. Freeze the complete method first, "
            "then pass --allow-held-out-test explicitly."
        )
    allowed = split_case_ids(args.split_manifest, args.split)
    records = [r for r in records if normalized_case(r)[0] in allowed]
    if args.case_id:
        wanted = set(args.case_id)
        records = [r for r in records if normalized_case(r)[0] in wanted]
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise RuntimeError("No matching input records")

    if args.dry_run:
        case_id, query = normalized_case(records[0])
        print(json.dumps({
            "method": "b0", "label": "B0 monolithic closed-book LLM",
            "configuration": config,
            "case_id": case_id,
            "system_prompt": DIRECT_ALLOCATION_SYSTEM_PROMPT,
            "user_prompt": direct_allocation_user_prompt(case_id, query),
            "output_schema": DIRECT_ALLOCATION_SCHEMA,
        }, ensure_ascii=False, indent=2))
        return

    env("OPENAI_API_KEY", required=True)
    completed = existing_case_ids(output) if args.resume else set()
    selected = [r for r in records if normalized_case(r)[0] not in completed]
    print(f"B0 monolithic allocation: {len(selected)} pending / {len(records)} selected; output={output}")
    for index, record in enumerate(selected, 1):
        case_id, query = normalized_case(record)
        started = time.perf_counter()
        response = None
        try:
            prediction, response = openai_call(
                DIRECT_ALLOCATION_SYSTEM_PROMPT,
                direct_allocation_user_prompt(case_id, query),
                structured=True,
                output_schema=DIRECT_ALLOCATION_SCHEMA,
                schema_name="igep_direct_allocation_v1",
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
                max_output_tokens=config["max_output_tokens"],
                timeout_seconds=config["timeout_seconds"],
                attempts=config["attempts"],
            )
            prediction["case_id"] = case_id
            errors = validate_instance(
                prediction, DIRECT_ALLOCATION_SCHEMA, DIRECT_ALLOCATION_SCHEMA
            )
            if errors:
                raise ValueError("; ".join(errors[:10]))
            append_jsonl(output, prediction)
            append_jsonl(trace, b0_trace_record(
                case_id, args.split, started, config,
                response=response, errors=errors,
            ))
            print(f"[{index}/{len(selected)}] case {case_id}: complete")
        except Exception as exc:
            append_jsonl(trace, b0_trace_record(
                case_id, args.split, started, config,
                response=response, exception=exc,
            ))
            print(f"[{index}/{len(selected)}] case {case_id}: ERROR {exc}", file=sys.stderr)


def chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def run_index(args: argparse.Namespace) -> None:
    records = load_records(args.input)
    output_rows: list[dict[str, Any]] = []
    total_tokens = 0
    for batch in chunks(records, args.batch_size):
        texts = [str(row[args.text_field]) for row in batch]
        vectors, tokens = voyage_embed(texts, "document")
        total_tokens += tokens
        for row, text, vector in zip(batch, texts, vectors, strict=True):
            identifier = row.get(args.id_field)
            if identifier is None:
                raise ValueError(f"Missing {args.id_field} in corpus record")
            output_rows.append(
                {
                    "id": str(identifier),
                    "text": text,
                    "metadata": {
                        key: value
                        for key, value in row.items()
                        if key not in {args.text_field, args.id_field}
                    },
                    "embedding": vector,
                }
            )
        print(f"Embedded {len(output_rows)}/{len(records)} documents")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Index: {args.output}; Voyage tokens: {total_tokens}")


def cosine(a: list[float], b: list[float]) -> float:
    numerator = sum(x * y for x, y in zip(a, b, strict=True))
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return numerator / denominator if denominator else 0.0


def search_row(
    row: dict[str, Any],
    id_field: str,
    text_field: str,
) -> dict[str, Any]:
    identifier = row.get("id", row.get(id_field))
    text = row.get("text", row.get(text_field))
    if identifier is None or not isinstance(text, str):
        raise ValueError(
            f"Every search record needs id/{id_field} and text/{text_field}"
        )
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {
            key: value
            for key, value in row.items()
            if key not in {id_field, text_field, "id", "text", "embedding"}
        }
    return {
        "id": str(identifier),
        "text": text,
        "metadata": metadata,
        "embedding": row.get("embedding"),
    }


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def bm25_scores(rows: list[dict[str, Any]], query: str) -> dict[str, float]:
    documents = [tokenize(row["text"]) for row in rows]
    query_terms = tokenize(query)
    count = len(documents)
    if not count:
        return {}
    average_length = sum(map(len, documents)) / count or 1.0
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    scores: dict[str, float] = {}
    k1, b = 1.5, 0.75
    for row, document in zip(rows, documents, strict=True):
        term_frequency = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = term_frequency[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (count - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + k1 * (
                1 - b + b * len(document) / average_length
            )
            score += inverse_frequency * frequency * (k1 + 1) / denominator
        scores[row["id"]] = score
    return scores


def ranks(scores: dict[str, float]) -> dict[str, int]:
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return {identifier: rank for rank, identifier in enumerate(ordered, 1)}


def enum_scores(
    rows: list[dict[str, Any]],
    query_enums: list[str],
    enum_field: str,
) -> dict[str, float]:
    wanted = set(query_enums)
    result: dict[str, float] = {}
    for row in rows:
        values = row["metadata"].get(enum_field, [])
        if isinstance(values, str):
            values = [values]
        overlap = len(wanted.intersection(map(str, values)))
        if overlap:
            result[row["id"]] = float(overlap)
    return result


def run_search(args: argparse.Namespace) -> None:
    rows = [
        search_row(row, args.id_field, args.text_field)
        for row in load_records(args.index)
    ]
    sparse = {
        identifier: score
        for identifier, score in bm25_scores(rows, args.query).items()
        if score > 0
    }
    dense: dict[str, float] = {}
    tokens = 0
    if args.mode in {"dense", "hybrid", "igep"}:
        missing = [row["id"] for row in rows if not isinstance(row["embedding"], list)]
        if missing:
            raise ValueError(
                f"{args.mode} needs Voyage embeddings; missing for {missing[:5]}"
            )
        vectors, tokens = voyage_embed([args.query], "query")
        dense = {
            row["id"]: cosine(vectors[0], row["embedding"])
            for row in rows
        }

    if args.mode == "bm25":
        combined = sparse
    elif args.mode == "dense":
        combined = dense
    else:
        combined = {row["id"]: 0.0 for row in rows}
        for channel in (sparse, dense):
            for identifier, rank in ranks(channel).items():
                combined[identifier] += 1.0 / (args.rrf_k + rank)
        if args.mode == "igep" and args.query_enum:
            enum_channel = enum_scores(
                rows,
                args.query_enum,
                args.enum_field,
            )
            for identifier, rank in ranks(enum_channel).items():
                combined[identifier] += 1.0 / (args.rrf_k + rank)

    by_id = {row["id"]: row for row in rows}
    ordered_ids = sorted(combined, key=lambda key: (-combined[key], key))[: args.top_k]
    hits = []
    for rank, identifier in enumerate(ordered_ids, 1):
        row = by_id[identifier]
        hits.append(
            {
                "rank": rank,
                "score": combined[identifier],
                "bm25_score": sparse.get(identifier),
                "dense_score": dense.get(identifier),
                "id": identifier,
                "text": row["text"],
                "metadata": row["metadata"],
            }
        )
    print(
        json.dumps(
            {
                "mode": args.mode,
                "embedding_model": (
                    env("VOYAGE_MODEL", "voyage-4-large")
                    if args.mode in {"dense", "hybrid", "igep"}
                    else None
                ),
                "tokens": tokens,
                "hits": hits,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def print_registry() -> None:
    print("Planned end-to-end baselines (only B0 is runnable now)")
    for method in PAPER_BASELINES:
        print(f"  {method['id']}: {method['name']} — {method['description']}")
    print(f"\nMain method\n  {MAIN_METHOD['id']}: {MAIN_METHOD['name']} — {MAIN_METHOD['description']}")
    print("\nExtraction experiments available now")
    for name, method in EXTRACTION_METHODS.items():
        print(f"  {name}: {method['label']}")
    print("\nDiagnostics (not competitive baselines)")
    for item in DIAGNOSTICS:
        print(f"  - {item}")
    print("\nAblations")
    for item in ABLATIONS:
        print(f"  - {item}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List baselines, main method, and ablations.")

    extract = subparsers.add_parser("extract", help="Run full-schema extraction.")
    extract.add_argument("--method", choices=EXTRACTION_METHODS, default="igep")
    extract.add_argument(
        "--prompt-version",
        choices=EXTRACTION_PROMPTS,
        default=DEFAULT_EXTRACTION_PROMPT,
    )
    extract.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    extract.add_argument(
        "--split", choices=["development", "test"], default="development"
    )
    extract.add_argument(
        "--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST
    )
    extract.add_argument("--allow-held-out-test", action="store_true")
    extract.add_argument("--output", type=Path)
    extract.add_argument("--trace", type=Path)
    extract.add_argument("--case-id", action="append")
    extract.add_argument("--limit", type=int)
    extract.add_argument("--max-repairs", type=int, default=1)
    extract.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    extract.add_argument("--dry-run", action="store_true")

    allocate = subparsers.add_parser(
        "allocate", help="Run final heir-and-amount allocation baselines."
    )
    allocate.add_argument("--method", choices=["b0"], default="b0")
    allocate.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    allocate.add_argument("--split", choices=["development", "test"], default="development")
    allocate.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    allocate.add_argument("--allow-held-out-test", action="store_true")
    allocate.add_argument("--output", type=Path)
    allocate.add_argument("--trace", type=Path)
    allocate.add_argument("--case-id", action="append")
    allocate.add_argument("--limit", type=int)
    allocate.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    allocate.add_argument("--dry-run", action="store_true")

    index = subparsers.add_parser(
        "index",
        help="Embed a frozen statute JSON/JSONL corpus with Voyage.",
    )
    index.add_argument("--input", type=Path, required=True)
    index.add_argument("--output", type=Path, required=True)
    index.add_argument("--id-field", default="article_id")
    index.add_argument("--text-field", default="text")
    index.add_argument("--batch-size", type=int, default=64)

    search = subparsers.add_parser(
        "search",
        help="Run BM25, Voyage dense, hybrid RRF, or IGEP soft-enum retrieval.",
    )
    search.add_argument("--index", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument(
        "--mode",
        choices=["bm25", "dense", "hybrid", "igep"],
        default="hybrid",
    )
    search.add_argument("--top-k", type=int, default=10)
    search.add_argument("--id-field", default="article_id")
    search.add_argument("--text-field", default="text")
    search.add_argument("--query-enum", action="append", default=[])
    search.add_argument("--enum-field", default="issue_enums")
    search.add_argument("--rrf-k", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    # Windows PowerShell can expose a legacy Vietnamese code page that cannot
    # encode all Unicode characters present in the benchmark.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    load_env(args.env_file)
    if args.command == "list":
        print_registry()
    elif args.command == "extract":
        run_extract(args)
    elif args.command == "allocate":
        run_allocate(args)
    elif args.command == "index":
        run_index(args)
    elif args.command == "search":
        run_search(args)


if __name__ == "__main__":
    main()
