#!/usr/bin/env python3
"""Build the single-file interactive course site from the markdown repo."""
import json, os, re, sys
import markdown

ROOT = "/sessions/wonderful-busy-bohr/mnt/Marketing/marketing-mastery"
BUILD = os.path.join(ROOT, "site-build")
OUT = os.path.join(ROOT, "marketing-course.html")
OUT_LOCAL = os.path.join(ROOT, "marketing-course-local.html")

MD = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

def md2html(text):
    MD.reset()
    html = MD.convert(text)
    # relative .md links cannot work inside the single-file site: keep the text, drop the link
    html = re.sub(r'<a href="(?!http)[^"]*?"[^>]*>(.*?)</a>', r'<em>\1</em>', html, flags=re.S)
    return html

def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

SHORT = {
 "M01": "What marketing actually is", "M02": "Customers, ICP & JTBD",
 "M03": "Positioning & messaging", "M04": "Offer, price, place",
 "M05": "Funnels & unit economics", "M06": "Marketing strategy",
 "M07": "Websites & CRO", "M08": "SEO & AI search",
 "M09": "Content & social", "M10": "Paid search",
 "M11": "Paid social & creative", "M12": "Email & lifecycle",
 "M13": "Analytics & measurement", "M14": "Experimentation",
 "M15": "Budget & incrementality", "M16": "B2B vs B2C",
 "M17": "Retention & growth loops", "M18": "AI-native marketing",
 "M19": "Capstone: GTM plan",
}
PARTS = [
 {"id": "p1", "name": "Foundations", "hours": 8, "dir": "01-foundations",
  "blurb": "The part that does not expire. Channels change every 18 months; this does not."},
 {"id": "p2", "name": "Digital core", "hours": 14, "dir": "02-digital-core",
  "blurb": "The channels. This is where your money and your hours actually go."},
 {"id": "p3", "name": "Expert layer", "hours": 8, "dir": "03-expert-layer",
  "blurb": "What separates a junior who runs campaigns from a senior who allocates budget."},
]

def parse_module(path, part_id, num):
    raw = open(path, encoding="utf-8").read()
    lines = raw.split("\n")
    title_line = lines[0].lstrip("# ").strip()
    mid = title_line.split("—")[0].strip().split()[0]
    title = title_line.split("—", 1)[1].strip() if "—" in title_line else title_line
    mmeta = ""
    for l in lines[1:8]:
        if l.startswith("**Time:**"):
            mmeta = l.replace("**Time:**", "").strip()
            break
    minutes = int(re.search(r"(\d+)", mmeta).group(1)) if mmeta else 60
    body = raw.split("\n## ", 1)
    secs = []
    if len(body) > 1:
        chunks = ("## " + body[1]).split("\n## ")
        for ch in chunks:
            ch = ch.lstrip("# ").rstrip()
            head, _, rest = ch.partition("\n")
            rest = re.sub(r"\n---\s*$", "", rest).strip()
            rest = re.sub(r"\*\*Next:\*\*.*$", "", rest, flags=re.S).strip()
            rest = re.sub(r"^---\s*$", "", rest, flags=re.M).strip()
            if not rest:
                continue
            html = md2html(rest)
            secs.append({"h": head.strip(), "html": html, "text": plain(html)[:2200]})
    return {"id": mid, "num": num, "part": part_id, "title": title,
            "short": SHORT.get(mid, title), "meta": mmeta, "minutes": minutes,
            "sections": secs}

modules, n = [], 0
for p in PARTS:
    d = os.path.join(ROOT, p["dir"])
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md"):
            continue
        n += 1
        modules.append(parse_module(os.path.join(d, f), p["id"], n))

# ---- assessments ----
assess = {}
for f in ["assess-part1.json", "assess-part2.json", "assess-part3.json"]:
    for a in json.load(open(os.path.join(BUILD, f), encoding="utf-8")):
        assess[a["id"]] = a
sugg = {}
for f in ["suggest-part1.json", "suggest-part2.json", "suggest-part3.json", "suggest-part4.json"]:
    sugg.update(json.load(open(os.path.join(BUILD, f), encoding="utf-8")))
