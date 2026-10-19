"""The mobile page: a work read on a phone, built with Ionic (ionicframework.com) from a CDN.

Written by tools/side_by_side.py beside the desktop pages, from the same data, as <work>-mobile.html.
On a wide screen it shows inside a phone frame (390 × 844, iOS style), as a mock-up; on a phone it
fills the screen. The same page could be wrapped as an iOS or Android app with Capacitor.

The desktop page's two columns become one edition at a time, chosen by a segmented control:
  - Compare: the other text's line, small and grey, under each line (interlinear); differing words
    underlined in red; tapping a word names its counterpart.
  - Notes (sepia, as on the desktop): brackets in the margin for passages of whole lines, underlines
    for words; tap to choose, tap again to go narrower. The notes open in a bottom sheet, which can
    be dragged between half and full height while the text stays usable above it.
"""

import html

IONIC = "https://cdn.jsdelivr.net/npm/@ionic/core@8.7.0"  # 8.5+ for a sheet's expandToScroll


def render(
    title: str,
    author: str | None,
    labels: dict[str, str],
    names: list[str],
    first: str,
    data_json: str,
    fonts: str,
) -> str:
    """The page, filled in. names: the segments, in order; first: the one shown on opening."""
    segments = "".join(
        f'<ion-segment-button value="{html.escape(n)}"><ion-label>{html.escape(short(labels[n]))}'
        "</ion-label></ion-segment-button>"
        for n in names
    )
    return (
        PAGE.replace("%IONIC%", IONIC)
        .replace("%FONTS%", fonts)
        .replace("%TAB%", html.escape(" · ".join(filter(None, [title, author]))))
        .replace("%TITLE%", html.escape(title))
        .replace("%AUTHOR%", html.escape(author or ""))
        .replace("%SEGMENTS%", segments)
        .replace("%FIRST%", html.escape(first))
        .replace("%DATA%", data_json)
    )


def short(label: str) -> str:
    """A segment's label, short enough for a phone: "Vendler (1997)" → "Vendler 1997"."""
    return label.replace("(", "").replace(")", "")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>%TAB%</title>
