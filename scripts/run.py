"""Small, resumable runner for IGEP model experiments.

Available now:
  * B0 closed-book, B2 BM25-RAG, and B4 hybrid-RAG allocation baselines;
  * extraction baselines and IGEP extraction on the 150-case benchmark;
  * Voyage statute-corpus indexing and dense search.

The statute corpus, applicability evaluator, operation registry, and executor
must be frozen before the end-to-end M1 experiment is enabled.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    B2_ALLOCATION_PROMPT_VERSION,
    B2_ALLOCATION_SYSTEM_PROMPT,
    B4_ALLOCATION_PROMPT_VERSION,
    B4_ALLOCATION_SYSTEM_PROMPT,
    B5_ALLOCATION_SYSTEM_PROMPT,
    B5_EXTRACTION_SCHEMA,
    B5_EXTRACTION_SYSTEM_PROMPT,
    B5_ISSUE_SCHEMA,
    B5_ISSUE_SYSTEM_PROMPT,
    B5_MODULE_ORDER,
    B5_PROMPT_VERSION,
    B5_REASONING_SCHEMA,
    B5_REASONING_SYSTEM_PROMPT,
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
    b2_allocation_user_prompt,
    b4_allocation_user_prompt,
    b5_allocation_user_prompt,
    b5_extraction_user_prompt,
    b5_issue_user_prompt,
    b5_reasoning_user_prompt,
    direct_allocation_user_prompt,
    raw_schema_instruction,
    repair_user_prompt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "canonical" / "input.jsonl"
DEFAULT_RUN_DIR = PROJECT_ROOT / "data" / "runs"
DEFAULT_SPLIT_MANIFEST = PROJECT_ROOT / "data" / "release" / "split.csv"
DEFAULT_STATUTE_CORPUS = (
    PROJECT_ROOT / "data" / "legal_corpus" / "normalized" / "statutes.jsonl"
)
B0_DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
B0_DEFAULT_REASONING_EFFORT = "low"
B0_DEFAULT_MAX_OUTPUT_TOKENS = 6000
B0_DEFAULT_TIMEOUT_SECONDS = 120
B0_DEFAULT_ATTEMPTS = 2
B2_RETRIEVAL_TOP_K = 5
BM25_K1 = 1.5
BM25_B = 0.75
B4_BM25_CANDIDATE_K = 20
B4_DENSE_CANDIDATE_K = 20
B4_RRF_K = 60
B4_FINAL_TOP_K = 5
B4_DENSE_METRIC = "cosine"
DEFAULT_DENSE_CACHE = PROJECT_ROOT / "data" / "cache" / "statute_embeddings_voyage.jsonl"


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


def b2_config() -> dict[str, Any]:
    """Use the frozen B0 inference settings; retrieval is the sole intervention."""
    config = b0_config()
    config["prompt_version"] = B2_ALLOCATION_PROMPT_VERSION
    config.update(
        {
            "retrieval_method": "bm25",
            "retrieval_top_k": B2_RETRIEVAL_TOP_K,
            "bm25_k1": BM25_K1,
            "bm25_b": BM25_B,
        }
    )
    return config


def b4_config() -> dict[str, Any]:
    """Frozen B0 inference plus the specified hybrid retrieval intervention."""
    config = b0_config()
    config["prompt_version"] = B4_ALLOCATION_PROMPT_VERSION
    config.update(
        {
            "retrieval_method": "hybrid",
            "bm25_k1": BM25_K1,
            "bm25_b": BM25_B,
            "bm25_candidate_k": B4_BM25_CANDIDATE_K,
            "dense_model": env("VOYAGE_MODEL", "voyage-4-large"),
            "dense_metric": B4_DENSE_METRIC,
            "dense_candidate_k": B4_DENSE_CANDIDATE_K,
            "dense_output_dimension": int(env("VOYAGE_OUTPUT_DIMENSION", "1024")),
            "rrf_k": B4_RRF_K,
            "final_top_k": B4_FINAL_TOP_K,
        }
    )
    return config


def b5_config() -> dict[str, Any]:
    """Use frozen B4 retrieval and B0 inference for modular coordination."""
    config = b4_config()
    config["prompt_version"] = B5_PROMPT_VERSION
    config["retrieval_method"] = "b4_hybrid"
    config["logical_llm_calls"] = len(B5_MODULE_ORDER)
    return config


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


def b2_trace_record(
    case_id: str,
    split: str,
    started: float,
    config: dict[str, Any],
    retrieved_statute_ids: list[str],
    corpus_path: Path,
    corpus_sha256: str,
    *,
    response: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    exception: Exception | None = None,
) -> dict[str, Any]:
    """B2 trace: frozen B0 settings plus deterministic BM25 provenance."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "split": split,
        "method": "b2",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "max_output_tokens": config["max_output_tokens"],
        "temperature": config["temperature"],
        "timeout_seconds": config["timeout_seconds"],
        "attempt_count": config["attempts"],
        "retry_count": max(config["attempts"] - 1, 0),
        "prompt_version": config["prompt_version"],
        "retrieval_method": config["retrieval_method"],
        "retrieval_top_k": config["retrieval_top_k"],
        "bm25_k1": config["bm25_k1"],
        "bm25_b": config["bm25_b"],
        "retrieval_query_source": "raw_case_text",
        "statute_corpus": str(corpus_path),
        "statute_corpus_sha256": corpus_sha256,
        "retrieved_statute_ids": retrieved_statute_ids,
        "response_id": response.get("id") if response else None,
        "usage": response.get("usage") if response else None,
        "structural_validation_errors": errors or [],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "error": str(exception) if exception else None,
    }


