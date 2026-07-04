import uuid
import json
import os
import time
import random
import tiktoken
from datetime import datetime
from typing import List, Dict, Any

from .query_generator import generate_queries
from .scraper import search_and_scrape


# -----------------------------
# CONFIG
# -----------------------------
TRACE_FILE = "./data/run_trace.json"

SUB_QUERY_DELAY_RANGE = (5, 45)
MAIN_QUERY_DELAY_RANGE = (150, 600)

encoding = tiktoken.get_encoding("cl100k_base")


# -----------------------------
# UTILS
# -----------------------------
def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(encoding.encode(text))


def save_trace(trace: Dict[str, Any]):
    with open(TRACE_FILE, "w") as f:
        json.dump(trace, f, indent=2)


def load_trace():
    if os.path.exists(TRACE_FILE):
        print("🔁 Resuming existing run...")
        with open(TRACE_FILE, "r") as f:
            return json.load(f)

    return {
        "run_id": generate_id("run"),
        "timestamp": datetime.utcnow().isoformat(),
        "questions": [],
        "timing": {},
        "token_usage": {}
    }


# -----------------------------
# SAFE QUERY GENERATION
# -----------------------------
def safe_generate_queries(question: str, objective: str, retries=3):

    for attempt in range(retries):
        try:
            result = generate_queries(question, objective)

            if not result or "search_queries" not in result:
                raise ValueError("Invalid LLM output")

            return result

        except Exception as e:
            print(f"⚠️ LLM failed (attempt {attempt+1}): {e}")
            # time.sleep(2)

    print("❌ Fallback query used")

    return {
        "original_question": question,
        "original_objective": objective,
        "difficulty": "unknown",
        "search_queries": [{
            "query_text": question,
            "query_reason": "fallback"
        }]
    }


