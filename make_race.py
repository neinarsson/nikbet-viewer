#!/usr/bin/env python3
"""
Bygger ett LIGGANDE "race"-diagram (bump chart) över hur alla 119 spelare rört sig
i totalplaceringen över tid. Vårt gäng (names.txt) får färgade linjer som slutar i
en cirkel med initialer; övriga spelare får tunna grå linjer.

Helt fristående leverans: skriver ENDAST public/race.html och rör inget annat
(topplista, dela-bild, notiser påverkas inte). Endast Pythons standardbibliotek.

Rekonstruktion: poäng = antal rätt (gröna boxar) i källans topplista, 1 p/rätt.
Kumulativa poäng efter varje spelad match → ranking → placering över tid. Vid lika
poäng rangordnas spelare efter nuvarande tabellplacering (approximation av det
officiella skiljet, som inte går att rekonstruera exakt per match).
"""

import os
import re
import html as H
import datetime
import urllib.request
from zoneinfo import ZoneInfo

SOURCE_URL = os.environ.get("SOURCE_URL", "https://fotbollstips.nikbet.com")
NAMES_FILE = os.environ.get("NAMES_FILE", "names.txt")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "public")
TITLE = os.environ.get("RACE_TITLE", "Fotbollstips VM 2026 – placering över tid")
TZ = ZoneInfo("Europe/Stockholm")

