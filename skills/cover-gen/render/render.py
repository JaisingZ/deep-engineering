#!/usr/bin/env python3
"""Offline cover / illustration renderer (HTML+SVG -> PNG via headless Chrome).

No image API needed. Usage:
  python3 render.py cover --title "第一行|第二行" --subtitle "副标题" [--eyebrow "X Draft"] -o cover.png
  python3 render.py diagram spec.json -o out.png
  python3 render.py batch specs/<article>/ -o <article-dir>/   # every *.json in the folder

Spec files are JSON; "type" is one of: cover, pipeline, compare, lanes, boundary.
See README.md for the fields of each type.
"""
import argparse, html, json, math, os, random, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE / "templates"
COVER_W, COVER_H = 1500, 600
DIAG_W, DIAG_H = 1600, 900


def esc(s):
    return html.escape(str(s))


def kw(s):
    """Escape text; [[word]] becomes a highlighted keyword span."""
    return re.sub(r"\[\[(.+?)\]\]", lambda m: f'<span class="kw">{m.group(1)}</span>', esc(s))


# ---------------------------------------------------------------- background motif
def wave_svg(w, h, x0, y_mid, amp, seed=7, opacity=1.0, particles=True, glow=True):
    """Three layers of thin-line waves (cyan / deep blue / amber) plus scattered particles."""
    rnd = random.Random(seed)
    layers = [
        # (color_a, color_b, n_lines, y_offset, amp_scale, freq, phase, width)
        ("#a9efff", "#2a8cb9", 14, -amp * 0.55, 1.0, 1.6, 0.0, 1.1),
        ("#2a6fd6", "#123a8a", 12, 0.0, 0.85, 1.3, 1.2, 1.0),
        ("#c6a48b", "#a36d42", 12, amp * 0.6, 0.7, 1.9, 2.4, 1.0),
    ]
    span = w - x0
    out = [f'<svg class="bgsvg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="opacity:{opacity}">',
           "<defs>",
           '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>']
    for i, (ca, cb, *_r) in enumerate(layers):
        end = "#56beff" if i == 2 else cb
        out.append(f'<linearGradient id="g{i}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{ca}" stop-opacity="0"/>'
                   f'<stop offset="0.18" stop-color="{ca}"/><stop offset="0.7" stop-color="{cb}"/><stop offset="1" stop-color="{end}"/></linearGradient>')
    out.append("</defs>")
    for i, (ca, cb, n, yo, asc, fr, ph, sw) in enumerate(layers):
        g = f'<g fill="none" stroke="url(#g{i})" stroke-width="{sw}"' + (' filter="url(#glow)"' if glow else "") + ">"
        out.append(g)
        for k in range(n):
            t = k / max(1, n - 1)
            pts = []
            steps = 90
            for s in range(steps + 1):
                u = s / steps
                x = x0 + u * span
                # amber layer narrows to a single line at the right edge
                spread = (1 - u * 0.85) if i == 2 else (1 - u * 0.35)
                y = (y_mid + yo + (t - 0.5) * amp * 0.9 * spread
                     + amp * asc * math.sin(u * math.pi * fr + ph + t * 0.9) * (0.35 + 0.65 * math.sin(u * math.pi * 0.9 + 0.2)))
                pts.append(f"{x:.1f},{y:.1f}")
            op = 0.35 + 0.6 * (1 - abs(t - 0.5) * 2)
            out.append(f'<polyline points="{" ".join(pts)}" stroke-opacity="{op:.2f}"/>')
        out.append("</g>")
    if particles:
        cols = ["#56beff", "#a9efff", "#ffffff", "#c6a48b"]
        for _ in range(70):
            # density grows toward the waves (x close to x0 + something)
            u = rnd.random() ** 0.55
            x = x0 - 200 + u * (span * 0.55 + 200)
            y = y_mid + rnd.gauss(0, amp * 1.1)
            if not (8 < y < h - 8) or x < x0 - 200:
                continue
            c = rnd.choice(cols)
            o = 0.25 + 0.6 * u
            if rnd.random() < 0.5:
                r = rnd.uniform(1.2, 2.8)
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c}" fill-opacity="{o:.2f}"/>')
            else:
                sz = rnd.uniform(4, 8); a = rnd.uniform(0, 360)
                out.append(f'<polygon points="0,{-sz:.1f} {sz*0.87:.1f},{sz/2:.1f} {-sz*0.87:.1f},{sz/2:.1f}" fill="none" stroke="{c}" stroke-opacity="{o:.2f}" stroke-width="1.2" transform="translate({x:.1f},{y:.1f}) rotate({a:.0f})"/>')
    out.append("</svg>")
    return "\n".join(out)


