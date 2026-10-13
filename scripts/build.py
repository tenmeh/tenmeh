"""Draw the pictures of the profile README and fill its blog list.

Run by .github/workflows/build.yml once a day. It needs only the standard
library. GITHUB_TOKEN raises the API rate limit and is needed for the
contribution count; without it the script still runs, with fewer numbers.

Every picture comes in a light and a dark version. The README picks one with
<picture> and prefers-color-scheme. The colours are those of the blog and of
the pkgdown sites, so the profile, the blog and the docs are one family.
"""

import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

USER = "tenmeh"
FEED = "https://tenmeh.github.io/index.xml"
# Public repos only. Private ones must not appear on the profile.
FEATURED = ["rewind", "bones", "tanmai-r", "tanmai"]

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
README = ROOT / "README.md"

# Same values as _pkgdown.yml in bones and the blog theme. Change them together.
THEMES = {
    "light": {
        "bg": "#f4efe4", "card": "#fbf8f1", "ink": "#17202a", "muted": "#566176",
        "border": "#cfc5b1", "accent": "#1B6A70", "tint": "#e3e4d9",
        "skel": "#e6dfd0", "shine": "#fbf8f1",
    },
    "dark": {
        "bg": "#1f1d1b", "card": "#282523", "ink": "#ece5d6", "muted": "#b9b2a3",
        "border": "#3d3833", "accent": "#5CC4CA", "tint": "#2c3a39",
        "skel": "#34302c", "shine": "#4a4540",
    },
}
LANG_COLOURS = {
    "R": "#276DC3", "Python": "#3572A5", "JavaScript": "#f1e05a", "CSS": "#663399",
    "HTML": "#e34c26", "TypeScript": "#3178c6", "Shell": "#89e051", "C++": "#f34b7d",
    "SCSS": "#c6538c",
}
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'Cascadia Code', Consolas, 'Liberation Mono', monospace"


# --- Data ------------------------------------------------------------------

