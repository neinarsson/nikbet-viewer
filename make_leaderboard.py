#!/usr/bin/env python3
"""
Bygger en KONDENSERAD leaderboard för de utvalda personerna (names.txt) och
upptäcker om den ändrats sedan förra körningen.

Output i public/:
  index.html    – mobilanpassad topplista med en "Dela till WhatsApp"-knapp
                  som skapar en bild av tabellen på telefonen och delar den.
  state.json    – { "hash": ..., "updated": ... } för ändringsdetektering.
  summary.txt   – kort textversion av topplistan (används i notisen).

Och i repo-roten:
  changed.txt   – "true" om topplistan ändrats sedan förra publiceringen,
                  annars "false". Workflowet läser denna för att avgöra notis.

Endast Pythons standardbibliotek.
"""

import os
import re
import json
import html as H
import hashlib
import datetime
import urllib.request
from zoneinfo import ZoneInfo

SOURCE_URL = os.environ.get("SOURCE_URL", "https://fotbollstips.nikbet.com")
NAMES_FILE = os.environ.get("NAMES_FILE", "names.txt")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "public")
# Var förra körningens state.json finns (för ändringsdetektering).
# Antingen en lokal fil (committad i repot) eller en publik URL.
PREV_STATE_FILE = os.environ.get("PREV_STATE_FILE", "").strip()
PREV_STATE_URL = os.environ.get("PREV_STATE_URL", "").strip()
TITLE = os.environ.get("TITLE", "Fotbollstips VM 2026 – vårt gäng")
TZ = ZoneInfo("Europe/Stockholm")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "nikbet-view/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def load_selected(path):
    names = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return {norm(n).casefold() for n in names}


def extract(html, selected):
    m = re.search(
        r'<table class="table table-borderless table-hover.*?</table>', html, re.DOTALL
    )
    body = m.group(0).split("<tbody>", 1)[1]
    people = []
    leader_points = None  # totalledarens poäng (första raden i tabellen)
    last_pos = ""  # vid delad placering är cellen tom – ärv senaste numrerade
    for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
        if 'scope="row"' not in row:
            continue
        # Behåll hela cell-taggen (inkl. bgcolor) så vi kan läsa matchfärgerna.
        cells = re.findall(r"<t[dh][^>]*>.*?</t[dh]>", row, re.DOTALL)
        if len(cells) < 4:
            continue
        pos = norm(strip_tags(cells[0])).rstrip(".")
        if pos and pos != "-":
            last_pos = pos
        else:
            pos = last_pos  # delad placering – samma som raden ovan
        if leader_points is None:
            leader_points = norm(strip_tags(cells[-1]))  # första raden = totalledaren
        name = norm(strip_tags(cells[2]))
        if name.casefold() not in selected:
            continue
        points = norm(strip_tags(cells[-1]))
        skilje = norm(strip_tags(cells[3]))
        # Matchcellerna ligger mellan skilje (index 3) och poäng (sista cellen).
        # Grön bakgrund = rätt tippad, röd = fel, ofärgad = ännu ej spelad.
        # Tomma celler är avdelare mellan omgångar – hoppa över dem.
        matches = []
        for c in cells[4:-1]:
            if norm(strip_tags(c)) == "":
                continue
            lc = c.lower()
            if "#008000" in lc:
                matches.append("hit")
            elif "#ff0000" in lc:
                matches.append("miss")
            else:
                matches.append("pending")
        people.append(
            {"pos": pos, "name": name, "points": points, "skilje": skilje, "matches": matches}
        )
    return people, leader_points


