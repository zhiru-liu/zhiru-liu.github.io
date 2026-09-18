#!/usr/bin/env python3
"""Regenerate the publication list from papers.bib and stamp the footer dates.

    python3 build.py

Rewrites only the block between the PUBS:START / PUBS:END markers in
publications/index.html, plus the copyright year (YEAR:START / YEAR:END) and
"last updated" date (UPDATED:START / UPDATED:END) in every .html file that has
them. It also fills in the href and hover title of every <a data-bib="KEY">
link (e.g. citations on the about page) from the bib entry with that key, so a
preprint that gets published only needs its bib entry updated. Everything else
is left for hand editing. Run it before each commit so the footer date is
current. Uses the standard library only.

Bib fields used: title, author, journal | booktitle, year, month, doi, url,
pdf, code, supp, preview (an image file name inside img/pubs/). Everything
else is ignored.
"""
import datetime
import html
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIB = ROOT / "papers.bib"
PAGE = ROOT / "publications" / "index.html"
IMG_DIR = ROOT / "img" / "pubs"
IMG_URL = "../img/pubs/"            # relative to publications/index.html

ME = "Zhiru Liu"                     # highlighted in author lists
MAX_AUTHORS = 8                      # longer author lists are abbreviated
PREPRINT_SERVERS = {"biorxiv", "arxiv", "medrxiv"}
MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}


# ---------------------------------------------------------------- bibtex --

