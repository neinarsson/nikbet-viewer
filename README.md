# nikbet-view

Bevakar [fotbollstips.nikbet.com](https://fotbollstips.nikbet.com) och visar en
**kondenserad topplista för ert eget gäng** – plus en notis när den ändrats så
att du kan dela den till er WhatsApp-grupp med ett tryck.

Eftersom repot är **privat** (där GitHub Pages inte är gratis) hostas sidan på
**Cloudflare**, och **GitHub Actions** sköter notiserna.

## Del 1 – Publicera sidan (Cloudflare Worker)

En [Cloudflare Worker](worker.js) hämtar källan live vid varje besök och
serverar:

| Adress | Innehåll |
| --- | --- |
| `/` | **Kondenserad topplista** för ert gäng + **"Dela till WhatsApp"-knapp** |
| `/full` | Hela originalsidan, men med bara era personer i topplistan |

Sidan är alltid live (inget bygge med intervall) och funkar med privat repo.

### Deploya från mobilen (ett tryck)

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/neinarsson/nikbet-view)

1. Tryck på knappen, logga in på Cloudflare (eller skapa **gratiskonto**).
2. Godkänn kopplingen till GitHub – ge åtkomst till repot `nikbet-view`.
3. Tryck **Deploy**.

Du får en adress som `https://nikbet-view.<ditt-konto>.workers.dev/`. Klart.

### …eller från en dator

```bash
npm i -g wrangler
wrangler login
wrangler deploy
```

## Del 2 – Notiser vid ändring (GitHub Actions)

Workflowet [`notify.yml`](.github/workflows/notify.yml) kollar källan **var 30:e
minut**. **Bara när er topplista faktiskt ändrats** (placering/poäng) skriver
det en kommentar i ett GitHub-issue ("📊 Topplistan – notiser") med den nya
ställningen. Du får då en vanlig GitHub-notis i mobilen → öppna sidan → **Dela**.

Notisen innehåller även ställningen som text, så du kan kopiera rakt in i
WhatsApp om du vill.

> När du har din Cloudflare-adress: fyll i den i `SITE_URL` överst i
> `notify.yml` så länkas sidan direkt i varje notis. (Säg till mig så fixar
> jag det åt dig.)

Körningarna drar GitHub Actions-minuter (~1 400/mån, gratistaket är 2 000).

## Välja vilka som visas

Två ställen (de styr olika delar):

- **Sidan:** listan `NAMES` överst i [`worker.js`](worker.js) – pusha så
  bygger Cloudflare om automatiskt.
- **Notiserna:** [`names.txt`](names.txt) – ett namn per rad, `#` för kommentar.

Håll dem i synk. Matchningen är skiftlägesokänslig men namnet måste annars
stavas exakt som på originalsidan (alla tillgängliga namn finns kommenterade i
`names.txt`). *Bo Einarsson* finns två gånger i källan – båda raderna visas.

### "Dela till WhatsApp"

Knappen skapar en **bild** av topplistan direkt på din telefon och öppnar
delningsmenyn – välj er grupp så postas bilden. Bilden skapas lokalt i mobilen,
så inget bryter mot WhatsApps villkor och inget extra behöver driftas.

## Köra/testa lokalt

```bash
python3 make_leaderboard.py     # skriver out/index.html, state.json, summary.txt
```

Miljövariabler: `SOURCE_URL`, `NAMES_FILE`, `OUTPUT_DIR`, `TITLE`,
`PREV_STATE_FILE` (lokal fil) eller `PREV_STATE_URL` för ändringsdetektering.
Inga beroenden – endast Python 3. Workern är ren JavaScript.

## Hur det fungerar

Både workern och `make_leaderboard.py` plockar ut era personers rad ur
topplistan (placering – inklusive delade placeringar via carry-forward – namn,
poäng, skilje). Workern renderar och serverar sidan live; `make_leaderboard.py`
beräknar en hash av ställningen och jämför mot förra körningens `state.json` för
att avgöra om något ändrats och en notis ska skickas.
