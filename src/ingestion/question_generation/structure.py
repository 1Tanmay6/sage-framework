from typing_extensions import TypedDict, Annotated


class QuestionGenerationOutput(TypedDict):
    SUFFICIENT_QUESTION: Annotated[str,
                                   "a question that can be fully and completely answered using the provided context, no external knowledge needed"]
    PARTIAL_QUESTION: Annotated[str,
                                "a question where the context gives some relevant information but is missing key details to fully answer it"]
    INSUFFICIENT_QUESTION: Annotated[str,
                                     "a question that cannot be answered at all from the context, the context is completely irrelevant"]
    SUFFICIENT_QUESTION_REASON: Annotated[str,
                                          "one sentence explaining exactly which part of the context makes it sufficient"]
    PARTIAL_QUESTION_REASON: Annotated[str,
                                       "one sentence explaining what the context covers and specifically what crucial information is missing"]
    INSUFFICIENT_QUESTION_REASON: Annotated[str,
                                            "one sentence explaining why the context is completely irrelevant to the question"]