def b4_trace_record(
    case_id: str,
    split: str,
    started: float,
    config: dict[str, Any],
    bm25_statute_ids: list[str],
    dense_statute_ids: list[str],
    retrieved_statute_ids: list[str],
    corpus_path: Path,
    corpus_sha256: str,
    *,
    response: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    exception: Exception | None = None,
    dense_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """B4 trace with complete hybrid-retrieval and inference provenance."""
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "split": split,
        "method": "b4",
        "model": config["model"],
        "reasoning_effort": config["reasoning_effort"],
        "max_output_tokens": config["max_output_tokens"],
        "temperature": config["temperature"],
        "timeout_seconds": config["timeout_seconds"],
        "attempts": config["attempts"],
        "attempt_count": config["attempts"],
        "retry_count": max(config["attempts"] - 1, 0),
        "prompt_version": config["prompt_version"],
        "retrieval_method": config["retrieval_method"],
        "bm25_k1": config["bm25_k1"],
        "bm25_b": config["bm25_b"],
        "bm25_candidate_k": config["bm25_candidate_k"],
        "dense_model": config["dense_model"],
        "dense_metric": config["dense_metric"],
        "dense_candidate_k": config["dense_candidate_k"],
        "dense_output_dimension": config["dense_output_dimension"],
        "rrf_k": config["rrf_k"],
        "final_top_k": config["final_top_k"],
        "query_source": "raw_case_text",
        "corpus_path": str(corpus_path),
        "corpus_sha256": corpus_sha256,
        "bm25_statute_ids": bm25_statute_ids,
        "dense_statute_ids": dense_statute_ids,
        "retrieved_statute_ids": retrieved_statute_ids,
        "dense_usage": dense_usage or {},
        "response_id": response.get("id") if response else None,
        "usage": response.get("usage") if response else None,
        "validation_errors": errors or [],
        "structural_validation_errors": errors or [],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime_error": str(exception) if exception else None,
        "error": str(exception) if exception else None,
    }


class B5ModuleError(RuntimeError):
    """Stops B5 at the failing module while preserving completed trace data."""

    def __init__(self, message: str, modules: list[dict[str, Any]]):
        super().__init__(message)
        self.modules = modules