# -----------------------------
# CORE PIPELINE
# -----------------------------
def run_pipeline(main_questions: List[Dict[str, str]]):

    trace = load_trace()
    run_start = time.time()

    for q_index, item in enumerate(main_questions):

        question = item["Q"]
        objective = item["O"]

        print(f"\n==============================")
        print(f"QUESTION {q_index+1}: {question}")
        print(f"==============================")

        # -----------------------------
        # FIND / CREATE QUESTION TRACE
        # -----------------------------
        question_trace = None

        for q in trace["questions"]:
            if q.get("original_question") == question:
                question_trace = q
                break

        # -----------------------------
        # NEW QUESTION
        # -----------------------------
        if question_trace is None:

            print("🆕 Generating queries...")

            gen_start = time.time()

            prompt = f"{question}\n{objective}"
            input_tokens = count_tokens(prompt)

            generated = safe_generate_queries(question, objective)

            output_tokens = count_tokens(str(generated))

            gen_end = time.time()

            question_trace = {
                "question_id": generate_id("q"),
                "original_question": generated["original_question"],
                "original_objective": generated["original_objective"],
                "difficulty": generated.get("difficulty", "unknown"),
                "generated_queries": generated["search_queries"],
                "queries": [],
                "timing": {
                    "query_generation_time_sec": round(gen_end - gen_start, 2)
                },
                "token_usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens
                }
            }

            trace["questions"].append(question_trace)
            save_trace(trace)

        else:
            print("🔁 Resuming existing question")

            # FIX: ensure generated_queries exists
            if "generated_queries" not in question_trace or not question_trace["generated_queries"]:
                print("⚠️ Missing generated_queries → regenerating")

                generated = safe_generate_queries(question, objective)
                question_trace["generated_queries"] = generated["search_queries"]

                save_trace(trace)

        # -----------------------------
        # PREP
        # -----------------------------
        all_queries = question_trace["generated_queries"]

        completed_queries = {
            q.get("query_text")
            for q in question_trace.get("queries", [])
        }

        # -----------------------------
        # PROCESS QUERIES
        # -----------------------------
        for i, q in enumerate(all_queries):

            query_text = q.get("query_text")
            query_reason = q.get("query_reason", "")

            if not query_text:
                continue

            if query_text in completed_queries:
                print(f"  ⏭️ Skipping: {query_text}")
                continue

            print(f"\n  🔎 [{i+1}/{len(all_queries)}] {query_text}")

            query_start = time.time()

            query_text_tokens = count_tokens(query_text)
            query_reason_tokens = count_tokens(query_reason)

            query_id = generate_id("query")

            try:
                scrape_start = time.time()

                files = search_and_scrape(
                    query=query_text,
                    topic=question,
                    uid_prefix=query_id,
                    difficulty=question_trace.get("difficulty", "unknown"),
                    objective=objective,
                    num_results=100
                )

                scrape_end = time.time()
                query_end = time.time()

                entry = {
                    "query_id": query_id,
                    "query_text": query_text,
                    "query_reason": query_reason,
                    "files_scraped": files,
                    "num_files": len(files),
                    "timestamp": datetime.utcnow().isoformat(),
                    "timing": {
                        "scrape_time_sec": round(scrape_end - scrape_start, 2),
                        "total_query_time_sec": round(query_end - query_start, 2)
                    },
                    "token_usage": {
                        "query_text_tokens": query_text_tokens,
                        "query_reason_tokens": query_reason_tokens,
                        "total_tokens": query_text_tokens + query_reason_tokens
                    }
                }

            except Exception as e:
                query_end = time.time()

                entry = {
                    "query_id": query_id,
                    "query_text": query_text,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "timing": {
                        "total_query_time_sec": round(query_end - query_start, 2)
                    },
                    "token_usage": {
                        "query_text_tokens": query_text_tokens,
                        "query_reason_tokens": query_reason_tokens,
                        "total_tokens": query_text_tokens + query_reason_tokens
                    }
                }

            # SAVE immediately
            question_trace["queries"].append(entry)
            save_trace(trace)

            # DELAY (sub-query)
            if i < len(all_queries) - 1:
                delay = random.randint(*SUB_QUERY_DELAY_RANGE)
                print(f"    ⏳ Sleeping {delay}s...")
                time.sleep(delay)

        # -----------------------------
        # QUESTION LEVEL STATS
        # -----------------------------
        total_sub_tokens = sum(
            q.get("token_usage", {}).get("total_tokens", 0)
            for q in question_trace["queries"]
        )

        question_trace["token_usage"]["sub_queries_total_tokens"] = total_sub_tokens

        # -----------------------------
        # MAIN DELAY
        # -----------------------------
        if q_index < len(main_questions) - 1:
            delay = random.randint(*MAIN_QUERY_DELAY_RANGE)
            print(f"\n⏳ Next question in {delay//60} min {delay%60} sec\n")
            time.sleep(delay)

        save_trace(trace)

    # -----------------------------
    # RUN LEVEL STATS
    # -----------------------------
    run_end = time.time()

    total_tokens_all = sum(
        q.get("token_usage", {}).get("total_tokens", 0) +
        q.get("token_usage", {}).get("sub_queries_total_tokens", 0)
        for q in trace["questions"]
    )

    trace["timing"]["total_run_time_sec"] = round(run_end - run_start, 2)
    trace["token_usage"]["total_tokens_all_questions"] = total_tokens_all

    save_trace(trace)

    print("\n🎉 RUN COMPLETE")


# -----------------------------
# LOAD QUESTIONS
# -----------------------------
def load_all_question_files(folder_path: str):

    all_questions = []

    for file in os.listdir(folder_path):
        if file.endswith(".json"):

            path = os.path.join(folder_path, file)
            print(f"📂 Loading: {file}")

            with open(path, "r") as f:
                data = json.load(f)

                for item in data.get("QS", []):
                    item["source_file"] = file
                    all_questions.append(item)

    return all_questions


# -----------------------------
# ENTRYPOINT
# -----------------------------
if __name__ == "__main__":

    DATA_FOLDER = "./data/queries"

    MAIN_QUESTIONS = load_all_question_files(DATA_FOLDER)

    print(f"\n✅ Total Questions Loaded: {len(MAIN_QUESTIONS)}\n")

    run_pipeline(MAIN_QUESTIONS)