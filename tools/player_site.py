#!/usr/bin/env python
"""The players' website, docs/player/: the pieces every guide shares, and the one command that rebuilds it all.

docs/player/ is published as it stands (the owner hosts the folder on Coolify, straight from the repo), so EVERYTHING
in it is public. tests/test_player_site_leaks.py reads every file there and fails on any id, name, coordinate or line
of a legendary, resident, shrine, cache, portal or story record.

THE ONE COMMAND:

  python tools/player_site.py            # run every registered guide's generator, then write index.html
  python tools/player_site.py --check    # each generator's --check, then the index's; exit 1 if anything is stale

This is a library the guide generators import, not a tool of its own: its `__main__` only runs the generators that
registered themselves in docs/player/guides.json and builds the index from that manifest. A new guide joins the site
by calling `page()` and `write()` here and being run once by itself; after that this command covers it.

THE SITE:
  assets/site.css   hand-written, the only stylesheet; generators emit classes, never a <style> of their own
  assets/site.js    hand-written, the shared light / dark switch
  guides.json       the manifest: file, title, nav label, one-line description, generator. Each generator registers
                    its own entry (`register()`) when it writes its page; nobody edits it by hand
  index.html        generated here from the manifest, so a new guide appears without anyone editing the index
  <guide>.html      written by its generator through `page()`: the shared header (site name, links to every guide,
                    the light / dark switch), the spoiler note, the guide's body, the shared footer

HOW --check SURVIVES THE FOOTER'S DATE AND COMMIT. The footer's "Generated on <date> from commit <sha>" is the only
line that changes from run to run, and it is emitted alone in <p class="site-generated">. `stable()` blanks that one
element, `check()` compares stable forms, and `write()` leaves a file untouched when its stable form has not changed,
so the date and commit say when the page's CONTENT last changed and which commit it was generated from, and a
re-run on an unchanged page writes nothing and never dirties the tree. The commit is `git rev-parse` HEAD at
generation, marked "with uncommitted changes" when data/ or tools/ differ from it; such a page is re-stamped by the
first run on a clean tree (commit the tools, then run this command, then commit the pages).

Who imports this: tools/player_guide_battles.py (battles.html) and tools/player_guide_map.py (region-map.html).
tools/challenge_guide.py does not: its page stays in build/maps/ and off the public site (see its docstring).
"""
from __future__ import annotations

import argparse
import datetime
import html
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "player"
MANIFEST = SITE / "guides.json"
INDEX = SITE / "index.html"
CSS = "assets/site.css"
JS = "assets/site.js"
SITE_NAME = "Cobblers"
SCHEMA = "cobblers.player_guides/1"
ENTRY_KEYS = ("file", "title", "label", "description", "generator", "order")

# What every page says it leaves out on purpose. Each guide's own "What this page does not cover" section adds its
# page's details; this is the site-wide promise, and tests/test_player_site_leaks.py holds the pages to it.
SPOILER = ("Spoiler-safe on purpose: these guides cover wild encounters and trainer battles only. They do not cover "
           "legendary or mythical Pokemon, resident Pokemon, Mega dens, shrines, caches, portals, quests, story or "
           "dialogue: those are left for you to find.")
GENERATED = re.compile(r'<p class="site-generated">.*?</p>', re.S)
UNCOMMITTED = "with uncommitted changes to data/ or tools/"


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ the manifest


def load_manifest():
    if not MANIFEST.is_file():
        return {"schema": SCHEMA, "guides": []}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _merged(entry, manifest=None):
    """The manifest's guides with `entry` put in (replacing its own file's), ordered by `order` then file."""
    guides = [g for g in (manifest or load_manifest())["guides"] if g["file"] != entry["file"]] if entry else \
        list((manifest or load_manifest())["guides"])
    if entry:
        guides.append({k: entry[k] for k in ENTRY_KEYS})
    return sorted(guides, key=lambda g: (g["order"], g["file"]))


def manifest_text(guides):
    doc = {"schema": SCHEMA,
           "note": "The public guides in docs/player/. Each generator writes its own entry through "
                   "tools/player_site.py register(); index.html and every page's header are built from this list. "
                   "Do not edit by hand. Everything in docs/player/ is public.",
           "guides": guides}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def register(entry):
    """Put a guide's entry in docs/player/guides.json. Returns True if the manifest changed."""
    missing = [k for k in ENTRY_KEYS if k not in entry]
    if missing:
        raise SystemExit("a guide entry needs %s" % ", ".join(missing))
    text = manifest_text(_merged(entry))
    if MANIFEST.is_file() and MANIFEST.read_text(encoding="utf-8") == text:
        return False
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(text, encoding="utf-8", newline="\n")
    return True


def registered(entry):
    """True if the manifest already holds exactly this entry."""
    return any(g == {k: entry[k] for k in ENTRY_KEYS} for g in load_manifest()["guides"])


# ------------------------------------------------------------------ header, spoiler note, footer, page


