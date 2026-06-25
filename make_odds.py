#!/usr/bin/env python3
"""
Bygger en DELNINGSSIDA med prispengschanser för vårt gäng (names.txt):
sannolikheten att var och en hamnar på topp-5 (prispeng) respektive blir etta i
HELA poolen, beräknat med en Monte Carlo-simulering inför de återstående
gruppspelsmatcherna.

Output: public/odds.html – samma kort-stil och "Dela bild"-knapp som topplistan.

Så funkar modellen (kort):
  • Källan ger varje deltagares faktiska tips (1/X/2) för ALLA matcher, även de
    ospelade, plus nuvarande poäng (1 p/rätt) och deras gissade totala målantal.
  • För varje återstående match har vi avmarginaliserade riktiga bookmaker-odds
    (ODDS nedan) -> sannolikhet för 1/X/2, samt förväntat antal mål (EG).
  • Varje simulering: lotta alla resultat + mål, räkna om alla 119 deltagares
    poäng, rangordna (poäng, därefter mål-skiljet = vems gissade totalmål ligger
    närmast facit), och bokför vem som hamnar topp-5 / etta.
  • Upprepa N gånger -> procentsatserna.

Saknas odds för en match (t.ex. tillagd match) faller vi tillbaka på poolens egen
tipsfördelning. Endast Pythons standardbibliotek.
"""

import os
import re
import math
import random
import html as H
import datetime
import urllib.request
from array import array
from zoneinfo import ZoneInfo

SOURCE_URL = os.environ.get("SOURCE_URL", "https://fotbollstips.nikbet.com")
SOURCE_FILE = os.environ.get("SOURCE_FILE", "").strip()  # lokal testfil (valfri)
NAMES_FILE = os.environ.get("NAMES_FILE", "names.txt")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "public")
TITLE = os.environ.get("ODDS_TITLE", "VM 2026 – prispengschans (vårt gäng)")
SIM_N = int(os.environ.get("SIM_N", "100000"))
TZ = ZoneInfo("Europe/Stockholm")

# Återstående gruppspelsmatcher, nyckel = matchnummer i källan (fast för turneringen).
# (P_hemma, P_oavgjort, P_borta, FörväntadeMål) – avmarginaliserade riktiga odds
# (bet365, FanDuel, DraftKings, ESPN, Oddschecker m.fl., hämtade 24 jun 2026).
# Uppdatera värdena om du vill köra om med färska odds; spelade matcher faller
# automatiskt bort (de räknas som ej längre ospelade i källan).
ODDS = {
    49: (0.40, 0.31, 0.29, 2.8),  # Schweiz–Kanada (spelad)
    50: (0.69, 0.18, 0.13, 2.4),  # Bosnien-Hercegovina–Qatar (spelad)
    51: (0.13, 0.18, 0.69, 2.5),  # Skottland–Brasilien (spelad)
    52: (0.80, 0.14, 0.06, 3.0),  # Marocko–Haiti (spelad)
    53: (0.27, 0.24, 0.49, 2.5),  # Tjeckien–Mexiko (spelad)
    54: (0.18, 0.25, 0.57, 2.5),  # Sydafrika–Sydkorea (spelad)
    55: (0.05, 0.11, 0.84, 2.6),  # Curaçao–Elfenbenskusten
    56: (0.22, 0.20, 0.58, 2.5),  # Ecuador–Tyskland
    57: (0.53, 0.26, 0.21, 2.8),  # Japan–Sverige  (Japan favorit – tvärtemot poolens tips)
    58: (0.04, 0.10, 0.86, 3.3),  # Tunisien–Nederländerna
    59: (0.27, 0.23, 0.50, 2.3),  # Turkiet–USA
    60: (0.34, 0.41, 0.25, 2.1),  # Paraguay–Australien
    61: (0.20, 0.23, 0.57, 2.7),  # Norge–Frankrike
    62: (0.77, 0.16, 0.07, 2.8),  # Senegal–Irak
    63: (0.41, 0.27, 0.32, 2.3),  # Kap Verde–Saudiarabien
    64: (0.14, 0.22, 0.64, 2.7),  # Uruguay–Spanien
    65: (0.39, 0.36, 0.25, 2.3),  # Egypten–Iran
    66: (0.09, 0.13, 0.78, 3.1),  # Nya Zeeland–Belgien
    67: (0.10, 0.17, 0.73, 2.5),  # Panama–England
    68: (0.54, 0.29, 0.17, 2.4),  # Kroatien–Ghana
    69: (0.27, 0.29, 0.44, 2.8),  # Colombia–Portugal
    70: (0.52, 0.25, 0.23, 2.6),  # DR Kongo–Uzbekistan
    71: (0.24, 0.42, 0.34, 2.4),  # Algeriet–Österrike
    72: (0.06, 0.15, 0.79, 2.9),  # Jordanien–Argentina
}
DEFAULT_EG = 2.7


