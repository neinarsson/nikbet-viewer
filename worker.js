/**
 * Cloudflare Worker – live "titthål" mot fotbollstips.nikbet.com.
 *
 * Rutter:
 *   /        Kondenserad topplista för ert gäng + "Dela till WhatsApp"-knapp.
 *   /full    Hela originalsidan, men med bara era personer i topplistan.
 *
 * Vid varje besök hämtas källsidan i realtid – sidan visar alltid exakt det
 * källan visar just nu. Funkar med privat GitHub-repo (deployas direkt med
 * wrangler, ingen repo-koppling krävs).
 *
 * Deploy (engångs, kräver gratis Cloudflare-konto):
 *   npm i -g wrangler && wrangler login && wrangler deploy
 *   -> du får en adress på *.workers.dev
 *
 * Ändra vilka som visas i listan NAMES nedan.
 */

const SOURCE_URL = "https://fotbollstips.nikbet.com";
const TITLE = "Appels Fotbollstips VM 2026 – vårt gäng";

const NAMES = [
  "Ellen Einarsson",
  "Anton Einarsson",
  "Niklas Einarsson",
  "Johanna Einarsson",
  "Bo Einarsson",
  "Emil Fransson",
  "Sven Möller",
];

const norm = (s) => s.replace(/\s+/g, " ").trim();
const SELECTED = new Set(NAMES.map((n) => norm(n).toLowerCase()));
const stripTags = (s) => s.replace(/<[^>]+>/g, "");
const esc = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function firstTable(html) {
  const m = html.match(
    /<table class="table table-borderless table-hover[\s\S]*?<\/table>/
  );
  return m ? m[0] : null;
}

