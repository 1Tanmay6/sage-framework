import os
import json
from typing import Dict, List, Any
from cleantext import clean


def count_files(folder_path: str) -> int:
    total_files = 0
    for _, _, files in os.walk(folder_path):
        total_files += len(files)
    return total_files


def load_json(path: str) -> Any:
    with open(path, "r") as f:
        return json.load(f)


def load_question_sets(base_path: str) -> Dict[str, List[str]]:
    def extract_questions(path):
        data = load_json(path)["QS"]
        return [x["Q"] for x in data]

    return {
        "ML": extract_questions(f"{base_path}/ML_QUESTIONS.json"),
        "AI": extract_questions(f"{base_path}/AI_QUESTIONS.json"),
        "CS": extract_questions(f"{base_path}/CS_QUESTIONS.json"),
        "FINANCE": extract_questions(f"{base_path}/FIN_QUESTIONS.json"),
    }


def clean_text_file(file_path: str) -> str:
    with open(file_path, "r") as f:
        text = f.read()

    return clean(
        text=text,
        fix_unicode=True,
        to_ascii=True,
        lower=True,
        replace_with_url="This is a URL",
        replace_with_email="Email",
        replace_with_number="123",
        replace_with_digit="0",
        replace_with_currency_symbol="$",
        lang="en",
    )


def get_category(question: str, question_sets: Dict[str, List[str]]) -> str:
    for category, questions in question_sets.items():
        if question in questions:
            return category
    raise ValueError(f"Question not found: {question}")


def deduplicate_files(files: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique = []

    for f in files:
        fname = f["file_name"]
        if fname not in seen:
            seen.add(fname)
            unique.append(f)

    return unique


def build_repo(data: Dict, question_sets: Dict[str, List[str]]) -> Dict:
    repo = {}

    for ques in data["questions"]:
        ques_dict = {
            "Q": ques["original_question"],
            "O": ques["original_objective"],
            "files": [],
            "num_files": 0,
            "question_topic": get_category(
                ques["original_question"], question_sets
            ),
            "metadata": {
                "total_time_question": ques["timing"],
                "total_token_usage_question": ques["token_usage"],
                "queries_metadata": {},
            },
        }

        for query in ques["queries"]:
            q_files = [x.split("/")[-1] for x in query["files_scraped"]]

            ques_dict["metadata"]["queries_metadata"][query["query_id"]] = {
                "query": query["query_text"],
                "reason": query["query_reason"],
                "files": q_files,
                "metadata": {
                    "timestamp": query["timestamp"],
                    "token_usage": query["token_usage"],
                    "time_taken": query["timing"],
                    "num_files": query["num_files"],
                },
            }

            ques_files = [
                {
                    "file_name": x.split("/")[-1],
                    "file_source": x.split("/")[-2],
                }
                for x in query["files_scraped"]
            ]

            ques_dict["files"].extend(ques_files)
            ques_dict["num_files"] += len(q_files)

        ques_dict["files"] = deduplicate_files(ques_dict["files"])
        ques_dict["num_files"] = len(ques_dict["files"])

        repo[ques["question_id"]] = ques_dict

    return repo


def count_total_queries(data: Dict) -> int:
    total = 0
    for ques in data["questions"]:
        total += len(ques.get("queries", []))
    return total


def save_repo(repo: Dict, output_path: str):
    with open(output_path, "w") as fp:
        json.dump(repo, fp, indent=4)


def main():
    run_trace_path = "./data/run_trace.json"
    queries_path = "./data/queries"
    output_path = "./data/metadata/metadata.json"
    folder_to_count = "./scraped_data"

    data = load_json(run_trace_path)
    question_sets = load_question_sets(queries_path)

    repo = build_repo(data, question_sets)
    save_repo(repo, output_path)

    print("Saved metadata!")
    print(f"Total questions: {len(data['questions'])}")
    print(f"Total queries: {count_total_queries(data)}")

    if os.path.exists(folder_to_count):
        print(f"Total files: {count_files(folder_to_count)}")


if __name__ == "__main__":
    main()
