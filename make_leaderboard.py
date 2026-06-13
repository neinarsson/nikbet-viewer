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

SOURCE_URL = os.environ.get("SOURCE_URL", "https://fotbollstips.nikbet.com")
NAMES_FILE = os.environ.get("NAMES_FILE", "names.txt")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "public")
# Var förra körningens state.json finns (för ändringsdetektering).
# Antingen en lokal fil (committad i repot) eller en publik URL.
PREV_STATE_FILE = os.environ.get("PREV_STATE_FILE", "").strip()
PREV_STATE_URL = os.environ.get("PREV_STATE_URL", "").strip()
TITLE = os.environ.get("TITLE", "Appels Fotbollstips VM 2026 – vårt gäng")


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
    last_pos = ""  # vid delad placering är cellen tom – ärv senaste numrerade
    for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
        if 'scope="row"' not in row:
            continue
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        if len(cells) < 4:
            continue
        pos = norm(strip_tags(cells[0])).rstrip(".")
        if pos and pos != "-":
            last_pos = pos
        else:
            pos = last_pos  # delad placering – samma som raden ovan
        name = norm(strip_tags(cells[2]))
        if name.casefold() not in selected:
            continue
        points = norm(strip_tags(cells[-1]))
        skilje = norm(strip_tags(cells[3]))
        people.append({"pos": pos, "name": name, "points": points, "skilje": skilje})
    return people


def render_html(people):
    rows = "\n".join(
        f"""      <tr>
        <td class="pos">{H.escape(p['pos'])}</td>
        <td class="name">{H.escape(p['name'])}</td>
        <td class="pts">{H.escape(p['points'])}</td>
        <td class="dif">{H.escape(p['skilje'])}</td>
      </tr>"""
        for p in people
    )
    updated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    share_text = "Vår topplista – Appels Fotbollstips VM 2026"
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#33ABF9">
<title>{H.escape(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root {{ --blue:#33ABF9; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#eef3f7; color:#1a1a1a; padding:16px; }}
  .wrap {{ max-width:540px; margin:0 auto; }}
  #card {{ background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.12); }}
  .head {{ background:var(--blue); color:#fff; padding:16px 18px; }}
  .head h1 {{ font-size:18px; margin:0 0 4px; line-height:1.25; }}
  .head .sub {{ font-size:12px; opacity:.9; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ padding:10px 12px; text-align:left; font-size:15px; }}
  thead th {{ font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#667;
             background:#f5f8fb; border-bottom:1px solid #e3eaf0; }}
  tbody tr:nth-child(even) {{ background:#f8fbfd; }}
  tbody tr {{ border-bottom:1px solid #eef2f5; }}
  td.pos {{ width:42px; font-weight:700; color:var(--blue); }}
  td.name {{ font-weight:600; }}
  td.pts {{ width:54px; text-align:right; font-weight:700; }}
  td.dif {{ width:120px; text-align:right; font-size:12px; color:#778; white-space:nowrap; }}
  th.pts {{ text-align:right; }}
  th.dif {{ text-align:right; }}
  .foot {{ padding:10px 14px; font-size:11px; color:#8a98a5; }}
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
      <div class="sub">Topplista – uppdaterad {updated}</div>
    </div>
    <table>
      <thead>
        <tr><th>P.</th><th>Namn</th><th class="pts">Poäng</th><th class="dif">Skilje (mål)</th></tr>
      </thead>
      <tbody>
{rows}
      </tbody>
    </table>
    <div class="foot">Källa: fotbollstips.nikbet.com</div>
  </div>
  <div class="actions">
    <button id="share">📲 Dela till WhatsApp</button>
    <div class="hint">Skapar en bild och öppnar delningsmenyn – välj er grupp.</div>
  </div>
</div>
<script>
const SHARE_TEXT = {json.dumps(share_text)};
async function makeBlob() {{
  const node = document.getElementById('card');
  const canvas = await html2canvas(node, {{scale: 2, backgroundColor: '#ffffff'}});
  return await new Promise(r => canvas.toBlob(r, 'image/png'));
}}
document.getElementById('share').addEventListener('click', async () => {{
  try {{
    const blob = await makeBlob();
    const file = new File([blob], 'leaderboard.png', {{type: 'image/png'}});
    if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
      await navigator.share({{files: [file], text: SHARE_TEXT}});
      return;
    }}
    // Fallback (desktop): ladda ned bilden och öppna WhatsApp.
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'leaderboard.png'; a.click();
    window.open('https://wa.me/?text=' + encodeURIComponent(SHARE_TEXT + ' ' + location.href), '_blank');
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
    people = extract(html, selected)

    digest = hashlib.sha256(
        json.dumps([[p["pos"], p["name"], p["points"], p["skilje"]] for p in people],
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    prev = previous_hash()
    changed = prev != digest
    print(f"Personer: {len(people)} | hash {digest[:10]} | förra {str(prev)[:10]} | ändrad: {changed}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(people))
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