def fetch_source():
    if SOURCE_FILE:
        with open(SOURCE_FILE, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "nikbet-view/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def norm(s):
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def first_name(name):
    return name.split()[0] if name else name


def load_selected(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(norm(line).casefold())
    return set(out)


def parse_matches(html):
    """Andra tabellen: matchnummer, lag, resultat och poolens tipsfördelning."""
    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.DOTALL)
    t = tables[1]
    body = t.split("<tbody>", 1)[1] if "<tbody>" in t else t
    matches = {}
    for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
        c = [norm(strip_tags(x)) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)]
        if len(c) < 11:
            continue
        try:
            mnum = int(c[0].rstrip("."))
        except ValueError:
            continue
        matches[mnum] = {
            "home": c[3], "away": c[5], "res": c[7],
            "c1": int(c[8] or 0), "cx": int(c[9] or 0), "c2": int(c[10] or 0),
        }
    return matches


def parse_players(html):
    """Topplistan: namn, poäng (= antal rätt), gissat totalmål, och tips per match
    (cellens text = tipset; ofärgad cell = ospelad match)."""
    tables = re.findall(r'<table class="table table-borderless table-hover.*?</table>', html, re.DOTALL)
    body = tables[0].split("<tbody>", 1)[1]
    players = []
    actual_so_far = None
    last_pos = ""
    for row in re.findall(r"<tr>.*?</tr>", body, re.DOTALL):
        if 'scope="row"' not in row:
            continue
        cells = re.findall(r"<t[dh][^>]*>.*?</t[dh]>", row, re.DOTALL)
        if len(cells) < 5:
            continue
        pos = norm(strip_tags(cells[0])).rstrip(".")
        if pos and pos != "-":
            last_pos = pos
        else:
            pos = last_pos
        name = norm(strip_tags(cells[2]))
        pts = int(norm(strip_tags(cells[-1])) or 0)
        sk = norm(strip_tags(cells[3]))  # "190 (49 - 141)"
        msk = re.match(r"(\d+)\s*\((-?\d+)\s*-\s*(\d+)\)", sk)
        if not msk:
            continue
        pred_total = int(msk.group(1))
        actual_so_far = int(msk.group(3))
        # Matchceller: text = tipset, ofärgad = ospelad.
        pending = {}  # mnum -> tip   (vi numrerar i ordning; separatorceller hoppas över)
        idx = 0
        for c in cells[4:-1]:
            tt = norm(strip_tags(c))
            if tt == "":
                continue
            idx += 1
            if "#008000" not in c.lower() and "#ff0000" not in c.lower():
                pending[idx] = tt  # ospelad – matchnummer = ordningsnummer
        players.append({"name": name, "pos": pos, "pts": pts,
                        "pred_total": pred_total, "pending": pending})
    return players, (actual_so_far or 0)


def match_prob(mnum, match):
    """Sannolikhet (P1,PX,P2,EG) – riktiga odds om de finns, annars poolens tips."""
    if mnum in ODDS:
        return ODDS[mnum]
    a, b, c = match["c1"] + 3, match["cx"] + 3, match["c2"] + 3  # Laplace
    s = a + b + c
    p1, px, p2 = a / s, b / s, c / s
    if px < 0.12:  # golv för oavgjort (poolen undertippar kryss)
        px = 0.12
        rest = 0.88 / (p1 + p2)
        p1, p2 = p1 * rest, p2 * rest
    return (p1, px, p2, DEFAULT_EG)


def pois(lam, rnd):
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        p *= rnd()
        if p <= L:
            return k
        k += 1


