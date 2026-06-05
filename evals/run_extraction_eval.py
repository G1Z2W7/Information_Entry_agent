from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.agent.constants import CONTACT_REQUIRED_FIELDS, MAIN_INFO_REQUIRED_FIELDS
from app.agent.extractor import extract_llm_incremental_patch
from app.agent.state import create_initial_state, merge_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_FILE = PROJECT_ROOT / "evals" / "cases" / "extraction_v1.jsonl"
DEFAULT_RESULT_DIR = PROJECT_ROOT / "evals" / "results"
ENV_FILE = PROJECT_ROOT / ".env"
EXCLUDED_PATH_PATTERNS = (
    "main_info.distributorLevel",
    "main_info.mainCategory",
    "main_info.mainCategoryGrade",
    "main_info.businessType",
    "main_info.cooperationStatus",
    "main_info.status",
    "main_info.informationSource",
    "main_info.providePoints",
    "main_info.providePointsRatio",
    "main_info.ownBrandDisplay",
    "main_info.competitorBrandDisplay",
    "sites[*].siteType",
    "sites[*].siteTypeName",
    "sites[*].siteSubType",
    "sites[*].hasStore",
    "sites[*].storeAreaRange",
    "sites[*].provinceName",
    "sites[*].cityName",
    "sites[*].districtName",
)


@dataclass
class EvalCase:
    case_id: str
    scene: str
    message: str
    expected_patch: dict[str, Any]
    initial_patch: dict[str, Any]
    tags: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-LLM extraction evaluation.")
    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="Path to a JSONL case file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional explicit output path for the JSON result.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Sleep between requests to avoid bursty traffic.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum attempts per case when transient model/network errors happen.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress every N cases.",
    )
    return parser.parse_args()


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            cases.append(
                EvalCase(
                    case_id=payload["case_id"],
                    scene=payload.get("scene", "default"),
                    message=payload["message"],
                    expected_patch=payload.get("expected_patch", {}),
                    initial_patch=payload.get("initial_patch", {}),
                    tags=payload.get("tags", []),
                )
            )
    if not cases:
        raise RuntimeError(f"No cases found in {path}")
    return cases


def build_state(case: EvalCase):
    state = create_initial_state(case.case_id)
    if case.initial_patch:
        merge_state(
            state,
            case.initial_patch,
            turn_number=0,
            source_text="[eval seed state]",
        )
    return state


def flatten_patch(value: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(flatten_patch(child, next_prefix))
        return flattened
    if isinstance(value, list):
        normalized_list = canonicalize_collection(value)
        for index, child in enumerate(normalized_list):
            next_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_patch(child, next_prefix))
        return flattened

    flattened[prefix] = normalize_scalar(prefix, value)
    return flattened


def canonicalize_collection(items: list[Any]) -> list[Any]:
    if not items:
        return items
    if all(isinstance(item, dict) for item in items):
        return sorted(items, key=collection_sort_key)
    return items


def collection_sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("contactName") or item.get("siteType") or ""),
        str(item.get("position") or item.get("fullAddress") or ""),
        str(item.get("mobile") or item.get("cityName") or ""),
    )


def normalize_scalar(path: str, value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, str):
        candidate = value.strip()
        if path.endswith(".status"):
            return candidate.lower()
        return candidate
    return value


def is_required_path(path: str) -> bool:
    if path.startswith("main_info."):
        field_name = path.split(".", 1)[1]
        return field_name in MAIN_INFO_REQUIRED_FIELDS
    if path.startswith("contacts["):
        field_name = path.split(".", 1)[1]
        return field_name in CONTACT_REQUIRED_FIELDS
    return False


