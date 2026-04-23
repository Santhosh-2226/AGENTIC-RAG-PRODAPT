from tools.query_data import query_data, classify_question

questions = [
    "Which team won IPL 2023?",
    "Who won the IPL 2023?",
    "Who won IPL 2023 final?",
]

for q in questions:
    print(f"\nQ: {q}")
    print(f"  classify: {classify_question(q)}")
    result = query_data(q)
    print(f"  result: {result}")