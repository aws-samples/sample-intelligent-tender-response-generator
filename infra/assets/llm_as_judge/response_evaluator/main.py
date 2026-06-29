import sys
import json_repair
import boto3
import os
import json
import math
import datetime
import shutil

from pathlib import Path
from typing import Any, Dict, List, Optional
from botocore.config import Config


# TODO: Update these paths with the files to evaluate (can be S3 URIs or local paths)
ANALYSIS_ID = 'your-analysis-id'
GROUND_TRUTH_PATH = "/path/to/ground_truth/document.pdf"
GENERATED_RESPONSE_PATH = "/path/to/generated/response.md"

# ============================== CONFIGURATION (DO NOT MODIFY) ============================== #
OUTPUT_FILES_BUCKET = os.environ.get('OUTPUT_FILES_BUCKET', 'your-output-bucket')

GROUND_TRUTH_FILENAME = GROUND_TRUTH_PATH.split("/")[-1]
GENERATED_RESPONSE_FILENAME = GENERATED_RESPONSE_PATH.split("/")[-1]
ASSETS_PATH = Path(__file__).resolve().parent

EVALUATOR_LLM_MODEL = "global.anthropic.claude-opus-4-5-20251101-v1:0"
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

cfg = Config(
    region_name=AWS_REGION,
    connect_timeout=10,
    read_timeout=600,
    retries={"max_attempts": 6, "mode": "adaptive"},
    tcp_keepalive=True,
)

bedrock_client = boto3.client('bedrock-runtime', config=cfg)
s3_client = boto3.client('s3', region_name=AWS_REGION)
# =========================================================================================== #


def copy_input_files_to_target_path_if_needed():
    dst = f'{ASSETS_PATH}/to_evaluate'

    for filename, path in zip(
            [GROUND_TRUTH_FILENAME, GENERATED_RESPONSE_FILENAME],
            [GROUND_TRUTH_PATH, GENERATED_RESPONSE_PATH]
    ):
        dst_path = Path(f'{dst}/{filename}')
        scr_path = Path(path)

        if path.startswith("s3://"):
            sys.exit('S3 path handling not implemented.')
        elif not path.startswith(dst):
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(scr_path, dst)


def call_bedrock_converse(prompt: str, document=None) -> str:
    content = [{"text": prompt}]

    if document:
        content.append({'document': document})

    response = bedrock_client.converse(
        modelId=EVALUATOR_LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": content
            }
        ],
        inferenceConfig={
            "temperature": 0.1,
            "maxTokens": 8000
        }
    )

    return json.loads(json_repair.repair_json(response['output']['message']['content'][0]['text']))


def get_ground_truth(path: str):
    with open(path, "rb") as fd:
        pdf_bytes = fd.read()

    return {
        "format": GROUND_TRUTH_FILENAME.split(".")[1],
        "name": GROUND_TRUTH_FILENAME.split(".")[0],
        "source": {
            "bytes": pdf_bytes
        },
        "context": "The attached PDF is the ground truth to analyze.",
        "citations": {"enabled": True},
    }


def get_generated_response(path: str):
    with open(path) as fd:
        return fd.read()


def evaluate_response(ground_truth: dict, generated_response: str):
    with open(f'{ASSETS_PATH}/prompts/evaluator_prompt_pdf_attached.txt') as fd:
        prompt = fd.read()

    prompt = prompt.replace('{genai_markdown}', generated_response)

    return call_bedrock_converse(prompt, ground_truth)


