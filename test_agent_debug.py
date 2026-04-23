import os
os.environ["GROQ_API_KEY"] = open(".env").read().split("GROQ_API_KEY=")[1].split("\n")[0].strip()

from memory.evidence import EvidenceMemory
from layers.normalizer import normalize_query
from layers.goal_decomposer import decompose_goals
from tools.query_data import query_data

question = "Which team won IPL 2023?"
normalized = normalize_query(question)
goals = decompose_goals(normalized)

memory = EvidenceMemory()

# Simulate what agent does
result = query_data(question)
print("query_data result:", result)
print("success:", result.get("success"))
print("rows:", result.get("rows"))

import hashlib, json
call_hash = hashlib.md5(f"query_data:{json.dumps({'question': question}, sort_keys=True)}".encode()).hexdigest()
memory.add("query_data", {"question": question}, result, call_hash)

print("\nmemory items:", len(memory.items))
print("get_by_tool:", memory.get_by_tool("query_data"))

from layers.composer import compose_answer
out = compose_answer(question, goals, memory, None)
print("\ncomposer output:", out)