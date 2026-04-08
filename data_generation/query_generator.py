
import os
import json
from typing import List
from typing_extensions import TypedDict, Annotated

from langchain_ollama import ChatOllama


class Query(TypedDict):
    """Query Structure to be generated"""

    query_text: Annotated[
        str,
        "Highly specific, keyword-rich search query optimized for search engines (8-15 words preferred)"
    ]
    query_reason: Annotated[str, "The reason why this query was asked how it relates to objective and the original question"]

# 1. Define schema (TypedDict)
class SearchQueryOutput(TypedDict):
    """Generate search queries that help answer the original question."""
    
    original_question: Annotated[str, "The user's original question"]
    original_objective: Annotated[str, "The user's original objective"]
    search_queries: Annotated[
        List[Query],
        "List of up to 25 optimized search queries that together can answer the question"
    ]
    difficulty: Annotated[str, "How difficult or complex is the original query"]


# 2. Initialize model (latest way)
llm = ChatOllama(
    model="llama3",
    temperature=0,
    num_predict=2048,
    top_p=0.9,
    repeat_penalty=1.1
)

# 3. Attach structured output (IMPORTANT)
structured_llm = llm.with_structured_output(SearchQueryOutput)


# 4. Prompt (keep instruction inside input)
def generate_queries(question: str, objective: str):
    prompt = f"""
        You are an expert at generating search queries.

        Given a question, generate up to 25 HIGH-QUALITY search queries such that:
        - If someone searches them, they can fully answer the question, AND fulfill their objective.
        - Cover multiple angles (definition, examples, comparisons, implementation)
        - Be specific, not vague
        - No repetition
        - Think like a researcher, someone who is out there to hurdle as much information as possible.
        - First queries should look from width and then depth of the topic. 
        - Think from an theoretical as well as a practical (applied/applicable) standpoint.
        - Don't make queries so conversation like, you are asking a browser not an human.

        Question: {question}
        Objective: {objective}
        """

    return structured_llm.invoke(prompt)