def provenance():
    """(date, commit words) for the footer: today's UTC date and HEAD, marked if data/ or tools/ have changes."""
    def git(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    sha = git("rev-parse", "--short=12", "HEAD")
    words = "commit %s" % sha if sha else "an unknown commit"
    if sha and git("status", "--porcelain", "--", "data", "tools"):
        words += " " + UNCOMMITTED
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat(), words


def header(entry, tools_html="", manifest=None):
    links = ['<a href="index.html"%s>All guides</a>' % (' aria-current="page"' if entry is None else "")]
    for g in _merged(entry, manifest):
        cur = entry is not None and g["file"] == entry["file"]
        links.append('<a href="%s"%s>%s</a>' % (esc(g["file"]), ' aria-current="page"' if cur else "", esc(g["label"])))
    return ('<header class="site-header"><a class="site-name" href="index.html">%s</a><nav class="site-nav" '
            'aria-label="Guides">%s</nav><div class="site-tools">%s<button type="button" id="theme" '
            'aria-label="Switch light or dark">Light / dark</button></div></header>'
            % (esc(SITE_NAME), "".join(links), tools_html))


def spoiler(not_covered_href=None):
    # no banner (the owner, 2026-10-08: "remove the banner at top about spoilers"); each guide keeps its own
    # "not covered" section in its body
    return ""


def footer(generator, sources_html="", manifest=None, entry=None):
    # the generated-on line and the regenerate note are gone (the owner, 2026-10-08); the footer is the guide links
    links = " &middot; ".join('<a href="%s">%s</a>' % (esc(g["file"]), esc(g["title"])) for g in _merged(entry, manifest))
    return ('<footer class="site-footer">%s<p>%s: <a href="index.html">all guides</a> &middot; %s</p></footer>'
            % (sources_html, esc(SITE_NAME), links))


def page(entry, body, *, body_class, tools_html="", head_html="", end_html="", not_covered_href=None, sources_html=""):
    """A whole page: the shared head (site.css, site.js), header, spoiler note, `body`, footer. `head_html` and
    `end_html` are the page's own scripts (never a <style>: styles live in assets/site.css)."""
    if "<style" in head_html + body + end_html:
        raise SystemExit("%s: a guide emits no <style>; put the rule in docs/player/%s" % (entry["file"], CSS))
    title = "%s: %s" % (SITE_NAME, entry["title"]) if entry else "%s player guides" % SITE_NAME
    return ('<!doctype html>\n<html lang="en" class="nojs"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>'
            '<link rel="stylesheet" href="%s"><script src="%s"></script>%s</head>\n<body class="%s">\n%s\n%s\n%s\n%s\n'
            '%s</body></html>\n'
            % (esc(title), CSS, JS, head_html, esc(body_class), header(entry, tools_html), spoiler(not_covered_href),
               body, footer(entry["generator"] if entry else "tools/player_site.py", sources_html, entry=entry),
               end_html))


# ------------------------------------------------------------------ write and check


def stable(text):
    """The page without its generated-on line: what --check compares."""
    return GENERATED.sub('<p class="site-generated"></p>', text)


def check(path, text, entry=None):
    """(ok, why). The page matches `text` but for the generated-on line, and its manifest entry is current."""
    path = Path(path)
    if not path.is_file():
        return False, "missing"
    if stable(path.read_text(encoding="utf-8")) != stable(text):
        return False, "stale"
    if entry is not None and not registered(entry):
        return False, "not registered in %s as it is now" % MANIFEST.relative_to(ROOT).as_posix()
    return True, "current"


def write(path, text, entry=None):
    """Write the page unless only its generated-on line would change, and register its entry. Returns what it did."""
    path = Path(path)
    did = "unchanged"
    have = path.read_text(encoding="utf-8") if path.is_file() else None
    # a page stamped from a dirty tree is re-stamped once the tree is clean, so its commit names what it came from
    restamp = have is not None and UNCOMMITTED in "".join(GENERATED.findall(have)) and UNCOMMITTED not in text
    if have is None or stable(have) != stable(text) or restamp:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        did = "wrote"
    if entry is not None and register(entry):
        did += ", registered"
    return did


# ------------------------------------------------------------------ the index and the one command


def build_index(manifest=None):
    manifest = manifest or load_manifest()
    items = "".join('<li><a href="%s">%s</a><p>%s</p></li>' % (esc(g["file"]), esc(g["title"]), esc(g["description"]))
                    for g in _merged(None, manifest))
    body = ('<main><h1>Cobblers player guides</h1><p class="lead">Guides for the Cobblers campaign, generated from its '
            'data. Pick one:</p><ul class="guides">%s</ul></main>' % items)
    return page(None, body, body_class="page-index")


def _generator(rel):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def main(argv=None):
    p = argparse.ArgumentParser(description="Regenerate every guide in docs/player/ and its index, or --check them.")
    p.add_argument("--check", action="store_true", help="run each generator's --check and the index's; write nothing")
    p.add_argument("--index-only", action="store_true", help="only the index, from the manifest as it stands")
    a = p.parse_args(argv)
    bad = []
    if not a.index_only:
        for g in load_manifest()["guides"]:
            print("== %s (%s)" % (g["file"], g["generator"]))
            rc = _generator(g["generator"]).main(["--check"] if a.check else [])
            if rc:
                bad.append(g["file"])
    text = build_index()
    if a.check:
        ok, why = check(INDEX, text)
        print("%s is %s" % (INDEX.relative_to(ROOT).as_posix(), why))
        if not ok:
            bad.append("index.html")
    else:
        print("%s: %s" % (INDEX.relative_to(ROOT).as_posix(), write(INDEX, text)))
    if bad:
        print("FAILED: %s" % ", ".join(bad))
        return 1
    print("site %s: %d guides and the index" % ("current" if a.check else "regenerated", len(load_manifest()["guides"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