def simulate(players, rem, prob, actual_so_far, nsim):
    N = len(players)
    TIP = {"1": 0, "X": 1, "2": 2}
    tips = [array("b", [TIP.get(p["pending"].get(m, "1"), 0) for m in rem]) for p in players]
    base = array("h", [p["pts"] for p in players])
    pred = array("h", [p["pred_total"] for p in players])
    by = [[[] for _ in range(3)] for _ in rem]
    for pi in range(N):
        for j in range(len(rem)):
            by[j][tips[pi][j]].append(pi)
    cdf = [(prob[m][0], prob[m][0] + prob[m][1]) for m in rem]
    egs = [prob[m][3] for m in rem]
    top5 = array("i", [0] * N)
    wins = array("i", [0] * N)
    rnd = random.random
    nj = len(rem)
    for _ in range(nsim):
        gain = bytearray(N)
        goals = 0
        for j in range(nj):
            r = rnd(); c1, c12 = cdf[j]
            o = 0 if r < c1 else (1 if r < c12 else 2)
            for pi in by[j][o]:
                gain[pi] += 1
            goals += pois(egs[j], rnd)
        final_total = actual_so_far + goals
        keys = [0.0] * N
        best_i = 0; best_k = -1e18
        for pi in range(N):
            err = pred[pi] - final_total
            if err < 0:
                err = -err
            k = (base[pi] + gain[pi]) * 1000.0 - err + rnd() * 1e-3  # jitter -> rättvist lika
            keys[pi] = k
            if k > best_k:
                best_k = k; best_i = pi
        wins[best_i] += 1
        for pi in sorted(range(N), key=lambda q: keys[q], reverse=True)[:5]:
            top5[pi] += 1
    return [100 * top5[i] / nsim for i in range(N)], [100 * wins[i] / nsim for i in range(N)]


def pct(x):
    if x >= 9.5:
        return f"{round(x)}%"
    if x >= 1:
        return f"{x:.0f}%"
    if x >= 0.1:
        return "<1%"
    return "≈0%"


