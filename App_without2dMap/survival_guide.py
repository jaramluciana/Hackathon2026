"""
survival_guide.py - The Hollow: Field Survival Guide
=====================================================

A standalone tkinter window that teaches residents two core skills:

  * Water   - an animated cross-section of a layered gravity filter
              (click a layer to inspect it, pour water through it, then boil it)
  * Fire    - seven interactive steps from the fire triangle to putting it out
  * Card    - a one-page quick card that can be saved as a text file

A toggle in the header switches every page between "Inside the Hollow"
and "On the Surface" advice.

Run on its own:
    python survival_guide.py

Open it from another tkinter app (e.g. tools_launcher.py):
    from survival_guide import open_survival_guide
    tk.Button(root, text="Survival guide",
              command=lambda: open_survival_guide(root)).pack()

Only the standard library is used (tkinter, math, random, re).
"""

import math
import random
import re
import tkinter as tk
from tkinter import filedialog, font as tkfont

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
BG = "#111317"
PANEL = "#1a1d23"
PANEL2 = "#242830"
HOVER = "#2f3440"
LINE = "#2a2f38"
TEXT = "#e7e2d6"
MUTED = "#8b919c"
ACCENT = "#e9a23b"
ACCENT_HI = "#f4b95c"
DANGER = "#e5604c"
OK = "#6cc58a"
CLEAR_WATER = "#5fb6ea"
MURKY = "#7a5730"
FLUSH_GRAY = "#59606a"
GLASS = "#7d97a8"
CANVAS_BG = "#0c0f13"
WOOD = "#8a6640"
WOOD_DARK = "#5e4128"
CHAR = "#2b2622"

TICK_MS = 33
CW, CH = 480, 580                     # canvas size used by both diagrams

FONT = {}                             # filled in by _init_fonts()


def _init_fonts(root):
    fams = set(tkfont.families(root))
    sans = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue",
                             "Inter", "DejaVu Sans", "Arial") if f in fams),
                "Helvetica")
    mono = next((f for f in ("Consolas", "Menlo", "JetBrains Mono",
                             "DejaVu Sans Mono") if f in fams), "Courier")
    FONT.update(
        title=(mono, 15, "bold"), sub=(mono, 9), tab=(sans, 10, "bold"),
        btn=(sans, 10, "bold"), h1=(sans, 15, "bold"), h2=(sans, 11, "bold"),
        body=(sans, 10), small=(sans, 9), tiny=(sans, 8),
        cv=(sans, 9), cvb=(sans, 9, "bold"), cvbig=(sans, 12, "bold"),
        mono=(mono, 9),
    )


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    """Blend two hex colours; t=0 -> c1, t=1 -> c2."""
    t = max(0.0, min(1.0, t))
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def round_rect(cv, x0, y0, x1, y1, r=8, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, **kw)


def draw_flame(cv, cx, by, intensity, rnd, tag="flame"):
    """Three flickering teardrop layers. intensity 0..1."""
    if intensity <= 0.01:
        return
    w = 24 + 92 * intensity
    h = 36 + 190 * intensity
    g = w * 1.05
    glow = cv.create_oval(cx - g, by - g * 0.4, cx + g, by + g * 0.12,
                          fill=mix(CANVAS_BG, "#3b1d08", min(0.6, intensity)),
                          outline="", tags=tag)
    cv.tag_lower(glow)
    for scale, col, lift in ((1.0, "#d9480f", 0), (0.7, "#f08c00", 4),
                             (0.42, "#ffd43b", 8)):
        ww, hh, b = w * scale, h * scale, by - lift

        def j(k):
            return rnd.uniform(-k, k) * ww
        pts = [cx, b + ww * 0.12,
               cx - ww * 0.5 + j(.04), b - hh * 0.12,
               cx - ww * 0.42 + j(.08), b - hh * 0.45,
               cx - ww * 0.16 + j(.10), b - hh * 0.78,
               cx + j(.12), b - hh,
               cx + ww * 0.16 + j(.10), b - hh * 0.75,
               cx + ww * 0.42 + j(.08), b - hh * 0.42,
               cx + ww * 0.5 + j(.04), b - hh * 0.1]
        cv.create_polygon(pts, smooth=True, fill=col, outline="", tags=tag)


def markup_to_plain(markup):
    out = []
    for line in markup.strip("\n").splitlines():
        line = line.strip()
        for p, rep in (("# ", ""), ("## ", ""), ("- ", "  * "), ("! ", "  !! "),
                       ("+ ", "  "), ("~ ", "  "), ("> ", "  ")):
            if line.startswith(p):
                line = rep + line[len(p):]
                break
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------
class FlatButton(tk.Label):
    """A label that behaves like a button; colours work on every platform."""
    KINDS = {"normal": (PANEL2, TEXT, HOVER),
             "accent": (ACCENT, "#1a1206", ACCENT_HI),
             "ghost": (BG, MUTED, PANEL)}

    def __init__(self, master, text, command=None, kind="normal", **kw):
        bg, fg, hov = self.KINDS[kind]
        super().__init__(master, text=text, bg=bg, fg=fg, padx=14, pady=7,
                         font=FONT["btn"], cursor="hand2", **kw)
        self._bg, self._fg, self._hov = bg, fg, hov
        self.command = command
        self.enabled = True
        self.bind("<Enter>", lambda e: self.enabled and self.configure(bg=self._hov))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))
        self.bind("<Button-1>", self._click)

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(fg=self._fg if on else mix(self._bg, self._fg, 0.35),
                       cursor="hand2" if on else "arrow")

    def set_kind(self, kind):
        self._bg, self._fg, self._hov = self.KINDS[kind]
        self.configure(bg=self._bg)
        self.set_enabled(self.enabled)

    def set_text(self, text):
        self.configure(text=text)


class Segmented(tk.Frame):
    """Row of FlatButtons bound to a StringVar; one is highlighted."""

    def __init__(self, master, options, variable, bg=BG):
        super().__init__(master, bg=bg)
        self.var = variable
        self.buttons = {}
        for value, label in options:
            b = FlatButton(self, label, command=lambda v=value: self.var.set(v))
            b.pack(side="left", padx=(0, 2))
            self.buttons[value] = b
        self._trace = self.var.trace_add("write", lambda *_: self._sync())
        self.bind("<Destroy>", self._on_destroy)
        self._sync()

    def _on_destroy(self, e):
        if e.widget is self and self._trace:
            self.var.trace_remove("write", self._trace)
            self._trace = None

    def _sync(self):
        for value, b in self.buttons.items():
            b.set_kind("accent" if value == self.var.get() else "normal")


class InfoPanel(tk.Frame):
    """Read-only rich text using a tiny line-prefix markup:
       '# ' h1, '## ' h2, '- ' bullet, '1. ' numbered, '! ' warning,
       '+ ' good, '~ ' muted, '> ' callout."""

    def __init__(self, master):
        super().__init__(master, bg=PANEL)
        self.text = tk.Text(self, bg=PANEL, fg=TEXT, relief="flat", bd=0,
                            wrap="word", padx=18, pady=14, highlightthickness=0,
                            cursor="arrow", font=FONT["body"])
        sb = tk.Scrollbar(self, command=self.text.yview, bg=PANEL,
                          troughcolor=PANEL, relief="flat", bd=0, width=10)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        t = self.text
        t.tag_configure("h1", font=FONT["h1"], foreground=ACCENT,
                        spacing1=4, spacing3=6)
        t.tag_configure("h2", font=FONT["h2"], foreground=TEXT,
                        spacing1=10, spacing3=3)
        t.tag_configure("body", spacing3=4)
        t.tag_configure("num", lmargin1=4, lmargin2=24, spacing3=4)
        t.tag_configure("bullet", lmargin1=6, lmargin2=24, spacing3=4)
        t.tag_configure("warn", foreground=DANGER, font=FONT["h2"],
                        lmargin1=4, lmargin2=24, spacing1=4, spacing3=6)
        t.tag_configure("ok", foreground=OK, spacing3=4)
        t.tag_configure("muted", foreground=MUTED, spacing3=4)
        t.tag_configure("callout", foreground=ACCENT_HI, background="#221d14",
                        lmargin1=10, lmargin2=10, rmargin=10,
                        spacing1=6, spacing3=6)
        t.tag_configure("gap", font=FONT["tiny"])

    def set(self, markup):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for raw in markup.strip("\n").splitlines():
            line = raw.strip()
            if not line:
                t.insert("end", "\n", "gap")
                continue
            tag, body = "body", line
            for prefix, name, deco in (("## ", "h2", ""), ("# ", "h1", ""),
                                       ("- ", "bullet", "•  "),
                                       ("! ", "warn", "⚠  "),
                                       ("+ ", "ok", "✓  "),
                                       ("~ ", "muted", ""),
                                       ("> ", "callout", "")):
                if line.startswith(prefix):
                    tag, body = name, deco + line[len(prefix):]
                    break
            else:
                if re.match(r"\d+\. ", line):
                    tag = "num"
            t.insert("end", body + "\n", tag)
        t.configure(state="disabled")
        t.yview_moveto(0)


# --------------------------------------------------------------------------
# Content: water
# --------------------------------------------------------------------------
# Listed top -> bottom, i.e. the order water flows through them.
LAYERS = [
    dict(name="Cloth pre-filter", h=16, texture="cloth", color="#c8b38a",
         depth="1 cloth, folded 2-4×", short="cloth",
         speed=2.4, wiggle=0.2, murk=(1.0, 0.86),
         does="Catches leaves, insects, grit and sludge before they clog the "
              "layers below. The cheapest layer to replace, so let it do the "
              "dirty work.",
         source="Bandana, T-shirt, sock or coffee filter. Use the tightest "
                "weave you have.",
         care="Rinse or swap after every batch."),
    dict(name="Coarse gravel", h=62, texture="gravel_big", color="#57534c",
         depth="about 5 cm", short="5 cm",
         speed=3.9, wiggle=0.9, murk=(0.86, 0.72),
         does="Spreads incoming water so it doesn't dig holes in the sand, and "
              "stops the largest particles.",
         source="Pebbles thumbnail-sized or larger. Rinse until the water "
                "runs clear.",
         care="Rinse when water starts pooling on top."),
    dict(name="Fine gravel", h=50, texture="gravel_small", color="#6b665e",
         depth="about 4 cm", short="4 cm",
         speed=3.3, wiggle=0.7, murk=(0.72, 0.56),
         does="Bridges the gap between big stones and sand so the sand can't "
              "wash down into the gravel.",
         source="Pea-sized stones or crushed rock, rinsed.",
         care="Rinse with the coarse gravel."),
    dict(name="Coarse sand", h=52, texture="sand_coarse", color="#a3804f",
         depth="about 4 cm", short="4 cm",
         speed=2.4, wiggle=0.45, murk=(0.56, 0.38),
         does="First real filtering layer: traps silt and the fine dirt that "
              "makes water look brown.",
         source="Builder's sand or river sand, washed several times.",
         care="Replace when flow slows to a trickle."),
    dict(name="Fine sand", h=62, texture="sand_fine", color="#d2b483",
         depth="8-10 cm (deepest)", short="8-10 cm",
         speed=1.8, wiggle=0.3, murk=(0.38, 0.18),
         does="The main filter. Fine grains trap clay and most of the "
              "cloudiness. More depth means clearer water, so make this the "
              "thickest layer.",
         source="Play sand or fine beach sand, rinsed well (rinse salt out "
                "of beach sand).",
         care="Scrape off and replace the top centimetre when it clogs."),
    dict(name="Activated charcoal", h=78, texture="charcoal", color="#1b1b1d",
         depth="about 6-8 cm", short="6-8 cm",
         speed=2.0, wiggle=0.5, murk=(0.18, 0.05),
         does="Soaks up many odours, off-tastes and some chemicals, and "
              "improves colour. It does not kill germs.",
         source="Crushed charcoal from a burnt-out hardwood fire, pea- to "
                "rice-sized. Rinse until the runoff is clear. Never use "
                "barbecue briquettes: they contain additives.",
         care="Wears out. Replace every few weeks of use, or when the taste "
              "comes back."),
    dict(name="Cotton / cloth plug", h=20, texture="cotton", color="#e3dfd6",
         depth="packed in the neck", short="plug",
         speed=1.6, wiggle=0.2, murk=(0.05, 0.03),
         does="Stops charcoal and sand from washing out of the spout.",
         source="Cotton balls, gauze or a tightly rolled strip of cloth.",
         care="Replace when it turns gray or slows the flow."),
]