for m in modules:
    rows = sugg.get(m["id"], [])
    if len(rows) != len(m["sections"]):
        sys.exit("suggestion count mismatch for %s: %d vs %d sections" % (m["id"], len(rows), len(m["sections"])))
    m["suggest"] = rows

missing = [m["id"] for m in modules if m["id"] not in assess]
if missing:
    sys.exit("Missing assessment for: " + ", ".join(missing))
for m in modules:
    a = assess[m["id"]]
    for q in a["quiz"]:
        assert 0 <= q["answer"] < len(q["options"]), (m["id"], q["q"])
    m["assess"] = {k: a[k] for k in ("predict", "quiz", "cards", "elaborate", "transfer")}

# ---- glossary ----
gloss = []
for line in open(os.path.join(ROOT, "reference/glossary.md"), encoding="utf-8"):
    mt = re.match(r"^\*\*(\\\*)?(.+?)\*\*\s*[—–-]\s*(.+)$", line.strip())
    if mt:
        gloss.append({"term": mt.group(2).replace("\\*", "").strip(),
                      "star": bool(mt.group(1)), "def": mt.group(3).strip()})

# ---- mental models ----
models, models_note = [], ""
mm = open(os.path.join(ROOT, "reference/mental-models.md"), encoding="utf-8").read()
for chunk in mm.split("\n## ")[1:]:
    head, _, rest = chunk.partition("\n")
    rest = re.sub(r"^---\s*$", "", rest, flags=re.M).strip()
    if re.match(r"^\d+\.", head.strip()):
        models.append({"title": re.sub(r"^\d+\.\s*", "", head.strip()), "html": md2html(rest)})
    else:
        models_note += "<h3>" + head.strip() + "</h3>" + md2html(rest)

# ---- templates ----
tpls = []
tdir = os.path.join(ROOT, "templates")
for f in sorted(os.listdir(tdir)):
    if not f.endswith(".md"):
        continue
    raw = open(os.path.join(tdir, f), encoding="utf-8").read()
    title = raw.split("\n")[0].lstrip("# ").strip()
    para = ""
    for l in raw.split("\n")[1:]:
        s = l.strip()
        if s and not s.startswith("#") and not s.startswith("---") and not s.startswith("|"):
            para = re.sub(r"[*_`\[\]]", "", s)
            break
    tpls.append({"slug": f[:-3], "title": title,
                 "blurb": (para[:95] + "…") if len(para) > 95 else para,
                 "html": md2html(raw)})

def page(rel):
    return md2html(open(os.path.join(ROOT, rel), encoding="utf-8").read())

DATA = {
    "parts": [{k: p[k] for k in ("id", "name", "hours", "blurb")} for p in PARTS],
    "modules": modules,
    "library": {
        "glossary": gloss,
        "models": models,
        "models_note": models_note,
        "templates": tpls,
        "resources": page("reference/resources.md"),
        "plan": {"curriculum": page("00-plan/curriculum.md"),
                 "how": page("00-plan/how-to-study.md"),
                 "expert": page("00-plan/path-to-expert.md")},
    },
}

tpl = open(os.path.join(BUILD, "template.html"), encoding="utf-8").read()
blob = json.dumps(DATA, ensure_ascii=False).replace("</", "<\\/")
html = tpl.replace("/*__DATA__*/", blob)
open(OUT, "w", encoding="utf-8").write(html)

# A standalone copy for opening straight from the folder. Same app, wrapped in a real
# document so it renders in standards mode — and only this copy can reach the local bridge.
head_end = html.index("</style>") + len("</style>")
head, rest = html[:head_end], html[head_end:]
local = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
         "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
         + head + "\n</head>\n<body>" + rest + "\n</body>\n</html>\n")
open(OUT_LOCAL, "w", encoding="utf-8").write(local)

print("modules:", len(modules))
print("sections:", sum(len(m["sections"]) for m in modules))
print("quiz items:", sum(len(m["assess"]["quiz"]) for m in modules))
print("cards:", sum(len(m["assess"]["cards"]) for m in modules))
print("glossary:", len(gloss), "models:", len(models), "templates:", len(tpls))
print("size: %.1f KB" % (len(html) / 1024))
print("out:", OUT)
