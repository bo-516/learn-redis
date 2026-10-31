import json, importlib, sys, os
sys.path.insert(0, os.path.dirname(__file__))
out = os.path.join(os.path.dirname(__file__), "..", "data")
for n in range(1, 7):
    m = importlib.import_module(f"ch{n}")
    ch = m.CH
    for q in ch["quiz"]:
        if q.get("snippet") is None: q.pop("snippet", None)
        t = q["type"]
        if t == "single": assert 0 <= q["answer"] < len(q["options"]), q["q"]
        if t == "multi": assert all(0 <= a < len(q["options"]) for a in q["answer"]) and len(q["answer"]) >= 1, q["q"]
        if t == "tf": assert isinstance(q["answer"], bool)
        if t == "fill": assert isinstance(q["answer"], list) and q["answer"]
    for b in ch["bank"]:
        if b.get("deep") is None: b.pop("deep", None)
    ch["lesson"] = ch["lesson"].strip()
    with open(os.path.join(out, f"ch{n}.js"), "w") as f:
        f.write("window.CHAPTERS=window.CHAPTERS||[];window.CHAPTERS.push(" + json.dumps(ch, ensure_ascii=False) + ");\n")
    print(ch["code"], "quiz", len(ch["quiz"]), "bank", len(ch["bank"]))
m = importlib.import_module("extra")
with open(os.path.join(out, "cmds.js"), "w") as f:
    f.write("window.CMDS=" + json.dumps(m.CMDS, ensure_ascii=False) + ";\nwindow.HOME_EXTRA=" + json.dumps(m.HOME.strip(), ensure_ascii=False) + ";\n")
print("cmds", sum(len(g["items"]) for g in m.CMDS))