WATER_GUIDE = """
# Build a gravity filter
~ The diagram reads top to bottom, the way water flows. You build it bottom up.
1. Cut the bottom off a 2-litre plastic bottle, or use any tall container with a small hole in the base. Turn it upside down with the cap off. The neck is the spout.
2. Push the cotton plug into the neck.
3. Add the layers from the bottom: charcoal, fine sand, coarse sand, fine gravel, coarse gravel. Press each one down lightly and leave space at the top.
4. Tie or lay the cloth pre-filter over the top.
5. Pour slowly so you don't dig craters in the layers. Throw away the first 2-3 batches: they wash out charcoal dust.
6. Still cloudy? Run it through a second time.

# Filtered is not safe
! This filter makes water clearer. It does NOT reliably remove bacteria, viruses or parasites, and it can't remove salt, heavy metals or fuel.
## Then disinfect. Pick one:
- Boil: a rolling boil for 1 minute (3 minutes above 2,000 m / 6,500 ft). Let it cool covered. This is the most reliable method.
- Bleach: plain, unscented household bleach (about 6%), 2 drops per litre or 8 drops per gallon. Stir and wait 30 minutes. It should smell faintly of chlorine. If it doesn't, add the same dose again and wait another 15 minutes.
- Purification tablets: follow the packet. Wait times range from 30 minutes to 4 hours.
- Sunlight (SODIS): a clear plastic bottle of filtered water in full sun for 6 hours, or 2 days if it's overcast. Surface only.
## Never drink
- Water that smells of fuel or chemicals or has an oily sheen. Filtering and boiling won't fix it.
- Seawater or brackish water.
- Snow or ice that hasn't been melted and boiled.
"""

WATER_ENV = {
    "hollow": """
# Inside the Hollow
- Best sources: condensation from cooling pipes and air ducts, and drip trays under seepage points.
- Treat sump and recycled water as contaminated. It can carry industrial runoff and metals that this filter can't remove, so use it only in an emergency and always boil it.
- There's no sunlight below ground, so SODIS won't work. Boil it or use chemicals.
- An open flame burns your level's oxygen. Boil on electric heat, or in a vented burn chamber.
> When a level's water system drops below 80%, residents start to lose health. One filter per household buys time while engineers repair the mains.
""",
    "surface": """
# On the surface
- Choose running water over still water, and collect upstream of camps and animals.
- Rain caught on a clean tarp is the safest wild source. Disinfect it anyway.
- Keep latrines at least 60 m (200 ft) from any water source.
- Muddy water: let it settle for 30 minutes and pour off the top before filtering. This makes the filter last longer.
- Water near ruined cities and industry can hold fuel or chemicals. If it smells wrong, don't drink it.
> Carry two containers: one marked DIRTY, one marked CLEAN. Never mix them.
""",
}


# --------------------------------------------------------------------------
# Content: fire
# --------------------------------------------------------------------------
LAYS = {
    "teepee": ("Teepee", """
## Teepee
- Tinder in the centre, with kindling leaned around it in a cone.
- Leave a gap facing the wind so you can reach in and light it.
- Burns fast and hot, which makes it the best lay for getting started. It collapses into a good bed of coals.
"""),
    "cabin": ("Log cabin", """
## Log cabin
- Build a small teepee, then stack sticks around it in crossed square layers, like a cabin.
- Stable and long-burning, with a flat top that's good for a pot.
- Slower to catch, so make sure the inner teepee is well built.
"""),
    "leanto": ("Lean-to", """
## Lean-to
- Lay a big log on the windward side, or push a green stick into the ground at an angle.
- Put the tinder in its shelter and lean kindling over it from the downwind side.
- Best in wind or light rain: the log takes the weather.
"""),
}

METHODS = {
    "lighter": ("Lighter / matches", """
## Lighter or matches
- Kneel with your back to the wind and cup the flame.
- Light the tinder low, on the windward side, so the flame climbs into it.
- Keep matches in a waterproof container. A cold lighter works better after warming in your pocket.
"""),
    "ferro": ("Ferro rod", """
## Ferro rod
- Put the rod's tip right in the tinder. Hold the striker still against it and pull the rod back.
- This sends sparks into the tinder without knocking the bundle over.
- Works when wet and lasts thousands of strikes. It needs fine, fluffy tinder.
"""),
    "bowdrill": ("Bow drill", """
## Bow drill
- Use a dry softwood board and spindle (cedar, willow, basswood, cottonwood). Cut a V-notch beside a shallow socket.
- Press down on the spindle with a bearing block and saw the bow in long, steady strokes until the dust smokes and forms a glowing coal.
- Tip the coal into a tinder bundle, fold it closed and blow gently until it flames.
! The hardest method. Practise it before you need it.
"""),
    "battery": ("Battery + steel wool", """
## Battery and steel wool
- Touch both terminals of a 9 V battery to fine (0000) steel wool. It glows straight away.
- Press the glowing wool into the tinder and blow gently.
! Pack steel wool and batteries separately. They can catch fire in a bag.
"""),
}

FIRE_STEPS = [
    dict(title="The fire triangle", body="""
# The fire triangle
Fire needs three things at once: HEAT, FUEL and OXYGEN. Take any one away and it dies.
- Starting a fire means bringing all three together in the right order.
- Putting one out means taking one away: water removes heat, dirt or a lid cuts off oxygen, and pulling logs apart removes fuel.
~ Try it: click a side of the triangle to remove it.
""", hollow="""
> In the Hollow, every fire draws on your level's oxygen. In a sealed space, an open flame competes with the people breathing.
""", surface="""
> Wind is extra oxygen. It helps a small fire catch and spreads a big one out of control.
"""),
    dict(title="Pick & clear the site", body="", hollow="""
# Inside the Hollow: vented chamber only
- Burn only in a designated vented burn chamber. Never in quarters, corridors or farm decks.
- The exhaust fan must be running before you light. No fan, no fire.
- Keep a working CO alarm inside and an extinguisher by the door.
- Stay at least 3 m from oxygen lines, fuel stores and cables.
! Carbon monoxide has no smell. Headache, dizziness, nausea or confusion means everyone leaves for fresh air immediately.
> When a level's oxygen falls below 50%, residents start to lose health. Don't add to the deficit.
""", surface="""
# On the surface: pick and clear the site
- Choose bare ground or rock, sheltered from strong wind and away from tents and gear.
- Clear a circle about 3 m (10 ft) across down to bare soil.
- Look up: no overhanging branches. Avoid roots and peat, which can let fire creep underground and come back up later.
- Ring the pit with dry rocks. Don't use rocks from rivers: trapped water can make them crack or burst when heated.
- Have water or a pile of dirt and a shovel within reach before you light anything.
"""),
    dict(title="Gather three sizes", body="""
# Gather three sizes of fuel
- Tinder catches from a spark or match: dry grass, birch bark, cattail fluff, dry pine needles, wood shavings, dryer lint, cotton balls with petroleum jelly, char cloth.
- Kindling is pencil-lead to thumb thick: dead twigs that snap cleanly.
- Fuel is wrist-thick and up. Dead standing wood is drier than wood lying on the ground.
- Gather everything before you light, about twice as much as you think you need.
- Wet weather: split wood to reach the dry core, or carve feather sticks (thin curls shaved along a stick).
""", hollow="""
> Hollow tinder: scrap paper, cardboard, lint, cotton rags. Fuel: approved scrap wood or fuel tablets only. Never burn plastic, foam, insulation or treated wood, because the smoke is toxic.
""", surface="""
> Test kindling by snapping it. A crisp snap means it's dry; if it bends, leave it.
"""),
    dict(title="Build the lay", body="""
# Build the lay
Choose a structure below. They all follow one rule: tinder in the middle, with kindling arranged so the flame can climb into it and air can get underneath.
""", hollow="""
> In a burn chamber, keep the fire small. A teepee no taller than your forearm is plenty.
""", surface="""
> Build the lay with its open side facing into the wind.
"""),
    dict(title="Light it", body="""
# Light it
Pick a method below and press Light it.
""", hollow="""
> In the Hollow, check that the exhaust fan is running and the CO alarm is green before you strike.
""", surface="""
> Carry at least two ways to light a fire. Matches get wet and lighters run dry.
"""),
    dict(title="Feed it", body="""
# Feed it, small to big
- Blow gently at the base of a young fire. Steady air helps; a hard blow scatters it.
- Add kindling a few pieces at a time. Move to bigger sizes only once the smaller ones are burning well.
- Too much fuel too soon smothers the fire.
- Never leave a fire unattended. A small fire you can sit close to beats a bonfire.
~ Try it: use the buttons under the diagram to add kindling, add a log or blow.
""", hollow="""
> In the Hollow, a bigger fire is not a better one. It burns more of your level's oxygen and makes more smoke.
""", surface="""
> Keep the fuel pile upwind and at least a step back from the fire.
"""),
    dict(title="Put it out", body="""
# Put it out: drown, stir, feel
1. Drown: pour water over all the embers, not just the red ones, until the hissing stops.
2. Stir: mix the ash and embers with a stick to expose hidden coals, then drown it again.
3. Feel: hold the back of your hand close to the ashes. If it's too hot to touch, it's too hot to leave.
- No water? Use dirt or sand and stir. Don't just bury it: buried coals can smoulder for hours.
""", hollow="""
> Use the chamber extinguisher on anything bigger than embers, and leave the exhaust fan running for at least 15 minutes afterwards.
""", surface="""
> Scatter the cold ashes and put back what you moved. Leave the site the way you found it.
"""),
]