def render(rows, n_rem, nsim):
    updated = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    blocks = []
    for r in rows:
        w = max(0.0, min(100.0, r["top5"]))
        blocks.append(f"""      <div class="person">
        <div class="prow">
          <span class="rank">{H.escape(r['pos'])}.</span>
          <span class="name">{H.escape(first_name(r['name']))}</span>
          <span class="cur">{r['pts']}p</span>
          <span class="big">{pct(r['top5'])}</span>
          <span class="lbl">topp&#8209;5</span>
          <span class="win">etta {pct(r['win'])}</span>
        </div>
        <div class="track"><span class="fill" style="width:{w:.1f}%"></span></div>
      </div>""")
    body = "\n".join(blocks)
    sub = f"Inför sista gruppomgången · {n_rem} matcher kvar · {updated}"
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#33ABF9">
<title>{H.escape(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root {{ --blue:#2b9fe6; --ink:#15212b; --muted:#8a98a5; --line:#eef2f5;
          --fill:#1bb265; --gold:#e8a400; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#e9eef3; color:var(--ink); padding:16px; }}
  .wrap {{ max-width:520px; margin:0 auto; }}
  #card {{ background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 6px 22px rgba(20,40,60,.13); }}
  .head {{ background:linear-gradient(135deg,#3aa9f0,#1577c7); color:#fff; padding:13px 15px; }}
  .head h1 {{ font-size:16px; font-weight:800; margin:0; line-height:1.2; }}
  .head .sub {{ font-size:11px; opacity:.92; margin-top:3px; }}
  .person {{ padding:7px 14px 8px; }}
  .person + .person {{ border-top:1px solid var(--line); }}
  .prow {{ display:flex; align-items:baseline; gap:8px; }}
  .rank {{ width:30px; flex:none; text-align:left; font-weight:800; font-size:13px; color:var(--blue); }}
  .name {{ flex:1; min-width:0; font-weight:700; font-size:14px;
          white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .cur {{ flex:none; font-size:11px; color:var(--muted); }}
  .big {{ flex:none; font-weight:800; font-size:17px; color:var(--fill); margin-left:4px; }}
  .lbl {{ flex:none; font-size:9px; font-weight:700; color:var(--muted); text-transform:uppercase;
         letter-spacing:.3px; }}
  .win {{ flex:none; width:74px; text-align:right; font-size:11px; font-weight:700; color:var(--gold); }}
  .track {{ margin-top:5px; height:7px; border-radius:4px; overflow:hidden; background:#e7ecf1; }}
  .track .fill {{ display:block; height:7px; background:var(--fill); border-radius:4px; }}
  .method {{ padding:10px 14px 12px; border-top:1px solid var(--line); font-size:10px;
            line-height:1.5; color:var(--muted); }}
  .method b {{ color:var(--ink); }}
  .foot {{ padding:7px 14px; font-size:10px; color:var(--muted); border-top:1px solid var(--line); }}
  .actions {{ max-width:520px; margin:14px auto 0; }}
  button {{ width:100%; border:0; border-radius:12px; padding:15px; font-size:16px; font-weight:700;
           color:#fff; background:#25D366; cursor:pointer; }}
  button:active {{ filter:brightness(.95); }}
  .hint {{ text-align:center; font-size:12px; color:var(--muted); margin-top:8px; }}
  .hint a {{ color:var(--blue); font-weight:600; }}
</style>
</head>
<body>
<div class="wrap">
  <div id="card">
    <div class="head">
      <h1>{H.escape(TITLE)}</h1>
      <div class="sub">{H.escape(sub)}</div>
    </div>
{body}
    <div class="method">
      <b>Topp&#8209;5</b> = prispengsplats · <b>etta</b> = vinst, i hela poolen (119 spelare).
      Monte&nbsp;Carlo, {nsim:,} simuleringar med riktiga bookmaker&#8209;odds + förväntade mål.
      Ögonblicksbild, inte facit.
    </div>
    <div class="foot">Källa: fotbollstips.nikbet.com · odds via bookmakers</div>
  </div>
  <div class="actions">
    <button id="share">📲 Dela bilden</button>
    <div class="hint">Skapar en bild – dela eller spara och klistra in i WhatsApp.</div>
    <div class="hint" style="margin-top:10px;"><a href="https://neinarsson.github.io/nikbet-viewer/">← Till topplistan</a></div>
  </div>
</div>
<script>
async function makeBlob() {{
  const node = document.getElementById('card');
  const canvas = await html2canvas(node, {{scale: 2, backgroundColor: null}});
  return await new Promise(r => canvas.toBlob(r, 'image/png'));
}}
document.getElementById('share').addEventListener('click', async () => {{
  try {{
    const blob = await makeBlob();
    const file = new File([blob], 'prispeng.png', {{type: 'image/png'}});
    if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
      await navigator.share({{files: [file]}});
      return;
    }}
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'prispeng.png'; a.click();
    URL.revokeObjectURL(url);
  }} catch (e) {{ /* avbruten delning */ }}
}});
</script>
</body>
</html>
"""


def main():
    selected = load_selected(NAMES_FILE)
    html = fetch_source()
    matches = parse_matches(html)
    players, actual_so_far = parse_players(html)

    # Ospelade matcher = de som någon fortfarande har som "pending" (robust signal).
    rem = sorted({m for p in players for m in p["pending"]})
    prob = {m: match_prob(m, matches.get(m, {"c1": 0, "cx": 0, "c2": 0})) for m in rem}

    if rem:
        top5, win = simulate(players, rem, prob, actual_so_far, SIM_N)
    else:
        top5 = win = [0.0] * len(players)

    rows = []
    for i, p in enumerate(players):
        if p["name"].casefold() in selected:
            rows.append({"name": p["name"], "pos": p["pos"], "pts": p["pts"],
                         "top5": top5[i], "win": win[i]})
    rows.sort(key=lambda r: (-r["top5"], -r["win"], -r["pts"]))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, "odds.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(rows, len(rem), SIM_N))
    print(f"Skrev {out} | spelare {len(players)} | matcher kvar {len(rem)} | sim {SIM_N}")
    for r in rows:
        print(f"  {r['pos']:>4} {first_name(r['name']):<10} top5={r['top5']:5.1f}%  etta={r['win']:5.1f}%")


if __name__ == "__main__":
    main()