def read_braced(s, i):
    """s[i] must be '{'. Return (inner text, index just past the closing brace)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError("unbalanced braces in papers.bib")


def parse_fields(s):
    fields = {}
    i, n = 0, len(s)
    while i < n:
        while i < n and (s[i].isspace() or s[i] == ","):
            i += 1
        if i >= n:
            break
        eq = s.find("=", i)
        if eq < 0:
            break
        name = s[i:eq].strip().lower()
        i = eq + 1
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] == "{":
            value, i = read_braced(s, i)
        elif s[i] == '"':
            j = s.find('"', i + 1)
            j = n if j < 0 else j
            value, i = s[i + 1:j], j + 1
        else:                                   # bare number or macro
            j = s.find(",", i)
            j = n if j < 0 else j
            value, i = s[i:j], j
        fields[name] = " ".join(value.split())
    return fields


def parse_bib(text):
    entries, pos = [], 0
    while True:
        at = text.find("@", pos)
        if at < 0:
            break
        brace = text.find("{", at)
        if brace < 0:
            break
        kind = text[at + 1:brace].strip().lower()
        body, pos = read_braced(text, brace)
        if kind in ("comment", "preamble", "string"):
            continue
        key, _, rest = body.partition(",")
        entry = {"_type": kind, "_key": key.strip()}
        entry.update(parse_fields(rest))
        entries.append(entry)
    return entries


# ------------------------------------------------------- latex -> text --

ACCENTS = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302",
           "~": "\u0303", "=": "\u0304", ".": "\u0307", "c": "\u0327",
           "v": "\u030c", "u": "\u0306", "H": "\u030b", "k": "\u0328"}
LETTERS = {"o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ", "ss": "ß", "l": "ł",
           "L": "Ł", "aa": "å", "AA": "Å", "i": "ı"}
SYMBOLS = {"\\&": "&", "\\%": "%", "\\_": "_", "\\$": "$", "\\#": "#"}


def delatex(s):
    def accent(m):
        base = m.group(2) or m.group(3) or ""
        return unicodedata.normalize("NFC", base + ACCENTS[m.group(1)]) if base else ""
    # \'e  \'{e}  {\'e}  and letter accents like \c{c} / \v s
    s = re.sub(r"\\([`'\"^~=.])\{?([A-Za-z]?)\}?()", accent, s)
    s = re.sub(r"\\([cvuHk])(?:\{([A-Za-z])\}|\s+([A-Za-z]))", accent, s)
    s = re.sub(r"\\(o|O|ae|AE|ss|l|L|aa|AA|i)(?![A-Za-z])(?:\{\})?",
               lambda m: LETTERS[m.group(1)], s)
    for k, v in SYMBOLS.items():
        s = s.replace(k, v)
    s = re.sub(r"\\[A-Za-z]+\s?", "", s)        # drop any other \command
    s = s.replace("{", "").replace("}", "")
    s = s.replace("---", "\u2014").replace("--", "\u2013").replace("~", "\u00a0")
    return " ".join(s.split())


# -------------------------------------------------------------- authors --

def split_authors(s):
    return [a.strip() for a in re.split(r"\s+and\s+", s) if a.strip()]


def format_author(raw):
    """'Lyulina*, Anastasia S' -> ('Anastasia S. Lyulina', True, False)

    A '*' anywhere in the name marks equal (first-author) contribution, a '+'
    marks equal senior contribution; they are rendered as * and †.
    """
    raw = delatex(raw)
    star, dagger = "*" in raw, "+" in raw
    raw = raw.replace("*", "").replace("+", "").strip()
    if "," in raw:
        last, first = [p.strip() for p in raw.split(",", 1)]
    else:
        parts = raw.split()
        first, last = " ".join(parts[:-1]), parts[-1]
    first = " ".join(t + "." if len(t) == 1 and t.isalpha() else t for t in first.split())
    return f"{first} {last}".strip(), star, dagger


def render_authors(raw_list):
    names = [format_author(a) for a in raw_list]

    def span(name, star, dagger):
        label = html.escape(name) + ("*" if star else "") + ("\u2020" if dagger else "")
        return f'<span class="me">{label}</span>' if name == ME else label

    if len(names) <= MAX_AUTHORS:
        return ", ".join(span(*n) for n in names)
    # Abbreviate: keep the first three, the last, and every marked author (or me);
    # each run of dropped names becomes a single ellipsis.
    keep = {0, 1, 2, len(names) - 1}
    keep |= {i for i, (name, star, dagger) in enumerate(names) if star or dagger or name == ME}
    parts, in_gap = [], False
    for i, n in enumerate(names):
        if i in keep:
            parts.append(span(*n))
            in_gap = False
        elif not in_gap:
            parts.append("\u2026")
            in_gap = True
    return ", ".join(parts) + f" ({len(names)} authors)"


# ----------------------------------------------------------------- html --

def esc(s):
    return html.escape(s, quote=True)


def entry_href(e):
    """DOI link if there is one, otherwise the url field, otherwise ''."""
    if e.get("doi"):
        return "https://doi.org/" + e["doi"].strip()
    return e.get("url", "").strip()


def entry_label(e):
    """'Title (Venue, Year)', used as the hover text of data-bib links."""
    venue = delatex(e.get("journal") or e.get("booktitle") or "")
    if venue.lower() in PREPRINT_SERVERS:
        venue += " preprint"
    tail = ", ".join(p for p in (venue, e.get("year", "")) if p)
    return delatex(e.get("title", "")) + (f" ({tail})" if tail else "")


def link_bib_refs(text, entries):
    """Set href and title on every <a data-bib="KEY" ...> from the bib entry KEY."""
    by_key = {e["_key"]: e for e in entries}

    def fix(m):
        tag = m.group(0)
        key = re.search(r'data-bib="([^"]+)"', tag).group(1)
        e = by_key.get(key)
        if e is None:
            print(f"warning: data-bib key {key!r} not found in papers.bib", file=sys.stderr)
            return tag
        for attr, value in (("href", entry_href(e)), ("title", entry_label(e))):
            attr_re = re.compile(r'\b' + attr + r'="[^"]*"')
            if attr_re.search(tag):
                tag = attr_re.sub(f'{attr}="{esc(value)}"', tag, count=1)
            else:
                tag = tag.replace("<a ", f'<a {attr}="{esc(value)}" ', 1)
        return tag

    return re.sub(r'<a\s[^>]*\bdata-bib="[^"]+"[^>]*>', fix, text)


def render_entry(e):
    title = delatex(e.get("title", "Untitled"))
    href = entry_href(e)
    title_html = (f'<a class="title" href="{esc(href)}">{esc(title)}</a>' if href
                  else f'<span class="title">{esc(title)}</span>')

    authors_html = render_authors(split_authors(e.get("author", "")))

    venue = delatex(e.get("journal") or e.get("booktitle") or "")
    if venue.lower() in PREPRINT_SERVERS:
        venue += " (preprint)"
    venue_html = esc(", ".join(p for p in (venue, e.get("year", "")) if p))
    extras = "".join(f' · <a href="{esc(e[f].strip())}">{label}</a>'
                     for label, f in (("pdf", "pdf"), ("code", "code"), ("supplement", "supp"))
                     if e.get(f))

    thumb = ""
    preview = e.get("preview", "").strip()
    if preview:
        if (IMG_DIR / preview).exists():
            thumb = f'<img src="{esc(IMG_URL + preview)}" alt="" loading="lazy">'
        else:
            print(f"warning: {e['_key']}: img/pubs/{preview} not found", file=sys.stderr)

    return "\n".join([
        '    <li class="pub">',
        f'      <div class="thumb">{thumb}</div>',
        '      <div>',
        f'        {title_html}',
        f'        <div class="authors">{authors_html}</div>',
        f'        <div class="venue">{venue_html}{extras}</div>',
        '      </div>',
        '    </li>',
    ])


def replace_between(text, start_marker, end_marker, new):
    a = text.index(start_marker)
    a = text.index("-->", a) + 3
    b = text.index(end_marker, a)
    return text[:a] + new + text[b:]


def sort_key(e):
    year = int(re.sub(r"\D", "", e.get("year", "")) or 0)
    m = e.get("month", "").strip(". ").lower()
    month = int(m) if m.isdigit() else MONTHS.get(m[:3], 0)
    return (-year, -month)


def main():
    entries = sorted(parse_bib(BIB.read_text(encoding="utf-8")), key=sort_key)
    out, current = [], None
    for e in entries:
        year = e.get("year", "n.d.")
        if year != current:
            if current is not None:
                out.append("  </ul>")
            out.append(f'  <h2 class="year">{esc(year)}</h2>')
            out.append('  <ul class="pubs">')
            current = year
        out.append(render_entry(e))
    if current is not None:
        out.append("  </ul>")

    page = PAGE.read_text(encoding="utf-8")
    page = replace_between(page, "<!-- PUBS:START", "<!-- PUBS:END -->", "\n" + "\n".join(out) + "\n  ")
    PAGE.write_text(page, encoding="utf-8")
    with_thumbs = sum(1 for e in entries if e.get("preview"))
    print(f"wrote {len(entries)} publications ({with_thumbs} with thumbnails) to {PAGE.relative_to(ROOT)}")

    today = datetime.date.today()
    touched = []
    for path in sorted(ROOT.glob("**/*.html")):
        original = text = path.read_text(encoding="utf-8")
        if 'data-bib="' in text:
            text = link_bib_refs(text, entries)
        if "<!-- UPDATED:START -->" in text:
            text = replace_between(text, "<!-- UPDATED:START -->", "<!-- UPDATED:END -->",
                                   f"{today:%B} {today.day}, {today.year}")
        if "<!-- YEAR:START -->" in text:
            text = replace_between(text, "<!-- YEAR:START -->", "<!-- YEAR:END -->", str(today.year))
        if text != original:
            path.write_text(text, encoding="utf-8")
            touched.append(str(path.relative_to(ROOT)))
    print("updated citation links / footer dates in: " + (", ".join(touched) or "nothing (already current)"))


if __name__ == "__main__":
    main()
