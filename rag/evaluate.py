import subprocess
import re
import sys


QUESTIONS = [
    "Where is the EntityExists contract defined?",
    "Where is the actual implementation of verifyEntityLoaded?",
    "Where is verifyEntityLoaded implemented and which parts of the system call it?",
    "How does the system prevent an unauthorized user from creating a post?",
    "Where is the user's role checked when creating a post?",
    "How does the system verify that an entity was actually loaded?",
    "Which repository method is used to load an entity before verification?",
    "What exception is thrown when an entity cannot be found?",
    "Where is the permission to create a post checked?",
    "Which use cases call verifyEntityLoaded?",
    "Where is verifyEntityLoaded declared abstract and where is it implemented?",
    "What does EntityExists::exists() define?",
    "How does the system determine which roles can create posts?",
    "How does the system check whether a user has Manage Posts permission?",
    "What happens after an entity is loaded in UpdateUsecase?"
]


for i, question in enumerate(QUESTIONS, 1):

    print(f"\n{'=' * 70}")
    print(f"QUESTION {i}")
    print(question)

    result = subprocess.run(
        [sys.executable, "search.py", question],
        capture_output=True,
        text=True
    )

    match = re.search(
        r"EVAL_RESULT\|(\d+)\|(\d+)\|(.+)",
        result.stdout
    )

    if match:
        original_rank = match.group(1)
        final_rank = match.group(2)
        source = match.group(3)

        print("Original Rank:", original_rank)
        print("Final Rank:", final_rank)
        print("Source:", source)

    else:
     print("EVALUATION FAILED")
     print("Return code:", result.returncode)
     print(result.stderr[-1000:])