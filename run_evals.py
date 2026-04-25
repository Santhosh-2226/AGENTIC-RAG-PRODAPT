import json
from agent import run_agent

with open("eval/questions.json", "r", encoding="utf-8") as f:
    evals = json.load(f)

total = len(evals)
passed = 0

print("\n" + "=" * 60)
print("EVAL RUN")
print("=" * 60)

for item in evals:
    q = item["question"]
    expected_tools = set(item.get("expected_tools", []))

    print(f"\n[{item['id']}] {q}")
    print("-" * 60)

    result = run_agent(q)

    used_tools = set()
    for c in result.get("citations", []):
        if "query_data" in c:
            used_tools.add("query_data")
        if "search_docs" in c:
            used_tools.add("search_docs")
        if "web_search" in c:
            used_tools.add("web_search")

    if item["category"] == "refusal":
        status_ok = result["status"] in ["refused", "insufficient_evidence"]
    elif item["category"] == "edge_case":
        status_ok = True
    else:
        status_ok = result["status"] in ["answered", "partial_answer"]

    tools_ok = expected_tools.issubset(used_tools)

    print(f"Expected tools : {list(expected_tools)}")
    print(f"Used tools     : {list(used_tools)}")
    print(f"Status         : {result['status']}")
    print(f"Steps used     : {result['steps_used']}")
    print("\nAnswer:")
    print(result["final_answer"][:1200])

    if result.get("citations"):
        print("\nCitations:")
        for c in result["citations"][:6]:
            print(f"  - {c}")

    if tools_ok and status_ok:
        print("\n✓ PASS")
        passed += 1
    else:
        print("\n✗ FAIL")

print("\n" + "=" * 60)
print(f"FINAL RESULT: {passed}/{total} passed")
print("=" * 60)