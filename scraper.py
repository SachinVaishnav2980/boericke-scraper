import requests
import time
import random
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

BASE_URL = "http://homeoint.org/books/boericmm"


def fetch_letter_index(letter: str) -> str:
    """
    Fetch the index page for a given letter.
    e.g. letter='a' -> fetches http://homeoint.org/books/boericmm/a.htm
    Returns raw HTML string.
    """
    url = f"{BASE_URL}/{letter.lower()}.htm"
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def parse_remedy_links(html: str, letter: str) -> list[dict]:
    """
    Parse all remedy links from a letter index page.
    Returns list of dicts with keys: abbreviation, url, letter.
    """
    soup = BeautifulSoup(html, "lxml")
    remedies = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        abbreviation = anchor.get_text().strip().upper()

        # only keep remedy links e.g. a/abies-c.htm
        if not href.startswith(f"{letter.lower()}/"):
            continue

        url = f"{BASE_URL}/{href}"
        remedies.append({
            "abbreviation": abbreviation,
            "url": url,
            "letter": letter.upper()
        })

    return remedies


def scrape_remedy_page(url: str, letter: str, abbreviation: str) -> dict:
    """
    Fetch a remedy page and extract its content into a structured dict.
    Extracts: full_name, common_name, general, sections, relationships.
    """
    time.sleep(random.uniform(0.5, 1.0))

    page = requests.get(url)
    page.encoding = page.apparent_encoding or "iso-8859-1"
    soup = BeautifulSoup(page.text, "lxml")

    # ── Step 1: get the remedy name and common name ──────────────────
    full_name = ""
    common_name = None

    for bold in soup.find_all("b"):
        inside = bold.find("font")
        if not inside:
            continue
        name = inside.get_text().strip()
        # remedy names are ALL CAPS like "ACONITUM NAPELLUS"
        if re.match(r"^[A-Z][A-Z\s\-]+$", name) and len(name) > 3:
            full_name = name
            # common name is on the second line e.g. "Monkshood"
            lines = bold.get_text().strip().splitlines()
            if len(lines) > 1:
                common_name = lines[1].strip() or None
            break

    # ── Step 2: get general description and sections ─────────────────
    general = ""
    sections = {}
    current_section = None
    found_general = False

    # some pages wrap content in nested <dir> tags instead of direct <body>
    # so we grab the innermost <dir> if it exists, otherwise use <body>
    all_dirs = soup.find_all("dir")
    if all_dirs:
        blockquote = all_dirs[-1].find("blockquote")
        has_content = blockquote and any(
            f.get_text().strip().endswith(".--")
            for f in blockquote.find_all("font")
        )
        content = blockquote if has_content else soup.body
    else:
        content = soup.body

    for node in content.children:

        # <p> tag = general description paragraph
        if isinstance(node, Tag) and node.name == "p":
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()

            # skip navigation, header, footer, title paragraphs
            skip = not text or "BOERICKE" in text or "Médi-T" in text
            skip = skip or text in ["Home", "\xa0"]
            skip = skip or (full_name and full_name in text)
            if skip:
                continue

            # first valid paragraph = general description
            if not found_general:
                general = text
                found_general = True

        # <font> tag = either a section heading or inline remedy reference
        elif isinstance(node, Tag) and node.name == "font":
            raw = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            # remove trailing ".--" to get clean name e.g. "Head.--" -> "Head"
            heading = re.sub(r"[\.\-\s]+$", "", raw).strip()

            if raw.endswith(".--") and re.match(r"^[A-Z][A-Za-z\s]{2,20}$", heading):
                # this is a section heading
                current_section = heading
                sections.setdefault(current_section, "")
            else:
                # this is inline text like a remedy reference "Acon"
                if raw and current_section:
                    sections[current_section] = (sections[current_section] + " " + raw).strip()

        # plain text node = the actual section content
        elif isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text and current_section:
                sections[current_section] = (sections[current_section] + " " + text).strip()

    # ── Step 3: pull out relationships as its own field ───────────────
    relationships = sections.pop("Relationships", None) or sections.pop("Relationship", None)

    # extract potencies from dose section
    dose_text = sections.get("Dose", "")
    potencies = extract_potencies(dose_text)

    return {
        "abbreviation": abbreviation,
        "full_name": full_name,
        "common_name": common_name,
        "source_url": url,
        "letter": letter,
        "general": general,
        "sections": sections,
        "relationships": relationships,
        "potencies": potencies
    }

def extract_potencies(dose_text: str) -> list[str]:
    """
    Extract potency values from the Dose section text.
    e.g. "First to third potency" -> ["1x", "3x"]
    """
    if not dose_text:
        return []

    potencies = []

    # words like "first", "third" map to potency numbers
    ordinals = {
        "first": "1", "second": "2", "third": "3",
        "fourth": "4", "fifth": "5", "sixth": "6",
        "twelfth": "12", "thirtieth": "30", "two-hundredth": "200"
    }

    text = dose_text.lower()

    # check if any ordinal word appears in the dose text
    # e.g. "First to third" -> ["1x", "3x"]
    for word, number in ordinals.items():
        if word in text:
            potencies.append(f"{number}x")

    # match potency numbers written directly e.g. "3x", "6c", "30c"
    direct = re.findall(r"\b(\d+[xXcC])\b", dose_text)
    potencies.extend([p.lower() for p in direct])

    # mother tincture is written as Q in homeopathy
    if "tincture" in text or "mother" in text:
        potencies.append("Q")

    # remove duplicates but keep the original order
    seen = set()
    result = []
    for p in potencies:
        if p not in seen:
            seen.add(p)
            result.append(p)

    return result


def save_output(remedies: list[dict], path: str = "boericke_remedies.json") -> None:
    """
    Save the list of remedies to a JSON file.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(remedies, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(remedies)} remedies to {path}")


def main():
    output_file = "boericke_remedies.json"
    remedies = []
    scraped_urls = set()

    # load existing output for resumability
    if Path(output_file).exists():
        with open(output_file, "r", encoding="utf-8") as f:
            remedies = json.load(f)
            scraped_urls = {r["source_url"] for r in remedies}
        print(f"Resuming — {len(remedies)} already scraped")

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        try:
            html = fetch_letter_index(letter)
        except Exception as e:
            print(f"[{letter}] FAILED to fetch index - {e}")
            with open("failed_urls.txt", "a") as f:
                f.write(f"{BASE_URL}/{letter.lower()}.htm\n")
            continue

        links = parse_remedy_links(html, letter)
        print(f"\n[{letter}] Found {len(links)} remedies")

        for idx, link in enumerate(links, 1):
            if link["url"] in scraped_urls:
                continue

            try:
                remedy = scrape_remedy_page(link["url"], letter, link["abbreviation"])
                remedies.append(remedy)
                scraped_urls.add(link["url"])
                print(f"[{letter}] Scraped {idx}/{len(links)} - {remedy['full_name']}")
            except Exception as e:
                print(f"[{letter}] FAILED {link['url']} - {e}")
                with open("failed_urls.txt", "a") as f:
                    f.write(link["url"] + "\n")

        save_output(remedies)


if __name__ == "__main__":
    main()