def diff_maps(
    expected: dict[str, Any],
    predicted: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    matches: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []

    for path, expected_value in expected.items():
        if path not in predicted:
            false_negatives.append(
                {"path": path, "expected": expected_value, "actual": None}
            )
            continue
        actual_value = predicted[path]
        if actual_value == expected_value:
            matches.append({"path": path, "expected": expected_value, "actual": actual_value})
            continue
        false_negatives.append({"path": path, "expected": expected_value, "actual": actual_value})
        false_positives.append({"path": path, "expected": expected_value, "actual": actual_value})

    for path, actual_value in predicted.items():
        if path in expected:
            continue
        false_positives.append({"path": path, "expected": None, "actual": actual_value})

    return matches, false_positives, false_negatives


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def run_case(
    case: EvalCase,
    *,
    max_attempts: int,
) -> dict[str, Any]:
    state = build_state(case)
    predicted_patch: dict[str, Any] = {}
    elapsed_seconds = 0.0
    error_message: str | None = None
    attempts = 0

    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        started_at = time.perf_counter()
        try:
            predicted_patch = extract_llm_incremental_patch(case.message, state)
            elapsed_seconds = round(time.perf_counter() - started_at, 3)
            error_message = None
            break
        except Exception as exc:
            elapsed_seconds = round(time.perf_counter() - started_at, 3)
            error_message = str(exc)
            if attempt >= max_attempts:
                predicted_patch = {}
                break
            time.sleep(min(2.0, 0.5 * attempt))

    expected_flat = filter_excluded_fields(flatten_patch(case.expected_patch))
    predicted_flat = filter_excluded_fields(flatten_patch(predicted_patch))
    matches, false_positives, false_negatives = diff_maps(expected_flat, predicted_flat)

    required_expected = {path: value for path, value in expected_flat.items() if is_required_path(path)}
    required_hits = sum(
        1 for path, value in required_expected.items() if predicted_flat.get(path) == value
    )

    return {
        "case_id": case.case_id,
        "scene": case.scene,
        "tags": case.tags,
        "message": case.message,
        "initial_patch": case.initial_patch,
        "expected_patch": case.expected_patch,
        "predicted_patch": predicted_patch,
        "expected_flat": expected_flat,
        "predicted_flat": predicted_flat,
        "exact_match": expected_flat == predicted_flat,
        "elapsed_seconds": elapsed_seconds,
        "attempt_count": attempts,
        "error": error_message,
        "match_count": len(matches),
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
        "required_expected_count": len(required_expected),
        "required_hit_count": required_hits,
        "matches": matches,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def summarize(case_results: list[dict[str, Any]], case_file: Path) -> dict[str, Any]:
    total_matches = sum(result["match_count"] for result in case_results)
    total_false_positives = sum(result["false_positive_count"] for result in case_results)
    total_false_negatives = sum(result["false_negative_count"] for result in case_results)
    total_cases = len(case_results)
    exact_match_cases = sum(1 for result in case_results if result["exact_match"])
    total_required_expected = sum(result["required_expected_count"] for result in case_results)
    total_required_hits = sum(result["required_hit_count"] for result in case_results)
    errored_cases = sum(1 for result in case_results if result.get("error"))

    precision = safe_ratio(total_matches, total_matches + total_false_positives)
    recall = safe_ratio(total_matches, total_matches + total_false_negatives)
    required_recall = safe_ratio(total_required_hits, total_required_expected)
    exact_match_rate = safe_ratio(exact_match_cases, total_cases)
    average_latency = round(
        sum(result["elapsed_seconds"] for result in case_results) / total_cases,
        3,
    )

    failure_cases = [
        {
            "case_id": result["case_id"],
            "scene": result["scene"],
            "tags": result["tags"],
            "message": result["message"],
            "predicted_patch": result["predicted_patch"],
            "false_positives": result["false_positives"],
            "false_negatives": result["false_negatives"],
        }
        for result in case_results
        if not result["exact_match"]
    ]

    failure_path_counter: dict[str, int] = {}
    for result in case_results:
        for item in result["false_positives"] + result["false_negatives"]:
            path = item["path"]
            failure_path_counter[path] = failure_path_counter.get(path, 0) + 1

    top_failure_paths = sorted(
        (
            {"path": path, "count": count}
            for path, count in failure_path_counter.items()
        ),
        key=lambda item: (-item["count"], item["path"]),
    )[:10]

    scene_metrics = summarize_by_scene(case_results)

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "case_file": str(case_file),
        "model": os.getenv("DS_MODEL", ""),
        "metrics": {
            "case_count": total_cases,
            "exact_match_cases": exact_match_cases,
            "exact_match_rate": exact_match_rate,
            "field_precision": precision,
            "field_recall": recall,
            "field_f1": f1_score(precision, recall),
            "required_field_recall": required_recall,
            "average_latency_seconds": average_latency,
            "errored_cases": errored_cases,
        },
        "scene_metrics": scene_metrics,
        "top_failure_paths": top_failure_paths,
        "failures": failure_cases,
        "cases": case_results,
    }


def print_summary(summary: dict[str, Any]) -> None:
    metrics = summary["metrics"]
    print("Extraction Eval Summary")
    print(f"case_file={summary['case_file']}")
    print(f"model={summary['model']}")
    print(f"case_count={metrics['case_count']}")
    print(f"exact_match_rate={metrics['exact_match_rate']}")
    print(f"field_precision={metrics['field_precision']}")
    print(f"field_recall={metrics['field_recall']}")
    print(f"field_f1={metrics['field_f1']}")
    print(f"required_field_recall={metrics['required_field_recall']}")
    print(f"average_latency_seconds={metrics['average_latency_seconds']}")
    print(f"errored_cases={metrics['errored_cases']}")
    if summary.get("scene_metrics"):
        print("scene_metrics=")
        for scene, scene_summary in summary["scene_metrics"].items():
            print(
                "  - "
                f"{scene}: cases={scene_summary['case_count']}, "
                f"exact_match_rate={scene_summary['exact_match_rate']}, "
                f"field_f1={scene_summary['field_f1']}, "
                f"avg_latency={scene_summary['average_latency_seconds']}"
            )
    if summary["top_failure_paths"]:
        print("top_failure_paths=")
        for item in summary["top_failure_paths"]:
            print(f"  - {item['path']}: {item['count']}")


def write_summary(summary: dict[str, Any], output_path: Path | None) -> Path:
    DEFAULT_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        case_stem = Path(summary["case_file"]).stem
        output_path = DEFAULT_RESULT_DIR / f"{case_stem}_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    args = parse_args()
    load_dotenv(ENV_FILE)

    if not os.getenv("DS_API_KEY"):
        raise RuntimeError("DS_API_KEY is required to run the real DeepSeek evaluation.")

    cases = load_cases(args.case_file)
    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        case_results.append(run_case(case, max_attempts=max(1, args.max_attempts)))
        if args.progress_every > 0 and (index + 1) % args.progress_every == 0:
            print(f"progress={index + 1}/{len(cases)}", flush=True)
        if args.sleep_seconds > 0 and index < len(cases) - 1:
            time.sleep(args.sleep_seconds)

    summary = summarize(case_results, args.case_file)
    output_path = write_summary(summary, args.output)
    print_summary(summary)
    print(f"result_file={output_path}")


def filter_excluded_fields(flattened: dict[str, Any]) -> dict[str, Any]:
    return {
        path: value
        for path, value in flattened.items()
        if not is_excluded_path(path)
    }


def is_excluded_path(path: str) -> bool:
    return any(path_matches_pattern(path, pattern) for pattern in EXCLUDED_PATH_PATTERNS)


def path_matches_pattern(path: str, pattern: str) -> bool:
    path_parts = split_path(path)
    pattern_parts = split_path(pattern)
    if len(path_parts) != len(pattern_parts):
        return False
    return all(
        pattern_part == "[*]" or pattern_part == path_part
        for path_part, pattern_part in zip(path_parts, pattern_parts)
    )


def split_path(path: str) -> list[str]:
    parts: list[str] = []
    buffer = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            if buffer:
                parts.append(buffer)
                buffer = ""
            index += 1
            continue
        if char == "[":
            if buffer:
                parts.append(buffer)
                buffer = ""
            closing = path.find("]", index)
            parts.append(path[index : closing + 1])
            index = closing + 1
            continue
        buffer += char
        index += 1
    if buffer:
        parts.append(buffer)
    return parts


def summarize_by_scene(case_results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in case_results:
        grouped.setdefault(result["scene"], []).append(result)

    scene_metrics: dict[str, dict[str, Any]] = {}
    for scene, results in sorted(grouped.items()):
        matches = sum(item["match_count"] for item in results)
        fps = sum(item["false_positive_count"] for item in results)
        fns = sum(item["false_negative_count"] for item in results)
        exact_matches = sum(1 for item in results if item["exact_match"])
        precision = safe_ratio(matches, matches + fps)
        recall = safe_ratio(matches, matches + fns)
        avg_latency = round(
            sum(item["elapsed_seconds"] for item in results) / len(results),
            3,
        )
        scene_metrics[scene] = {
            "case_count": len(results),
            "exact_match_rate": safe_ratio(exact_matches, len(results)),
            "field_precision": precision,
            "field_recall": recall,
            "field_f1": f1_score(precision, recall),
            "average_latency_seconds": avg_latency,
        }
    return scene_metrics


if __name__ == "__main__":
    main()