def page(w, h, css_files, body):
    css = "\n".join((TPL / f).read_text(encoding="utf-8") for f in css_files)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>:root{{--w:{w}px;--h:{h}px}}
{css}</style></head><body><div class="canvas">{body}</div></body></html>"""


# ---------------------------------------------------------------- types
def build_cover(spec):
    w, h = COVER_W, COVER_H
    lines = spec["title"] if isinstance(spec["title"], list) else spec["title"].split("|")
    t = "".join(f'<span class="ln">{esc(l)}</span>' for l in lines)
    eb = f'<div class="eyebrow">{esc(spec["eyebrow"])}</div>' if spec.get("eyebrow") else ""
    sub = f'<div class="subtitle">{esc(spec["subtitle"])}</div>' if spec.get("subtitle") else ""
    bg = wave_svg(w, h, 760, 330, 120, seed=spec.get("seed", 7))
    body = f'{bg}<div class="content cover-text">{eb}<div class="title">{t}</div><div class="rule"></div>{sub}</div>'
    return w, h, page(w, h, ["base.css", "cover.css"], body)


def header(spec):
    sub = f'<div class="sub">{esc(spec["subtitle"])}</div>' if spec.get("subtitle") else ""
    tag = f'<span class="tag">{esc(spec["tag"])}</span>' if spec.get("tag") else ""
    return f'<div class="hd"><div><h1>{esc(spec["title"])}</h1>{sub}<div class="rule"></div></div>{tag}</div>'


def footer(spec):
    return f'<div class="foot"><span class="dot"></span>{esc(spec["footer"])}</div>' if spec.get("footer") else ""


def diag_bg(seed):
    return wave_svg(DIAG_W, DIAG_H, 900, 840, 70, seed=seed, opacity=0.35, particles=False)


def build_pipeline(spec):
    steps = spec["steps"]
    per_row = spec.get("per_row", 4)
    rows = [steps[i:i + per_row] for i in range(0, len(steps), per_row)]
    cells = []
    n = 0
    for r, row in enumerate(rows):
        idxs = list(range(len(row)))
        order = idxs if r % 2 == 0 else idxs[::-1]  # snake layout
        placed = [None] * per_row
        for j, k in enumerate(idxs):
            col = order[j] if r % 2 == 0 else per_row - 1 - j
            placed[col] = (n + k, row[k])
        n += len(row)
        for col in range(per_row):
            if placed[col] is None:
                cells.append("<div></div>"); continue
            i, st = placed[col]
            last = i == len(steps) - 1
            if last: arrow = ""
            elif (i + 1) % per_row == 0: arrow = "arrow-d"
            else: arrow = "arrow-r" if r % 2 == 0 else "arrow-l"
            cls = "step " + arrow + (" amber" if st.get("accent") == "amber" else "")
            who = f'<span class="who">{esc(st["who"])}</span>' if st.get("who") else ""
            cells.append(f'<div class="{cls}">{who}<div class="no">{i+1}</div><div class="t">{esc(st["title"])}</div><div class="d">{esc(st.get("desc",""))}</div></div>')
    body = diag_bg(spec.get("seed", 3)) + f'<div class="content">{header(spec)}<div class="pipe">{"".join(cells)}</div></div>{footer(spec)}'
    return DIAG_W, DIAG_H, page(DIAG_W, DIAG_H, ["base.css", "diagram.css"], body)


def build_compare(spec):
    lb, la = spec.get("labels", ["脱敏前", "脱敏后"])
    parts = [f'<div class="colh"><span class="tag" style="border-color:var(--red);color:var(--red)">{esc(lb)}</span></div><div></div>'
             f'<div class="colh"><span class="tag green">{esc(la)}</span></div>']
    for row in spec["rows"]:
        parts.append(f'<div class="cell before">{kw(row["before"])}</div><div class="mid"><div class="ar"></div></div><div class="cell after">{kw(row["after"])}</div>')
    body = diag_bg(spec.get("seed", 4)) + f'<div class="content">{header(spec)}<div class="cmp">{"".join(parts)}</div></div>{footer(spec)}'
    return DIAG_W, DIAG_H, page(DIAG_W, DIAG_H, ["base.css", "diagram.css"], body)


def build_lanes(spec):
    lanes = spec["lanes"]
    cols = []
    for ln in lanes:
        items = "".join(f"<li>{esc(x)}</li>" for x in ln["items"])
        cls = "lane human" if ln.get("kind") == "human" else "lane"
        cols.append(f'<div class="{cls}"><div class="lh"><div class="ic">{esc(ln["icon"])}</div><div class="ln">{esc(ln["name"])}</div></div>'
                    f'<div class="role">{esc(ln.get("role",""))}</div><ul>{items}</ul></div>')
    grid = f'<div class="lanes" style="grid-template-columns:repeat({len(lanes)},1fr)">{"".join(cols)}</div>'
    body = diag_bg(spec.get("seed", 5)) + f'<div class="content">{header(spec)}{grid}</div>{footer(spec)}'
    return DIAG_W, DIAG_H, page(DIAG_W, DIAG_H, ["base.css", "diagram.css"], body)


def build_boundary(spec):
    def side(s, kind):
        its = []
        for it in s["items"]:
            text, cls = (it, "") if isinstance(it, str) else (it["text"], it.get("class", ""))
            its.append(f'<div class="it {cls}"><span class="ck">✓</span>{esc(text)}</div>')
        tag = f'<span class="tag{" amber" if kind=="human" else ""}">{esc(s["tag"])}</span>' if s.get("tag") else ""
        btn = f'<div class="btn">{esc(s["button"])}</div>' if s.get("button") else ""
        return f'<div class="side {kind}"><div class="sh"><span class="nm">{esc(s["name"])}</span>{tag}</div><div class="chain">{"".join(its)}</div>{btn}</div>'
    wall = f'<div class="wall"><div class="ln"></div><div class="lb">{esc(spec.get("wall","边界"))}</div><div class="ln"></div></div>'
    grid = f'<div class="bd" style="height:{spec.get("height",560)}px">{side(spec["left"],"bot")}{wall}{side(spec["right"],"human")}</div>'
    body = diag_bg(spec.get("seed", 6)) + f'<div class="content">{header(spec)}{grid}</div>{footer(spec)}'
    return DIAG_W, DIAG_H, page(DIAG_W, DIAG_H, ["base.css", "diagram.css"], body)


BUILDERS = {"cover": build_cover, "pipeline": build_pipeline, "compare": build_compare,
            "lanes": build_lanes, "boundary": build_boundary}


# ---------------------------------------------------------------- render
def chrome_bin():
    for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(b):
            return b
    sys.exit("no headless Chrome/Chromium found")


def render_html(html_str, w, h, out, keep_html=False):
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "page.html"
        src.write_text(html_str, encoding="utf-8")
        cmd = [chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
               "--force-device-scale-factor=1", f"--user-data-dir={td}/prof",
               f"--window-size={w},{h}", f"--screenshot={out}", "--virtual-time-budget=1500", src.as_uri()]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if keep_html:
            shutil.copy(src, out.with_suffix(".html"))
    try:  # verify / normalise exact size
        from PIL import Image
        im = Image.open(out)
        if im.size != (w, h):
            print(f"warn: chrome produced {im.size}, normalising to {w}x{h}", file=sys.stderr)
            canvas = Image.new("RGB", (w, h), (1, 9, 32))
            canvas.paste(im.crop((0, 0, min(w, im.width), min(h, im.height))), (0, 0))
            canvas.save(out)
    except ImportError:
        pass
    print(out)


def render_spec(spec, out, keep_html=False):
    w, h, doc = BUILDERS[spec["type"]](spec)
    render_html(doc, w, h, out, keep_html)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("cover"); c.add_argument("--title", required=True, help='use "|" to break lines')
    c.add_argument("--subtitle", default=""); c.add_argument("--eyebrow", default="")
    c.add_argument("--seed", type=int, default=7); c.add_argument("-o", "--out", default="cover.png")
    d = sp.add_parser("diagram"); d.add_argument("spec"); d.add_argument("-o", "--out", required=True)
    b = sp.add_parser("batch"); b.add_argument("dir"); b.add_argument("-o", "--out", required=True,
                                                                         help="article dir; each spec's 'output' is relative to it")
    for p in (c, d, b):
        p.add_argument("--keep-html", action="store_true", help="also write the intermediate .html")
    a = ap.parse_args()
    if a.cmd == "cover":
        render_spec({"type": "cover", "title": a.title, "subtitle": a.subtitle, "eyebrow": a.eyebrow, "seed": a.seed}, a.out, a.keep_html)
    elif a.cmd == "diagram":
        render_spec(json.loads(Path(a.spec).read_text(encoding="utf-8")), a.out, a.keep_html)
    else:
        for f in sorted(Path(a.dir).glob("*.json")):
            spec = json.loads(f.read_text(encoding="utf-8"))
            render_spec(spec, Path(a.out) / spec.get("output", f.stem + ".png"), a.keep_html)


if __name__ == "__main__":
    main()
