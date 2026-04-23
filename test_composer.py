from layers.composer import compose_answer
from memory.evidence import EvidenceMemory

m = EvidenceMemory()
tool_input = {"question": "Who scored most runs in IPL 2023", "table_hint": "batting"}
result = {
    "rows": [
        {"player": "Shubman Gill", "total_runs": 900},
        {"player": "Faf du Plessis", "total_runs": 720}
    ],
    "row_count": 2,
    "sql": "SELECT...",
    "source_table": "deliveries"
}
m.add("query_data", tool_input, result, "abc123")
out = compose_answer("Who scored the most runs in IPL 2023?", [], m, None)
print(out)