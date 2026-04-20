"""
extract_pdf_to_txt.py
---------------------
Converts each scanned PDF in data/docs/ into cleaner .txt in data/docs_text/
using PyMuPDF + Tesseract OCR.

Usage:
    python ingest/extract_pdf_to_txt.py
"""

import re
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageFilter, ImageOps

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "data" / "docs"
OUTPUT_DIR = BASE_DIR / "data" / "docs_text"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ZOOM_X = 2.5
ZOOM_Y = 2.5
MIN_WORDS = 25

IPL_TERMS = {
    "buitler": "buttler",
    "butler": "buttler",
    "rutural": "ruturaj",
    "de keck": "de kock",
    "keck": "kock",
    "challeengers": "challengers",
    "bangaloree": "bangalore",
    "guiarat": "gujarat",
    "titanss": "titans",
    "shamii": "shami",
    "rahanee": "rahane",
    "iyer ": "iyer ",
    "kolkatta": "kolkata",
    "dethi": "delhi",
    "capitalss": "capitals",
    "supergiants": "super giants",
    "lukhnow": "lucknow",
    "sunriserss": "sunrisers",
    "mumbal": "mumbai",
    "rajasthanroyals": "rajasthan royals",
    "du plessiss": "du plessis",
    "hasarangaa": "hasaranga",
    "chakravarthyy": "chakravarthy",
    "gaikwadd": "gaikwad",
    "dhonii": "dhoni",
}

HEADER_PATTERNS = [
    r"^\s*\d{1,2}/\d{1,2}/\d{2,4},?\s*",
    r"^\s*2022 indian premier league\s*-?\s*",
    r"^\s*2023 indian premier league\s*-?\s*",
]

NOISE_PATTERNS = [
    r"https?://\S+",
    r"www\.\S+",
    r"en\.org/wiki/\S+",
    r"\[\d+\]",
    r"retrieved\s+\d{1,2}\s+\w+\s+\d{4}.*",
    r"archived\s+.*?from the original.*",
    r"free encyclopedia",
    r"wikipedia",
    r"official website",
    r"scorecard\s*\(http.*?\)",
    r"utm[_ ]source\s*chatgpt\.com",
    r"\b\d+/\d+\b",
]

PLAYER_TEAM_FIXES = {
    "ms dhoni": "MS Dhoni",
    "virat kohli": "Virat Kohli",
    "rohit sharma": "Rohit Sharma",
    "jos buttler": "Jos Buttler",
    "shubman gill": "Shubman Gill",
    "mohammed shami": "Mohammed Shami",
    "ruturaj gaikwad": "Ruturaj Gaikwad",
    "faf du plessis": "Faf du Plessis",
    "chennai super kings": "Chennai Super Kings",
    "mumbai indians": "Mumbai Indians",
    "gujarat titans": "Gujarat Titans",
    "rajasthan royals": "Rajasthan Royals",
    "delhi capitals": "Delhi Capitals",
    "kolkata knight riders": "Kolkata Knight Riders",
    "lucknow super giants": "Lucknow Super Giants",
    "sunrisers hyderabad": "Sunrisers Hyderabad",
    "punjab kings": "Punjab Kings",
    "royal challengers bangalore": "Royal Challengers Bangalore",
    "royal challengers bengaluru": "Royal Challengers Bengaluru",
}

NOISE_RE = re.compile("|".join(NOISE_PATTERNS), flags=re.IGNORECASE)


def clean_basic(text: str) -> str:
    text = text.replace("\x0c", " ")
    text = text.replace("|", "I")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_repeated_headers(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned = []

    for line in lines:
        if not line:
            cleaned.append("")
            continue

        line_lower = line.lower()
        skip = False
        for pat in HEADER_PATTERNS:
            if re.match(pat, line_lower):
                skip = True
                break

        if skip:
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


def normalize_ocr_words(text: str) -> str:
    text = text.lower()

    for bad, good in IPL_TERMS.items():
        text = re.sub(rf"\b{re.escape(bad)}\b", good, text)

    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"(?<=[a-z])(?=\d)", " ", text)
    text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)

    text = NOISE_RE.sub(" ", text)

    text = re.sub(r"[^\w\s.,:;!?()/%-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    for low, proper in PLAYER_TEAM_FIXES.items():
        text = re.sub(rf"\b{re.escape(low)}\b", proper, text, flags=re.IGNORECASE)

    text = re.sub(r"\s+([.,:;!?])", r"\1", text)
    return text.strip()


def restore_line_structure(text: str) -> str:
    text = re.sub(r"\b(match\s+\d+)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(points table)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(match summary)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(venues)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(background)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(format)\b", r"\n\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_table_garbage(text: str) -> bool:
    words = text.split()
    if not words:
        return True

    short_tokens = sum(1 for w in words if len(w) <= 2)
    digit_tokens = sum(1 for w in words if any(ch.isdigit() for ch in w))
    slash_tokens = sum(1 for w in words if "/" in w)

    ratio_short = short_tokens / len(words)
    ratio_digit = digit_tokens / len(words)
    ratio_slash = slash_tokens / len(words)

    if ratio_short > 0.45 and ratio_digit > 0.20:
        return True

    if ratio_slash > 0.15 and len(words) < 120:
        return True

    return False


def preprocess_image(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.filter(ImageFilter.SHARPEN)

    img = img.point(lambda p: 255 if p > 165 else 0)
    return img


def render_body_only(page: fitz.Page) -> Image.Image:
    rect = page.rect

    top_crop = rect.height * 0.06
    bottom_crop = rect.height * 0.05

    clip = fitz.Rect(
        rect.x0,
        rect.y0 + top_crop,
        rect.x1,
        rect.y1 - bottom_crop,
    )

    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM_X, ZOOM_Y), clip=clip, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


def ocr_page(page: fitz.Page) -> str:
    img = render_body_only(page)
    img = preprocess_image(img)

    raw = pytesseract.image_to_string(
        img,
        config="--oem 3 --psm 4"
    )

    text = clean_basic(raw)
    text = strip_repeated_headers(text)
    text = normalize_ocr_words(text)
    text = restore_line_structure(text)

    return text


def process_pdf(pdf_path: Path) -> bool:
    print(f"\n{'=' * 60}")
    print(f"Processing: {pdf_path.name}")
    print(f"{'=' * 60}")

    doc = fitz.open(pdf_path)
    good_pages = []

    for i, page in enumerate(doc, start=1):
        print(f"  Page {i}/{len(doc)} OCR...", end="\r", flush=True)
        text = ocr_page(page)

        word_count = len(text.split())
        if word_count < MIN_WORDS:
            continue

        if looks_like_table_garbage(text):
            continue

        good_pages.append(f"[PAGE {i}]\n{text}\n")

    doc.close()
    print()

    if not good_pages:
        print(f"  No usable text extracted from {pdf_path.name}")
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{pdf_path.stem}.txt"
    out_file.write_text("\n".join(good_pages), encoding="utf-8")

    print(f"  Saved {len(good_pages)} cleaned pages -> {out_file}")
    return True


def main():
    pdfs = sorted(DOCS_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDF files found in: {DOCS_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdfs)} PDF(s) in {DOCS_DIR}\n")
    results = [process_pdf(p) for p in pdfs]

    ok = sum(results)
    bad = len(results) - ok

    print(f"\n{'=' * 60}")
    print(f"Done. {ok} succeeded, {bad} failed.")


if __name__ == "__main__":
    main()