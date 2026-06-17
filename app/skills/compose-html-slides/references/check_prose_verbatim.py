#!/usr/bin/env python3
"""
check_prose_verbatim.py — mechanical no-drift gate for compose-html-slides.

Confirms every reader-visible PROSE run in a built deck is a contiguous, verbatim
substring of the narrative.md it was built from. The point: deck prose is
*transcribed* from the source, not paraphrased — so the narrative's wording (and
the numbers embedded in that wording) cannot silently change. The guarantee comes
from this check, not from how the bytes were typed.

A prose run that does NOT match is one of:
  (a) chrome — text the deck structurally needs but the narrative lacks: the cover
      <h1>, chapter-divider ledes, "Part N" kickers. List each such string, one per
      line, in an allowlist file so chrome is explicit and countable (you can't
      sneak invented prose past the check without deliberately allowlisting it); or
  (b) DRIFT — paraphrased or invented wording. Rewrite it to a verbatim span of the
      narrative, or delete it.

Usage:
  python3 check_prose_verbatim.py DECK.html NARRATIVE.md [ALLOWLIST.txt]

Scope / honesty about heuristics (this flags candidates for review; it is not a
perfect oracle):
  * Only PROSE is checked: text runs of >= MIN_WORDS words. Short runs — chart
    labels, stat numbers, bar names, section headings, kickers, page numbers — are
    skipped. Numeric fidelity is the *data-integrity* pass's job, checked against
    the raw source files, not here.
  * Matching unescapes HTML entities, ignores tag boundaries and runs of
    whitespace, and normalizes dashes/quotes. It is otherwise exact: a synonym, a
    reordering, or an inserted word will NOT match.
  * Only text inside <main> is examined (the slide stage); the left <nav> is not.

Exit code: 0 = clean, 1 = drift found, 2 = bad invocation.
"""
import sys
import re
import html
from html.parser import HTMLParser

MIN_WORDS = 5


def normalize(s: str) -> str:
    s = html.unescape(s)
    for a, b in (("—", "-"), ("–", "-"),      # em / en dash
                 ("’", "'"), ("‘", "'"),      # curly single quotes
                 ("“", '"'), ("”", '"'),      # curly double quotes
                 (" ", " ")):                       # nbsp
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def edge_trim(s: str) -> str:
    """Drop boundary punctuation so a sentence the deck ends with a period still
    matches the narrative span that continued into a parenthetical (Source: …)."""
    return s.strip(" .,:;-")


class Stage(HTMLParser):
    """Collect prose text fragments from block elements inside <main>.

    Skips structural, non-narrative text: source attributions (`.src`) are checked
    by the separate Sources rule, and chart titles (`.bar-title`) are deck-authored
    chart scaffolding, not narrative prose."""
    BLOCK = {"p", "li", "h1", "h2", "h3", "blockquote"}
    SKIP_CLASSES = {"src", "bar-title"}

    def __init__(self):
        super().__init__()
        self.in_main = 0
        self.capture = False
        self.skip = False
        self.buf = []
        self.frags = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.in_main += 1
        if self.in_main and tag in self.BLOCK:
            self._flush()
            cls = (dict(attrs).get("class") or "").split()
            self.skip = any(c in self.SKIP_CLASSES for c in cls)
            self.capture = True

    def handle_endtag(self, tag):
        if self.in_main and tag in self.BLOCK:
            self._flush()
            self.capture = False
        if tag == "main" and self.in_main:
            self.in_main -= 1

    def handle_data(self, data):
        if self.in_main and self.capture:
            self.buf.append(data)

    def _flush(self):
        if self.buf and not self.skip:
            t = normalize("".join(self.buf))
            if t:
                self.frags.append(t)
        self.buf = []
        self.skip = False


def sentences(text: str):
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z\"'])", text)
    return [p.strip() for p in parts if p.strip()]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    deck = open(sys.argv[1], encoding="utf-8").read()
    # Source corpus: strip markdown markers, then normalize to one flat string.
    raw = open(sys.argv[2], encoding="utf-8").read()
    corpus = normalize(re.sub(r"[*#`>|]", " ", raw))

    allow = set()
    if len(sys.argv) > 3:
        for line in open(sys.argv[3], encoding="utf-8"):
            line = normalize(line)
            if line:
                allow.add(line)

    parser = Stage()
    parser.feed(deck)

    def matches(run: str) -> bool:
        run = edge_trim(run)
        return run in corpus or run in allow

    drift = []
    for frag in parser.frags:
        if len(frag.split()) < MIN_WORDS:
            continue
        if matches(frag):
            continue
        # The run may legitimately concatenate two transcribed spans; check each
        # sentence on its own before declaring drift.
        for s in sentences(frag):
            if len(s.split()) >= MIN_WORDS and not matches(s):
                drift.append(s)

    if drift:
        print(f"DRIFT — {len(drift)} prose run(s) are NOT verbatim in the narrative.")
        print("Rewrite each to a verbatim span of narrative.md, or, if it is chrome")
        print("(cover h1 / divider lede / kicker), add it to the allowlist file:\n")
        for d in drift:
            print(f"  - {d}")
        sys.exit(1)

    print("OK - every prose run (>= %d words) is verbatim from the narrative "
          "or allowlisted chrome." % MIN_WORDS)


if __name__ == "__main__":
    main()
