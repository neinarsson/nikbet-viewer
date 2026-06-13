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
    medals = ("🥇", "🥈", "🥉")
    blocks = []
    for i, p in enumerate(people):
        boxes = "".join(f'<span class="{m}"></span>' for m in p.get("matches", []))
        medal = f'<span class="medal">{medals[i]}</span>' if i < len(medals) else ""
        cls = "person lead" if i == 0 else "person"
        blocks.append(
            f"""      <div class="{cls}">
        <div class="prow">
          <span class="rank">{H.escape(p['pos'])}</span>
          <span class="name">{medal}{H.escape(p['name'])}</span>
          <span class="dif">{H.escape(p['skilje'])}</span>
          <span class="pts">{H.escape(p['points'])}<i>p</i></span>
        </div>
        <div class="track">{boxes}</div>
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
    seg_w = f"calc(100% / {total})" if total else "0"
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#33ABF9">
<title>{H.escape(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root {{ --blue:#2b9fe6; --hit:#1bb265; --miss:#ec4d4d; --pending:#e7ecf1;
          --ink:#15212b; --muted:#8a98a5; --line:#eef2f5; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#e9eef3; color:var(--ink); padding:16px; }}
  .wrap {{ max-width:520px; margin:0 auto; }}
  #card {{ background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 6px 22px rgba(20,40,60,.13); }}
  .head {{ background:linear-gradient(135deg,#3aa9f0,#1577c7); color:#fff; padding:14px 16px; }}
  .head h1 {{ font-size:17px; font-weight:800; margin:0; line-height:1.2; }}
  .head .sub {{ font-size:11.5px; opacity:.92; margin-top:4px; line-height:1.5; }}
  .person {{ padding:7px 14px 8px; }}
  .person + .person {{ border-top:1px solid var(--line); }}
  .person.lead {{ background:linear-gradient(90deg,rgba(43,159,230,.08),rgba(43,159,230,0)); }}
  .prow {{ display:flex; align-items:baseline; gap:8px; }}
  .rank {{ width:26px; flex:none; text-align:right; font-weight:800; font-size:13px; color:var(--blue); }}
  .name {{ flex:1; min-width:0; font-weight:700; font-size:13.5px;
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .medal {{ margin-right:3px; }}
  .dif {{ flex:none; font-size:10px; color:var(--muted); }}
  .pts {{ flex:none; font-weight:800; font-size:15px; }}
  .pts i {{ font-style:normal; font-size:10px; font-weight:600; color:var(--muted); margin-left:1px; }}
  .track {{ margin-top:5px; height:9px; border-radius:3px; overflow:hidden;
           background:var(--pending); white-space:nowrap; font-size:0; }}
  .track span {{ display:inline-block; vertical-align:top; width:{seg_w}; height:9px; }}
  .track .hit {{ background:var(--hit); }}
  .track .miss {{ background:var(--miss); }}
  .track .pending {{ background:transparent; }}
  .foot {{ padding:9px 14px; font-size:11px; color:var(--muted); border-top:1px solid var(--line);
          display:flex; flex-wrap:wrap; align-items:center; gap:10px; }}
  .foot .lg {{ display:inline-flex; align-items:center; gap:5px; }}
  .foot .lg i {{ width:11px; height:11px; flex:none; border-radius:2px; }}
  .foot .lg i.hit {{ background:var(--hit); }}
  .foot .lg i.miss {{ background:var(--miss); }}
  .foot .lg i.pending {{ background:var(--pending); }}
  .foot .src {{ margin-left:auto; }}
  .actions {{ max-width:520px; margin:14px auto 0; }}
  button {{ width:100%; border:0; border-radius:12px; padding:15px; font-size:16px; font-weight:700;
           color:#fff; background:#25D366; cursor:pointer; }}
  button:active {{ filter:brightness(.95); }}
  .hint {{ text-align:center; font-size:12px; color:var(--muted); margin-top:8px; }}
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
  // backgroundColor: null = transparenta (rundade) hörn, ingen vit bakgrund.
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