def get(url, data=None):
    headers = {"User-Agent": USER, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def get_json(url, data=None):
    try:
        return json.loads(get(url, data))
    except Exception as e:  # one failed call must not stop the whole build
        print(f"warning: {url}: {e}")
        return None


def cran_version(pkg):
    # crandb answers 404 for a package that is not on CRAN. That is expected.
    try:
        info = json.loads(get(f"https://crandb.r-pkg.org/{pkg}"))
    except Exception:
        return None
    return info.get("Version") if info and "Version" in info else None


def own_repos():
    repos = get_json(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner") or []
    return [r for r in repos if not r["fork"] and not r["private"]]


def contributions():
    if not os.environ.get("GITHUB_TOKEN"):
        return None
    query = 'query { user(login: "%s") { contributionsCollection {' \
            ' contributionCalendar { totalContributions } } } }' % USER
    res = get_json("https://api.github.com/graphql", {"query": query})
    try:
        return res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except (TypeError, KeyError):
        return None


def languages(repos):
    totals = {}
    for r in repos:
        for lang, n in (get_json(r["languages_url"]) or {}).items():
            totals[lang] = totals.get(lang, 0) + n
    return sorted(totals.items(), key=lambda kv: -kv[1])


def posts(n=4):
    try:
        root = ET.fromstring(get(FEED))
    except Exception as e:
        print(f"warning: feed: {e}")
        return None
    out = []
    for item in root.iter("item"):
        date = datetime.strptime(item.findtext("pubDate").strip()[:16], "%a, %d %b %Y")
        out.append((item.findtext("title").strip(), item.findtext("link").strip(), date))
    return out[:n]


# --- Drawing ---------------------------------------------------------------

def esc(s):
    return html.escape(str(s), quote=True)


def wrap(text, width, lines=2):
    words, out, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    out.append(line)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1].rstrip(".,;:") + "..."
    return out


def svg(w, h, body, t, title):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<style>
  text {{ font-family: {FONT}; fill: {t['ink']}; }}
  .mono {{ font-family: {MONO}; }}
  .muted {{ fill: {t['muted']}; }}
  .accent {{ fill: {t['accent']}; }}
  .shine {{ animation: shine 2.4s ease-in-out infinite; }}
  .cursor {{ animation: blink 1.1s steps(1) infinite; }}
  @keyframes shine {{ from {{ transform: translateX(-420px); }} to {{ transform: translateX(520px); }} }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .shine, .cursor {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{t['card']}" stroke="{t['border']}"/>
{body}
</svg>
"""


def banner(t):
    # The right side is a loading skeleton with a shimmer: the idea of bones.
    bars = [(0, 0, 220, 18), (0, 34, 330, 10), (0, 54, 300, 10), (0, 74, 250, 10)]
    cols = [(0, 70), (46, 40), (92, 95), (138, 55), (184, 82), (230, 30), (276, 64)]
    clip = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}"/>' for x, y, w, h in bars)
    clip += "".join(f'<rect x="{x}" y="{200 - h}" width="30" height="{h}" rx="4"/>' for x, h in cols)
    body = f"""
<defs>
  <clipPath id="skel">{clip}</clipPath>
  <linearGradient id="glow" x1="0" x2="1">
    <stop offset="0" stop-color="{t['shine']}" stop-opacity="0"/>
    <stop offset="0.5" stop-color="{t['shine']}" stop-opacity="0.9"/>
    <stop offset="1" stop-color="{t['shine']}" stop-opacity="0"/>
  </linearGradient>
</defs>
<text x="64" y="84" class="mono accent" font-size="18" letter-spacing="1">R / SHINY / OPEN SOURCE</text>
<text x="64" y="146" font-size="60" font-weight="700" letter-spacing="-1.5">Tanmay Chanda</text>
<text x="64" y="184" class="muted" font-size="24">Notes on R, Shiny, and building things</text>
<text x="64" y="216" class="muted" font-size="24">that other people use.</text>
<text x="64" y="258" class="mono accent" font-size="19">&gt; install.packages("rewind")<tspan class="cursor">_</tspan></text>
<g transform="translate(760 58)">
  <rect x="-28" y="-26" width="400" height="252" rx="12" fill="{t['bg']}" stroke="{t['border']}"/>
  <g clip-path="url(#skel)">
    <rect x="-20" y="-10" width="400" height="230" fill="{t['skel']}"/>
    <rect class="shine" x="0" y="-10" width="160" height="230" fill="url(#glow)"/>
  </g>
</g>"""
    return svg(1200, 300, body, t, "Tanmay Chanda. Notes on R, Shiny, and building things that other people use.")


def repo_card(repo, cran, t):
    name, desc = repo["name"], repo.get("description") or ""
    lang = repo.get("language") or ""
    lines = "".join(
        f'<text x="28" y="{86 + i * 22}" class="muted" font-size="14.5">{esc(l)}</text>'
        for i, l in enumerate(wrap(desc, 50))
    )
    pill = ""
    if cran:
        label = f"CRAN {cran}"
        pw = 16 + len(label) * 7.6
        pill = (f'<rect x="{412 - pw}" y="26" width="{pw}" height="24" rx="12" fill="{t["tint"]}"/>'
                f'<text x="{412 - pw / 2}" y="42.5" class="mono accent" font-size="12.5" '
                f'text-anchor="middle" font-weight="600">{esc(label)}</text>')
    foot, x = "", 28
    if lang:
        foot += (f'<circle cx="{x + 6}" cy="151" r="6" fill="{LANG_COLOURS.get(lang, t["muted"])}"/>'
                 f'<text x="{x + 18}" y="156" class="muted" font-size="13.5">{esc(lang)}</text>')
        x += 40 + len(lang) * 8
    star = "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"
    foot += (f'<path transform="translate({x} 143)" d="{star}" fill="{t["muted"]}"/>'
             f'<text x="{x + 22}" y="156" class="muted" font-size="13.5">{repo["stargazers_count"]}</text>')
    book = "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8Z"
    body = f"""
<path transform="translate(28 30)" d="{book}" fill="{t['accent']}"/>
<text x="54" y="44" class="accent" font-size="20" font-weight="700">{esc(name)}</text>
{pill}{lines}{foot}"""
    return svg(440, 182, body, t, f"{name}: {desc}")


def stats_card(stats, t):
    rows = "".join(
        f'<text x="28" y="{80 + i * 30}" class="muted" font-size="15">{esc(k)}</text>'
        f'<text x="412" y="{80 + i * 30}" font-size="16" font-weight="700" text-anchor="end">{esc(v)}</text>'
        for i, (k, v) in enumerate(stats)
    )
    body = f'<text x="28" y="44" class="accent" font-size="20" font-weight="700">In numbers</text>{rows}'
    return svg(440, 182, body, t, "In numbers: " + ", ".join(f"{k} {v}" for k, v in stats))


def langs_card(langs, t):
    langs = langs[:5]
    total = sum(n for _, n in langs) or 1
    bar, x = "", 28.0
    for lang, n in langs:
        w = 384 * n / total
        bar += f'<rect x="{x:.1f}" y="66" width="{max(w - 2, 1):.1f}" height="10" fill="{LANG_COLOURS.get(lang, t["muted"])}"/>'
        x += w
    legend = ""
    for i, (lang, n) in enumerate(langs):
        cx, cy = 28 + (i % 2) * 200, 112 + (i // 2) * 26
        legend += (f'<circle cx="{cx + 6}" cy="{cy - 5}" r="6" fill="{LANG_COLOURS.get(lang, t["muted"])}"/>'
                   f'<text x="{cx + 20}" y="{cy}" font-size="14">{esc(lang)} '
                   f'<tspan class="muted">{100 * n / total:.1f}%</tspan></text>')
    body = f"""
<text x="28" y="44" class="accent" font-size="20" font-weight="700">Languages</text>
<clipPath id="bar"><rect x="28" y="66" width="384" height="10" rx="5"/></clipPath>
<g clip-path="url(#bar)">{bar}</g>{legend}"""
    return svg(440, 182, body, t, "Languages: " + ", ".join(l for l, _ in langs))


# --- Build -----------------------------------------------------------------

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_block(text, name, content):
    pattern = re.compile(rf"(<!-- {name}:START -->\n).*?(<!-- {name}:END -->)", re.S)
    return pattern.sub(lambda m: m.group(1) + content + m.group(2), text)


def main():
    repos = own_repos()
    by_name = {r["name"]: r for r in repos}
    cran = {name: cran_version(name) for name in FEATURED}

    for mode, t in THEMES.items():
        write(ASSETS / f"banner-{mode}.svg", banner(t))
        for name in FEATURED:
            if name in by_name:
                write(ASSETS / "cards" / f"{name}-{mode}.svg", repo_card(by_name[name], cran[name], t))

    stats = [
        ("Stars on my repos", sum(r["stargazers_count"] for r in repos)),
        ("Public repos", len(repos)),
        ("Packages on CRAN", sum(1 for v in cran.values() if v)),
    ]
    n = contributions()
    if n is not None:
        stats.append(("Contributions, last 12 months", n))
    langs = languages(repos)
    for mode, t in THEMES.items():
        write(ASSETS / f"stats-{mode}.svg", stats_card(stats, t))
        if langs:
            write(ASSETS / f"languages-{mode}.svg", langs_card(langs, t))

    items = posts()
    if items:
        lines = "".join(f"- [{title}]({link}) <sub>{d:%d %b %Y}</sub>\n" for title, link, d in items)
        text = README.read_text(encoding="utf-8")
        write(README, replace_block(text, "BLOG", lines))


if __name__ == "__main__":
    main()