CARD = {
    "water": """
# Water in 60 seconds
1. Collect: running water, rain, condensation. Never water that smells of fuel or chemicals.
2. Settle: let mud sink for 30 minutes, then pour off the top.
3. Filter: cloth, gravel, sand, charcoal. Throw away the first batches.
4. Disinfect: a rolling boil for 1 minute (3 above 2,000 m), or 2 drops of unscented 6% bleach per litre and wait 30 minutes.
5. Store it covered in clean containers, and label treated and untreated water.
! Clear water is not safe water.
""",
    "fire": """
# Fire in 60 seconds
1. Site: cleared, sheltered, nothing overhead, water ready.
2. Gather tinder, kindling and fuel: twice what you think.
3. Build a teepee around the tinder, with the gap facing the wind.
4. Light it low on the windward side, and blow gently at the base.
5. Feed it small to big. Don't smother a young fire.
6. Put it out: drown, stir, drown, feel. It must be cold before you leave.
! Never burn in an unventilated space. Carbon monoxide kills silently.
""",
    "hollow": """
## Inside the Hollow
- Fire only in a vented burn chamber, with the fan on, a CO alarm and an extinguisher.
- Water: condensation and drip trays first. Always boil sump water.
- CO alarm sounds: get out, shut the door and report to your level engineer.
""",
    "surface": """
## On the surface
- Rain on a clean tarp is the safest water. Disinfect it anyway.
- Latrines at least 60 m from water. Tents upwind of the fire.
- Shelter, water, fire, food: in that order.
""",
}


