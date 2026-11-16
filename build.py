#!/usr/bin/env python3
"""Build Shikimori Sakura.

  src/*.css       -> dist/sakura.css      (the theme, shared)
  personal/*.css  -> dist/<name>.css      (per-user extras, e.g. animated badges)

Every output is checked against a port of Shikimori's own sanitizer
(app/services/misc/sanitize_evil_css.rb). If the sanitizer would change a
single byte, the build fails: what you see in preview is what the site serves.

Usage:
  python3 build.py                      # assets pinned to v<VERSION>
  python3 build.py --assets-ref preview # assets from a branch / commit
  python3 build.py --check              # fail if dist/ is out of date (CI)
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = "andrey03410/shikimori-sakura"


# --- Port of Misc::SanitizeEvilCss -------------------------------------------

def _w(word: str) -> str:
    return "".join(r"\\?" + re.escape(ch) for ch in word)


EVIL_WORDS = re.compile(
    r"\b(?:"
    + "|".join(
        _w(x)
        for x in [
            "eval", "cookie", "window", "parent", "this", "javascript",
            "vbscript", "script", "behavior", "behaviour", "expression",
        ]
    )
    + r")\b|"
    + _w("moz-binding")
    + "|"
    + _w("@") + "*" + _w("charset")
    + "|"
    + _w("<"),
    re.I,
)
COMMENTS = re.compile(r"/\*.*?\*/\s*[\n\r]*", re.S | re.I)
IMPORTS = re.compile(
    r"""(?:@*import\s+url\(['"]?.*?['"]?\);|@*import\s+['"].*?['"]|"""
    + _w("@") + "+" + _w("import")
    + r""")\ ?[\n\r]*""",
    re.S | re.I,
)
EVIL_CSS = [
    EVIL_WORDS,
    re.compile(r"\\+[\n\r]+"),
    re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]+"),
    re.compile(r"&#"),
    COMMENTS,
    IMPORTS,
]
SPECIAL = re.compile(r"""((?>content: ?['"].*?['"]))|\\\w""")
FIX_CONTENT = re.compile(r"""(content: ?['"]\\)\\.?(\w{4}['"])""")
DATA_IMAGE = re.compile(
    r"(?:\b|^)(?:((?>data:(?:image/(?:svg\+xml|png|jpeg|jpg|gif)|application/octet-stream);base64,))|"
    + _w("data:")
    + r"(?:\b|$))",
    re.I,
)


def sanitize(css: str) -> str:
    fixed = FIX_CONTENT.sub(r"\1\2", css)
    while True:
        prior = fixed
        for rx in EVIL_CSS:
            fixed = rx.sub("", fixed)
        fixed = SPECIAL.sub(lambda m: m.group(1) or "", fixed)
        fixed = DATA_IMAGE.sub(lambda m: m.group(1) or "", fixed).strip()
        if fixed == prior:
            break
    return re.sub(r";;+", ";", fixed)


# --- Build -------------------------------------------------------------------

def minify(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    lines = [ln.strip() for ln in css.splitlines()]
    css = "\n".join(ln for ln in lines if ln)
    css = re.sub(r"\s*\{\s*", "{", css)
    css = re.sub(r";\s*\}", "}", css)
    css = re.sub(r"\s*\}\s*", "}\n", css)
    css = re.sub(r";\s*\n\s*", ";", css)
    return css.strip() + "\n"


def report_sanitizer_diff(name: str, css: str, clean: str) -> None:
    i = 0
    while i < min(len(css), len(clean)) and css[i] == clean[i]:
        i += 1
    line = css.count("\n", 0, i) + 1
    snippet = css[max(0, i - 60): i + 60].replace("\n", "⏎")
    print(f"✗ {name}: Shikimori's sanitizer would alter line {line}:\n    …{snippet}…", file=sys.stderr)


def check_braces(name: str, css: str) -> bool:
    depth = 0
    for n, ch in enumerate(css):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            print(f"✗ {name}: unbalanced '}}' at char {n}", file=sys.stderr)
            return False
    if depth:
        print(f"✗ {name}: {depth} unclosed '{{'", file=sys.stderr)
        return False
    return True


def build_one(name: str, parts: list[pathlib.Path], assets: str, version: str) -> str | None:
    source = "\n".join(p.read_text(encoding="utf-8") for p in parts)
    source = source.replace("{{ASSETS}}", assets).replace("{{VERSION}}", version)
    css = minify(source)
    ok = check_braces(name, css)
    clean = sanitize(css)
    if clean != css.strip():
        report_sanitizer_diff(name, css, clean)
        ok = False
    return css if ok else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets-ref", help="git ref for asset URLs (default v<VERSION>)")
    ap.add_argument("--check", action="store_true", help="fail if dist/ is stale")
    args = ap.parse_args()

    version = (ROOT / "VERSION").read_text().strip()
    ref = args.assets_ref or f"v{version}"
    assets = f"https://raw.githubusercontent.com/{REPO}/{ref}/assets"

    targets = {"sakura.css": sorted((ROOT / "src").glob("*.css"))}
    for p in sorted((ROOT / "personal").glob("*.css")):
        targets[p.name] = [p]

    failed = False
    for out_name, parts in targets.items():
        css = build_one(out_name, parts, assets, version)
        if css is None:
            failed = True
            continue
        out = ROOT / "dist" / out_name
        if args.check:
            if not out.exists() or out.read_text(encoding="utf-8") != css:
                print(f"✗ dist/{out_name} is stale — run python3 build.py", file=sys.stderr)
                failed = True
            continue
        out.parent.mkdir(exist_ok=True)
        out.write_text(css, encoding="utf-8")
        print(f"✓ dist/{out_name}  {len(css.encode()) / 1024:.1f} KB")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
