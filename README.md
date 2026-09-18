# zhiru-minimal

A from-scratch, dependency-free replacement for the al-folio site at
zhiru-liu.github.io. Two pages, one stylesheet, no JavaScript, no build
step on GitHub.

```
index.html                 about page (bio, photo, links) — edit by hand
publications/index.html    publication list — generated from papers.bib
style.css                  all styling (~80 lines); light/dark follows the OS
papers.bib                 source of truth for publications (same file as before)
build.py                   regenerates the publication list and stamps the footer dates
img/zhiru.jpg              profile photo (400×400)
img/pubs/                  publication thumbnails, referenced by `preview = {...}` in the bib
.nojekyll                  tells GitHub Pages to serve the files as-is
```

## Editing

* **Bio / links** — edit `index.html` directly.
* **Publications** — add an entry to `papers.bib` (Zotero export works as-is),
  drop an optional thumbnail into `img/pubs/` and reference it with
  `preview = {file.png}`, then run:

  ```bash
  python3 build.py
  ```

  Optional bib fields `pdf`, `code` and `supp` become small links after the venue.
  A `*` on a name (e.g. `Liu*, Zhiru`) marks equal contribution and a `+`
  (e.g. `Good+, Benjamin H.`) marks equal senior contribution; they render as
  `*` and `†`. Author lists longer than 8 are abbreviated, but every marked
  author and Zhiru's name always stay visible.
* **Citing a paper from the about page** — write `<a data-bib="BIBKEY">1</a>`
  and run `build.py`; it fills in the DOI link and a hover title from that bib
  entry. When a preprint is published, update the bib entry (journal, doi) and
  rerun the script: both pages follow.
* **Footer** — the copyright year and "last updated" date are stamped by
  `build.py`, so run it before committing any change (it takes a fraction of
  a second and is safe to run repeatedly).
* **Look and feel** — everything is in `style.css`. Colours are CSS variables
  at the top; the font is the system font stack.

## Previewing locally

Open `index.html` in a browser, or run `python3 -m http.server` in this folder
and visit http://localhost:8000.

## Deploying (when ready to switch)

The files are plain HTML, so GitHub Pages can serve them straight from the
repository with no Actions workflow:

1. In the `zhiru-liu.github.io` repo, replace the contents of `master` with
   this folder (keep `.git`; delete the old `.github/workflows`).
2. In the repo's Settings → Pages, set the source to *Deploy from a branch*,
   branch `master`, folder `/ (root)`. The old `gh-pages` branch can then be
   deleted.

URLs are preserved: `/` and `/publications/` are the same as on the old site.