def generate_md_summary(results):
    title = f"{GENERATED_RESPONSE_FILENAME} evaluation report"

    def _safe_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False)
        return str(v)

    def _clip(text: str, n: int = 140) -> str:
        text = (text or "").replace("\n", " ").strip()
        return text if len(text) <= n else text[: n - 1] + "…"

    def _pct(x: Any) -> str:
        if x is None:
            return "—"
        try:
            xf = float(x)
            if math.isnan(xf):
                return "—"
            return f"{xf:.0%}"
        except Exception:
            return "—"

    def _avg_score(row: Dict[str, Any]) -> Optional[float]:
        vals = []
        for k in ("presence_score", "completeness_score", "accuracy_score"):
            v = row.get(k)
            if v is None:
                continue
            try:
                vf = float(v)
                if not math.isnan(vf):
                    vals.append(vf)
            except (ValueError, TypeError):
                pass  # Non-numeric value, skip (expected for missing/invalid scores)
        return sum(vals) / len(vals) if vals else None

    def _rank_emoji(avg: Optional[float]) -> str:
        if avg is None:
            return "❔"
        if avg >= 0.95:
            return "🏆"
        if avg >= 0.85:
            return "🌟"
        if avg >= 0.70:
            return "👍"
        if avg >= 0.50:
            return "⚠️"
        return "🚨"

    # ---------- Summary ----------
    total = len(results)
    found_count = sum(1 for r in results if bool(r.get("found")))
    avg_scores = [a for a in (_avg_score(r) for r in results) if a is not None]
    avg_overall = sum(avg_scores) / len(avg_scores) if avg_scores else None

    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = [
        f"# {title}\n", f"_Generated: {now}_\n", f"_Ground truth file: {GROUND_TRUTH_FILENAME}_\n", f"_GenAI generated file: {GENERATED_RESPONSE_FILENAME}_\n",
        "## Summary\n", f"- 📦 Total sections: **{total}**", f"- ✅ Found: **{found_count}** | ❌ Missing: **{total - found_count}**",
        f"- 📊 Overall average score: **{_pct(avg_overall)}** {_rank_emoji(avg_overall)}\n",
        "## Results Table\n",
        "| ID | Found | Avg Score | Presence | Completeness | Accuracy | Ground truth title | Matched headings | Location | Coverage gap (short) |",
        "|---:|:---:|:---:|:---:|:---:|:---:|---|---|---|---|"
    ]

    # ---------- Table (NO EMOJIS) ----------

    def _sort_key(r: Dict[str, Any]):
        sid = r.get("section_id")
        try:
            return (0, int(str(sid)))
        except Exception:
            return (1, str(sid))

    for r in sorted(results, key=_sort_key):
        sid = _safe_str(r.get("section_id"))
        found = "✅" if r.get("found") else "❌"

        pres = r.get("presence_score")
        comp = r.get("completeness_score")
        acc = r.get("accuracy_score")
        avg = _avg_score(r)

        title_gt = _clip(_safe_str(r.get("section_title_ground_truth")), 80)

        headings = r.get("matched_headings_in_genai") or []
        headings_s = ", ".join(map(str, headings)) if isinstance(headings, list) else _safe_str(headings)
        headings_s = _clip(headings_s, 60)

        locs = r.get("matched_locations") or []
        locs_s = ", ".join(map(str, locs)) if isinstance(locs, list) else _safe_str(locs)
        locs_s = _clip(locs_s, 30)

        gap = _clip(_safe_str(r.get("coverage_gap")), 60)

        lines.append(
            f"| {sid} | {found} | {_pct(avg)} | {_pct(pres)} | {_pct(comp)} | {_pct(acc)} | "
            f"{title_gt} | {headings_s} | {locs_s} | {gap} |"
        )

    # ---------- Details (emojis allowed) ----------
    lines.append("\n## Details per section\n")

    for r in sorted(results, key=_sort_key):
        sid = _safe_str(r.get("section_id"))
        title_gt = _safe_str(r.get("section_title_ground_truth"))
        found = bool(r.get("found"))
        avg = _avg_score(r)

        headings = r.get("matched_headings_in_genai") or []
        locs = r.get("matched_locations") or []

        matched_text = _safe_str(r.get("matched_text"))
        coverage_gap = _safe_str(r.get("coverage_gap"))
        reasoning = _safe_str(r.get("reasoning"))

        lines.append(
            f"<details>\n"
            f"<summary><strong>{sid}</strong> — "
            f"{'✅ Found' if found else '❌ Missing'} — {title_gt}</summary>\n"
        )
        lines.append(f"- 📊 Avg score: **{_pct(avg)}**")
        lines.append(f"- 🧩 Presence: **{_pct(r.get('presence_score'))}**")
        lines.append(f"- 🧱 Completeness: **{_pct(r.get('completeness_score'))}**")
        lines.append(f"- 🎯 Accuracy: **{_pct(r.get('accuracy_score'))}**")
        lines.append(f"- 🔎 Matched headings: {', '.join(map(str, headings))}")
        lines.append(f"- 🧭 Locations: {', '.join(map(str, locs))}")

        if coverage_gap:
            lines.append(f"\n**🕳️ Coverage gap**\n\n{coverage_gap}\n")
        if reasoning:
            lines.append(f"**🧠 Reasoning**\n\n{reasoning}\n")
        if matched_text:
            lines.append(f"**📌 Matched text (excerpt)**\n\n> {_clip(matched_text, 600)}\n")

        lines.append("</details>\n")

    return "\n".join(lines)


def persist_file(contents, path):
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(contents, encoding="utf-8")


def upload_to_s3(content, bucket, key, content_type):
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type
    )


if __name__ == "__main__":
    # Move input files to the required path
    copy_input_files_to_target_path_if_needed()

    # Retrieve ground truth and generated response
    ground_truth_doc = get_ground_truth(GROUND_TRUTH_PATH)
    response = get_generated_response(GENERATED_RESPONSE_PATH)

    # Call LLM as judge and persist the response
    evaluation = evaluate_response(ground_truth_doc, response)
    evaluation_filename = f'{ANALYSIS_ID}/evaluation_{GENERATED_RESPONSE_FILENAME}.json'

    persist_file(json.dumps(evaluation, indent=2),f'{ASSETS_PATH}/results/{evaluation_filename}')
    # upload_to_s3(json.dumps(evaluation, indent=2), OUTPUT_FILES_BUCKET,
    #              f'LLM_AS_JUDGE/Final_Tender_Response/{evaluation_filename}',
    #              'application/json')

    # Generate a Markdown report and persist it
    report = generate_md_summary(evaluation)
    report_filename = f'{ANALYSIS_ID}/report_{GENERATED_RESPONSE_FILENAME}.md'

    persist_file(report,f'{ASSETS_PATH}/results/{report_filename}')
    # upload_to_s3(report, OUTPUT_FILES_BUCKET, f'LLM_AS_JUDGE/Final_Tender_Response/{report_filename}',
    #              'text/plain')
