import uuid
import json
import os
import time
import random
import tiktoken
from datetime import datetime
from typing import List, Dict, Any

from transformers import AutoTokenizer

# Your modules
from .query_generator import generate_queries
from .scraper import search_and_scrape


# -----------------------------
# CONFIG
# -----------------------------
TRACE_FILE = "./data/run_trace.json"

SUB_QUERY_DELAY_RANGE = (20, 45)       # seconds
MAIN_QUERY_DELAY_RANGE = (150, 500)   # seconds


# Load tokenizer once
# tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B")
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


def save_trace(trace_data: Dict[str, Any]):
    with open(TRACE_FILE, "w") as f:
        json.dump(trace_data, f, indent=2)


# -----------------------------
# PIPELINE
# -----------------------------
def run_pipeline(main_questions: List[Dict[str, str]]):

    run_id = generate_id("run")
    run_start_time = time.time()

    full_trace = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "questions": [],
        "timing": {},
        "token_usage": {}
    }

    # =============================
    # MAIN LOOP
    # =============================
    for q_index, item in enumerate(main_questions):
        question = item["Q"]
        objective = item["O"]

        question_id = generate_id("q")

        print(f"\n[START] Question {q_index+1}: {question}")

        q_start_time = time.time()

        # -----------------------------
        # STEP 1: GENERATE QUERIES
        # -----------------------------
        prompt = f"""
        You are an expert research assistant.

        Generate up to 15 HIGH-QUALITY search queries.

        Rules:
        - Cover breadth → then depth
        - Include theory + practical + implementation
        - No repetition
        - Each query_reason must explain WHY this query is useful

        Question: {question}
        Objective: {objective}
        """

        gen_start = time.time()

        input_tokens = count_tokens(prompt)

        generated = generate_queries(question, objective)

        output_tokens = count_tokens(str(generated))

        gen_end = time.time()

        question_trace = {
            "question_id": question_id,
            "original_question": generated["original_question"],
            "objective": generated["original_objective"],
            "difficulty": generated.get("difficulty", "unknown"),
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

        # -----------------------------
        # STEP 2: PROCESS SUB-QUERIES
        # -----------------------------
        queries = generated["search_queries"]

        for i, q in enumerate(queries):
            query_id = generate_id("query")

            query_text = q["query_text"]
            query_reason = q["query_reason"]

            print(f"\n  [QUERY {i+1}] {query_text}")

            query_start = time.time()

            query_text_tokens = count_tokens(query_text)
            query_reason_tokens = count_tokens(query_reason)

            try:
                scrape_start = time.time()

                files = search_and_scrape(
                    query=query_text,
                    topic=generated["original_question"],
                    uid_prefix=query_id,
                    difficulty=question_trace["difficulty"],
                    objective=objective,
                    num_results=50
                )

                scrape_end = time.time()
                query_end = time.time()

                query_trace = {
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

                query_trace = {
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

            # -----------------------------
            # SUB-QUERY DELAY
            # -----------------------------
            if i < len(queries) - 1:
                delay = random.randint(*SUB_QUERY_DELAY_RANGE)
                print(f"    ⏳ Sleeping {delay}s before next sub-query...")
                time.sleep(delay)
            else:
                delay = 0

            query_trace["delay_after_sec"] = delay

            question_trace["queries"].append(query_trace)

        # -----------------------------
        # QUESTION LEVEL STATS
        # -----------------------------
        q_end_time = time.time()

        total_subquery_tokens = sum(
            q["token_usage"]["total_tokens"]
            for q in question_trace["queries"]
        )

        question_trace["timing"]["total_question_time_sec"] = round(q_end_time - q_start_time, 2)
        question_trace["token_usage"]["sub_queries_total_tokens"] = total_subquery_tokens

        # -----------------------------
        # MAIN QUESTION DELAY
        # -----------------------------
        if q_index < len(main_questions) - 1:
            delay = random.randint(*MAIN_QUERY_DELAY_RANGE)

            print(f"\n⏳ Sleeping {delay//60} min {delay%60} sec before next question...\n")
            time.sleep(delay)
        else:
            delay = 0

        question_trace["delay_after_sec"] = delay

        full_trace["questions"].append(question_trace)

        # Save progress
        save_trace(full_trace)

    # -----------------------------
    # RUN LEVEL STATS
    # -----------------------------
    run_end_time = time.time()

    total_tokens_all = sum(
        q["token_usage"]["total_tokens"] + q["token_usage"]["sub_queries_total_tokens"]
        for q in full_trace["questions"]
    )

    full_trace["timing"]["total_run_time_sec"] = round(run_end_time - run_start_time, 2)
    full_trace["token_usage"]["total_tokens_all_questions"] = total_tokens_all

    save_trace(full_trace)

    return full_trace

def load_all_question_files(folder_path: str):
    all_questions = []

    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            file_path = os.path.join(folder_path, file)

            print(f"📂 Loading: {file}")

            with open(file_path, "r") as f:
                data = json.load(f)
                items = []
                # Optional: tag source
                for item in data['QS']:
                    item["source_file"] = file
                    items.append(item)
                    
                all_questions.extend(items)

    return all_questions
# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    DATA_FOLDER = "./data/queries"

    MAIN_QUESTIONS = load_all_question_files(DATA_FOLDER)

    print(f"\n✅ Total Questions Loaded: {len(MAIN_QUESTIONS)}\n")

    run_pipeline(MAIN_QUESTIONS)