# --------------------------------------------------------------------------
# Water tab
# --------------------------------------------------------------------------
class WaterTab:
    X0, X1 = 120, 300
    CX = 210
    TOP = 70
    LAYER_TOP = 104
    JAR = (165, 508, 255, 574)
    POT_CX = 390

    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=BG)

        left = tk.Frame(self.frame, bg=BG)
        left.pack(side="left", fill="y", padx=(18, 10), pady=12)
        self.cv = tk.Canvas(left, width=CW, height=CH, bg=CANVAS_BG,
                            highlightthickness=1, highlightbackground=LINE)
        self.cv.pack()
        ctrl = tk.Frame(left, bg=BG)
        ctrl.pack(fill="x", pady=(10, 0))
        self.b_pour = FlatButton(ctrl, "Pour water", self.pour, kind="accent")
        self.b_empty = FlatButton(ctrl, "Empty jar", self.empty_jar)
        self.b_boil = FlatButton(ctrl, "Boil it", self.boil)
        self.b_reset = FlatButton(ctrl, "Reset", self.reset, kind="ghost")
        for b in (self.b_pour, self.b_empty, self.b_boil, self.b_reset):
            b.pack(side="left", padx=(0, 6))
        self.status = tk.Label(left, bg=BG, fg=MUTED, font=FONT["small"],
                               wraplength=CW, justify="left", anchor="w")
        self.status.pack(fill="x", pady=(8, 0))

        right = tk.Frame(self.frame, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(10, 18), pady=12)
        self._build_inspector(right)
        self.info = InfoPanel(right)
        self.info.pack(fill="both", expand=True, pady=(10, 0))

        y = self.LAYER_TOP
        for L in LAYERS:
            L["y0"], L["y1"] = y, y + L["h"]
            y += L["h"]
        self.LB = y                                    # bottom of the layers
        self.SPOUT = self.LB + 48
        self.rnd = random.Random()
        self._draw_static()
        self.refresh_info()
        self.reset()

    # ---- right-hand inspector -------------------------------------------
    def _build_inspector(self, parent):
        card = tk.Frame(parent, bg=PANEL, padx=18, pady=14)
        card.pack(fill="x")
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x")
        self.swatch = tk.Canvas(top, width=38, height=38, bg=PANEL,
                                highlightthickness=0)
        self.swatch.pack(side="left", padx=(0, 12))
        names = tk.Frame(top, bg=PANEL)
        names.pack(side="left", fill="x")
        self.i_name = tk.Label(names, bg=PANEL, fg=ACCENT, font=FONT["h1"],
                               anchor="w")
        self.i_name.pack(fill="x")
        self.i_depth = tk.Label(names, bg=PANEL, fg=MUTED, font=FONT["small"],
                                anchor="w")
        self.i_depth.pack(fill="x")
        self.i_rows = {}
        for key, label in (("does", "WHAT IT DOES"), ("source", "WHERE TO GET IT"),
                           ("care", "UPKEEP")):
            tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=FONT["tiny"],
                     anchor="w").pack(fill="x", pady=(10, 0))
            v = tk.Label(card, bg=PANEL, fg=TEXT, font=FONT["body"], anchor="w",
                         justify="left", wraplength=560)
            v.pack(fill="x")
            self.i_rows[key] = v
        card.bind("<Configure>", lambda e: [
            v.configure(wraplength=max(200, e.width - 40))
            for v in self.i_rows.values()])
        self.show_layer(None)

    def show_layer(self, i):
        self.swatch.delete("all")
        if i is None:
            self.i_name.configure(text="Layer inspector")
            self.i_depth.configure(text="Click any layer in the diagram")
            self.i_rows["does"].configure(
                text="Each layer removes smaller dirt than the one above it: "
                     "big particles at the top, fine silt and taste lower down.")
            self.i_rows["source"].configure(
                text="Everything can be scavenged: a bottle, cloth, stones, "
                     "sand and charcoal from an old fire.")
            self.i_rows["care"].configure(
                text="Rinse the top layers often. Replace sand and charcoal "
                     "when the flow slows or the taste returns.")
            round_rect(self.swatch, 3, 3, 35, 35, 8, fill=PANEL2, outline=LINE)
            return
        L = LAYERS[i]
        self.i_name.configure(text=L["name"])
        self.i_depth.configure(text="Layer %d of %d  ·  %s"
                               % (i + 1, len(LAYERS), L["depth"]))
        for k in ("does", "source", "care"):
            self.i_rows[k].configure(text=L[k])
        round_rect(self.swatch, 3, 3, 35, 35, 8, fill=L["color"], outline=GLASS)

    def refresh_info(self):
        self.info.set(WATER_ENV[self.app.env.get()] + "\n" + WATER_GUIDE)

    # ---- static diagram -------------------------------------------------
    def _draw_static(self):
        cv, X0, X1, CX = self.cv, self.X0, self.X1, self.CX

        # jug + label
        cv.create_text(16, 22, anchor="w", text="DIRTY WATER IN",
                       fill=MUTED, font=FONT["cvb"])
        cv.create_polygon(136, 18, 194, 30, 186, 64, 128, 52, fill="#33404b",
                          outline=GLASS, width=2)
        cv.create_polygon(194, 30, 214, 40, 206, 50, 188, 46, fill="#33404b",
                          outline=GLASS, width=2)
        cv.create_polygon(140, 40, 190, 48, 186, 62, 130, 51, fill=MURKY,
                          outline="")
        self.stream = cv.create_line(210, 48, 214, self.TOP + 10, fill=MURKY,
                                     width=5, capstyle="round", state="hidden")

        # flow arrow
        cv.create_line(30, self.LAYER_TOP, 30, self.LB, fill=LINE, width=3,
                       arrow="last", arrowshape=(12, 14, 6))
        cv.create_text(48, (self.LAYER_TOP + self.LB) / 2, angle=90,
                       text="WATER FLOWS DOWN", fill=MUTED, font=FONT["tiny"])

        # dirty water standing on top
        cv.create_rectangle(X0, self.TOP + 8, X1, self.LAYER_TOP, fill=MURKY,
                            outline="")
        for k in range(6):
            x = X0 + 14 + k * 28
            cv.create_line(x, self.TOP + 14, x + 14, self.TOP + 14,
                           fill="#94703f", width=2)

        # layers
        for i, L in enumerate(LAYERS):
            self._texture(i, L)
            mid = (L["y0"] + L["y1"]) / 2
            tags = ("layer", "layer%d" % i, "lbl%d" % i)
            cv.create_line(X1 + 6, mid, X1 + 16, mid, fill=LINE, width=2,
                           tags=("layer", "layer%d" % i))
            cv.create_text(X1 + 20, mid, anchor="w", text=L["name"], fill=TEXT,
                           font=FONT["cv"], tags=tags)
            cv.create_text(X0 - 8, mid, anchor="e", text=L["short"], fill=MUTED,
                           font=FONT["tiny"], tags=("layer", "layer%d" % i))
            cv.create_line(X0 - 4, L["y1"], X0, L["y1"], fill=LINE)
            cv.tag_bind("layer%d" % i, "<Button-1>",
                        lambda e, i=i: self.select(i))
            cv.tag_bind("layer%d" % i, "<Enter>", lambda e, i=i: self.hover(i))
            cv.tag_bind("layer%d" % i, "<Leave>", lambda e: self.hover(None))

        # glass column + neck
        cv.create_rectangle(X0 - 4, self.TOP, X1 + 4, self.LB, outline=GLASS,
                            width=2)
        cv.create_line(X0 + 4, self.TOP + 10, X0 + 4, self.LB - 10,
                       fill="#3e5463", width=2)
        n = self.LB
        cv.create_polygon(X0 - 4, n, X1 + 4, n, CX + 16, n + 34, CX + 16, n + 48,
                          CX - 16, n + 48, CX - 16, n + 34, fill="#0f161c",
                          outline=GLASS, width=2)

        # jar
        jx0, jy0, jx1, jy1 = self.JAR
        self.jar_water = cv.create_rectangle(jx0 + 2, jy1, jx1 - 2, jy1,
                                             fill=CLEAR_WATER, outline="")
        cv.create_line(jx0, jy0, jx0, jy1, jx1, jy1, jx1, jy0, fill=GLASS,
                       width=2)
        cv.create_line(jx0 - 5, jy0, jx0 + 6, jy0, fill=GLASS, width=2)
        cv.create_line(jx1 - 6, jy0, jx1 + 5, jy0, fill=GLASS, width=2)
        self.jar_badge_bg = round_rect(cv, 14, 526, 154, 556, 8, fill=DANGER,
                                       outline="", state="hidden")
        self.jar_badge = cv.create_text(84, 541, text="", fill="#1a0b08",
                                        font=FONT["cvb"], state="hidden")

        # pot on a small fire
        px = self.POT_CX
        cv.create_line(self.JAR[2] + 6, 534, px - 60, 516, fill=MUTED, dash=(4, 3),
                       arrow="last", width=2)
        self.pot_title = cv.create_text(px, 462, text="THEN BOIL",
                                        fill=MUTED, font=FONT["cvb"],
                                        tags="pottext")
        self.pot_sub = cv.create_text(px, 480, text="1 min rolling boil",
                                      fill=MUTED, font=FONT["tiny"],
                                      tags="pottext")
        cv.create_line(px - 45, 572, px + 45, 562, fill=WOOD_DARK, width=7,
                       capstyle="round", tags="potlogs")
        cv.create_line(px - 45, 562, px + 45, 572, fill=WOOD, width=7,
                       capstyle="round", tags="potlogs")
        round_rect(cv, px - 55, 494, px + 55, 538, 8, fill="#59606b",
                   outline="#8a919c", width=2, tags="pot")
        cv.create_line(px - 62, 494, px + 62, 494, fill="#9aa1ab", width=4,
                       capstyle="round", tags="pot")
        cv.create_rectangle(px - 70, 502, px - 55, 508, fill="#3a3f47",
                            outline="", tags="pot")
        cv.create_rectangle(px + 55, 502, px + 70, 508, fill="#3a3f47",
                            outline="", tags="pot")

        # selection + hover outlines (kept on top)
        self.sel = cv.create_rectangle(0, 0, 0, 0, outline=ACCENT, width=3,
                                       state="hidden")
        self.hov = cv.create_rectangle(0, 0, 0, 0, outline=ACCENT_HI, width=1,
                                       dash=(3, 3), state="hidden")

    def _texture(self, i, L):
        cv, x0, x1 = self.cv, self.X0, self.X1
        y0, y1 = L["y0"], L["y1"]
        tag = ("layer", "layer%d" % i)
        r = random.Random(i * 7 + 3)
        cv.create_rectangle(x0, y0, x1, y1, fill=L["color"], outline="", tags=tag)
        t = L["texture"]
        if t == "cloth":
            for x in range(x0, x1, 6):
                cv.create_line(x, y0, x, y1, fill="#a8946c", tags=tag)
            for y in range(y0 + 3, y1, 5):
                cv.create_line(x0, y, x1, y, fill="#ddc9a0", tags=tag)
        elif t.startswith("gravel"):
            big = t == "gravel_big"
            n, (rmin, rmax) = (70, (7, 12)) if big else (170, (3, 6))
            shades = ["#6d685f", "#4a4741", "#807a6f", "#5c574f", "#8e877a"]
            for _ in range(n):
                rr = r.uniform(rmin, rmax)
                cx = r.uniform(x0 + rr, x1 - rr)
                cy = r.uniform(y0 + rr * 0.75, y1 - rr * 0.75)
                cv.create_oval(cx - rr, cy - rr * 0.75, cx + rr, cy + rr * 0.75,
                               fill=r.choice(shades), outline="#2d2b27", tags=tag)
        elif t.startswith("sand"):
            coarse = t == "sand_coarse"
            n, s = (420, 1.7) if coarse else (650, 1.1)
            shades = (["#8f6d43", "#c9a271", "#7d5d38", "#dcc093"] if coarse
                      else ["#b9996a", "#e3cb9c", "#c6a878", "#f0dcb4"])
            for _ in range(n):
                cx, cy = r.uniform(x0 + 2, x1 - 2), r.uniform(y0 + 2, y1 - 2)
                cv.create_oval(cx - s, cy - s, cx + s, cy + s,
                               fill=r.choice(shades), outline="", tags=tag)
        elif t == "charcoal":
            shades = ["#2a2a2e", "#38383e", "#1f1f22", "#45454c"]
            for _ in range(60):
                rr = r.uniform(4, 10)
                cx = r.uniform(x0 + rr, x1 - rr)
                cy = r.uniform(y0 + rr * 0.8, y1 - rr * 0.8)
                k = r.randint(5, 6)
                pts = []
                for a in range(k):
                    ang = 2 * math.pi * a / k + r.uniform(-0.3, 0.3)
                    d = rr * r.uniform(0.6, 1.0)
                    pts += [cx + d * math.cos(ang), cy + d * math.sin(ang) * 0.8]
                cv.create_polygon(pts, fill=r.choice(shades), outline="#0b0b0c",
                                  tags=tag)
            for _ in range(40):
                cx, cy = r.uniform(x0 + 2, x1 - 2), r.uniform(y0 + 2, y1 - 2)
                cv.create_oval(cx - 1, cy - 1, cx + 1, cy + 1, fill="#6a6a75",
                               outline="", tags=tag)
        elif t == "cotton":
            for _ in range(45):
                rr = r.uniform(2, 5)
                cx = r.uniform(x0 + rr, x1 - rr)
                cy = r.uniform(y0 + rr, y1 - rr)
                cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                               fill=r.choice(["#ffffff", "#d6d1c6", "#f1eee8"]),
                               outline="", tags=tag)

    # ---- interaction ----------------------------------------------------
    def _layer_box(self, i):
        L = LAYERS[i]
        return self.X0 - 2, L["y0"] + 1, self.X1 + 2, L["y1"] - 1

    def select(self, i):
        self.cv.coords(self.sel, *self._layer_box(i))
        self.cv.itemconfigure(self.sel, state="normal")
        self.cv.tag_raise(self.sel)
        for k in range(len(LAYERS)):
            self.cv.itemconfigure("lbl%d" % k, fill=ACCENT if k == i else TEXT)
        self.show_layer(i)

    def hover(self, i):
        if i is None:
            self.cv.itemconfigure(self.hov, state="hidden")
            self.cv.configure(cursor="")
            return
        self.cv.coords(self.hov, *self._layer_box(i))
        self.cv.itemconfigure(self.hov, state="normal")
        self.cv.tag_raise(self.hov)
        self.cv.configure(cursor="hand2")

    def say(self, msg):
        self.status.configure(text=msg)

    def reset(self):
        self.cv.delete("drop", "steam")
        self.drops = []
        self.steam = []
        self.pour_left = 0
        self.pouring = False
        self.runs = 0
        self.jar_level = 0.0
        self.jar_state = "empty"        # empty | flush | filtered
        self.boil_t = -1
        self.safe = False
        self.flush_run = False
        self.cv.delete("potflame")
        self.cv.itemconfigure(self.stream, state="hidden")
        self.cv.itemconfigure(self.pot_title, text="THEN BOIL", fill=MUTED)
        self.cv.itemconfigure(self.pot_sub, text="1 min rolling boil", fill=MUTED)
        self._update_jar()
        self.say("Click a layer to inspect it, then press Pour water.")
        self._sync_buttons()

    def _sync_buttons(self):
        busy = self.pouring or self.boil_t >= 0
        self.b_pour.set_enabled(not busy)
        self.b_empty.set_enabled(not busy and self.jar_level > 0)
        self.b_boil.set_enabled(not busy and self.jar_state == "filtered"
                                and self.jar_level >= 18)

    def pour(self):
        self.flush_run = self.runs == 0
        self.pour_left = 120
        self.pouring = True
        self.safe = False
        self.cv.itemconfigure(self.stream, state="normal")
        self.cv.itemconfigure(self.pot_title, text="THEN BOIL", fill=MUTED)
        self.cv.itemconfigure(self.pot_sub, text="1 min rolling boil", fill=MUTED)
        self.say("Pouring slowly onto the cloth so the layers aren't disturbed…")
        self._sync_buttons()

    def empty_jar(self):
        self.jar_level = 0
        self.jar_state = "empty"
        self._update_jar()
        self.say("Jar emptied. Pour again." if self.runs else "Jar emptied.")
        self._sync_buttons()

    def boil(self):
        self.boil_t = 0
        self.jar_level = 0
        self.jar_state = "empty"
        self._update_jar()
        msg = "Rolling boil for one full minute (3 minutes above 2,000 m)…"
        if self.app.env.get() == "hollow":
            msg += "  In the Hollow: use electric heat or a vented burn chamber."
        self.say(msg)
        self._sync_buttons()

    def _murk_at(self, y):
        if y < self.LAYER_TOP:
            return 1.0
        for L in LAYERS:
            if y < L["y1"]:
                t = (y - L["y0"]) / L["h"]
                a, b = L["murk"]
                return a + (b - a) * t
        return LAYERS[-1]["murk"][1]

    def _drop_color(self, y):
        target = FLUSH_GRAY if self.flush_run else CLEAR_WATER
        return mix(MURKY, target, 1 - self._murk_at(y))

    def _update_jar(self):
        jx0, jy0, jx1, jy1 = self.JAR
        lvl = min(self.jar_level, jy1 - jy0 - 6)
        self.cv.coords(self.jar_water, jx0 + 2, jy1 - lvl, jx1 - 2, jy1 - 1)
        col = {"flush": FLUSH_GRAY, "filtered": CLEAR_WATER}.get(self.jar_state,
                                                                CLEAR_WATER)
        self.cv.itemconfigure(self.jar_water, fill=col)
        if self.jar_level <= 0:
            state = "hidden"
        else:
            state = "normal"
            txt = ("FLUSH – DUMP IT" if self.jar_state == "flush"
                   else "FILTERED ≠ SAFE")
            self.cv.itemconfigure(self.jar_badge, text=txt)
            self.cv.itemconfigure(self.jar_badge_bg,
                                  fill=FLUSH_GRAY if self.jar_state == "flush"
                                  else DANGER)
        self.cv.itemconfigure(self.jar_badge, state=state)
        self.cv.itemconfigure(self.jar_badge_bg, state=state)

    def tick(self):
        cv, rnd = self.cv, self.rnd
        # spawn
        if self.pour_left > 0:
            self.pour_left -= 1
            if self.pour_left % 3 == 0:
                x = rnd.uniform(self.X0 + 8, self.X1 - 8)
                y = self.LAYER_TOP - 10
                d = dict(x=x, y=y, v=0.0, ph=rnd.uniform(0, 6.28),
                         id=cv.create_oval(0, 0, 0, 0, outline="", tags="drop"))
                self.drops.append(d)
            if self.pour_left == 0:
                cv.itemconfigure(self.stream, state="hidden")
        # move
        surface = self.JAR[3] - min(self.jar_level, 60)
        for d in self.drops[:]:
            y = d["y"]
            if y < self.LAYER_TOP:
                d["y"] += 3.0
            elif y < self.LB:
                L = next(L for L in LAYERS if y < L["y1"])
                d["ph"] += 0.25
                d["x"] += math.sin(d["ph"]) * L["wiggle"]
                d["x"] = max(self.X0 + 3, min(self.X1 - 3, d["x"]))
                d["y"] += L["speed"]
            elif y < self.SPOUT:
                frac = (y - self.LB) / (self.SPOUT - self.LB)
                d["x"] += (self.CX - d["x"]) * (0.12 + 0.3 * frac)
                d["y"] += 3.0
            else:
                d["x"] = self.CX
                d["v"] = min(d["v"] + 0.6, 9)
                d["y"] += d["v"]
                if d["y"] >= surface:
                    cv.delete(d["id"])
                    self.drops.remove(d)
                    self.jar_level += 0.9
                    new = "flush" if self.flush_run else "filtered"
                    if self.jar_state != "flush":
                        self.jar_state = new
                    self._update_jar()
                    continue
            x, y = d["x"], d["y"]
            cv.coords(d["id"], x - 3, y - 4, x + 3, y + 4)
            cv.itemconfigure(d["id"], fill=self._drop_color(y))
        # pour finished
        if self.pouring and self.pour_left == 0 and not self.drops:
            self.pouring = False
            self.runs += 1
            if self.jar_state == "flush" and self.flush_run:
                self.say("Flush run: the first water out carries charcoal dust "
                         "and fine sand, so it comes out gray. Empty the jar "
                         "and pour again.")
            elif self.jar_state == "flush":
                self.say("This jar still has gray flush water in it. Empty it "
                         "first, then pour again.")
            else:
                self.say("Clearer, but filtering doesn't kill germs. Press "
                         "Boil it.")
            self._sync_buttons()
        # boiling
        if self.boil_t >= 0:
            self._tick_boil()
        self._tick_steam()

    def _tick_boil(self):
        cv, rnd, px = self.cv, self.rnd, self.POT_CX
        self.boil_t += 1
        total = 150
        cv.delete("potflame")
        if self.boil_t < total:
            draw_flame(cv, px, 566, 0.2 + rnd.uniform(-0.03, 0.03), rnd,
                       tag="potflame")
            cv.tag_raise("potlogs")
            cv.tag_raise("pot")
            secs = max(0, 60 - int(60 * self.boil_t / total))
            cv.itemconfigure(self.pot_title, text="BOILING", fill=ACCENT)
            cv.itemconfigure(self.pot_sub, text="0:%02d left (sped up)" % secs,
                             fill=ACCENT_HI)
            if self.boil_t % 2 == 0:
                x = rnd.uniform(px - 48, px + 48)
                s = cv.create_oval(0, 0, 0, 0, outline="", tags="steam")
                self.steam.append(dict(id=s, x=x, y=492.0, life=0))
        elif self.boil_t == total:
            self.boil_t = -1
            self.safe = True
            cv.itemconfigure(self.pot_title, text="SAFE ✓", fill=OK)
            cv.itemconfigure(self.pot_sub, text="cool it, keep it covered",
                             fill=OK)
            self.say("Safe to drink once it has cooled. Store it covered in a "
                     "clean container, apart from untreated water.")
            self._sync_buttons()

    def _tick_steam(self):
        cv, rnd = self.cv, self.rnd
        for s in self.steam[:]:
            s["life"] += 1
            s["y"] -= 1.1
            s["x"] += rnd.uniform(-0.6, 0.6)
            if s["life"] > 16:
                cv.delete(s["id"])
                self.steam.remove(s)
                continue
            r = 1.5 + s["life"] * 0.12
            cv.coords(s["id"], s["x"] - r, s["y"] - r, s["x"] + r, s["y"] + r)
            cv.itemconfigure(s["id"],
                             fill=mix("#c9d4dc", CANVAS_BG, s["life"] / 16))
        cv.tag_raise("pottext")


