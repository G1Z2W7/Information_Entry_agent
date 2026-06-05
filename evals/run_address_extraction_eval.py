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

from app.agent.extractor import extract_llm_incremental_patch
from app.agent.state import create_initial_state, merge_state


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_FILE = PROJECT_ROOT / "evals" / "cases" / "address_extraction_50.jsonl"
DEFAULT_RESULT_DIR = PROJECT_ROOT / "evals" / "results"
ENV_FILE = PROJECT_ROOT / ".env"


@dataclass
class EvalCase:
    case_id: str
    scene: str
    message: str
    expected_patch: dict[str, Any]
    tags: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run address extraction evaluation.")
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_FILE)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--progress-every", type=int, default=10)
    return parser.parse_args()


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            cases.append(
                EvalCase(
                    case_id=payload["case_id"],
                    scene=payload["scene"],
                    message=payload["message"],
                    expected_patch=payload["expected_patch"],
                    tags=payload.get("tags", []),
                )
            )
    if not cases:
        raise RuntimeError(f"No cases found in {path}")
    return cases


def flatten_patch(value: Any, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(flatten_patch(child, next_prefix))
        return flattened
    if isinstance(value, list):
        for index, child in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_patch(child, next_prefix))
        return flattened

    flattened[prefix] = normalize_scalar(value)
    return flattened


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, str):
        return value.strip()
    return value


def diff_maps(
    expected: dict[str, Any],
    predicted: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    matches: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []

    for path, expected_value in expected.items():
        if path not in predicted:
            false_negatives.append({"path": path, "expected": expected_value, "actual": None})
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


def run_case(case: EvalCase, *, max_attempts: int) -> dict[str, Any]:
    state = create_initial_state(case.case_id)
    predicted_patch: dict[str, Any] = {}
    final_site_patch: dict[str, Any] = {}
    elapsed_seconds = 0.0
    error_message: str | None = None
    attempts = 0

    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        started_at = time.perf_counter()
        try:
            predicted_patch = extract_llm_incremental_patch(case.message, state)
            merge_state(
                state,
                predicted_patch,
                turn_number=1,
                source_text=case.message,
            )
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

    if state.sites:
        final_site_patch = {"sites": [state.sites[0].model_dump(exclude_none=True)]}

    expected_flat = flatten_patch(case.expected_patch)
    predicted_flat = flatten_patch(final_site_patch)
    matches, false_positives, false_negatives = diff_maps(expected_flat, predicted_flat)

    return {
        "case_id": case.case_id,
        "scene": case.scene,
        "tags": case.tags,
        "message": case.message,
        "expected_patch": case.expected_patch,
        "raw_predicted_patch": predicted_patch,
        "final_site_patch": final_site_patch,
        "expected_flat": expected_flat,
        "predicted_flat": predicted_flat,
        "exact_match": expected_flat == predicted_flat,
        "elapsed_seconds": elapsed_seconds,
        "attempt_count": attempts,
        "error": error_message,
        "match_count": len(matches),
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
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
    errored_cases = sum(1 for result in case_results if result.get("error"))

    precision = safe_ratio(total_matches, total_matches + total_false_positives)
    recall = safe_ratio(total_matches, total_matches + total_false_negatives)
    exact_match_rate = safe_ratio(exact_match_cases, total_cases)
    average_latency = round(
        sum(result["elapsed_seconds"] for result in case_results) / total_cases,
        3,
    )

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
            "average_latency_seconds": average_latency,
            "errored_cases": errored_cases,
        },
        "scene_metrics": scene_metrics,
        "cases": case_results,
    }


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


def write_summary_json(summary: dict[str, Any], output_path: Path | None) -> Path:
    DEFAULT_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DEFAULT_RESULT_DIR / f"address_extraction_50_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def write_markdown_report(summary: dict[str, Any], output_path: Path | None) -> Path:
    DEFAULT_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DEFAULT_RESULT_DIR / f"address_extraction_50_{timestamp}.md"

    lines = [
        "# 地址字段提取测试报告",
        "",
        f"- 运行时间：{summary['run_at']}",
        f"- 用例文件：`{summary['case_file']}`",
        f"- 模型：`{summary['model']}`",
        "",
        "## 总体指标",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 用例数 | {summary['metrics']['case_count']} |",
        f"| 完全一致率 | {summary['metrics']['exact_match_rate']} |",
        f"| 字段精确率 | {summary['metrics']['field_precision']} |",
        f"| 字段召回率 | {summary['metrics']['field_recall']} |",
        f"| 字段 F1 | {summary['metrics']['field_f1']} |",
        f"| 平均耗时（秒） | {summary['metrics']['average_latency_seconds']} |",
        f"| 错误用例数 | {summary['metrics']['errored_cases']} |",
        "",
        "## 分场景指标",
        "",
        "| 场景 | 用例数 | 完全一致率 | 精确率 | 召回率 | F1 | 平均耗时（秒） |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for scene, metrics in summary["scene_metrics"].items():
        lines.append(
            f"| {scene} | {metrics['case_count']} | {metrics['exact_match_rate']} | "
            f"{metrics['field_precision']} | {metrics['field_recall']} | "
            f"{metrics['field_f1']} | {metrics['average_latency_seconds']} |"
        )

    lines.extend(
        [
            "",
            "## 用例明细",
            "",
            "| 用例 | 场景 | 测试语句 | 期望提取 | 最终提取结果 | 完全一致 | 耗时（秒） |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for case in summary["cases"]:
        expected_json = json.dumps(case["expected_patch"], ensure_ascii=False)
        actual_json = json.dumps(case["final_site_patch"], ensure_ascii=False)
        safe_message = case["message"].replace("|", "\\|")
        safe_expected = expected_json.replace("|", "\\|")
        safe_actual = actual_json.replace("|", "\\|")
        lines.append(
            f"| {case['case_id']} | {case['scene']} | {safe_message} | "
            f"`{safe_expected}` | `{safe_actual}` | "
            f"{'是' if case['exact_match'] else '否'} | {case['elapsed_seconds']} |"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def print_summary(summary: dict[str, Any], json_path: Path, md_path: Path) -> None:
    metrics = summary["metrics"]
    print("Address Extraction Eval Summary")
    print(f"case_file={summary['case_file']}")
    print(f"model={summary['model']}")
    print(f"case_count={metrics['case_count']}")
    print(f"exact_match_rate={metrics['exact_match_rate']}")
    print(f"field_precision={metrics['field_precision']}")
    print(f"field_recall={metrics['field_recall']}")
    print(f"field_f1={metrics['field_f1']}")
    print(f"average_latency_seconds={metrics['average_latency_seconds']}")
    print(f"errored_cases={metrics['errored_cases']}")
    print(f"json_result_file={json_path}")
    print(f"markdown_result_file={md_path}")


def main() -> None:
    args = parse_args()
    load_dotenv(ENV_FILE)

    if not os.getenv("DS_API_KEY"):
        raise RuntimeError("DS_API_KEY is required to run the real DeepSeek evaluation.")

    cases = load_cases(args.case_file)
    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_results.append(run_case(case, max_attempts=max(1, args.max_attempts)))
        if args.progress_every > 0 and index % args.progress_every == 0:
            print(f"progress={index}/{len(cases)}", flush=True)
        if args.sleep_seconds > 0 and index < len(cases):
            time.sleep(args.sleep_seconds)

    summary = summarize(case_results, args.case_file)
    json_path = write_summary_json(summary, args.output_json)
    md_path = write_markdown_report(summary, args.output_md)
    print_summary(summary, json_path, md_path)


if __name__ == "__main__":
    main()
