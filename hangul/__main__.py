"""
Hangul Practice Sheet Generator
(Cloze + Compact Breakdown + Interlinear Gloss + Vocab + Duplex-even pages)

Features
--------
1) Compact syllable breakdown with English labels:
      양 = ㅇ(silent/ng ...) + ㅑ(ya) + ㅇ(...)
2) NO tiny-part (jamo) repetition rows.
3) One repetition line per *syllable*, arranged in 4 columns.
4) Cloze (fill-in-the-blank) uses large blanks (＿) and selects 10 at random (stable per sentence).
5) Prints English gloss + ASCII interlinear gloss side-by-side.
6) Prints per-sentence vocab at bottom: "word: definition"
7) Ensures an EVEN number of pages (adds one blank page if odd) for duplex printing.

Packages
--------
pip install reportlab jamo

Usage
-----
1) Set FONT_PATH to a Hangul-capable TTF (TrueType outlines). On Windows:
      C:\Windows\Fonts\malgun.ttf
   (ReportLab TTFont does NOT support CFF/PostScript-outline OTF files.)
2) Run: python hangul_workbook.py
3) Output: ./out/hangul_workbook.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import hashlib
import random

from jamo import h2j, j2hcj
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


# =========================
# DATA (edit this section)
# =========================


@dataclass(frozen=True)
class Sentence:
    """A single workbook item."""

    hangul: str
    romanized: str
    gloss: str  # English gloss
    interlinear_gloss: str  # ASCII interlinear gloss (e.g., morpheme tags)
    vocab: Sequence[Tuple[str, str]]  # (word, definition) e.g., ("고양이", "cat")


@dataclass(frozen=True)
class Theme:
    """A themed collection of sentences."""

    name: str
    sentences: Sequence[Sentence]


CAT_THEME: Theme = Theme(
    name="Cats",
    sentences=(
        Sentence(
            hangul="고양이는 있다.",
            romanized="goyang-ineun itda.",
            gloss="There is a cat.",
            interlinear_gloss="cat-TOP exist-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("있다", "to exist; to have"),
            ),
        ),
        Sentence(
            hangul="고양이는 잔다.",
            romanized="goyang-ineun janda.",
            gloss="The cat sleeps.",
            interlinear_gloss="cat-TOP sleep-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("자다", "to sleep"),
            ),
        ),
        Sentence(
            hangul="고양이는 먹는다.",
            romanized="goyang-ineun meokneunda.",
            gloss="The cat eats.",
            interlinear_gloss="cat-TOP eat-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("먹다", "to eat"),
                ("-는다/-ㄴ다", "present declarative"),
            ),
        ),
        Sentence(
            hangul="작은 고양이는 검다.",
            romanized="jageun goyang-ineun geomda.",
            gloss="The small cat is black.",
            interlinear_gloss="small cat-TOP black-DECL",
            vocab=(
                ("작다", "to be small"),
                ("-은", "attributive (adj)"),
                ("고양이", "cat"),
                ("검다", "to be black"),
            ),
        ),
        Sentence(
            hangul="고양이는 의자 위에 있다.",
            romanized="goyang-ineun uija wie itda.",
            gloss="The cat is on the chair.",
            interlinear_gloss="cat-TOP chair top-LOC exist-DECL",
            vocab=(
                ("고양이", "cat"),
                ("의자", "chair"),
                ("위", "top; above"),
                ("-에", "location/time particle"),
                ("있다", "to exist; to be located"),
            ),
        ),
        Sentence(
            hangul="고양이는 걷는다.",
            romanized="goyang-ineun geotneunda.",
            gloss="The cat walks.",
            interlinear_gloss="cat-TOP walk-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("걷다", "to walk"),
                ("-는다/-ㄴ다", "present declarative"),
            ),
        ),
        Sentence(
            hangul="고양이는 운다.",
            romanized="goyang-ineun unda.",
            gloss="The cat cries/meows.",
            interlinear_gloss="cat-TOP cry-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("울다", "to cry; to meow"),
                ("-ㄴ다", "present declarative"),
            ),
        ),
        Sentence(
            hangul="고양이는 본다.",
            romanized="goyang-ineun bonda.",
            gloss="The cat sees.",
            interlinear_gloss="cat-TOP see-DECL",
            vocab=(
                ("고양이", "cat"),
                ("-는/-은", "TOPIC marker"),
                ("보다", "to see"),
                ("-ㄴ다", "present declarative"),
            ),
        ),
    ),
)

THEMES: Sequence[Theme] = (CAT_THEME,)

# =========================
# CONFIG
# =========================

FONT_PATH: Path = Path(r"C:\Windows\Fonts\malgun.ttf")  # must be TrueType .ttf (glyf)
OUTPUT_PDF: Path = Path("./out/hangul_workbook.pdf")
PAGE_SIZE = letter

# Typography
FONT_NAME: str = "HangulFont"
FONT_SIZE_HANGUL: int = 20
FONT_SIZE_ROM: int = 11
FONT_SIZE_GLOSS: int = 10
FONT_SIZE_IGLOSS: int = 10
FONT_SIZE_SECTION: int = 12
FONT_SIZE_BODY: int = 11
FONT_SIZE_CLOZE: int = 12
FONT_SIZE_VOCAB: int = 10

# Layout (points; 72pt = 1 inch)
MARGIN_X: float = 48
MARGIN_Y: float = 54
LINE_GAP: float = 16
SECTION_GAP: float = 18

# Ink efficiency
THIN_LINE_WIDTH: float = 0.25

# Cloze generation
MAX_CLOZE_POOL: int = 60  # generate pool then sample 10
CLOZE_SAMPLE_N: int = 10
MAX_SPAN_LEN: int = 6
INCLUDE_WORD_LEVEL: bool = True
INCLUDE_SPAN_LEVEL: bool = True

# Rendering density
CLOZE_COLUMNS: int = 2
CLOZE_ROW_GAP_MULT: float = 1.5  # 1/2 blank line between rows
SYLLABLE_PRACTICE_COLUMNS: int = 4

# Large blanks
BLANK_CHAR: str = "＿"  # U+FF3F FULLWIDTH LOW LINE
BLANK_CHARS_PER_SYLLABLE: int = 3

# Vocab rendering
VOCAB_COLUMNS: int = 2  # bottom section columns


# =========================
# CODE
# =========================


def is_hangul_syllable(ch: str) -> bool:
    return "가" <= ch <= "힣"


def register_font(font_path: Path) -> None:
    if not font_path.exists():
        raise FileNotFoundError(
            f"FONT_PATH does not exist: {font_path}. "
            "Point FONT_PATH to a Hangul-capable TrueType .ttf (e.g., malgun.ttf on Windows)."
        )
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))


def decompose_syllable(ch: str) -> List[str]:
    """Return compatibility jamo for a single Hangul syllable."""
    return list(j2hcj(h2j(ch)))


def unique_syllables_in_order(text: str) -> List[str]:
    """Unique Hangul syllables in first-seen order."""
    seen: set[str] = set()
    out: List[str] = []
    for c in text:
        if is_hangul_syllable(c) and c not in seen:
            seen.add(c)
            out.append(c)
    return out


JAMO_LABEL: Dict[str, str] = {
    # consonants
    "ㄱ": "g/k", #  (giyeok)
    "ㄲ": "kk", # (ssanggiyeok)
    "ㄴ": "n", #  (nieun)
    "ㄷ": "d/t", #  (digeut)
    "ㄸ": "tt", # (ssangdigeut)
    "ㄹ": "r/l", # (rieul)
    "ㅁ": "m", # (mieum)
    "ㅂ": "b/p", # (bieup)
    "ㅃ": "pp", # (ssangbieup)
    "ㅅ": "s", # (siot)
    "ㅆ": "ss", # (ssangsiot)
    "ㅇ": "silent/ng", # (ieung)
    "ㅈ": "j", # (jieut)
    "ㅉ": "jj", # (ssangjieut)
    "ㅊ": "ch", # (chieut)
    "ㅋ": "k", # (kieuk)
    "ㅌ": "t", # (tieut)
    "ㅍ": "p", # (pieup)
    "ㅎ": "h", # (hieut)
    # vowels
    "ㅏ": "a",
    "ㅐ": "ae",
    "ㅑ": "ya",
    "ㅒ": "yae",
    "ㅓ": "eo",
    "ㅔ": "e",
    "ㅕ": "yeo",
    "ㅖ": "ye",
    "ㅗ": "o",
    "ㅘ": "wa",
    "ㅙ": "wae",
    "ㅚ": "oe",
    "ㅛ": "yo",
    "ㅜ": "u",
    "ㅝ": "wo",
    "ㅞ": "we",
    "ㅟ": "wi",
    "ㅠ": "yu",
    "ㅡ": "eu",
    "ㅢ": "ui",
    "ㅣ": "i",
}


def breakdown_line(syllable: str) -> str:
    if not is_hangul_syllable(syllable):
        return ""
    parts = decompose_syllable(syllable)
    labeled: List[str] = []
    for j in parts:
        lbl = JAMO_LABEL.get(j)
        labeled.append(f"{j}({lbl})" if lbl else j)
    return f"{syllable} = " + " + ".join(labeled)


def _blank_run(n_syllables: int) -> str:
    count = max(1, n_syllables) * max(1, BLANK_CHARS_PER_SYLLABLE)
    return BLANK_CHAR * count


def _hangul_syllable_positions(text: str) -> List[int]:
    return [i for i, ch in enumerate(text) if is_hangul_syllable(ch)]


def _replace_range(text: str, start: int, end_exclusive: int, repl: str) -> str:
    return text[:start] + repl + text[end_exclusive:]


def generate_cloze_pool(
        text: str,
        *,
        include_word_level: bool,
        include_span_level: bool,
        max_items: int,
        max_span_len: int,
) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()

    def emit(candidate: str) -> None:
        if candidate == text or candidate in seen:
            return
        seen.add(candidate)
        out.append(candidate)

    if include_word_level:
        tokens = text.split(" ")
        for idx, tok in enumerate(tokens):
            if not any(is_hangul_syllable(ch) for ch in tok):
                continue
            blanked_chars = [BLANK_CHAR if is_hangul_syllable(ch) else ch for ch in tok]
            new_tokens = list(tokens)
            new_tokens[idx] = "".join(blanked_chars)
            emit(" ".join(new_tokens))
            if len(out) >= max_items:
                return out

    if include_span_level:
        positions = _hangul_syllable_positions(text)
        if positions:
            runs: List[List[int]] = []
            cur: List[int] = [positions[0]]
            for p in positions[1:]:
                if p == cur[-1] + 1:
                    cur.append(p)
                else:
                    runs.append(cur)
                    cur = [p]
            runs.append(cur)

            for run in runs:
                L = len(run)
                for span_len in range(1, min(max_span_len, L) + 1):
                    for start_i in range(0, L - span_len + 1):
                        start_pos = run[start_i]
                        end_pos = run[start_i + span_len - 1] + 1
                        emit(_replace_range(text, start_pos, end_pos, _blank_run(span_len)))
                        if len(out) >= max_items:
                            return out

    return out[:max_items]


def stable_rng_for_sentence(hangul: str) -> random.Random:
    digest = hashlib.sha256(hangul.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    return random.Random(seed)


def draw_header(c: Canvas, x: float, y: float, theme_name: str, page_no: int) -> None:
    c.setLineWidth(THIN_LINE_WIDTH)
    c.setFont(FONT_NAME, 10)
    c.drawString(x, y, f"Theme: {theme_name}")
    c.drawRightString(PAGE_SIZE[0] - MARGIN_X, y, f"Page {page_no}")


def draw_sentence_block(c: Canvas, x: float, y: float, s: Sentence) -> float:
    c.setFont(FONT_NAME, FONT_SIZE_HANGUL)
    c.drawString(x, y, s.hangul)
    y -= LINE_GAP * 1.35

    if s.romanized.strip():
        c.setFont(FONT_NAME, FONT_SIZE_ROM)
        c.drawString(x, y, s.romanized)
        y -= LINE_GAP * 0.95

    # Gloss + Interlinear gloss side-by-side
    usable_w = PAGE_SIZE[0] - 2 * MARGIN_X
    col_w = usable_w / 2.0

    c.setFont(FONT_NAME, FONT_SIZE_GLOSS)
    c.drawString(x, y, f"Gloss: {s.gloss}".strip())

    c.setFont(FONT_NAME, FONT_SIZE_IGLOSS)
    c.drawString(x + col_w, y, f"IG: {s.interlinear_gloss}".strip())
    y -= LINE_GAP * 1.0

    return y - SECTION_GAP


def draw_breakdown_and_syllable_practice(c: Canvas, x: float, y: float, hangul: str) -> float:
    syllables = unique_syllables_in_order(hangul)

    c.setFont(FONT_NAME, FONT_SIZE_SECTION)
    c.drawString(x, y, "Breakdown (syllable = parts)")
    y -= LINE_GAP * 0.95

    c.setFont(FONT_NAME, FONT_SIZE_BODY)
    for sy in syllables:
        line = breakdown_line(sy)
        if line:
            c.drawString(x, y, line)
            y -= LINE_GAP * 0.90
        if y < MARGIN_Y + 12 * LINE_GAP:
            break

    y -= SECTION_GAP * 0.8

    c.setFont(FONT_NAME, FONT_SIZE_SECTION)
    c.drawString(x, y, "Write each syllable (repeat on the line)")
    y -= LINE_GAP

    cols = max(1, SYLLABLE_PRACTICE_COLUMNS)
    usable_w = PAGE_SIZE[0] - 2 * MARGIN_X
    col_w = usable_w / float(cols)
    row_h = LINE_GAP * 1.2

    c.setLineWidth(THIN_LINE_WIDTH)
    c.setFont(FONT_NAME, 12)

    rows_used = 0
    for i, sy in enumerate(syllables):
        row = i // cols
        col = i % cols
        rows_used = max(rows_used, row + 1)

        cx = x + col * col_w
        cy = y - row * row_h
        if cy < MARGIN_Y + 9 * LINE_GAP:
            break

        c.drawString(cx, cy, f"{sy}:")
        line_x0 = cx + 22
        line_x1 = cx + col_w - 6
        if line_x1 > line_x0 + 20:
            c.line(line_x0, cy - 4, line_x1, cy - 4)

    y = y - rows_used * row_h
    return y - SECTION_GAP


def draw_cloze_block(c: Canvas, x: float, y: float, hangul: str) -> float:
    c.setFont(FONT_NAME, FONT_SIZE_SECTION)
    c.drawString(x, y, "Fill in the blank (10 selected)")
    y -= LINE_GAP

    pool = generate_cloze_pool(
        hangul,
        include_word_level=INCLUDE_WORD_LEVEL,
        include_span_level=INCLUDE_SPAN_LEVEL,
        max_items=MAX_CLOZE_POOL,
        max_span_len=MAX_SPAN_LEN,
    )

    rng = stable_rng_for_sentence(hangul)
    if len(pool) > CLOZE_SAMPLE_N:
        items = rng.sample(pool, k=CLOZE_SAMPLE_N)
    else:
        items = pool

    c.setFont(FONT_NAME, FONT_SIZE_CLOZE)
    usable_w = PAGE_SIZE[0] - 2 * MARGIN_X
    col_w = usable_w / float(max(1, CLOZE_COLUMNS))
    rows = (len(items) + CLOZE_COLUMNS - 1) // CLOZE_COLUMNS

    for idx, line in enumerate(items):
        col = idx // rows
        row = idx % rows
        cx = x + col * col_w
        cy = y - row * (LINE_GAP * CLOZE_ROW_GAP_MULT)
        if cy < MARGIN_Y + 8 * LINE_GAP:
            break
        c.drawString(cx, cy, line)

    y = y - rows * (LINE_GAP * CLOZE_ROW_GAP_MULT) - SECTION_GAP * 0.8
    return y


def draw_vocab_block(c: Canvas, x: float, y: float, vocab: Sequence[Tuple[str, str]]) -> float:
    c.setFont(FONT_NAME, FONT_SIZE_SECTION)
    c.drawString(x, y, "Vocab")
    y -= LINE_GAP * 0.9

    if not vocab:
        c.setFont(FONT_NAME, FONT_SIZE_VOCAB)
        c.drawString(x, y, "(none)")
        return y - SECTION_GAP

    c.setFont(FONT_NAME, FONT_SIZE_VOCAB)

    cols = max(1, VOCAB_COLUMNS)
    usable_w = PAGE_SIZE[0] - 2 * MARGIN_X
    col_w = usable_w / float(cols)

    rows = (len(vocab) + cols - 1) // cols
    # Render column-major (fills down) to keep scanning simple.
    for i, (word, definition) in enumerate(vocab):
        col = i // rows
        row = i % rows
        cx = x + col * col_w
        cy = y - row * (LINE_GAP * 0.9)
        if cy < MARGIN_Y + LINE_GAP:
            break
        c.drawString(cx, cy, f"{word}: {definition}")

    y = y - rows * (LINE_GAP * 0.9) - SECTION_GAP * 0.5
    return y


def render_sentence_page(c: Canvas, theme_name: str, page_no: int, s: Sentence) -> int:
    draw_header(c, MARGIN_X, PAGE_SIZE[1] - MARGIN_Y + 18, theme_name, page_no)

    y = PAGE_SIZE[1] - MARGIN_Y - 20
    y = draw_sentence_block(c, MARGIN_X, y, s)
    y = draw_breakdown_and_syllable_practice(c, MARGIN_X, y, s.hangul)
    y = draw_cloze_block(c, MARGIN_X, y, s.hangul)

    # Force vocab to bottom-ish by jumping near bottom if there is lots of space.
    # (Still safe if sections ran long.)
    min_vocab_y = MARGIN_Y + 8 * LINE_GAP
    if y > min_vocab_y + 3 * LINE_GAP:
        y = max(min_vocab_y, y)

    _ = draw_vocab_block(c, MARGIN_X, max(MARGIN_Y + 4 * LINE_GAP, y), s.vocab)

    c.showPage()
    return page_no + 1


def ensure_out_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_workbook(themes: Sequence[Theme], out_pdf: Path) -> None:
    ensure_out_dir(out_pdf)
    register_font(FONT_PATH)

    c = Canvas(str(out_pdf), pagesize=PAGE_SIZE)

    page_no = 1
    for theme in themes:
        for s in theme.sentences:
            page_no = render_sentence_page(c, theme.name, page_no, s)

    total_pages = page_no - 1
    if total_pages % 2 == 1:
        # Pad with one blank page to make total even for duplex printing.
        c.showPage()

    c.save()


def main() -> None:
    build_workbook(THEMES, OUTPUT_PDF)
    print(f"Wrote: {OUTPUT_PDF.resolve()}")


if __name__ == "__main__":
    main()