/** Plocka ut placering (m. carry-forward vid delad plats), namn, poäng, skilje. */
function extractPeople(html) {
  const table = firstTable(html);
  if (!table) return [];
  const body = table.slice(table.indexOf("<tbody>") + "<tbody>".length);
  const people = [];
  let lastPos = "";
  for (const rm of body.matchAll(/<tr>[\s\S]*?<\/tr>/g)) {
    const row = rm[0];
    if (!row.includes('scope="row"')) continue;
    const cells = [...row.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((c) => c[1]);
    if (cells.length < 4) continue;
    let pos = norm(stripTags(cells[0])).replace(/\.$/, "");
    if (pos && pos !== "-") lastPos = pos;
    else pos = lastPos; // delad placering – samma som raden ovan
    const name = norm(stripTags(cells[2]));
    if (!SELECTED.has(name.toLowerCase())) continue;
    const points = norm(stripTags(cells[cells.length - 1]));
    const skilje = norm(stripTags(cells[3]));
    people.push({ pos, name, points, skilje });
  }
  return people;
}

function renderCondensed(people) {
  const rows = people
    .map(
      (p) => `      <tr>
        <td class="pos">${esc(p.pos)}</td>
        <td class="name">${esc(p.name)}</td>
        <td class="pts">${esc(p.points)}</td>
        <td class="dif">${esc(p.skilje)}</td>
      </tr>`
    )
    .join("\n");
  const updated = new Date().toISOString().slice(0, 16).replace("T", " ") + " UTC";
  const shareText = "Vår topplista – Appels Fotbollstips VM 2026";
  return `<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#33ABF9">
<title>${esc(TITLE)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
  :root { --blue:#33ABF9; }
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#eef3f7; color:#1a1a1a; padding:16px; }
  .wrap { max-width:540px; margin:0 auto; }
  #card { background:#fff; border-radius:14px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.12); }
  .head { background:var(--blue); color:#fff; padding:16px 18px; }
  .head h1 { font-size:18px; margin:0 0 4px; line-height:1.25; }
  .head .sub { font-size:12px; opacity:.9; }
  table { width:100%; border-collapse:collapse; }
  th,td { padding:10px 12px; text-align:left; font-size:15px; }
  thead th { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#667;
             background:#f5f8fb; border-bottom:1px solid #e3eaf0; }
  tbody tr:nth-child(even) { background:#f8fbfd; }
  tbody tr { border-bottom:1px solid #eef2f5; }
  td.pos { width:42px; font-weight:700; color:var(--blue); }
  td.name { font-weight:600; }
  td.pts { width:54px; text-align:right; font-weight:700; }
  td.dif { width:120px; text-align:right; font-size:12px; color:#778; white-space:nowrap; }
  th.pts, th.dif { text-align:right; }
  .foot { padding:10px 14px; font-size:11px; color:#8a98a5; }
  .actions { max-width:540px; margin:14px auto 0; }
  button { width:100%; border:0; border-radius:12px; padding:15px; font-size:16px; font-weight:700;
           color:#fff; background:#25D366; cursor:pointer; }
  button:active { filter:brightness(.95); }
  .hint { text-align:center; font-size:12px; color:#8a98a5; margin-top:8px; }
</style>
</head>
<body>
<div class="wrap">
  <div id="card">
    <div class="head">
      <h1>${esc(TITLE)}</h1>
      <div class="sub">Topplista – uppdaterad ${updated}</div>
    </div>
    <table>
      <thead>
        <tr><th>P.</th><th>Namn</th><th class="pts">Poäng</th><th class="dif">Skilje (mål)</th></tr>
      </thead>
      <tbody>
${rows}
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
const SHARE_TEXT = ${JSON.stringify(shareText)};
async function makeBlob() {
  const node = document.getElementById('card');
  const canvas = await html2canvas(node, {scale: 2, backgroundColor: '#ffffff'});
  return await new Promise(r => canvas.toBlob(r, 'image/png'));
}
document.getElementById('share').addEventListener('click', async () => {
  try {
    const blob = await makeBlob();
    const file = new File([blob], 'leaderboard.png', {type: 'image/png'});
    if (navigator.canShare && navigator.canShare({files: [file]})) {
      await navigator.share({files: [file], text: SHARE_TEXT});
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'leaderboard.png'; a.click();
    window.open('https://wa.me/?text=' + encodeURIComponent(SHARE_TEXT + ' ' + location.href), '_blank');
  } catch (e) { /* användaren avbröt delningen */ }
});
</script>
</body>
</html>`;
}

function renderFull(html) {
  const table = firstTable(html);
  if (table) {
    const idx = table.indexOf("<tbody>");
    const head = table.slice(0, idx);
    const body = table.slice(idx + "<tbody>".length);
    const newBody = body.replace(/<tr>[\s\S]*?<\/tr>/g, (row) => {
      if (!row.includes('scope="row"')) return row;
      const cells = [...row.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)];
      if (cells.length < 3) return row;
      const name = norm(stripTags(cells[2][1])).toLowerCase();
      return SELECTED.has(name) ? row : "";
    });
    // Skarva med index/slice – inte String.replace, vars $-sekvenser i
    // ersättningssträngen annars korrumperar resultatet.
    const start = html.indexOf(table);
    html = html.slice(0, start) + head + "<tbody>" + newBody + html.slice(start + table.length);
  }
  if (!/<base\s/i.test(html)) {
    const hm = html.match(/<head[^>]*>/i);
    if (hm) {
      const at = hm.index + hm[0].length;
      html = html.slice(0, at) + `\n<base href="${SOURCE_URL}/">` + html.slice(at);
    }
  }
  return html;
}

export default {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    const upstream = await fetch(SOURCE_URL, {
      headers: { "User-Agent": "Mozilla/5.0 (nikbet-view worker)" },
      cf: { cacheTtl: 60, cacheEverything: true },
    });
    const src = await upstream.text();

    const body = path === "/full" ? renderFull(src) : renderCondensed(extractPeople(src));
    return new Response(body, {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "public, max-age=60",
      },
    });
  },
};