# --------------------------------------------------------------------------
# Fire tab
# --------------------------------------------------------------------------
class FireTab:
    LAY_CX, LAY_BY = 240, 478

    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=BG)
        self.rnd = random.Random()
        self.step = 0
        self.lay = tk.StringVar(value="teepee")
        self.method = tk.StringVar(value="ferro")
        self.lay.trace_add("write", lambda *_: self.render())
        self.method.trace_add("write", lambda *_: self.render())
        self.tri = {"heat": True, "fuel": True, "oxygen": True}
        self.intensity = 0.0
        self.logs = 0
        self.lit = False
        self.anim = None
        self.particles = []
        self.fan_angle = 0.0
        self.flame = None
        self.out_stage = 0
        self.embers = 0.0

        left = tk.Frame(self.frame, bg=BG)
        left.pack(side="left", fill="y", padx=(18, 10), pady=12)
        self.cv = tk.Canvas(left, width=CW, height=CH, bg=CANVAS_BG,
                            highlightthickness=1, highlightbackground=LINE)
        self.cv.pack()
        self.opt_row = tk.Frame(left, bg=BG)
        self.opt_row.pack(fill="x", pady=(10, 0))
        self.status = tk.Label(left, bg=BG, fg=MUTED, font=FONT["small"],
                               wraplength=CW, justify="left", anchor="w")
        self.status.pack(fill="x", pady=(8, 0))

        right = tk.Frame(self.frame, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(10, 18), pady=12)
        nav = tk.Frame(right, bg=PANEL, padx=14, pady=10)
        nav.pack(fill="x")
        self.b_back = FlatButton(nav, "◀  Back", self.back)
        self.b_back.pack(side="left")
        self.b_next = FlatButton(nav, "Next  ▶", self.next, kind="accent")
        self.b_next.pack(side="right")
        mid = tk.Frame(nav, bg=PANEL)
        mid.pack(side="left", expand=True)
        self.step_lbl = tk.Label(mid, bg=PANEL, fg=MUTED, font=FONT["tiny"])
        self.step_lbl.pack()
        dots = tk.Frame(mid, bg=PANEL)
        dots.pack()
        self.dots = []
        for i in range(len(FIRE_STEPS)):
            d = tk.Label(dots, text="●", bg=PANEL, font=FONT["h2"],
                         cursor="hand2")
            d.pack(side="left", padx=3)
            d.bind("<Button-1>", lambda e, i=i: self.go(i))
            self.dots.append(d)
        self.info = InfoPanel(right)
        self.info.pack(fill="both", expand=True, pady=(10, 0))
        self.go(0)

    # ---- navigation -----------------------------------------------------
    def back(self):
        if self.step > 0:
            self.go(self.step - 1)

    def next(self):
        if self.step < len(FIRE_STEPS) - 1:
            self.go(self.step + 1)

    def go(self, i):
        self.step = i
        self.anim = None
        self.particles = []
        if i == 4:
            self.lit = False
            self.intensity = 0.0
        elif i == 5:
            if self.intensity < 0.25:
                self.intensity = 0.3
            self.logs = 0
        elif i == 6:
            self.out_stage = 0
            self.intensity = max(self.intensity, 0.55)
            self.embers = 1.0
        self.say("")
        self._build_options()
        self.render()

    def say(self, msg, color=MUTED):
        self.status.configure(text=msg, fg=color)

    def _build_options(self):
        for w in self.opt_row.winfo_children():
            w.destroy()
        s = self.step
        if s == 3:
            Segmented(self.opt_row, [(k, v[0]) for k, v in LAYS.items()],
                      self.lay).pack(side="left")
        elif s == 4:
            Segmented(self.opt_row, [(k, v[0]) for k, v in METHODS.items()],
                      self.method).pack(side="left")
            self.b_light = FlatButton(self.opt_row, "Light it", self.light,
                                      kind="accent")
            self.b_light.pack(side="right")
        elif s == 5:
            FlatButton(self.opt_row, "Add kindling",
                       lambda: self.feed("kindling")).pack(side="left", padx=(0, 6))
            FlatButton(self.opt_row, "Add a log",
                       lambda: self.feed("log")).pack(side="left", padx=(0, 6))
            FlatButton(self.opt_row, "Blow gently",
                       lambda: self.feed("blow")).pack(side="left", padx=(0, 6))
            FlatButton(self.opt_row, "Relight", self.relight,
                       kind="ghost").pack(side="right")
        elif s == 6:
            self.b_out = FlatButton(self.opt_row, "1. Drown", self.put_out,
                                    kind="accent")
            self.b_out.pack(side="left")
            FlatButton(self.opt_row, "Start over", lambda: self.go(6),
                       kind="ghost").pack(side="right")
        elif s == 0:
            FlatButton(self.opt_row, "Restore all three", self.restore_tri,
                       kind="ghost").pack(side="left")

    # ---- rendering ------------------------------------------------------
    def render(self):
        s = self.step
        env = self.app.env.get()
        st = FIRE_STEPS[s]
        body = st["body"] if st["body"] else ""
        if s == 3:
            body += LAYS[self.lay.get()][1]
        if s == 4:
            body += METHODS[self.method.get()][1]
        if s == 1:
            body = st[env]
        else:
            body += "\n" + st[env]
        self.info.set(body)
        self.step_lbl.configure(text="STEP %d OF %d  ·  %s"
                                % (s + 1, len(FIRE_STEPS), st["title"].upper()))
        for i, d in enumerate(self.dots):
            d.configure(fg=ACCENT if i == s else (MUTED if i < s else HOVER))
        self.b_back.set_enabled(s > 0)
        self.b_next.set_enabled(s < len(FIRE_STEPS) - 1)

        cv = self.cv
        cv.delete("all")
        self.flame = None
        getattr(self, "_draw_step%d" % s)()

    def _ground(self, by):
        self.cv.create_rectangle(0, by + 4, CW, CH, fill="#17140f", outline="")
        self.cv.create_line(0, by + 4, CW, by + 4, fill="#3a3226", width=2)

    def _caption(self, text, y=28):
        self.cv.create_text(CW / 2, y, text=text, fill=MUTED, font=FONT["cvb"])

    # step 0: triangle
    def _draw_step0(self):
        cv = self.cv
        self._caption("CLICK A SIDE TO REMOVE IT")
        top, bl, br = (240, 90), (80, 370), (400, 370)
        sides = {"fuel": (top, bl, "#c08a50", (118, 214), "e"),
                 "oxygen": (top, br, CLEAR_WATER, (362, 214), "w"),
                 "heat": (bl, br, DANGER, (240, 396), "n")}
        for key, (a, b, col, (lx, ly), anc) in sides.items():
            cv.create_line(*a, *b, fill=CANVAS_BG, width=30,     # wide hit area
                           tags="side_" + key)
        for key, (a, b, col, (lx, ly), anc) in sides.items():
            on = self.tri[key]
            tag = "side_" + key
            cv.create_line(*a, *b, fill=col if on else HOVER, width=12 if on else 4,
                           capstyle="round", dash=() if on else (6, 6), tags=tag)
            cv.create_text(lx, ly, text=key.upper(), anchor=anc,
                           fill=col if on else MUTED, font=FONT["cvbig"], tags=tag)
            cv.tag_bind(tag, "<Button-1>", lambda e, k=key: self.toggle_side(k))
            cv.tag_bind(tag, "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.configure(cursor=""))
        alive = all(self.tri.values())
        if alive:
            self.flame = (240, 330, 0.5)
            cv.create_text(240, 440, text="All three present: FIRE", fill=OK,
                           font=FONT["cvb"])
        else:
            missing = [k for k, v in self.tri.items() if not v]
            cv.create_text(240, 300, text="no fire", fill=MUTED, font=FONT["cvbig"])
            cv.create_text(240, 440, text="Missing: " + ", ".join(missing).upper(),
                           fill=DANGER, font=FONT["cvb"])
        how = [("Remove HEAT", "pour water on it"),
               ("Remove OXYGEN", "smother with dirt, sand or a lid"),
               ("Remove FUEL", "pull logs apart, clear around it")]
        for i, (a, b) in enumerate(how):
            y = 488 + i * 24
            cv.create_text(70, y, text=a, anchor="w", fill=TEXT, font=FONT["cvb"])
            cv.create_text(200, y, text=b, anchor="w", fill=MUTED, font=FONT["cv"])

    def toggle_side(self, key):
        self.tri[key] = not self.tri[key]
        self.render()

    def restore_tri(self):
        self.tri = {"heat": True, "fuel": True, "oxygen": True}
        self.render()

    # step 1: site
    def _draw_step1(self):
        if self.app.env.get() == "hollow":
            self._draw_chamber()
        else:
            self._draw_clearing()

    def _draw_clearing(self):
        cv, r = self.cv, random.Random(11)
        self._caption("TOP-DOWN VIEW")
        cv.create_rectangle(10, 44, CW - 10, CH - 10, fill="#262b1d", outline="")
        for _ in range(140):
            x, y = r.uniform(20, CW - 20), r.uniform(54, CH - 20)
            if (x - 250) ** 2 + (y - 300) ** 2 < 160 ** 2:
                continue
            cv.create_line(x - 3, y - 6, x, y, x + 3, y - 6, fill="#4f6b34")
        cv.create_oval(90, 140, 410, 460, fill="#4d3f2e", outline="")
        cv.create_oval(90, 140, 410, 460, outline=ACCENT, dash=(6, 4), width=2)
        cv.create_line(90, 300, 410, 300, fill=ACCENT, arrow="both", dash=(2, 3))
        cv.create_text(250, 290, text="≈ 3 m (10 ft) cleared to bare soil",
                       fill=ACCENT_HI, font=FONT["cvb"])
        for k in range(12):
            a = 2 * math.pi * k / 12
            x, y = 250 + 44 * math.cos(a), 340 + 34 * math.sin(a)
            cv.create_oval(x - 10, y - 8, x + 10, y + 8, fill="#7c7f86",
                           outline="#4b4e54")
        cv.create_oval(220, 318, 280, 362, fill="#2d2620", outline="")
        cv.create_text(250, 384, text="dry-rock ring", fill=TEXT, font=FONT["tiny"])
        # overhanging tree (bad)
        cv.create_oval(330, 60, 470, 190, fill="#2f4a2a", outline="#456b3d")
        cv.create_line(370, 140, 405, 175, fill=DANGER, width=4)
        cv.create_line(405, 140, 370, 175, fill=DANGER, width=4)
        cv.create_text(400, 205, text="no branches overhead", fill=DANGER,
                       font=FONT["tiny"])
        # wind + tent upwind
        cv.create_line(20, 92, 110, 92, fill=CLEAR_WATER, width=3, arrow="last")
        cv.create_text(20, 78, text="WIND", anchor="w", fill=CLEAR_WATER,
                       font=FONT["cvb"])
        cv.create_polygon(26, 520, 66, 470, 106, 520, fill="#5c6e7f",
                          outline="#8aa0b3")
        cv.create_text(66, 540, text="tents & gear upwind", fill=TEXT,
                       font=FONT["tiny"])
        # water bucket + shovel
        cv.create_polygon(392, 486, 432, 486, 426, 526, 398, 526, fill="#3f6f99",
                          outline="#8ab8de")
        cv.create_line(446, 470, 462, 530, fill=WOOD, width=4)
        cv.create_text(420, 546, text="water + shovel ready", fill=TEXT,
                       font=FONT["tiny"])

    def _draw_chamber(self):
        cv = self.cv
        cv.create_text(16, 20, anchor="w", text="SIDE VIEW: VENTED BURN CHAMBER",
                       fill=MUTED, font=FONT["cvb"])
        cv.create_rectangle(40, 70, 440, 470, fill="#1b1f25", outline="#4a515c",
                            width=6)
        cv.create_rectangle(37, 470, 443, 486, fill="#30353d", outline="")
        # exhaust vent + fan
        cv.create_rectangle(200, 52, 280, 74, fill="#2a2f37", outline="#5b6470")
        for dx in (-22, 0, 22):
            cv.create_line(240 + dx, 48, 240 + dx, 32, fill=MUTED, width=2,
                           arrow="last")
        cv.create_text(296, 42, text="exhaust fan ON", anchor="w", fill=OK,
                       font=FONT["cvb"])
        self.fan_center = (240, 110)
        cv.create_oval(208, 78, 272, 142, outline="#5b6470", width=2)
        self._draw_fan()
        # pit
        for k in range(7):
            x = 190 + k * 17
            cv.create_oval(x - 10, 446, x + 10, 470, fill="#7c7f86",
                           outline="#4b4e54")
        self.flame = (240, 452, 0.25)
        # CO alarm
        round_rect(cv, 400, 150, 432, 186, 6, fill="#d9dde3", outline="")
        cv.create_oval(411, 160, 421, 170, fill=OK, outline="", tags="led")
        cv.create_text(416, 196, text="CO alarm", fill=TEXT, font=FONT["tiny"])
        # door + extinguisher
        cv.create_rectangle(380, 300, 438, 468, fill="#2b313a", outline="#5b6470")
        cv.create_oval(386, 380, 392, 386, fill=MUTED, outline="")
        round_rect(cv, 344, 386, 368, 464, 8, fill="#c0392b", outline="")
        cv.create_rectangle(350, 374, 362, 388, fill="#2d2d2d", outline="")
        cv.create_line(362, 380, 374, 396, fill="#2d2d2d", width=3)
        cv.create_text(356, 500, text="extinguisher", fill=TEXT,
                       font=FONT["tiny"])
        # oxygen line
        cv.create_line(62, 74, 62, 466, fill="#4f8fc0", width=10)
        cv.create_text(76, 150, text="O₂ LINE", anchor="w", fill=CLEAR_WATER,
                       font=FONT["cvb"])
        cv.create_line(70, 420, 196, 420, fill=ACCENT, arrow="both", width=2)
        cv.create_text(133, 406, text="≥ 3 m", fill=ACCENT_HI,
                       font=FONT["cvb"])
        cv.create_text(240, 530, text="No fan, no fire. Never burn in quarters "
                       "or corridors.", fill=DANGER, font=FONT["cvb"])

    def _draw_fan(self):
        cv = self.cv
        cv.delete("fan")
        cx, cy = self.fan_center
        for k in range(3):
            a = self.fan_angle + k * 2 * math.pi / 3
            pts = [cx, cy,
                   cx + 28 * math.cos(a - 0.35), cy + 28 * math.sin(a - 0.35),
                   cx + 28 * math.cos(a + 0.25), cy + 28 * math.sin(a + 0.25)]
            cv.create_polygon(pts, fill="#8a919c", outline="", tags="fan")
        cv.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#3a3f47",
                       outline="", tags="fan")

    # step 2: materials
    def _draw_step2(self):
        cv, r = self.cv, random.Random(5)
        hollow = self.app.env.get() == "hollow"
        by = 380
        self._ground(by)
        self._caption("EACH SIZE ABOUT 10× THICKER THAN THE LAST")
        # tinder nest
        for _ in range(70):
            a = r.uniform(0, math.pi)
            rr = r.uniform(10, 40)
            x, y = 85 + rr * math.cos(a) * 1.3, by - rr * math.sin(a) * 0.7
            cv.create_line(x, y, x + r.uniform(-12, 12), y + r.uniform(-4, 4),
                           fill=r.choice(["#d8c08a", "#bfa36b", "#e8d7aa"]))
        # kindling bundle
        for _ in range(16):
            x0 = 180 + r.uniform(-4, 4)
            y0 = by - r.uniform(0, 34)
            cv.create_line(x0, y0, x0 + r.uniform(90, 120),
                           y0 + r.uniform(-8, 8), fill=r.choice([WOOD, "#a07a4f"]),
                           width=3, capstyle="round")
        # fuel pile
        rows = [(3, by - 13), (2, by - 39), (1, by - 65)]
        for n, y in rows:
            for k in range(n):
                x = 400 + (k - (n - 1) / 2) * 30
                cv.create_oval(x - 14, y - 13, x + 14, y + 13, fill="#a07a4f",
                               outline=WOOD_DARK, width=2)
                cv.create_oval(x - 7, y - 6, x + 7, y + 6, outline="#7a5a36")
        labels = [(85, "TINDER", "hair-thin", "catches a spark",
                   "paper, lint, rags" if hollow else "grass, bark, fluff"),
                  (235, "KINDLING", "pencil-thick", "snaps cleanly",
                   "split scrap wood" if hollow else "dead dry twigs"),
                  (400, "FUEL", "wrist-thick +", "keeps it going",
                   "approved fuel only" if hollow else "dead standing wood")]
        for x, t, a, b, c in labels:
            cv.create_text(x, by + 34, text=t, fill=ACCENT, font=FONT["cvbig"])
            cv.create_text(x, by + 56, text=a, fill=TEXT, font=FONT["cvb"])
            cv.create_text(x, by + 74, text=b, fill=MUTED, font=FONT["cv"])
            cv.create_text(x, by + 92, text=c, fill=MUTED, font=FONT["cv"])
        for x in (150, 320):
            cv.create_text(x, by - 20, text="▶", fill=HOVER, font=FONT["cvbig"])
        # amount bars
        cv.create_text(30, 90, anchor="w", text="HOW MUCH TO GATHER",
                       fill=MUTED, font=FONT["cvb"])
        for i, (name, frac, txt) in enumerate(
                [("tinder", 0.2, "two big handfuls"),
                 ("kindling", 0.5, "an armload"),
                 ("fuel", 1.0, "twice what you think")]):
            y = 118 + i * 34
            cv.create_text(30, y, anchor="w", text=name, fill=TEXT, font=FONT["cv"])
            cv.create_rectangle(100, y - 8, 100 + 260 * frac, y + 8, fill=ACCENT,
                                outline="")
            cv.create_text(108 + 260 * frac, y, anchor="w", text=txt,
                           fill=MUTED, font=FONT["tiny"])
        if hollow:
            cv.create_text(240, 236, text="Never burn plastic, foam, insulation "
                           "or treated wood", fill=DANGER, font=FONT["cvb"])

    # shared: lay drawing
    def _draw_lay(self, kind=None, charred=False):
        cv, r = self.cv, random.Random(3)
        kind = kind or self.lay.get()
        cx, by = self.LAY_CX, self.LAY_BY
        stick = [CHAR, "#3a322c"] if charred else [WOOD, "#a07a4f", "#7a5534"]
        log_fill = CHAR if charred else "#a07a4f"
        log_line = "#1a1714" if charred else WOOD_DARK

        def tinder(x):
            if charred:
                cv.create_oval(x - 28, by - 10, x + 28, by + 4, fill="#3d3a37",
                               outline="")
                return
            for _ in range(40):
                a = r.uniform(0, math.pi)
                rr = r.uniform(4, 22)
                px, py = x + rr * math.cos(a) * 1.3, by - rr * math.sin(a) * 0.6
                cv.create_line(px, py, px + r.uniform(-9, 9), py + r.uniform(-3, 3),
                               fill=r.choice(["#d8c08a", "#bfa36b", "#e8d7aa"]))

        def teepee(x, h=110, n=11, spread=70):
            for k in range(n):
                bx = x + (k - (n - 1) / 2) * (2 * spread / n)
                ax = x + r.uniform(-4, 4)
                cv.create_line(bx, by + 2, ax, by - h, fill=r.choice(stick),
                               width=4, capstyle="round")

        if kind == "teepee":
            tinder(cx)
            teepee(cx)
            self.flame_base = (cx, by - 4)
            self.kindling_pt = (cx + 22, by - 70)
        elif kind == "cabin":
            tinder(cx)
            teepee(cx, h=70, n=7, spread=36)
            for j in range(5):
                y = by - 6 - j * 15
                if j % 2 == 0:
                    cv.create_line(cx - 78, y, cx + 78, y, fill=log_line,
                                   width=14, capstyle="round")
                    cv.create_line(cx - 76, y - 2, cx + 76, y - 2, fill=log_fill,
                                   width=9, capstyle="round")
                else:
                    for sx in (-70, 70):
                        cv.create_oval(cx + sx - 8, y - 8, cx + sx + 8, y + 8,
                                       fill=log_fill, outline=log_line, width=2)
            self.flame_base = (cx, by - 6)
            self.kindling_pt = (cx + 70, by - 70)
        else:  # lean-to
            lx = cx - 70
            cv.create_oval(lx - 26, by - 48, lx + 26, by + 4, fill=log_fill,
                           outline=log_line, width=3)
            for rr in (16, 9):
                cv.create_oval(lx - rr, by - 22 - rr, lx + rr, by - 22 + rr,
                               outline=log_line)
            tinder(cx - 22)
            for k in range(8):
                bx = cx + 20 + k * 11
                cv.create_line(bx, by + 2, lx + 14 + r.uniform(-3, 3),
                               by - 44 + r.uniform(-3, 3), fill=r.choice(stick),
                               width=4, capstyle="round")
            if not charred:
                cv.create_line(16, by - 70, 100, by - 70, fill=CLEAR_WATER,
                               width=3, arrow="last")
                cv.create_text(16, by - 86, text="WIND", anchor="w",
                               fill=CLEAR_WATER, font=FONT["cvb"])
            self.flame_base = (cx - 24, by - 4)
            self.kindling_pt = (cx + 30, by - 22)

    def _draw_logs_added(self):
        cv, cx, by = self.cv, self.LAY_CX, self.LAY_BY
        for k in range(min(self.logs, 6)):
            off = (k - 2.5) * 16
            cv.create_line(cx - 70 + off, by + 2 - k % 2 * 6, cx + 70 + off,
                           by - 8 + k % 2 * 6, fill=WOOD_DARK, width=10,
                           capstyle="round")

    # step 3: lay
    def _draw_step3(self):
        self._ground(self.LAY_BY)
        self._caption("SIDE VIEW: " + LAYS[self.lay.get()][0].upper())
        self._draw_lay()
        cv, cx, by = self.cv, self.LAY_CX, self.LAY_BY
        kx, ky = self.kindling_pt
        tx, ty = self.flame_base
        cv.create_text(cx + 130, by - 170, text="kindling", fill=MUTED,
                       font=FONT["cv"], anchor="w")
        cv.create_line(cx + 128, by - 166, kx, ky, fill=MUTED)
        cv.create_text(cx + 40, by + 44, text="tinder in the centre", fill=MUTED,
                       font=FONT["cv"], anchor="w")
        cv.create_line(cx + 38, by + 40, tx, ty, fill=MUTED)
        cv.create_text(cx, 150, text="Leave gaps: air must reach the tinder "
                       "from below.", fill=MUTED, font=FONT["cv"])

    # step 4: light it
    def _draw_step4(self):
        cv = self.cv
        self._ground(self.LAY_BY)
        self._draw_lay()
        m = self.method.get()
        self._caption(METHODS[m][0].upper())
        if m == "lighter":
            round_rect(cv, 150, 150, 196, 250, 8, fill="#c0392b", outline="")
            cv.create_rectangle(154, 126, 192, 152, fill="#9aa3ad", outline="")
            cv.create_oval(178, 116, 196, 134, fill="#5d6670", outline="")
            draw_flame(cv, 168, 122, 0.04, random.Random(1), tag="static")
            cv.create_line(300, 260, 340, 170, fill="#e8d3a8", width=5,
                           capstyle="round")
            cv.create_oval(333, 158, 349, 176, fill="#b03a2e", outline="")
            cv.create_text(173, 270, text="lighter", fill=MUTED, font=FONT["cv"])
            cv.create_text(320, 280, text="matches in a\nwaterproof tin",
                           fill=MUTED, font=FONT["cv"], justify="center")
            self.spark_origin = (168, 112)
        elif m == "ferro":
            cv.create_line(150, 170, 200, 210, fill=WOOD, width=18, capstyle="round")
            cv.create_line(200, 210, 300, 290, fill="#4b4f57", width=9,
                           capstyle="round")
            cv.create_line(280, 300, 330, 262, fill="#c9ced6", width=7,
                           capstyle="round")
            cv.create_line(300, 296, 220, 232, fill=ACCENT, dash=(4, 4),
                           arrow="last")
            cv.create_text(170, 140, text="pull the rod back,\nstriker stays still",
                           fill=MUTED, font=FONT["cv"], justify="center")
            self.spark_origin = (302, 292)
        elif m == "bowdrill":
            cv.create_rectangle(140, 330, 340, 346, fill="#a07a4f", outline=WOOD_DARK)
            cv.create_polygon(238, 330, 250, 346, 226, 346, fill=CANVAS_BG,
                              outline="")
            cv.create_rectangle(110, 316, 150, 330, fill="#3a3f47", outline="")
            cv.create_text(130, 306, text="foot", fill=MUTED, font=FONT["tiny"])
            cv.create_rectangle(232, 200, 244, 330, fill="#c49a63",
                                outline=WOOD_DARK, tags="spindle")
            cv.create_rectangle(220, 184, 256, 202, fill="#6b4a2b", outline="",
                                tags="spindle")
            cv.create_line(100, 262, 240, 236, 380, 262, smooth=True,
                           fill="#7a5230", width=6, capstyle="round", tags="bow")
            cv.create_line(100, 262, 238, 262, 380, 262, fill="#dddddd",
                           tags="bow")
            cv.create_text(300, 186, text="bearing block", fill=MUTED,
                           font=FONT["tiny"], anchor="w")
            cv.create_text(350, 340, text="board + notch", fill=MUTED,
                           font=FONT["tiny"], anchor="w")
            self.spark_origin = (238, 344)
        else:  # battery
            round_rect(cv, 200, 170, 256, 268, 6, fill="#2d3e50", outline="")
            cv.create_text(228, 222, text="9V", fill="#ffffff", font=FONT["cvbig"])
            cv.create_oval(208, 158, 222, 172, fill="#9aa3ad", outline="")
            cv.create_rectangle(236, 158, 250, 172, fill="#9aa3ad", outline="")
            r = random.Random(4)
            for _ in range(60):
                a = r.uniform(0, 2 * math.pi)
                rr = r.uniform(4, 30)
                x, y = 228 + rr * math.cos(a), 132 + rr * math.sin(a) * 0.6
                cv.create_line(x, y, x + r.uniform(-10, 10), y + r.uniform(-5, 5),
                               fill="#8f959e", tags="wool")
            cv.create_text(300, 120, text="0000 steel wool", fill=MUTED,
                           font=FONT["cv"], anchor="w")
            self.spark_origin = (228, 138)
        if self.lit:
            self.flame = (*self.flame_base, self.intensity)
        if self.lit and self.anim is None:
            cv.create_text(240, 90, text="It's lit. Press Next to feed it.",
                           fill=OK, font=FONT["cvb"])

    def light(self):
        if self.anim:
            return
        self.anim = dict(t=0, kind=self.method.get())
        self.lit = False
        self.intensity = 0.0
        self.render()
        self.say({"lighter": "Shield the flame and light it low, on the windward side…",
                  "ferro": "Striker held still, rod pulled back. Sparks into the tinder…",
                  "bowdrill": "Long, steady strokes until the dust smokes…",
                  "battery": "Both terminals onto the wool. It glows at once…"}
                 [self.method.get()])

    # step 5: feed
    def _draw_step5(self):
        cv = self.cv
        self._ground(self.LAY_BY)
        self._draw_lay("teepee")
        self._draw_logs_added()
        self.flame = (*self.flame_base, self.intensity)
        cv.create_text(24, 36, text="HEAT", anchor="w", fill=MUTED,
                       font=FONT["cvb"])
        cv.create_rectangle(70, 28, 330, 44, outline=LINE)
        cv.create_rectangle(71, 29, 71, 43, fill=ACCENT, outline="", tags="meter")

    def feed(self, what):
        I = self.intensity
        if I <= 0.01:
            self.say("The fire is out. Press Relight.", DANGER)
            return
        if what == "kindling":
            if I < 0.75:
                self.intensity = min(1.0, I + 0.12)
                self.say("Good. A few sticks at a time, and the flame climbs.", OK)
            else:
                self.intensity = min(1.0, I + 0.03)
                self.say("Kindling burns fast at this size. It's ready for logs.")
        elif what == "log":
            if I < 0.45:
                self.intensity = max(0.04, I - 0.18)
                self.say("Too big, too soon: a log smothers a young fire. Build "
                         "it up with kindling first.", DANGER)
            else:
                self.intensity = min(1.0, I + 0.16)
                self.logs += 1
                self.say("The log catches. A steady fire now burns for a long time.",
                         OK)
                self.render()
        else:
            if I < 0.4:
                self.intensity = min(1.0, I + 0.08)
                self.say("Gentle air at the base wakes it up.", OK)
            else:
                self.say("A fire this size doesn't need it. Save your breath.")

    def relight(self):
        self.intensity = 0.3
        self.logs = 0
        self.say("Relit with fresh tinder.")
        self.render()

    # step 6: put out
    def _draw_step6(self):
        cv, r = self.cv, random.Random(9 + self.out_stage)
        self._ground(self.LAY_BY)
        charred = self.out_stage >= 1
        self._draw_lay("teepee", charred=charred)
        cx, by = self.LAY_CX, self.LAY_BY
        if self.out_stage == 0:
            self.flame = (*self.flame_base, self.intensity)
        for _ in range(26):
            x, y = cx + r.uniform(-60, 60), by + r.uniform(-6, 2)
            heat = self.embers * r.uniform(0.3, 1.0)
            cv.create_oval(x - 5, y - 3, x + 5, y + 3,
                           fill=mix("#3a3a3a", "#ff6a1a", heat), outline="")
        if self.out_stage >= 4:
            # back of a hand held over the ashes
            round_rect(cv, cx - 30, by - 140, cx + 30, by - 90, 14, fill="#c79b7a",
                       outline="#8a6a52")
            for k in range(4):
                x = cx - 22 + k * 15
                cv.create_line(x, by - 92, x, by - 70, fill="#c79b7a", width=11,
                               capstyle="round")
            cv.create_line(cx + 30, by - 118, cx + 50, by - 100, fill="#c79b7a",
                           width=11, capstyle="round")
            cv.create_text(cx, by - 170, text="Cold to the touch ✓  Safe to leave",
                           fill=OK, font=FONT["cvbig"])
        labels = ["Burning", "Drowned: still steaming", "Stirred: hidden coals",
                  "Drowned again", "Checked by hand"]
        self._caption(labels[self.out_stage].upper())

    def put_out(self):
        if self.anim:
            return
        nxt = ["2. Stir", "3. Drown again", "4. Feel for heat", "Done ✓",
               "Done ✓"]
        msgs = ["Drown every ember, not just the red ones, until the hissing stops.",
                "Stir the ash to expose hidden coals. There are still some glowing.",
                "Drown it again.",
                "Back of the hand close to the ash, not touching. It's cold. "
                "Now it's out.",
                ""]
        s = self.out_stage
        if s >= 4:
            return
        if s in (0, 2):
            self.anim = dict(t=0, kind="douse")
        elif s == 1:
            self.embers = 0.6
        elif s == 3:
            self.embers = 0.0
        self.out_stage += 1
        if s not in (0, 2):
            self.render()
        self.b_out.set_text(nxt[s])
        self.say(msgs[s], OK if s == 3 else MUTED)

    # ---- animation ------------------------------------------------------
    def _spawn_spark(self, ox, oy, tx, ty, color, T=22, g=0.4):
        r = self.rnd
        vx = (tx - ox) / T + r.uniform(-1.2, 1.2)
        vy = (ty - oy) / T - 0.5 * g * T + r.uniform(-1, 1)
        pid = self.cv.create_oval(0, 0, 0, 0, fill=color, outline="",
                                  tags="particle")
        self.particles.append(dict(id=pid, x=ox, y=oy, vx=vx, vy=vy, g=g,
                                   life=0, max=T + 4, kind="spark"))

    def _spawn_puff(self, x, y, color="#9aa1ab"):
        pid = self.cv.create_oval(0, 0, 0, 0, fill=color, outline="",
                                  tags="particle")
        self.particles.append(dict(id=pid, x=x, y=y, vx=self.rnd.uniform(-0.5, 0.5),
                                   vy=-1.2, g=0, life=0, max=34, kind="puff",
                                   color=color))

    def tick(self):
        cv, r = self.cv, self.rnd
        s = self.step
        if s == 1 and self.app.env.get() == "hollow":
            self.fan_angle += 0.35
            self._draw_fan()

        # step-specific animations
        if self.anim and s == 4:
            a = self.anim
            a["t"] += 1
            ox, oy = self.spark_origin
            tx, ty = self.flame_base
            kind = a["kind"]
            if kind == "bowdrill":
                if a["t"] < 60:
                    cv.move("bow", 8 * math.cos(a["t"] * 0.5), 0)
                    if a["t"] % 4 == 0:
                        self._spawn_puff(ox + r.uniform(-4, 4), oy - 6)
                    if a["t"] > 40:
                        cv.delete("coal")
                        cv.create_oval(ox - 6, oy - 4, ox + 6, oy + 4,
                                       fill=mix("#5a1d0a", "#ff6a1a",
                                                (a["t"] - 40) / 20),
                                       outline="", tags="coal")
                elif a["t"] == 60:
                    self.say("A glowing coal. Tip it into the tinder and blow gently.")
            elif kind == "battery":
                if a["t"] < 40:
                    cv.itemconfigure("wool", fill=mix("#8f959e", "#ff8a2a",
                                                     min(1, a["t"] / 12)))
                    if a["t"] % 3 == 0:
                        self._spawn_spark(ox, oy, tx, ty, "#ffb347", T=24)
            elif kind == "ferro":
                if a["t"] < 30:
                    for _ in range(4):
                        self._spawn_spark(ox, oy, tx, ty,
                                          r.choice(["#fff3b0", "#ffd43b", "#ffa94d"]))
            start = {"bowdrill": 62, "battery": 40, "ferro": 30, "lighter": 12}[kind]
            if a["t"] >= start:
                self.lit = True
                self.intensity = min(0.32, (a["t"] - start) * 0.012)
                self.flame = (*self.flame_base, self.intensity)
            if a["t"] >= start + 28:
                self.anim = None
                self.render()
                self.say("Lit. Shield it from wind and press Next to feed it.", OK)

        if s == 5 and self.flame:
            self.intensity = max(0.0, self.intensity - 0.0009)
            self.flame = (*self.flame_base, self.intensity)
            w = 258 * self.intensity
            cv.coords("meter", 71, 29, 71 + max(0, w), 43)
            cv.itemconfigure("meter", fill=DANGER if self.intensity < 0.2 else ACCENT)
            if self.intensity <= 0:
                self.flame = None
                cv.delete("flame")
                self.say("It burned out. Feed it before it dies down. Press "
                         "Relight.", DANGER)

        if s == 6 and self.anim and self.anim["kind"] == "douse":
            a = self.anim
            a["t"] += 1
            cx, by = self.LAY_CX, self.LAY_BY
            if a["t"] < 22:
                for _ in range(3):
                    pid = cv.create_oval(0, 0, 0, 0, fill=CLEAR_WATER, outline="",
                                         tags="particle")
                    self.particles.append(dict(id=pid, x=cx + r.uniform(-70, 70),
                                               y=70.0, vx=0, vy=6, g=0.5, life=0,
                                               max=24, kind="spark"))
            if a["t"] == 22:
                self.intensity = 0.0
                self.embers = 0.0 if self.out_stage >= 3 else 0.55
                self.render()
            if 22 <= a["t"] < 60 and a["t"] % 2 == 0:
                self._spawn_puff(cx + r.uniform(-60, 60), by - 10, "#cfd6dc")
            if a["t"] >= 60:
                self.anim = None

        # particles
        for p in self.particles[:]:
            p["life"] += 1
            p["vy"] += p["g"]
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["life"] > p["max"]:
                cv.delete(p["id"])
                self.particles.remove(p)
                continue
            if p["kind"] == "puff":
                rr = 3 + p["life"] * 0.35
                cv.itemconfigure(p["id"], fill=mix(p["color"], CANVAS_BG,
                                                   p["life"] / p["max"]))
            else:
                rr = 2
            cv.coords(p["id"], p["x"] - rr, p["y"] - rr, p["x"] + rr, p["y"] + rr)

        # flame
        cv.delete("flame")
        if self.flame:
            fx, fy, fi = self.flame
            draw_flame(cv, fx, fy, fi * r.uniform(0.95, 1.05), r)
            cv.tag_raise("particle")


