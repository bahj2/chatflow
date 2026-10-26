"""One-off codemod: hardcoded dark-only Tailwind colours -> theme tokens (light + dark)."""
import re
import sys
from pathlib import Path

SRC = Path("/app/frontend/src")
FILES = [p for p in list((SRC / "components").glob("*.jsx")) + list((SRC / "pages").glob("*.jsx"))
         if p.name not in {"TelegramDemo.jsx", "Demo.jsx"}]

PHRASES = [
    ("bg-emerald-500/10 text-emerald-400", "bg-primary/10 text-primary"),
    ("bg-emerald-500/[0.07] border-l-2 border-l-emerald-400", "bg-primary/[0.07] border-l-2 border-l-primary"),
    ("rounded-full bg-emerald-500 text-slate-950 text-[11px]", "rounded-full bg-brand text-white text-[11px]"),
    ("bg-emerald-500 text-slate-950", "btn-brand"),
    ("bg-white text-slate-900 py-3 font-semibold hover:bg-slate-200", "bg-white text-slate-900 py-3 font-semibold border border-border shadow-sm hover:bg-slate-50"),
    ("bg-white text-slate-950", "bg-foreground text-background"),
]

NEUTRAL = {
    "bg-[#0B0F17]": "bg-background", "bg-[#0B0F17]/70": "bg-background/70", "from-[#0B0F17]": "from-background",
    "via-[#0B0F17]/95": "via-background/95", "to-[#0B0F17]/60": "to-background/60", "bg-[#0D121C]": "bg-surface",
    "bg-[#0F1522]": "bg-card", "bg-[#121a2a]": "bg-card", "border-[#1c2230]": "border-border",
    "text-white": "text-foreground", "text-white/90": "text-foreground/90",
    "text-slate-100": "text-foreground", "text-slate-200": "text-foreground", "text-slate-300": "text-foreground/80",
    "text-slate-400": "text-muted-foreground", "text-slate-400/80": "text-muted-foreground/80",
    "text-slate-500": "text-muted-foreground/80", "text-slate-600": "text-muted-foreground/60", "text-slate-700": "text-muted-foreground/40",
    "border-white/5": "border-border/60", "border-white/10": "border-border", "border-white/15": "border-border", "border-white/20": "border-foreground/15",
    "divide-white/5": "divide-border/60", "bg-white/5": "bg-muted/60", "bg-white/10": "bg-muted",
    "bg-white/[0.02]": "bg-muted/30", "bg-white/[0.03]": "bg-muted/40", "bg-slate-900": "bg-muted/50", "bg-slate-800/80": "bg-muted",
    "hover:bg-emerald-400": "",
}
DUAL = {
    "text-emerald-400": ("text-emerald-600", "text-emerald-400"), "text-emerald-300": ("text-emerald-700", "text-emerald-300"),
    "text-amber-300": ("text-amber-700", "text-amber-300"), "text-amber-200": ("text-amber-800", "text-amber-200"),
    "text-amber-400": ("text-amber-600", "text-amber-400"), "text-red-400": ("text-red-600", "text-red-400"),
    "text-red-300": ("text-red-600", "text-red-300"), "text-sky-300": ("text-sky-700", "text-sky-300"),
    "text-sky-400": ("text-sky-600", "text-sky-400"), "text-rose-300": ("text-rose-600", "text-rose-300"),
    "text-indigo-200": ("text-indigo-700", "text-indigo-200"),
}
TOKEN = re.compile(r'(?<=[\s"\'`{])((?:[a-z0-9-]+:)*)([a-z]+-[^\s"\'`}]+)(?=[\s"\'`}])')


def sub(m):
    pre, tok = m.group(1), m.group(2)
    full = pre + tok
    if full in NEUTRAL:
        return NEUTRAL[full]
    if tok in NEUTRAL and NEUTRAL[tok]:
        return pre + NEUTRAL[tok]
    if tok in DUAL and "dark:" not in pre:
        light, dark = DUAL[tok]
        return f"{pre}{light} dark:{pre}{dark}"
    return m.group(0)


for p in FILES:
    src = p.read_text()
    out = src
    for a, b in PHRASES:
        out = out.replace(a, b)
    out = TOKEN.sub(sub, out)
    out = re.sub(r"bg-red-(500|600) text-foreground", r"bg-red-\1 text-white", out)
    out = re.sub(r'className="([^"]*)"', lambda m: 'className="' + " ".join(m.group(1).split()) + '"', out)
    if out != src:
        p.write_text(out)
        print("updated", p.name)
left = re.compile(r"(bg|text|border)-(\[#0[0-9A-Fa-f]{5}\]|slate-\d+|white(/\S+)?)")
for p in FILES:
    for i, line in enumerate(p.read_text().splitlines(), 1):
        for m in left.finditer(line):
            print(f"left {p.name}:{i} {m.group(0)}", file=sys.stderr)
