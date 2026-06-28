import sys, json
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

graph = json.loads(Path("graphify-out/graph.json").read_text(encoding="utf-8"))
id2label = {n["id"]: n.get("label", n["id"]) for n in graph["nodes"]}

print("top-level keys:", list(graph.keys()))
edges = graph.get("edges") or graph.get("links") or []
target_ids = [n["id"] for n in graph["nodes"] if id2label.get(n["id"]) == "RegistroAgronomico"]
print("RegistroAgronomico node ids:", target_ids)
print()

for e in edges:
    s, t = e.get("source"), e.get("target")
    if s in target_ids or t in target_ids:
        conf = e.get("confidence", "?")
        if conf != "INFERRED":
            continue
        rel = e.get("relation", "?")
        sc = e.get("confidence_score", "?")
        sf = e.get("source_file", "?")
        print(f"[{conf} {sc}] {id2label.get(s,s)} --{rel}--> {id2label.get(t,t)}")
        print(f"    {s} -> {t}   ({sf})")