def render_html(people, leader_points=None):
    blocks = []
    for p in people:
        boxes = "".join(f'<span class="{m}"></span>' for m in p.get("matches", []))
        blocks.append(
            f"""      <div class="person">
        <div class="prow">
          <span class="pos">{H.escape(p['pos'])}</span>
          <div class="who">
            <span class="name">{H.escape(p['name'])}</span>
            <span class="dif">{H.escape(p['skilje'])}</span>
          </div>
          <span class="pts">{H.escape(p['points'])} p</span>
        </div>
        <div class="grid">{boxes}</div>
      </div>"""
        )
    rows = "\n".join(blocks)
    updated = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    total = max((len(p.get("matches", [])) for p in people), default=0)
    played = max(
        (sum(1 for m in p.get("matches", []) if m != "pending") for p in people),
        default=0,
    )
    # Rad 2 i underrubriken: totalledare + matcher spelade (egen rad = snyggare).
    parts = []
    if leader_points:
        parts.append(f"Totalledaren har {H.escape(leader_points)} p")
    if total:
        parts.append(f"{played} av {total} spelade")
    subline2 = f"<br>{' · '.join(parts)}" if parts else ""
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#33ABF9">
<title>{H.escape(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root {{ --blue:#33ABF9; --hit:#22c55e; --miss:#ef4444; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#eef3f7; color:#1a1a1a; padding:16px; }}
  .wrap {{ max-width:540px; margin:0 auto; }}
  #card {{ background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.12); }}
  .head {{ background:linear-gradient(135deg,#42b4fb,#1e84d8); color:#fff; padding:16px 18px; }}
  .head h1 {{ font-size:18px; margin:0 0 4px; line-height:1.25; }}
  .head .sub {{ font-size:12px; opacity:.9; }}
  .person {{ padding:7px 14px; border-bottom:1px solid #eef2f5; }}
  .person:last-of-type {{ border-bottom:0; }}
  .prow {{ display:flex; align-items:baseline; gap:8px; }}
  .pos {{ width:30px; flex:none; font-weight:700; color:var(--blue); font-size:14px; }}
  .who {{ flex:1; min-width:0; display:flex; align-items:baseline; gap:8px; }}
  .name {{ font-weight:600; font-size:14px; }}
  .dif {{ font-size:10px; color:#8a98a5; }}
  .pts {{ flex:none; font-weight:700; font-size:14px; white-space:nowrap; }}
  .grid {{ margin-top:4px; display:flex; flex-wrap:wrap; gap:1px; }}
  .grid span {{ width:8px; height:8px; flex:none; border-radius:1px; }}
  .grid .hit {{ background:var(--hit); }}
  .grid .miss {{ background:var(--miss); }}
  .grid .pending {{ background:transparent; border:1px solid #d8e2ec; }}
  .foot {{ padding:11px 16px; font-size:11px; color:#8a98a5;
          display:flex; flex-wrap:wrap; align-items:center; gap:10px; }}
  .foot .lg {{ display:inline-flex; align-items:center; gap:4px; }}
  .foot .lg i {{ width:11px; height:11px; flex:none; border-radius:2px; }}
  .foot .lg i.hit {{ background:var(--hit); }}
  .foot .lg i.miss {{ background:var(--miss); }}
  .foot .lg i.pending {{ border:1px solid #d8e2ec; }}
  .foot .src {{ margin-left:auto; }}
  .actions {{ max-width:540px; margin:14px auto 0; }}
  button {{ width:100%; border:0; border-radius:12px; padding:15px; font-size:16px; font-weight:700;
           color:#fff; background:#25D366; cursor:pointer; }}
  button:active {{ filter:brightness(.95); }}
  .hint {{ text-align:center; font-size:12px; color:#8a98a5; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div id="card">
    <div class="head">
      <h1>{H.escape(TITLE)}</h1>
      <div class="sub">Uppdaterad {updated}{subline2}</div>
    </div>
{rows}
    <div class="foot">
      <span class="lg"><i class="hit"></i>rätt</span>
      <span class="lg"><i class="miss"></i>fel</span>
      <span class="lg"><i class="pending"></i>ej spelad</span>
      <span class="src">Källa: fotbollstips.nikbet.com</span>
    </div>
  </div>
  <div class="actions">
    <button id="share">📲 Dela bilden</button>
    <div class="hint">Skapar en bild av topplistan – dela eller spara och klistra in i WhatsApp.</div>
  </div>
</div>
<script>
async function makeBlob() {{
  const node = document.getElementById('card');
  // backgroundColor: null = transparent utanför kortets rundade hörn.
  const canvas = await html2canvas(node, {{scale: 2, backgroundColor: null}});
  return await new Promise(r => canvas.toBlob(r, 'image/png'));
}}
document.getElementById('share').addEventListener('click', async () => {{
  try {{
    const blob = await makeBlob();
    const file = new File([blob], 'topplista.png', {{type: 'image/png'}});
    // Dela ENBART bilden (ingen text/länk) så det blir en sak att klistra in.
    if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
      await navigator.share({{files: [file]}});
      return;
    }}
    // Fallback (t.ex. desktop): ladda ned bilden.
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'topplista.png'; a.click();
    URL.revokeObjectURL(url);
  }} catch (e) {{ /* användaren avbröt delningen */ }}
}});
</script>
</body>
</html>
"""


def make_summary(people):
    lines = [TITLE, ""]
    for p in people:
        lines.append(f"{p['pos']}. {p['name']} — {p['points']} p ({p['skilje']})")
    return "\n".join(lines) + "\n"


def previous_hash():
    # 1) lokal committad fil
    if PREV_STATE_FILE and os.path.exists(PREV_STATE_FILE):
        try:
            with open(PREV_STATE_FILE, encoding="utf-8") as f:
                return json.load(f).get("hash")
        except Exception:
            pass
    # 2) publicerad URL (cache-bustad)
    if PREV_STATE_URL:
        sep = "&" if "?" in PREV_STATE_URL else "?"
        url = f"{PREV_STATE_URL}{sep}t={int(datetime.datetime.now().timestamp())}"
        try:
            return json.loads(fetch(url)).get("hash")
        except Exception:
            pass
    return None


def main():
    selected = load_selected(NAMES_FILE)
    html = fetch(SOURCE_URL)
    people, leader_points = extract(html, selected)

    digest = hashlib.sha256(
        json.dumps([[p["pos"], p["name"], p["points"], p["skilje"]] for p in people],
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    prev = previous_hash()
    changed = prev != digest
    print(f"Personer: {len(people)} | hash {digest[:10]} | förra {str(prev)[:10]} | ändrad: {changed}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(people, leader_points))
    with open(os.path.join(OUTPUT_DIR, "state.json"), "w", encoding="utf-8") as f:
        json.dump({"hash": digest,
                   "updated": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                  f, ensure_ascii=False)
    with open(os.path.join(OUTPUT_DIR, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(make_summary(people))
    with open("changed.txt", "w", encoding="utf-8") as f:
        f.write("true" if changed else "false")


if __name__ == "__main__":
    main()
