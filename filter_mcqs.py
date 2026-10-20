"""
MCQ Topic Filter using TypeSafe Jev Model
Filters questions related to:
"Experimental Techniques & Lab Practices: Basic laboratory errors, calculation of significant figures, vernier calipers, screw gauge mechanisms"
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_KEY = os.getenv(
    "TYPESAFE_API_KEY",
    "apikey_2125333ab2981a414b869eb691ee222a745e_c825200c54b8d353d86b889a9b1a5480a279263a4b83e512140adc50e1fee131"
)
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"

TARGET_TOPIC = (
    "Experimental Techniques & Lab Practices: Basic laboratory errors (systematic, random, absolute, relative, "
    "percentage errors, combination of errors), calculation of significant figures and rounding off rules, "
    "vernier calipers mechanisms and readings, and screw gauge / micrometer mechanisms (least count, pitch, zero error, backlash error)."
)

INSTRUCTIONS = (
    f"Does this physics multiple choice question belong to the topic: '{TARGET_TOPIC}'? "
    "Questions purely on standard SI units, dimensions and dimensional formulas, orders of magnitude, "
    "or astronomical distance measurement (parallax) are NOT part of this topic."
)


def evaluate_question(mcq: dict, retries: int = 3) -> dict:
    """Sends a single question to the Jev model and returns the evaluated score."""
    q_no = mcq.get("q_no", "?")
    q_text = mcq.get("question", "")
    opt_a = mcq.get("opt_a", "")
    opt_b = mcq.get("opt_b", "")
    opt_c = mcq.get("opt_c", "")
    opt_d = mcq.get("opt_d", "")

    state_prompt = (
        f"Question {q_no}: {q_text}\n"
        f"Options:\n"
        f"A) {opt_a}\n"
        f"B) {opt_b}\n"
        f"C) {opt_c}\n"
        f"D) {opt_d}\n"
    )

    payload = {
        "model": "jev-latest",
        "state": state_prompt,
        "questions": {
            "is_target_topic": {
                "type": "noul",
                "instructions": INSTRUCTIONS
            }
        }
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TYPESAFE_URL,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                score = res["answers"]["is_target_topic"]["noul"]
                return {
                    "mcq": mcq,
                    "confidence": round(score, 4),
                    "confidence_pct": round(score * 100, 1),
                    "error": None
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if attempt == retries:
                return {"mcq": mcq, "confidence": 0.0, "confidence_pct": 0.0, "error": f"HTTP {e.code}: {err_body}"}
            time.sleep(1.5 * attempt)
        except Exception as e:
            if attempt == retries:
                return {"mcq": mcq, "confidence": 0.0, "confidence_pct": 0.0, "error": str(e)}
            time.sleep(1.5 * attempt)

    return {"mcq": mcq, "confidence": 0.0, "confidence_pct": 0.0, "error": "Max retries exceeded"}


def filter_mcqs(
    input_file: str,
    output_filtered_file: str,
    threshold: float = 0.70,
    max_workers: int = 5,
    output_scored_file: str = None
):
    """
    Evaluates all MCQs in the input file using the Jev model and saves
    questions that meet or exceed the threshold confidence score.
    """
    if not os.path.exists(input_file):
        print(f"[-] Error: Input file '{input_file}' not found.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        mcqs = json.load(f)

    total = len(mcqs)
    print(f"==================================================")
    print(f" TypeSafe Jev MCQ Topic Classifier & Filter")
    print(f"==================================================")
    print(f"[+] Loaded {total} questions from: {input_file}")
    print(f"[+] Target Topic: Experimental Techniques & Lab Practices")
    print(f"[+] Confidence Threshold: {threshold * 100:.1f}% ({threshold})")
    print(f"[+] Workers: {max_workers} parallel requests")
    print(f"--------------------------------------------------")

    results = []
    completed = 0
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_mcq = {executor.submit(evaluate_question, mcq): mcq for mcq in mcqs}

        for future in concurrent.futures.as_completed(future_to_mcq):
            res = future.result()
            results.append(res)
            completed += 1

            status = "MATCH" if res["confidence"] >= threshold else "SKIP "
            q_num = res["mcq"].get("q_no", completed)
            q_title = res["mcq"].get("question", "")[:45]

            # Print live progress
            print(
                f"[{completed:3d}/{total:3d}] [{status}] ({res['confidence_pct']:5.1f}%) "
                f"Q{q_num}: {q_title}..."
            )

    # Sort results back to original question order
    results.sort(key=lambda x: int(x["mcq"].get("q_no", 0)) if str(x["mcq"].get("q_no", "")).isdigit() else 0)

    # Filter by threshold
    accepted = []
    all_reviewed = []
    import csv

    for r in results:
        is_match = r["confidence"] >= threshold
        item = dict(r["mcq"])
        item["confidence_score"] = r["confidence"]
        item["confidence_pct"] = r["confidence_pct"]
        item["status"] = "TAKEN" if is_match else "SKIPPED"
        all_reviewed.append(item)
        if is_match:
            accepted.append(item)

    # 1. Save filtered output JSON
    with open(output_filtered_file, "w", encoding="utf-8") as f:
        json.dump(accepted, f, indent=2, ensure_ascii=False)

    # 2. Save complete report JSON
    scored_json_file = output_scored_file or output_filtered_file.replace(".json", "_full_review.json")
    with open(scored_json_file, "w", encoding="utf-8") as f:
        json.dump(all_reviewed, f, indent=2, ensure_ascii=False)

    # 3. Save readable CSV for verification
    csv_file = output_filtered_file.replace(".json", "_verification.csv")
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Q_No", "Status", "Confidence", "Question", "Explanation"])
        for item in all_reviewed:
            writer.writerow([
                item.get("q_no", ""),
                item["status"],
                f"{item['confidence_pct']}%",
                item.get("question", ""),
                item.get("explanation", "")[:120] + "..." if item.get("explanation") else ""
            ])

    # 4. Save readable Markdown summary for verification
    md_file = output_filtered_file.replace(".json", "_verification.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# MCQ Topic Classification & Verification Report\n\n")
        f.write(f"- **Target Topic**: Experimental Techniques & Lab Practices\n")
        f.write(f"- **Confidence Cutoff**: {threshold * 100:.1f}%\n")
        f.write(f"- **Total Questions**: {total}\n")
        f.write(f"- **TAKEN (>= {threshold * 100:.0f}%)**: {len(accepted)} ({len(accepted)/total*100:.1f}%)\n")
        f.write(f"- **SKIPPED (< {threshold * 100:.0f}%)**: {total - len(accepted)}\n\n")
        f.write("## 1. Questions TAKEN (Included)\n\n")
        f.write("| Q# | Score | Question | Options |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for item in accepted:
            f.write(f"| **Q{item.get('q_no')}** | `{item['confidence_pct']}%` | {item.get('question', '').replace('|', '-')} | A: {item.get('opt_a','')} / B: {item.get('opt_b','')} |\n")

        f.write("\n## 2. Questions SKIPPED (Excluded)\n\n")
        f.write("| Q# | Score | Question |\n")
        f.write("| :--- | :--- | :--- |\n")
        for item in all_reviewed:
            if item["status"] == "SKIPPED":
                f.write(f"| Q{item.get('q_no')} | `{item['confidence_pct']}%` | {item.get('question', '').replace('|', '-')} |\n")

    elapsed = time.time() - start_time
    print(f"==================================================")
    print(f"[+] Complete in {elapsed:.1f}s!")
    print(f"[+] TAKEN (>= {threshold*100:.0f}%): {len(accepted)} / {total} questions ({len(accepted) / total * 100:.1f}%)")
    print(f"[+] SKIPPED: {total - len(accepted)} questions")
    print(f"[+] Saved filtered MCQs: {output_filtered_file}")
    print(f"[+] Saved Verification CSV: {csv_file}")
    print(f"[+] Saved Verification Markdown: {md_file}")
    print(f"[+] Saved Full Review JSON: {scored_json_file}")
    print(f"==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter physics MCQs by topic using TypeSafe Jev model.")
    parser.add_argument(
        "--input", "-i",
        default="chap 1/chapter_1_all_394_mcqs.json",
        help="Path to the input JSON file containing MCQs"
    )
    parser.add_argument(
        "--output", "-o",
        default="chap 1/chapter_1_lab_practices_filtered.json",
        help="Path to save the filtered MCQs JSON file"
    )
    parser.add_argument(
        "--confidence", "-c",
        type=float,
        default=0.70,
        help="Confidence threshold between 0.0 and 1.0 (default: 0.70 for 70%%)"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=8,
        help="Number of concurrent API workers (default: 8)"
    )
    parser.add_argument(
        "--report", "-r",
        default=None,
        help="Optional path to save all questions with their confidence scores"
    )

    args = parser.parse_args()

    # Normalize confidence if entered as percentage (e.g., 70 -> 0.70)
    thresh = args.confidence
    if thresh > 1.0:
        thresh = thresh / 100.0

    filter_mcqs(
        input_file=args.input,
        output_filtered_file=args.output,
        threshold=thresh,
        max_workers=args.workers,
        output_scored_file=args.report
    )