<link rel="stylesheet" href="%IONIC%/css/ionic.bundle.css">
<script>window.Ionic = { config: { mode: "ios" } };</script>
<script type="module" src="%IONIC%/dist/ionic/ionic.esm.js"></script>
<style>
%FONTS%
:root {
  --paper: #f4f1ea; --ink: #000; --fade: #6b6b6b; --editor: #3050b0; --differs: #cc0000;
  --note: #c9a35f; --note-faint: #dcc59a; --note-deep: #8a5a1c; --note-paper: #f7e9c4;
  --serif: Libertinus, "Libertinus Serif", "Linux Libertine O", "Palatino Linotype", Georgia, serif;
  --ion-color-primary: #8a5a1c; --ion-color-primary-rgb: 138, 90, 28; --ion-color-primary-contrast: #fff;
  --ion-color-primary-shade: #794f19; --ion-color-primary-tint: #966b33;
  --lane-width: 9px;  /* each bracket's lane in the margin */
}
/* The desk: on a wide screen, the phone stands on it as a mock-up; on a phone, it is the screen. */
html, body { height: 100%; }
body { background: #e6e2d9; display: flex; align-items: center; justify-content: center; gap: 48px; }
.phone { border-radius: 52px; box-shadow: 0 0 0 11px #1d1d1f, 0 0 0 12px #48484a, 0 40px 80px rgba(0, 0, 0, .28); }
.device { position: relative; width: 390px; height: 844px; border-radius: 52px; overflow: hidden; background: #fff;
  transform: translateZ(0);  /* contains the app's fixed layers (sheet, toast) within the phone */
  clip-path: inset(0 round 52px);  /* and clips them to its rounded corners, layers included */
  --ion-safe-area-top: 50px; --ion-safe-area-bottom: 26px; }
.statusbar { position: absolute; top: 0; left: 0; right: 0; height: 50px; z-index: 100; pointer-events: none;
  display: flex; align-items: center; justify-content: space-between; padding: 6px 34px 0;
  font: 600 16px -apple-system, "Segoe UI", system-ui, sans-serif; }
.statusbar .island { position: absolute; left: 50%; top: 11px; width: 122px; height: 35px; margin-left: -61px;
  border-radius: 20px; background: #000; }
.statusbar .icons { letter-spacing: 2px; font-size: 12px; }
.desk-note { max-width: 260px; color: #5a554b; font: 14px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif; }
.desk-note b { color: #1d1d1f; }
ion-app { position: absolute; inset: 0; }
@media (max-width: 520px) {
  body { display: block; background: #fff; }
  .phone { box-shadow: none; border-radius: 0; }
  .device { width: 100vw; height: 100dvh; border-radius: 0; clip-path: none;
    --ion-safe-area-top: env(safe-area-inset-top); --ion-safe-area-bottom: env(safe-area-inset-bottom); }
  .statusbar, .desk-note { display: none; }
}

/* The app's chrome is native (system font, iOS look); the poem is set in Libertinus on paper. */
ion-content { --background: var(--paper); }
ion-content::part(scroll) { scrollbar-width: none; }  /* a phone shows no scrollbar */
ion-title .by { font-size: 12px; font-weight: 400; color: var(--fade); }
.reading { font: 16.5px/1.75 var(--serif); color: var(--ink); padding: 18px 16px 120px; user-select: text; }
.tally { font: 13px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif; color: var(--fade); margin: 0 16px; padding-top: 12px; }
.tally b { color: #000; }
.facsimile { margin: 0; display: flex; justify-content: center; }
.facsimile img { display: block; max-width: 100%; height: auto; border: 1px solid #c8ccd1; padding: 2px; background: #fff; }

/* Lines: one column, turning over with a hanging indent when too long for the screen; the margin's
   brackets; then the line numbers. */
.text { display: grid; grid-template-columns: minmax(0, 1fr) auto 1.6em; align-items: baseline; }
.line { display: contents; }
.head { grid-column: 1; margin: 0 0 .5em; font-size: 1.15em; font-weight: normal; text-align: center; }
.lt { grid-column: 1; position: relative; white-space: pre-wrap; text-indent: -1.1em;
  padding-left: calc(var(--indent, 0) * 1.6em + 1.1em); }
.ln { grid-column: 3; color: var(--editor); font-size: .7em; text-align: right; }
.initial.dropped { position: absolute; left: 0; top: 0; line-height: 1; text-indent: 0; }
.probe { display: inline-block; width: 0; height: 0; text-indent: 0; }
.w { border-radius: 3px; -webkit-tap-highlight-color: transparent; }
.w.lit { background: #dfe7f8; }

/* Compare: the other text, interlinear. */
.line.under .lt { color: #8b8b8b; font-size: .8em; line-height: 1.5; margin-bottom: .55em; }
.compare .w.differs { text-decoration: underline dotted var(--differs) 1.5px; text-underline-offset: .2em; }

/* Notes, in sepia (as on the desktop). */
.mg { grid-column: 2; align-self: stretch; position: relative; width: calc(var(--lanes, 0) * var(--lane-width));
  margin-left: calc(min(var(--lanes, 0), 1) * .35em); }
.rule { position: absolute; top: 0; bottom: 0; width: var(--lane-width); visibility: hidden;
  left: calc((var(--lanes) - 1 - var(--lane)) * var(--lane-width)); --ink-rule: var(--note); --stroke: 1.5px;
  background: linear-gradient(var(--ink-rule), var(--ink-rule)) center / var(--stroke) 100% no-repeat; }
.rule.top { top: .55em; }
.rule.end { bottom: .55em; }
.rule.top::before, .rule.end::after { content: ""; position: absolute; right: 50%; width: 4px; height: var(--stroke);
  background: var(--ink-rule); }
.rule.top::before { top: 0; }
.rule.end::after { bottom: 0; }
.show-notes .rule { visibility: visible; }
.show-notes .rule.sel { --ink-rule: var(--note-deep); --stroke: 2.5px; }
.show-notes .an.u { text-decoration: underline var(--note-faint) 1px; text-underline-offset: .24em; }
.show-notes .an.u[data-k="2"] { text-decoration-color: var(--note); text-decoration-thickness: 2px; }
.show-notes .an.sel { background: var(--note-paper); text-decoration-color: var(--note-deep); }

/* The notes sheet. Ionic turns sheets into centred cards on screens wider than 768px, judged by the
   browser window, not the phone frame: pin it to the phone's full width. */
#sheet { --width: 100%; --height: 100%; --max-width: none; --border-radius: 14px 14px 0 0; }
.reading:not(.show-notes) .mg { display: none; }  /* the margin only with the notes: more room for lines */
.where { font: 13px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif; color: var(--fade); padding: 4px 18px 8px; }
.where q { color: #000; font-style: italic; quotes: "“" "”"; }
.notes-list { padding: 0 6px 40px; font: 16px/1.5 var(--serif); }
.notes-list h3 { margin: 14px 12px 4px; font: 600 12px -apple-system, "Segoe UI", system-ui, sans-serif;
  letter-spacing: .06em; text-transform: uppercase; color: var(--fade); }
.nt { margin: 6px 6px; padding: 10px 12px; border-radius: 12px; background: #fff; }
.nt.lit { background: #fbf6ea; box-shadow: inset 3px 0 0 var(--note-deep); }
.nt .lemma { margin: 0 0 4px; }
.nt .lemma i { font-style: italic; }
.nt p { margin: 0 0 .5em; }
</style>
</head>
<body>
<div class="phone"><div class="device">
  <div class="statusbar"><span>9:41</span><span class="island"></span><span class="icons">▂▄▆ ◔</span></div>
  <ion-app>
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>%TITLE%<div class="by">%AUTHOR%</div></ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment id="edition" value="%FIRST%">%SEGMENTS%</ion-segment>
      </ion-toolbar>
    </ion-header>
    <ion-content id="content" fullscreen="true">
      <p class="tally" id="tally"></p>
      <div class="reading" id="reading"></div>
    </ion-content>
    <ion-footer translucent="true">
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-button id="compare-button" fill="clear">Compare</ion-button>
        </ion-buttons>
        <ion-buttons slot="end">
          <ion-button id="notes-button" fill="clear">Notes&nbsp;<ion-badge id="notes-badge" color="primary"></ion-badge></ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-footer>
    <ion-modal id="sheet">
      <ion-header>
        <ion-toolbar>
          <ion-buttons slot="start"><ion-button id="all-notes">All notes</ion-button></ion-buttons>
          <ion-title>Notes</ion-title>
          <ion-buttons slot="end"><ion-button id="narrower">Narrower</ion-button></ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content>
        <p class="where" id="where"></p>
        <div class="notes-list" id="notes-list"></div>
      </ion-content>
    </ion-modal>
  </ion-app>
</div></div>
<p class="desk-note"><b>Mock-up.</b> Ionic 8 in iOS mode, at iPhone size. Choose an edition at the top.
<b>Compare</b> puts the other text under each line; tap a word for its counterpart. <b>Notes</b> marks the
passages notes discuss: tap a bracket or an underlined word, tap again to go narrower. The notes scroll
in the sheet; drag its handle to make it taller or shorter.</p>
<script>
const DATA = %DATA%;
const reading = document.getElementById("reading");
const content = document.getElementById("content");
const segment = document.getElementById("edition");
const tally = document.getElementById("tally");
const sheet = document.getElementById("sheet");
const notesList = document.getElementById("notes-list");
const where = document.getElementById("where");
const narrower = document.getElementById("narrower");
const allNotes = document.getElementById("all-notes");
const notesButton = document.getElementById("notes-button");
const notesBadge = document.getElementById("notes-badge");
const compareButton = document.getElementById("compare-button");

let shown = segment.getAttribute("value");  // the edition on screen (read before Ionic upgrades it)
let notesOn = false, compareOn = false;
let pairs = null;  // when comparing: word id → its group, for this text and for the one under it
let drill = null, selected = [], lit = [];

const isText = name => DATA.texts.includes(name);
const otherText = () => DATA.texts.find(t => t !== shown);
const hasNotes = () => Boolean(DATA.notes[shown]);

function sourceOf(name) {
  const template = document.createElement("template");
  template.innerHTML = DATA.sources[name];
  return template.content;
}

// The groups linking two texts, oriented so that "mine" is the first text's words.
function groupsFor(mine, other) {
  const forward = DATA.pairs[mine + "|" + other];
  if (forward) return forward.map(g => ({ mine: g.a, other: g.b, kind: g.kind }));
  return DATA.pairs[other + "|" + mine].map(g => ({ mine: g.b, other: g.a, kind: g.kind }));
}

// ── Showing an edition ──────────────────────────────────────────────────────────────────────────
function render() {
  reading.replaceChildren(sourceOf(shown));
  reading.classList.toggle("show-notes", notesOn && hasNotes());
  reading.classList.toggle("compare", compareOn);
  pairs = null;
  tally.textContent = "";
  if (compareOn && isText(shown) && otherText()) interleave();
  else afterLayout(() => setInitials(reading));  // measured once Ionic has laid the text out
  clearChoice();
  updateButtons();
  fillNotes(null);
}

function updateButtons() {
  const notes = DATA.notes[shown] || [];
  notesButton.style.display = notes.length ? "" : "none";
  notesBadge.textContent = String(notes.length);
  notesButton.setAttribute("fill", notesOn ? "solid" : "clear");
  const comparable = isText(shown) && Boolean(otherText());
  compareButton.style.display = comparable ? "" : "none";
  compareButton.setAttribute("fill", compareOn ? "solid" : "clear");
  if (!notes.length && notesOn) { notesOn = false; sheet.dismiss(); }
}

// ── Compare: the other text under each line ─────────────────────────────────────────────────────
function interleave() {
  const other = otherText(), groups = groupsFor(shown, other);
  const mine = new Map(), theirs = new Map();
  groups.forEach(g => { g.mine.forEach(id => mine.set(id, g)); g.other.forEach(id => theirs.set(id, g)); });
  pairs = { mine, theirs };
  const otherLines = [...sourceOf(other).querySelectorAll(".line")];
  reading.querySelectorAll(".line").forEach((line, i) => {
    const under = otherLines[i];
    if (!under) return;
    under.classList.add("under");
    under.querySelectorAll(".an").forEach(a => a.classList.remove("an", "u"));
    under.querySelectorAll(".rule").forEach(r => r.remove());
    under.querySelectorAll(".initial").forEach(c => c.classList.remove("initial"));
    const number = under.querySelector(".ln");
    if (number) number.textContent = "";
    line.after(under);
  });
  reading.querySelectorAll(".line:not(.under) .w").forEach(w =>
    w.classList.toggle("differs", (mine.get(w.dataset.w)?.kind ?? "same") !== "same"));
  reading.querySelectorAll(".line.under .w").forEach(w =>
    w.classList.toggle("differs", (theirs.get(w.dataset.w)?.kind ?? "same") !== "same"));
  const same = groups.filter(g => g.kind === "same").length, differ = groups.length - same;
  tally.innerHTML = `Under each line: <b>${DATA.labels[other]}</b> · ${same} words identical · ${differ} differ`;
}

function lightPair(word) {
  lit.forEach(el => el.classList.remove("lit"));
  const under = Boolean(word.closest(".under"));
  const g = (under ? pairs.theirs : pairs.mine).get(word.dataset.w);
  if (!g) return;
  const mineIds = under ? g.other : g.mine, theirIds = under ? g.mine : g.other;
  const find = (scope, ids) => ids.flatMap(id => [...reading.querySelectorAll(`${scope} [data-w="${id}"]`)]);
  const a = find(".line:not(.under)", mineIds), b = find(".line.under", theirIds);
  lit = a.concat(b);
  lit.forEach(el => el.classList.add("lit"));
  const text = els => els.map(e => e.textContent).join(" ") || "—";
  const kind = { same: "identical", different: "differs", "only-a": "no counterpart", "only-b": "no counterpart" }[g.kind];
  toast(`${text(a)}  ↔  ${text(b)}  ·  ${kind}`);
}

function toast(message) {
  const t = document.createElement("ion-toast");
  t.message = message;
  t.duration = 1800;
  t.position = "top";
  t.positionAnchor = "edition";
  document.querySelector("ion-app").append(t);
  t.present();
}

// ── Notes: marks in the text, the notes in a sheet ──────────────────────────────────────────────
function levelsAt(piece) {
  const byPassage = new Map();
  for (const entry of piece.dataset.p.split(" ")) {
    const [key, size, id] = entry.split("|");
    if (!byPassage.has(key)) byPassage.set(key, { key, size: Number(size), ids: [] });
    byPassage.get(key).ids.push(id);
  }
  return [...byPassage.values()].sort((a, b) => b.size - a.size);
}

function choose(target, levels) {
  if (drill && drill.target === target) drill.at = (drill.at + 1) % drill.levels.length;
  else drill = { target, levels, at: 0 };
  showLevel();
}

function showLevel() {
  const level = drill.levels[drill.at];
  clearSelection();
  selected = [...reading.querySelectorAll(".an")].filter(el =>
    el.dataset.p.split(" ").some(e => e.startsWith(level.key + "|")))
    .concat([...reading.querySelectorAll(".rule")].filter(r => r.dataset.pass === level.key));
  selected.forEach(el => el.classList.add("sel"));
  fillNotes(level);
  sheet.isOpen ? sheet.setCurrentBreakpoint(0.45) : openSheet();
  keepInView(selected[0]);
}

function clearSelection() {
  selected.forEach(el => el.classList.remove("sel"));
  selected = [];
}

function clearChoice() {
  clearSelection();
  drill = null;
}

// The chosen passage stays in the upper part of the screen, above the sheet.
async function keepInView(el) {
  if (!el) return;
  const box = el.getBoundingClientRect(), frame = content.getBoundingClientRect();
  const top = box.top - frame.top;
  if (top < 80 || top > frame.height * 0.45) await content.scrollByPoint(0, top - 110, 300);
}

function fillNotes(level) {
  const notes = DATA.notes[shown] || [];
  const byId = new Map(notes.map(n => [n.id, n]));
  const sections = [];
  if (level) {
    const n = drill.levels.length, count = level.ids.length;
    where.innerHTML = `Passage ${drill.at + 1} of ${n}: <q>${escapeHtml(DATA.passages[shown][level.key])}</q> · ${count} ${count === 1 ? "note" : "notes"}`;
    sections.push(...level.ids.map(id => entry(byId.get(id), true)));
  } else {
    where.textContent = notes.length ? "Tap a bracket or an underlined word to read what is said about it." : "";
    const whole = notes.filter(n => n.whole), parts = notes.filter(n => !n.whole);
    if (whole.length) sections.push(heading("On the whole poem"), ...whole.map(n => entry(n)));
    if (parts.length) sections.push(heading("On passages"), ...parts.map(n => entry(n)));
  }
  notesList.replaceChildren(...sections);
  narrower.style.display = level && drill.levels.length > 1 ? "" : "none";
  narrower.textContent = level && drill.at + 1 === drill.levels.length ? "Broadest" : "Narrower";
  allNotes.style.display = level ? "" : "none";
}

function heading(text) {
  const h = document.createElement("h3");
  h.textContent = text;
  return h;
}

function entry(note, chosen = false) {
  const article = document.createElement("article");
  article.className = chosen ? "nt lit" : "nt";
  const lemma = document.createElement("p");
  lemma.className = "lemma";
  const quoted = document.createElement("i");
  quoted.textContent = note.whole ? "the whole poem" : note.lemma;
  lemma.append(quoted, " ]");
  article.append(lemma);
  article.insertAdjacentHTML("beforeend", note.body);
  article.addEventListener("click", () => fixNote(note.id, article));
  return article;
}

// Tapping a note in the list marks its passages in the text (tap again to let go).
function fixNote(id, article) {
  const was = article.classList.contains("lit") && !drill;
  notesList.querySelectorAll(".nt.lit").forEach(a => a.classList.remove("lit"));
  clearChoice();
  if (was) return;
  article.classList.add("lit");
  selected = [...reading.querySelectorAll(".an, .rule")].filter(el => el.dataset.n.split(" ").includes(id));
  selected.forEach(el => el.classList.add("sel"));
  keepInView(selected[0]);
}

function escapeHtml(text) {
  const span = document.createElement("span");
  span.textContent = text;
  return span.innerHTML;
}

async function openSheet() {
  await customElements.whenDefined("ion-modal");
  await sheet.present();
  await sheet.setCurrentBreakpoint(0.45);  // half height, the text still usable above
}

function afterLayout(task) {
  requestAnimationFrame(() => requestAnimationFrame(task));
}

// ── Drop caps (as on the desktop): measured on the page ─────────────────────────────────────────
const measure = document.createElement("canvas").getContext("2d");
function baseline(el, atStart) {
  const probe = document.createElement("span");
  probe.className = "probe";
  atStart ? el.prepend(probe) : el.append(probe);
  const y = probe.getBoundingClientRect().bottom;
  probe.remove();
  return y;
}
function setInitials(root) {
  for (const cap of root.querySelectorAll(".initial")) {
    cap.classList.remove("dropped");
    cap.removeAttribute("style");
    const first = cap.closest(".lt");
    const lines = [...first.closest(".text").querySelectorAll(".lt")];
    const at = lines.indexOf(first);
    const covered = lines.slice(at, at + Number(cap.dataset.drop));
    const style = getComputedStyle(first), size = parseFloat(style.fontSize);
    measure.font = `${style.fontWeight} ${size}px ${style.fontFamily}`;
    const capHeight = measure.measureText(cap.textContent).actualBoundingBoxAscent / size;
    const top = baseline(first, true) - capHeight * size, foot = baseline(covered[covered.length - 1], true);
    cap.classList.add("dropped");
    cap.style.fontSize = `${(foot - top) / capHeight}px`;
    cap.style.top = `${foot - baseline(cap, false)}px`;
    const width = cap.getBoundingClientRect().width + 0.25 * size;
    cap.style.left = `${-width}px`;
    covered.forEach(lt => { lt.style.marginLeft = `${width}px`; });
  }
}

// ── Wiring ──────────────────────────────────────────────────────────────────────────────────────
segment.addEventListener("ionChange", e => { shown = e.detail.value; render(); });
compareButton.addEventListener("click", () => { compareOn = !compareOn; render(); });
notesButton.addEventListener("click", () => {
  notesOn = !notesOn;
  reading.classList.toggle("show-notes", notesOn);
  updateButtons();
  if (notesOn) { fillNotes(null); openSheet(); } else { sheet.dismiss(); clearChoice(); }
});
sheet.addEventListener("ionModalDidDismiss", () => {
  if (!notesOn) return;
  notesOn = false;
  reading.classList.remove("show-notes");
  clearChoice();
  updateButtons();
});
narrower.addEventListener("click", () => { if (drill) { drill.at = (drill.at + 1) % drill.levels.length; showLevel(); } });
allNotes.addEventListener("click", () => { clearChoice(); fillNotes(null); });
reading.addEventListener("click", e => {
  if (notesOn) {
    const rule = e.target.closest(".rule"), piece = e.target.closest(".an");
    if (rule) return choose(rule, [{ key: rule.dataset.pass, ids: rule.dataset.n.split(" ") }]);
    if (piece) return choose(piece, levelsAt(piece));
  }
  if (compareOn && pairs) {
    const word = e.target.closest(".w");
    if (word) lightPair(word);
  }
});

customElements.whenDefined("ion-modal").then(() => {
  sheet.breakpoints = [0, 0.45, 0.92];
  sheet.initialBreakpoint = 0.45;
  sheet.backdropBreakpoint = 0.6;  // below this the text above stays usable
  sheet.handle = true;
  sheet.expandToScroll = false;  // the notes scroll at any height; drag the handle or header to resize
});
Promise.all([document.fonts.ready, customElements.whenDefined("ion-content")]).then(render);
</script>
</body>
</html>
"""
