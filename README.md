# nikbet-viewer

Bevakar [fotbollstips.nikbet.com](https://fotbollstips.nikbet.com) och visar en
**kondenserad topplista för vårt eget gäng** – med en matchmatris per person och
en knapp för att dela en bild till WhatsApp – plus en notis när ställningen
ändrats.

**Live:** https://neinarsson.github.io/nikbet-viewer/

## Så funkar det

Källsidan blockerar serverhämtningar från t.ex. Cloudflares IP-adresser, så sidan
kan inte hämtas live i en webbläsare/worker (då blir tabellen tom). Istället
hämtar en **GitHub Actions-runner** (som inte blockeras) källan med jämna
mellanrum, bygger en färdig statisk sida och publicerar den på **GitHub Pages**.

Eftersom ställningen bara ändras när matchresultat kommer in är detta i praktiken
alltid aktuellt.

Allt sköts av workflowet [`.github/workflows/pages.yml`](.github/workflows/pages.yml):

1. **Bygger** sidan med [`make_leaderboard.py`](make_leaderboard.py) (ren Python,
   inga beroenden).
2. **Publicerar** den till GitHub Pages.
3. **Postar en notis** i ett issue (`📊 Topplistan – notiser`) när vårt gängs
   ställning ändrats, med en länk till sidan.

Körs **var 30:e minut**, vid varje push till `main`, och kan startas manuellt
(Actions-fliken → *Publicera topplista* → *Run workflow*).

Ändringsdetektering sker mot förra publicerade `state.json` (via `PREV_STATE_URL`),
så inget behöver committas tillbaka till repot.

## Sidan visar

| Del | Innehåll |
| --- | --- |
| Rubrik | Titel + senaste uppdatering (svensk tid) + totalledarens poäng |
| Per person | Placering, namn, skilje (mål) och poäng |
| Matchmatris | 72 rutor per person – 🟩 grön = rätt, 🟥 röd = fel, ⬜ transparent = ej spelad |
| Dela-knapp | Skapar en **bild** av topplistan på telefonen och delar den (eller laddar ned den på desktop) |

Bilden skapas lokalt i din webbläsare (html2canvas + Web Share), så inget extra
behöver driftas och inget bryter mot WhatsApps villkor.

## Välja vilka som visas

Ändra [`names.txt`](names.txt) – ett namn per rad, `#` för kommentar. Matchningen
är skiftlägesokänslig men namnet måste annars stavas exakt som på
fotbollstips.nikbet.com (alla tillgängliga namn finns kommenterade i filen).
Pusha till `main` så bygger och publicerar workflowet om sidan automatiskt.

> *Bo Einarsson* finns två gånger i källan – båda raderna visas.

## Köra/testa lokalt

```bash
python3 make_leaderboard.py      # skriver public/index.html, state.json, summary.txt
```

Miljövariabler: `SOURCE_URL`, `NAMES_FILE`, `OUTPUT_DIR`, `TITLE`,
`PREV_STATE_FILE` (lokal fil) eller `PREV_STATE_URL` (publik URL) för
ändringsdetektering. Endast Python 3 krävs.

## Engångsinställningar i GitHub

- **Settings → Pages → Source:** `GitHub Actions`.
- **Settings → Actions:** tillåt actions att köra.