def run_b5_modules(
    case_id: str,
    query: str,
    retrieved: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    call_fn=None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Execute four distinct B5 LLM modules with no repair or verifier loop."""
    call = call_fn or openai_call
    modules: list[dict[str, Any]] = []
    extraction: dict[str, Any] | None = None
    issues: dict[str, Any] | None = None
    reasoning: dict[str, Any] | None = None
    specifications = [
        (
            "structured_case_extraction", B5_EXTRACTION_SYSTEM_PROMPT,
            lambda: b5_extraction_user_prompt(case_id, query),
            B5_EXTRACTION_SCHEMA, "b5_case_extraction_v1",
        ),
        (
            "inheritance_issue_analysis", B5_ISSUE_SYSTEM_PROMPT,
            lambda: b5_issue_user_prompt(case_id, query, extraction, retrieved),
            B5_ISSUE_SCHEMA, "b5_issue_analysis_v1",
        ),
        (
            "statute_aware_reasoning", B5_REASONING_SYSTEM_PROMPT,
            lambda: b5_reasoning_user_prompt(case_id, extraction, issues, retrieved),
            B5_REASONING_SCHEMA, "b5_statute_reasoning_v1",
        ),
        (
            "coordinated_final_allocation", B5_ALLOCATION_SYSTEM_PROMPT,
            lambda: b5_allocation_user_prompt(case_id, query, extraction, issues, reasoning),
            DIRECT_ALLOCATION_SCHEMA, "igep_direct_allocation_v1",
        ),
    ]
    final_prediction: dict[str, Any] | None = None
    for module_name, system_prompt, user_prompt_fn, schema, schema_name in specifications:
        started = time.perf_counter()
        response: dict[str, Any] | None = None
        try:
            output, response = call(
                system_prompt,
                user_prompt_fn(),
                structured=True,
                output_schema=schema,
                schema_name=schema_name,
                model=config["model"],
                reasoning_effort=config["reasoning_effort"],
                max_output_tokens=config["max_output_tokens"],
                timeout_seconds=config["timeout_seconds"],
                attempts=config["attempts"],
            )
            output["case_id"] = case_id
            errors = validate_instance(output, schema, schema)
            module_record = {
                "module": module_name,
                "response_id": response.get("id") if response else None,
                "usage": response.get("usage") if response else None,
                "output": output,
                "validation_errors": errors,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "runtime_error": None,
            }
            modules.append(module_record)
            if errors:
                raise B5ModuleError(
                    f"{module_name}: " + "; ".join(errors[:10]), modules
                )
            if module_name == "structured_case_extraction":
                extraction = output
            elif module_name == "inheritance_issue_analysis":
                issues = output
            elif module_name == "statute_aware_reasoning":
                reasoning = output
            else:
                final_prediction = output
        except B5ModuleError:
            raise
        except Exception as exc:
            modules.append({
                "module": module_name,
                "response_id": response.get("id") if response else None,
                "usage": response.get("usage") if response else None,
                "output": None,
                "validation_errors": [],
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "runtime_error": str(exc),
            })
            raise B5ModuleError(f"{module_name}: {exc}", modules) from exc
    if final_prediction is None:
        raise B5ModuleError("B5 produced no final allocation", modules)
    total_usage = merge_numeric_dicts([
        module["usage"] for module in modules if isinstance(module.get("usage"), dict)
    ])
    return final_prediction, modules, total_usage


def b5_trace_record(
    case_id: str,
    split: str,
    started: float,
    config: dict[str, Any],
    bm25_statute_ids: list[str],
    dense_statute_ids: list[str],
    retrieved_statute_ids: list[str],
    corpus_path: Path,
    corpus_sha256: str,
    modules: list[dict[str, Any]],
    *,
    total_usage: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    exception: Exception | None = None,
    dense_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "split": split,
        "method": "b5",
        "model": config["model"],
        "reasoning": config["reasoning_effort"],
        "reasoning_effort": config["reasoning_effort"],
        "max_output_tokens": config["max_output_tokens"],
        "temperature": config["temperature"],
        "timeout_seconds": config["timeout_seconds"],
        "attempts": config["attempts"],
        "retry_count": max(config["attempts"] - 1, 0),
        "prompt_version": config["prompt_version"],
        "retrieval_method": config["retrieval_method"],
        "bm25_k1": config["bm25_k1"],
        "bm25_b": config["bm25_b"],
        "bm25_candidate_k": config["bm25_candidate_k"],
        "dense_model": config["dense_model"],
        "dense_metric": config["dense_metric"],
        "dense_candidate_k": config["dense_candidate_k"],
        "dense_output_dimension": config["dense_output_dimension"],
        "rrf_k": config["rrf_k"],
        "final_top_k": config["final_top_k"],
        "query_source": "raw_case_text",
        "corpus_path": str(corpus_path),
        "corpus_sha256": corpus_sha256,
        "bm25_statute_ids": bm25_statute_ids,
        "dense_statute_ids": dense_statute_ids,
        "retrieved_statute_ids": retrieved_statute_ids,
        "logical_llm_calls_planned": config["logical_llm_calls"],
        "logical_llm_calls_attempted": len(modules),
        "logical_llm_calls_completed": sum(
            not module.get("runtime_error") and not module.get("validation_errors")
            for module in modules
        ),
        "module_execution_order": list(B5_MODULE_ORDER),
        "modules": modules,
        "module_response_ids": [module.get("response_id") for module in modules],
        "module_usage": {module["module"]: module.get("usage") for module in modules},
        "total_usage": total_usage or {},
        "dense_usage": dense_usage or {},
        "validation_errors": errors or [],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime_error": str(exception) if exception else None,
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
    """Run frozen allocation baselines B0, B2, B4, or modular B5."""
    method = args.method
    output = args.output or DEFAULT_RUN_DIR / f"allocation_dev_{method}.jsonl"
    trace = args.trace or output.with_name(output.stem + ".trace.jsonl")
    config = {"b0": b0_config, "b2": b2_config, "b4": b4_config, "b5": b5_config}[method]()
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

    corpus_path = args.statute_corpus
    corpus_rows: list[dict[str, Any]] = []
    corpus_sha256 = ""
    if method in {"b2", "b4", "b5"}:
        corpus_rows = [
            search_row(row, "citation_id", "retrieval_text")
            for row in load_records(corpus_path)
        ]
        if not corpus_rows:
            raise RuntimeError(f"Empty statute corpus: {corpus_path}")
        corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()

    if args.dry_run:
        case_id, query = normalized_case(records[0])
        bm25_hits: list[dict[str, Any]] = []
        dense_hits: list[dict[str, Any]] = []
        if method == "b2":
            retrieved = bm25_retrieve(corpus_rows, query, B2_RETRIEVAL_TOP_K)
        elif method in {"b4", "b5"}:
            fake_dimension = 32
            fake_rows = [
                {**row, "embedding": deterministic_fake_embedding(row["text"], fake_dimension)}
                for row in corpus_rows
            ]
            bm25_hits, dense_hits, retrieved = hybrid_retrieve(
                corpus_rows, fake_rows, query,
                deterministic_fake_embedding(query, fake_dimension), config,
            )
        else:
            retrieved = []
        system_prompt = None
        user_prompt = None
        module_requests: list[dict[str, Any]] = []
        if method != "b5":
            system_prompt = {
                "b0": DIRECT_ALLOCATION_SYSTEM_PROMPT,
                "b2": B2_ALLOCATION_SYSTEM_PROMPT,
                "b4": B4_ALLOCATION_SYSTEM_PROMPT,
            }[method]
            user_prompt = {
                "b0": lambda: direct_allocation_user_prompt(case_id, query),
                "b2": lambda: b2_allocation_user_prompt(case_id, query, retrieved),
                "b4": lambda: b4_allocation_user_prompt(case_id, query, retrieved),
            }[method]()
        else:
            empty_extraction = {
                "case_id": case_id, "persons": [], "relationships": [],
                "succession_openings": [], "assets": [], "obligations": [],
                "wills_gifts_transfers": [], "explicit_uncertainties": [],
            }
            empty_issues = {
                "case_id": case_id, "succession_modes": [], "succession_order": [],
                "will_issues": [], "representation_issues": [], "mandatory_share_issues": [],
                "estate_issues": [], "obligation_issues": [], "multi_stage_issues": [],
                "other_issues": [], "fact_issue_links": [], "unresolved_ambiguities": [],
            }
            empty_reasoning = {
                "case_id": case_id, "applicable_statutes": [], "reasoning_steps": [],
                "intermediate_calculations": [], "intermediate_succession_states": [],
                "assumptions": [], "unresolved_ambiguities": [],
            }
            module_requests = [
                {"module": B5_MODULE_ORDER[0], "system_prompt": B5_EXTRACTION_SYSTEM_PROMPT,
                 "user_prompt": b5_extraction_user_prompt(case_id, query), "output_schema": B5_EXTRACTION_SCHEMA},
                {"module": B5_MODULE_ORDER[1], "system_prompt": B5_ISSUE_SYSTEM_PROMPT,
                 "user_prompt": b5_issue_user_prompt(case_id, query, empty_extraction, retrieved), "output_schema": B5_ISSUE_SCHEMA},
                {"module": B5_MODULE_ORDER[2], "system_prompt": B5_REASONING_SYSTEM_PROMPT,
                 "user_prompt": b5_reasoning_user_prompt(case_id, empty_extraction, empty_issues, retrieved), "output_schema": B5_REASONING_SCHEMA},
                {"module": B5_MODULE_ORDER[3], "system_prompt": B5_ALLOCATION_SYSTEM_PROMPT,
                 "user_prompt": b5_allocation_user_prompt(case_id, query, empty_extraction, empty_issues, empty_reasoning), "output_schema": DIRECT_ALLOCATION_SCHEMA},
            ]
        dry_run_record = {
            "method": method,
            "label": (
                "B0 monolithic closed-book LLM"
                if method == "b0"
                else "B2 BM25-RAG direct allocation"
                if method == "b2"
                else "B4 hybrid-RAG direct allocation"
                if method == "b4"
                else "B5 coordinated modular LLM"
            ),
            "configuration": config,
            "case_id": case_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_schema": DIRECT_ALLOCATION_SCHEMA,
        }
        if method in {"b2", "b4", "b5"}:
            dry_run_record.update(
                {
                    "retrieved_statute_ids": [row["id"] for row in retrieved],
                    "statute_corpus": str(corpus_path),
                    "statute_corpus_sha256": corpus_sha256,
                }
            )
        if method in {"b4", "b5"}:
            dry_run_record.update({
                "dry_run_dense_source": "deterministic_fake_embeddings",
                "bm25_statute_ids": [row["id"] for row in bm25_hits],
                "dense_statute_ids": [row["id"] for row in dense_hits],
                "retrieved_statute_ids": [row["id"] for row in retrieved],
            })
        if method == "b5":
            dry_run_record.update({
                "module_execution_order": list(B5_MODULE_ORDER),
                "logical_llm_calls": len(B5_MODULE_ORDER),
                "module_requests": module_requests,
            })
        print(json.dumps(dry_run_record, ensure_ascii=False, indent=2))
        return

    env("OPENAI_API_KEY", required=True)
    embedded_rows: list[dict[str, Any]] = []
    dense_cache_usage: dict[str, Any] = {}
    if method in {"b4", "b5"}:
        embedded_rows, dense_cache_usage = load_or_build_dense_cache(
            corpus_rows, args.dense_cache, corpus_sha256, config,
            batch_size=args.dense_batch_size,
        )
    completed = existing_case_ids(output) if args.resume else set()
    selected = [r for r in records if normalized_case(r)[0] not in completed]
    label = {
        "b0": "B0 monolithic allocation",
        "b2": "B2 BM25-RAG allocation",
        "b4": "B4 hybrid-RAG allocation",
        "b5": "B5 coordinated modular allocation",
    }[method]
    print(f"{label}: {len(selected)} pending / {len(records)} selected; output={output}")
    for index, record in enumerate(selected, 1):
        case_id, query = normalized_case(record)
        started = time.perf_counter()
        response = None
        retrieved: list[dict[str, Any]] = []
        bm25_hits: list[dict[str, Any]] = []
        dense_hits: list[dict[str, Any]] = []
        dense_usage = dict(dense_cache_usage)
        modules: list[dict[str, Any]] = []
        total_usage: dict[str, Any] = {}
        try:
            if method == "b2":
                retrieved = bm25_retrieve(corpus_rows, query, B2_RETRIEVAL_TOP_K)
            elif method in {"b4", "b5"}:
                query_vectors, query_tokens = voyage_embed([query], "query")
                if len(query_vectors[0]) != config["dense_output_dimension"]:
                    raise ValueError("Voyage query embedding dimension does not match B4 configuration")
                dense_usage["query_embedding_tokens"] = query_tokens
                bm25_hits, dense_hits, retrieved = hybrid_retrieve(
                    corpus_rows, embedded_rows, query, query_vectors[0], config,
                )
            if method == "b5":
                prediction, modules, total_usage = run_b5_modules(
                    case_id, query, retrieved, config
                )
            else:
                system_prompt = {
                    "b0": DIRECT_ALLOCATION_SYSTEM_PROMPT,
                    "b2": B2_ALLOCATION_SYSTEM_PROMPT,
                    "b4": B4_ALLOCATION_SYSTEM_PROMPT,
                }[method]
                user_prompt = {
                    "b0": lambda: direct_allocation_user_prompt(case_id, query),
                    "b2": lambda: b2_allocation_user_prompt(case_id, query, retrieved),
                    "b4": lambda: b4_allocation_user_prompt(case_id, query, retrieved),
                }[method]()
                prediction, response = openai_call(
                    system_prompt,
                    user_prompt,
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
            if method == "b0":
                trace_row = b0_trace_record(
                    case_id, args.split, started, config,
                    response=response, errors=errors,
                )
            elif method == "b2":
                trace_row = b2_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, response=response, errors=errors,
                )
            elif method == "b4":
                trace_row = b4_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in bm25_hits],
                    [row["id"] for row in dense_hits],
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, response=response, errors=errors,
                    dense_usage=dense_usage,
                )
            else:
                trace_row = b5_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in bm25_hits],
                    [row["id"] for row in dense_hits],
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, modules, total_usage=total_usage,
                    errors=errors, dense_usage=dense_usage,
                )
            append_jsonl(trace, trace_row)
            print(f"[{index}/{len(selected)}] case {case_id}: complete")
        except Exception as exc:
            if isinstance(exc, B5ModuleError):
                modules = exc.modules
                total_usage = merge_numeric_dicts([
                    module["usage"] for module in modules
                    if isinstance(module.get("usage"), dict)
                ])
            if method == "b0":
                trace_row = b0_trace_record(
                    case_id, args.split, started, config,
                    response=response, exception=exc,
                )
            elif method == "b2":
                trace_row = b2_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, response=response, exception=exc,
                )
            elif method == "b4":
                trace_row = b4_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in bm25_hits],
                    [row["id"] for row in dense_hits],
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, response=response, exception=exc,
                    dense_usage=dense_usage,
                )
            else:
                trace_row = b5_trace_record(
                    case_id, args.split, started, config,
                    [row["id"] for row in bm25_hits],
                    [row["id"] for row in dense_hits],
                    [row["id"] for row in retrieved], corpus_path,
                    corpus_sha256, modules, total_usage=total_usage,
                    exception=exc, dense_usage=dense_usage,
                )
            append_jsonl(trace, trace_row)
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
    if len(a) != len(b):
        raise ValueError("Cosine vectors must have equal dimensions")
    # Explicit length validation preserves ``zip(strict=True)`` semantics on
    # the project's supported Python 3.9 runtime.
    numerator = sum(x * y for x, y in zip(a, b))
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
    # ``documents`` is constructed one-for-one from ``rows`` above. Avoid
    # zip(strict=True) so the frozen BM25 baseline runs on the project's
    # supported Python 3.9 environment.
    for row, document in zip(rows, documents):
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
            denominator = frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * len(document) / average_length
            )
            score += (
                inverse_frequency
                * frequency
                * (BM25_K1 + 1)
                / denominator
            )
        scores[row["id"]] = score
    return scores


def bm25_retrieve(
    rows: list[dict[str, Any]], query: str, top_k: int = B2_RETRIEVAL_TOP_K
) -> list[dict[str, Any]]:
    """Return deterministic BM25 hits, breaking equal scores by stable ID."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    scores = bm25_scores(rows, query)
    ordered = sorted(rows, key=lambda row: (-scores[row["id"]], row["id"]))
    return [
        {**row, "bm25_score": scores[row["id"]]}
        for row in ordered[:top_k]
    ]


def dense_retrieve(
    rows: list[dict[str, Any]],
    query_embedding: list[float],
    top_k: int = B4_DENSE_CANDIDATE_K,
) -> list[dict[str, Any]]:
    """Rank embedded corpus rows by cosine, with citation ID tie-breaking."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    scored: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        embedding = row.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError(f"Missing dense embedding for {row['id']}")
        if len(embedding) != len(query_embedding):
            raise ValueError(f"Embedding dimension mismatch for {row['id']}")
        scored.append((row, cosine(query_embedding, embedding)))
    scored.sort(key=lambda item: (-item[1], item[0]["id"]))
    return [{**row, "dense_score": score} for row, score in scored[:top_k]]


def rrf_fuse(
    bm25_hits: list[dict[str, Any]],
    dense_hits: list[dict[str, Any]],
    *,
    rrf_k: int = B4_RRF_K,
    top_k: int = B4_FINAL_TOP_K,
) -> list[dict[str, Any]]:
    """Fuse only the supplied sparse/dense candidate pools using 1-based RRF."""
    if rrf_k < 1 or top_k < 1:
        raise ValueError("rrf_k and top_k must be positive")
    by_id: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}
    sparse_ranks: dict[str, int] = {}
    dense_ranks: dict[str, int] = {}
    for channel, channel_ranks in ((bm25_hits, sparse_ranks), (dense_hits, dense_ranks)):
        for rank, row in enumerate(channel, 1):
            identifier = row["id"]
            if identifier in channel_ranks:
                raise ValueError(f"Duplicate candidate in retrieval channel: {identifier}")
            channel_ranks[identifier] = rank
            by_id.setdefault(identifier, row)
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (rrf_k + rank)
    ordered_ids = sorted(scores, key=lambda identifier: (-scores[identifier], identifier))
    return [
        {
            **by_id[identifier],
            "rrf_score": scores[identifier],
            "bm25_rank": sparse_ranks.get(identifier),
            "dense_rank": dense_ranks.get(identifier),
        }
        for identifier in ordered_ids[:top_k]
    ]


def deterministic_fake_embedding(text: str, dimension: int = 32) -> list[float]:
    """Local test/dry-run embedding; deliberately never used by real B4 runs."""
    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        position = int.from_bytes(digest[:4], "big") % dimension
        vector[position] += -1.0 if digest[4] & 1 else 1.0
    return vector


def attach_embeddings(
    corpus_rows: list[dict[str, Any]], embeddings: dict[str, list[float]]
) -> list[dict[str, Any]]:
    missing = [row["id"] for row in corpus_rows if row["id"] not in embeddings]
    extra = sorted(set(embeddings) - {row["id"] for row in corpus_rows})
    if missing or extra:
        raise ValueError(f"Dense cache/corpus ID mismatch: missing={missing[:5]} extra={extra[:5]}")
    return [{**row, "embedding": embeddings[row["id"]]} for row in corpus_rows]


def load_or_build_dense_cache(
    corpus_rows: list[dict[str, Any]],
    cache_path: Path,
    corpus_sha256: str,
    config: dict[str, Any],
    *,
    batch_size: int = 64,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load a validated fixed-corpus cache, or create it once with Voyage."""
    model = config["dense_model"]
    dimension = config["dense_output_dimension"]
    if cache_path.exists():
        cache_rows = load_records(cache_path)
        embeddings: dict[str, list[float]] = {}
        for row in cache_rows:
            if row.get("dense_model") != model:
                raise ValueError(f"Dense cache model mismatch in {cache_path}")
            if row.get("dense_output_dimension") != dimension:
                raise ValueError(f"Dense cache dimension mismatch in {cache_path}")
            if row.get("corpus_sha256") != corpus_sha256:
                raise ValueError(f"Dense cache corpus checksum mismatch in {cache_path}")
            embedding = row.get("embedding")
            if not isinstance(embedding, list) or len(embedding) != dimension:
                raise ValueError(f"Invalid embedding in {cache_path}: {row.get('id')}")
            identifier = str(row["id"])
            if identifier in embeddings:
                raise ValueError(f"Duplicate dense cache ID: {identifier}")
            embeddings[identifier] = embedding
        return attach_embeddings(corpus_rows, embeddings), {
            "document_embedding_cache": str(cache_path),
            "document_embedding_cache_hit": True,
            "document_embedding_tokens": 0,
        }

    env("VOYAGE_API_KEY", required=True)
    cache_rows: list[dict[str, Any]] = []
    total_tokens = 0
    for batch in chunks(corpus_rows, batch_size):
        vectors, tokens = voyage_embed([row["text"] for row in batch], "document")
        total_tokens += tokens
        if len(batch) != len(vectors):
            raise ValueError("Voyage document embedding count mismatch")
        for row, vector in zip(batch, vectors):
            if len(vector) != dimension:
                raise ValueError(f"Voyage returned unexpected dimension for {row['id']}")
            cache_rows.append({
                "id": row["id"],
                "dense_model": model,
                "dense_output_dimension": dimension,
                "corpus_sha256": corpus_sha256,
                "embedding": vector,
            })
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in cache_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(cache_path)
    embeddings = {row["id"]: row["embedding"] for row in cache_rows}
    return attach_embeddings(corpus_rows, embeddings), {
        "document_embedding_cache": str(cache_path),
        "document_embedding_cache_hit": False,
        "document_embedding_tokens": total_tokens,
    }


def hybrid_retrieve(
    corpus_rows: list[dict[str, Any]],
    embedded_rows: list[dict[str, Any]],
    query: str,
    query_embedding: list[float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sparse = bm25_retrieve(corpus_rows, query, config["bm25_candidate_k"])
    dense = dense_retrieve(embedded_rows, query_embedding, config["dense_candidate_k"])
    fused = rrf_fuse(sparse, dense, rrf_k=config["rrf_k"], top_k=config["final_top_k"])
    return sparse, dense, fused


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
    print("End-to-end baselines (B0, B2, B4, and B5 are runnable now)")
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
    allocate.add_argument("--method", choices=["b0", "b2", "b4", "b5"], default="b0")
    allocate.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    allocate.add_argument("--split", choices=["development", "test"], default="development")
    allocate.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST)
    allocate.add_argument(
        "--statute-corpus", type=Path, default=DEFAULT_STATUTE_CORPUS,
        help="Canonical article-level statute corpus used by B2 and B4.",
    )
    allocate.add_argument(
        "--dense-cache", type=Path, default=DEFAULT_DENSE_CACHE,
        help="Ignored local cache for B4 statute embeddings.",
    )
    allocate.add_argument("--dense-batch-size", type=int, default=64)
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
