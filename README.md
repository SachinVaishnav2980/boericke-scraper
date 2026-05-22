# Boericke Materia Medica Scraper

Scrapes [Boericke's Homoeopathic Materia Medica](http://homeoint.org/books/boericmm/index.htm) and outputs a structured JSON dataset of all remedies A–Z.

Built for **jarvis.care** — AI-powered clinical assistant for homeopathic practitioners.

## Setup

1. Clone the repo
```bash
   git clone https://github.com/YOUR_USERNAME/boericke-scraper.git
   cd boericke-scraper
```

2. Create virtual environment
```bash
   python -m venv venv
   venv\Scripts\activate
```

3. Install dependencies
```bash
   pip install -r requirements.txt
```

## Run

```bash
python scraper.py
```

Progress is printed as it runs:

[A] Found 202 remedies
[A] Scraped 1/202 - ABIES CANADENSIS-PINUS CANADENSIS
[A] Scraped 2/202 - ABIES NIGRA
...


## Resumable

If the script is interrupted, just run it again. It automatically skips already scraped URLs and continues from where it left off.

## Output Files

| File | Description |
|------|-------------|
| `boericke_remedies.json` | Full dataset — all A–Z remedies |
| `sample_output.json` | 5 remedy sample for review |
| `failed_urls.txt` | Any URLs that failed during scraping |

## Schema

```json
{
  "abbreviation": "ACON",
  "full_name": "ACONITUM NAPELLUS",
  "common_name": "Monkshood",
  "source_url": "http://homeoint.org/books/boericmm/a/acon.htm",
  "letter": "A",
  "general": "A state of fear, anxiety...",
  "sections": {
    "Mind": "...",
    "Head": "...",
    "Dose": "First to third potency."
  },
  "relationships": "Compare: Coff, Cham, Bell."
}
```

## Functions

| Function | Description |
|----------|-------------|
| `fetch_letter_index(letter)` | Fetches the index page for a given letter |
| `parse_remedy_links(html, letter)` | Extracts all remedy links from the index page |
| `scrape_remedy_page(url, letter, abbreviation)` | Scrapes a single remedy page |
| `save_output(remedies)` | Saves the remedy list to JSON |