# --------------------------------------------------------------------------
# Quick card tab
# --------------------------------------------------------------------------
class CardTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=BG)
        top = tk.Frame(self.frame, bg=BG)
        top.pack(fill="x", padx=18, pady=(12, 0))
        tk.Label(top, text="Keep this on you. Both skills on one card.", bg=BG,
                 fg=MUTED, font=FONT["small"]).pack(side="left")
        FlatButton(top, "Save as text file", self.save).pack(side="right")
        cols = tk.Frame(self.frame, bg=BG)
        cols.pack(fill="both", expand=True, padx=18, pady=12)
        self.left = InfoPanel(cols)
        self.right = InfoPanel(cols)
        self.left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.refresh()

    def refresh(self):
        env = self.app.env.get()
        self.left.set(CARD["water"] + CARD[env])
        self.right.set(CARD["fire"] + CARD[env])

    def save(self):
        path = filedialog.asksaveasfilename(
            parent=self.frame, defaultextension=".txt",
            initialfile="hollow_survival_card.txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        env = self.app.env.get()
        text = ("THE HOLLOW: FIELD SURVIVAL CARD\n"
                "================================\n\n"
                + markup_to_plain(CARD["water"]) + "\n\n"
                + markup_to_plain(CARD["fire"]) + "\n\n"
                + markup_to_plain(CARD[env]) + "\n")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as ex:
            self.app.flash("Cannot save: " + str(ex))
            return
        self.app.flash("Saved to " + path)


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class SurvivalGuide:
    def __init__(self, win):
        self.win = win
        if not FONT:
            _init_fonts(win)
        win.title("The Hollow – Field Survival Guide")
        win.geometry("1180x%d" % min(800, win.winfo_screenheight() - 80))
        win.minsize(1000, 720)
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", self.close)
        self.alive = True
        self.env = tk.StringVar(value="hollow")

        head = tk.Frame(win, bg=PANEL, padx=18, pady=10)
        head.pack(fill="x")
        titles = tk.Frame(head, bg=PANEL)
        titles.pack(side="left")
        tk.Label(titles, text="THE HOLLOW // FIELD SURVIVAL GUIDE", bg=PANEL,
                 fg=ACCENT, font=FONT["title"]).pack(anchor="w")
        self.sub = tk.Label(titles, bg=PANEL, fg=MUTED, font=FONT["sub"])
        self.sub.pack(anchor="w")
        Segmented(head, [("hollow", "Inside the Hollow"),
                         ("surface", "On the Surface")], self.env,
                  bg=PANEL).pack(side="right")

        self.tab = tk.StringVar(value="water")
        bar = tk.Frame(win, bg=BG, padx=18, pady=10)
        bar.pack(fill="x")
        Segmented(bar, [("water", "Water filtration"), ("fire", "Making fire"),
                        ("card", "Quick card")], self.tab).pack(side="left")
        self.flash_lbl = tk.Label(bar, bg=BG, fg=OK, font=FONT["small"])
        self.flash_lbl.pack(side="right")

        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True)
        self.tabs = {"water": WaterTab(body, self), "fire": FireTab(body, self),
                     "card": CardTab(body, self)}
        self.tab.trace_add("write", lambda *_: self._show_tab())
        self.env.trace_add("write", lambda *_: self._env_changed())
        self._show_tab()
        self._env_changed()
        self._loop()

    def _show_tab(self):
        for name, t in self.tabs.items():
            if name == self.tab.get():
                t.frame.pack(fill="both", expand=True)
            else:
                t.frame.pack_forget()

    def _env_changed(self):
        hollow = self.env.get() == "hollow"
        self.sub.configure(text="Rev. 2087  ·  issued to all levels  ·  "
                           + ("showing advice for INSIDE the Hollow" if hollow
                              else "showing advice for the SURFACE"))
        self.tabs["water"].refresh_info()
        self.tabs["fire"].render()
        self.tabs["card"].refresh()

    def flash(self, msg):
        self.flash_lbl.configure(text=msg)
        self.win.after(4000, lambda: self.alive and self.flash_lbl.configure(text=""))

    def _loop(self):
        if not self.alive:
            return
        t = self.tabs.get(self.tab.get())
        if hasattr(t, "tick"):
            t.tick()
        self.win.after(TICK_MS, self._loop)

    def close(self):
        self.alive = False
        self.win.destroy()


def open_survival_guide(master=None):
    """Open the guide. With a master window it opens as a separate Toplevel
    (use this from another tkinter app); without one it runs as its own app."""
    if master is None:
        root = tk.Tk()
        SurvivalGuide(root)
        root.mainloop()
        return None
    top = tk.Toplevel(master)
    return SurvivalGuide(top)


if __name__ == "__main__":
    open_survival_guide()