# Kategoriska färger för vårt gäng – tydligt skilda från grått och mörka nog för
# vit text i slutcirkeln. (Identitet, inte utfall – inte topplistans grön/röd.)
PALETTE = [
    "#E6194B",  # crimson
    "#4363D8",  # blå
    "#3CB44B",  # grön
    "#F58231",  # orange
    "#911EB4",  # lila
    "#469990",  # teal
    "#F032E6",  # magenta
    "#9A6324",  # brun
    "#2F4858",  # mörk slate
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "nikbet-view/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def norm(s):
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def first_name(name):
    return name.split()[0] if name else name


def load_selected(path):
    names = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return {norm(n).casefold() for n in names}


def parse_all_players(html):
    """Alla 119 spelare ur topplistan (tabell 0), i nuvarande tabellordning.
    Återanvänder samma cell-/färglogik som make_leaderboard.extract()."""
    m = re.search(
        r'<table class="table table-borderless table-hover.*?</table>', html, re.DOTALL
    )
    body = m.group(0).split("<tbody>", 1)[1]
    players = []
    order = 0
    for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
        if 'scope="row"' not in row:
            continue
        cells = re.findall(r"<t[dh][^>]*>.*?</t[dh]>", row, re.DOTALL)  # hela cell-taggar
        if len(cells) < 4:
            continue
        name = norm(strip_tags(cells[2]))
        points = norm(strip_tags(cells[-1]))
        matches = []
        for c in cells[4:-1]:
            if norm(strip_tags(c)) == "":
                continue  # avdelarcell mellan omgångar
            lc = c.lower()
            if "#008000" in lc:
                matches.append("hit")
            elif "#ff0000" in lc:
                matches.append("miss")
            else:
                matches.append("pending")
        players.append(
            {"order": order, "name": name, "points_str": points, "matches": matches}
        )
        order += 1
    return players


def played_count(players):
    best = 0
    for p in players:
        n = 0
        for x in p["matches"]:
            if x == "pending":
                break
            n += 1
        best = max(best, n)
    return best


def compute_cumulative(players, M):
    for p in players:
        c = 0
        cum = []
        for i in range(M):
            if i < len(p["matches"]) and p["matches"][i] == "hit":
                c += 1
            cum.append(c)
        p["cum"] = cum


def compute_placements(players, M):
    for p in players:
        p["rank"] = [0] * M
    for mi in range(M):
        ordered = sorted(players, key=lambda p: (-p["cum"][mi], p["order"]))
        for rank, p in enumerate(ordered, start=1):
            p["rank"][mi] = rank


def parse_dates(html):
    """'Dat'-kolumnen ur matchtabellen via header-namn (robust mot omordning)."""
    for t in re.findall(r"<table[^>]*>.*?</table>", html, re.DOTALL):
        head = t[: t.find("<tbody>")] if "<tbody>" in t else t
        headers = [norm(strip_tags(h)) for h in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", head, re.DOTALL)]
        if "Dat" not in headers:
            continue
        idx = headers.index("Dat")
        body = t.split("<tbody>", 1)[1] if "<tbody>" in t else t
        out = []
        for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
            if len(cells) <= idx:
                continue
            out.append(norm(strip_tags(cells[idx])))
        return out
    return []


def assign_labels_and_colors(sel):
    sel.sort(key=lambda p: p["order"])
    seen = {}
    for i, p in enumerate(sel):
        p["color"] = PALETTE[i % len(PALETTE)]
        ini = "".join(w[0] for w in p["name"].split()[:2]).upper() or "?"
        n = seen.get(ini, 0) + 1
        seen[ini] = n
        p["label"] = ini if n == 1 else f"{ini}{n}"


def esc(s):
    return H.escape(s, quote=True)


def text_color(hexc):
    """Svart eller vit text beroende på färgens upplevda ljushet (YIQ)."""
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#15212b" if (r * 299 + g * 587 + b * 114) / 1000 > 150 else "#ffffff"


# --- SVG-layout ---
VIEW_W, VIEW_H = 1200, 675
ML, MR, MT, MB = 56, 150, 78, 52
X0, X1 = ML, VIEW_W - MR
Y0, Y1 = MT, VIEW_H - MB
N_TOTAL = 119
FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif'


def render_race_html(players, sel, M, dates):
    N = max((len(players)), 1)

    def X(m):  # m = 1..M
        return X0 if M <= 1 else X0 + (X1 - X0) * (m - 1) / (M - 1)

    def Y(r):  # r = 1..N (1 överst)
        return Y0 if N <= 1 else Y0 + (Y1 - Y0) * (r - 1) / (N - 1)

    def pts_str(p):
        return " ".join(f"{X(i + 1):.1f},{Y(p['rank'][i]):.1f}" for i in range(M))

    parts = []

    # bakgrundsplatta för plotten
    parts.append(f'<rect x="{X0}" y="{Y0}" width="{X1-X0}" height="{Y1-Y0}" fill="#fbfcfd"/>')

    # Y-gridlinjer + etiketter
    for r in [1, 25, 50, 75, 100, N_TOTAL]:
        if r > N:
            continue
        y = Y(r)
        parts.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="#eef2f5"/>')
        parts.append(
            f'<text x="{X0-8}" y="{y+3:.1f}" text-anchor="end" font-family=\'{FONT}\' '
            f'font-size="11" fill="#8a98a5">{r}</text>'
        )
    # X-ticks (var 5:e + alltid M)
    xticks = sorted(set(list(range(1, M + 1, 5)) + [M])) if M >= 1 else []
    for m in xticks:
        x = X(m)
        parts.append(f'<line x1="{x:.1f}" y1="{Y0}" x2="{x:.1f}" y2="{Y1}" stroke="#f3f6f8"/>')
        lbl = str(m)
        parts.append(
            f'<text x="{x:.1f}" y="{Y1+16:.1f}" text-anchor="middle" font-family=\'{FONT}\' '
            f'font-size="10" fill="#8a98a5">{lbl}</text>'
        )
        if len(dates) >= m and dates[m - 1]:
            d = esc(" ".join(dates[m - 1].split()[:2]))
            parts.append(
                f'<text x="{x:.1f}" y="{Y1+28:.1f}" text-anchor="middle" font-family=\'{FONT}\' '
                f'font-size="9" fill="#aab4be">{d}</text>'
            )
    # axelrubriker
    parts.append(
        f'<text x="{X0-44}" y="{(Y0+Y1)/2:.1f}" transform="rotate(-90 {X0-44} {(Y0+Y1)/2:.1f})" '
        f'text-anchor="middle" font-family=\'{FONT}\' font-size="11" fill="#8a98a5">Placering</text>'
    )
    parts.append(
        f'<text x="{(X0+X1)/2:.1f}" y="{Y1+42:.1f}" text-anchor="middle" font-family=\'{FONT}\' '
        f'font-size="11" fill="#8a98a5">Match</text>'
    )

    sel_ids = {id(p) for p in sel}

    # 1) grå linjer (övriga)
    for p in players:
        if id(p) in sel_ids:
            continue
        parts.append(
            f'<polyline fill="none" stroke="#c7d0d8" stroke-width="1" stroke-opacity="0.45" '
            f'stroke-linejoin="round" points="{pts_str(p)}"/>'
        )
    # 2) halo bakom våra
    for p in sel:
        parts.append(
            f'<polyline fill="none" stroke="#ffffff" stroke-width="5" stroke-opacity="0.9" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{pts_str(p)}"/>'
        )
    # 3) färgade linjer
    for p in sel:
        parts.append(
            f'<polyline fill="none" stroke="{p["color"]}" stroke-width="2.6" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{pts_str(p)}"/>'
        )

    # 4) slutetiketter med kollisionshantering (etiketter i högermarginalen)
    R = 11
    GAP = 2 * R + 3
    cx = X1 + 26
    for p in sel:
        p["_end"] = (X(M), Y(p["rank"][M - 1]))
        p["_cy"] = Y(p["rank"][M - 1])
    labels = sorted(sel, key=lambda p: p["_cy"])
    prev = -1e9
    for p in labels:
        cyv = max(p["_cy"], prev + GAP)
        p["_ly"] = cyv
        prev = cyv
    prev = 1e9
    for p in reversed(labels):
        cyv = min(p["_ly"], prev - GAP)
        cyv = max(cyv, Y0 + R)
        p["_ly"] = cyv
        prev = cyv
    for p in sel:
        ex, ey = p["_end"]
        ly = p["_ly"]
        # liten datapunkt på linjen
        parts.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="{p["color"]}"/>')
        # connector
        parts.append(
            f'<path d="M{ex:.1f},{ey:.1f} L{cx-R:.1f},{ly:.1f}" fill="none" '
            f'stroke="{p["color"]}" stroke-width="1" stroke-opacity="0.6"/>'
        )
        # etikettcirkel + initialer
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{ly:.1f}" r="{R}" fill="{p["color"]}" '
            f'stroke="#fff" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="central" '
            f'font-family=\'{FONT}\' font-size="10" font-weight="700" '
            f'fill="{text_color(p["color"])}">{esc(p["label"])}</text>'
        )

    svg = (
        f'<svg viewBox="0 0 {VIEW_W} {VIEW_H}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="Placering över tid">' + "".join(parts) + "</svg>"
    )

    # legend
    chips = []
    for p in sel:
        chips.append(
            f'<span class="chip"><i style="background:{p["color"]}"></i>'
            f'{esc(first_name(p["name"]))} <b>{p["rank"][M-1]}:a</b></span>'
        )
    legend = "".join(chips)

    updated = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#2b9fe6">
<title>{esc(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root {{ --blue:#2b9fe6; --ink:#15212b; --muted:#8a98a5; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:{FONT}; margin:0; background:#e9eef3; color:var(--ink); padding:16px; }}
  .wrap {{ max-width:min(96vw,1100px); margin:0 auto; }}
  #card {{ background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 6px 22px rgba(20,40,60,.13); }}
  .head {{ background:linear-gradient(135deg,#3aa9f0,#1577c7); color:#fff; padding:14px 18px; }}
  .head h1 {{ font-size:18px; font-weight:800; margin:0; line-height:1.2; }}
  .head .sub {{ font-size:12px; opacity:.92; margin-top:4px; }}
  .chart {{ padding:10px 12px 4px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:8px 14px; padding:6px 16px 12px; }}
  .chip {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:var(--ink); }}
  .chip i {{ width:12px; height:12px; border-radius:3px; display:inline-block; flex:none; }}
  .chip b {{ color:var(--muted); font-weight:600; }}
  .foot {{ padding:8px 16px 14px; font-size:11px; color:var(--muted); line-height:1.5; }}
  .foot a {{ color:var(--blue); }}
  .actions {{ max-width:min(96vw,1100px); margin:14px auto 0; }}
  .actions button {{ width:100%; border:0; border-radius:12px; padding:15px; font-size:16px;
           font-weight:700; color:#fff; background:#25D366; cursor:pointer; }}
  .actions button:active {{ filter:brightness(.95); }}
  .actions .hint {{ text-align:center; font-size:12px; color:var(--muted); margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <div id="card">
    <div class="head">
      <h1>{esc(TITLE)}</h1>
      <div class="sub">{M}/72 matcher spelade · Uppd. {updated}</div>
    </div>
    <div class="chart">{svg}</div>
    <div class="legend">{legend}</div>
    <div class="foot">
      Tunna grå linjer = övriga {N_TOTAL - len(sel)} spelare. Placering 1 överst.
      Vid lika poäng rangordnas spelare efter nuvarande tabellplacering (en approximation
      av det officiella skiljet). · <a href="index.html">← Till topplistan</a>
    </div>
  </div>
  <div class="actions">
    <button id="share">📲 Dela bilden</button>
    <div class="hint">Liggande bild – inte WhatsApp-optimerad, men fullt delbar.</div>
  </div>
</div>
<script>
async function makeBlob() {{
  const node = document.getElementById('card');
  const canvas = await html2canvas(node, {{scale: 2, backgroundColor: '#ffffff'}});
  return await new Promise(r => canvas.toBlob(r, 'image/png'));
}}
document.getElementById('share').addEventListener('click', async () => {{
  try {{
    const blob = await makeBlob();
    const file = new File([blob], 'race.png', {{type: 'image/png'}});
    if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
      await navigator.share({{files: [file]}});
      return;
    }}
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'race.png'; a.click();
    URL.revokeObjectURL(url);
  }} catch (e) {{ /* användaren avbröt delningen */ }}
}});
</script>
</body>
</html>
"""


def main():
    selected = load_selected(NAMES_FILE)
    html = fetch(SOURCE_URL)
    players = parse_all_players(html)
    M = played_count(players)
    if M < 1:
        out = "<!doctype html><meta charset=utf-8><p>Inga matcher spelade ännu.</p>"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, "race.html"), "w", encoding="utf-8") as f:
            f.write(out)
        print("race: inga matcher spelade – skrev platshållare")
        return
    compute_cumulative(players, M)
    compute_placements(players, M)
    sel = [p for p in players if p["name"].casefold() in selected]
    assign_labels_and_colors(sel)

    # sanity: kumulativ slutpoäng ska matcha källans poäng
    bad = [p["name"] for p in players if p["points_str"].isdigit() and p["cum"][M - 1] != int(p["points_str"])]
    if bad:
        print(f"VARNING: {len(bad)} spelare där kumulativ poäng != källans poäng (t.ex. {bad[:3]})")

    dates = []
    try:
        dates = parse_dates(html)
    except Exception:
        dates = []

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "race.html"), "w", encoding="utf-8") as f:
        f.write(render_race_html(players, sel, M, dates))
    print(f"race: {len(players)} spelare, M={M}, {len(sel)} valda -> {OUTPUT_DIR}/race.html")


if __name__ == "__main__":
    main()
