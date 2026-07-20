"""Generate the T1-T8 test label images per SPEC.md section 12.

Labels are synthetically rendered (not AI-generated photos) for deterministic
ground truth: every character on every label is known exactly, so expected
verdicts are provable rather than hoped-for. T7 applies glare/rotation/blur
post-processing to simulate a bad photo.

Run: python generate_test_labels.py [output_dir]
"""

import math
import sys
import textwrap

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
SERIF_BOLD = f"{FONT_DIR}/DejaVuSerif-Bold.ttf"
SERIF = f"{FONT_DIR}/DejaVuSerif.ttf"
SANS = f"{FONT_DIR}/DejaVuSans.ttf"
SANS_BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"

W, H = 1100, 1500
CREAM = (245, 240, 228)
INK = (32, 28, 24)
GOLD = (146, 110, 42)
WINE_BG = (243, 238, 230)
WINE_ACCENT = (94, 28, 38)

WARNING_PREFIX_CORRECT = "GOVERNMENT WARNING:"
WARNING_PREFIX_TITLE = "Government Warning:"
WARNING_BODY_CORRECT = (
    "(1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability "
    "to drive a car or operate machinery, and may cause health problems."
)
# T4: one word changed — "drive" -> "use"
WARNING_BODY_WORD_SWAP = WARNING_BODY_CORRECT.replace(
    "to drive a car", "to use a car"
)


def draw_centered(draw, y, text, font, fill=INK, tracking=0):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)
    return y + (bbox[3] - bbox[1])


def draw_warning_block(draw, y, prefix, body, bold_prefix=True, box_w=900):
    """Render the warning: prefix inline-bold at the start of wrapped body."""
    f_bold = ImageFont.truetype(SANS_BOLD, 26)
    f_reg = ImageFont.truetype(SANS, 26)
    x0 = (W - box_w) / 2
    full = prefix + " " + body
    words = full.split(" ")
    n_prefix_words = len(prefix.split(" "))
    line_h = 38
    x, cur_y = x0, y
    for i, word in enumerate(words):
        font = f_bold if (bold_prefix and i < n_prefix_words) else f_reg
        wbox = draw.textbbox((0, 0), word + " ", font=font)
        ww = wbox[2] - wbox[0]
        if x + ww > x0 + box_w:
            x = x0
            cur_y += line_h
        draw.text((x, cur_y), word, font=font, fill=INK)
        x += ww
    return cur_y + line_h


def base_label(brand, class_lines, abv_text, net_text, bg=CREAM, accent=GOLD,
               est_year="EST. 1897"):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    # border
    d.rectangle([30, 30, W - 30, H - 30], outline=accent, width=6)
    d.rectangle([50, 50, W - 50, H - 50], outline=accent, width=2)

    y = 130
    f_small = ImageFont.truetype(SERIF, 30)
    y = draw_centered(d, y, est_year, f_small, fill=accent) + 40

    f_brand = ImageFont.truetype(SERIF_BOLD, 78)
    for line in brand.split("\n"):
        y = draw_centered(d, y, line, f_brand) + 24
    y += 10

    # rule
    d.line([(W / 2 - 260, y), (W / 2 + 260, y)], fill=accent, width=3)
    y += 50

    f_class = ImageFont.truetype(SERIF, 42)
    for line in class_lines:
        y = draw_centered(d, y, line, f_class) + 22
    y += 60

    f_stats = ImageFont.truetype(SANS, 36)
    if abv_text:
        y = draw_centered(d, y, abv_text, f_stats) + 20
    y = draw_centered(d, y, net_text, f_stats) + 20
    return img, d, y


def finish(img, path):
    img.save(path, "PNG")
    print(f"  wrote {path}")


def t1(out):
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_CORRECT)
    finish(img, f"{out}/t1_clean_pass.png")


def t2(out):
    img, d, y = base_label(
        "STONE'S THROW",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_CORRECT)
    finish(img, f"{out}/t2_brand_case_variant.png")


def t3(out):
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_TITLE, WARNING_BODY_CORRECT)
    finish(img, f"{out}/t3_warning_title_case.png")


def t4(out):
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_WORD_SWAP)
    finish(img, f"{out}/t4_warning_word_swap.png")


def t5(out):
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    # no warning at all
    finish(img, f"{out}/t5_warning_missing.png")


def t6(out):
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "40% Alc./Vol. (80 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_CORRECT)
    finish(img, f"{out}/t6_abv_mismatch.png")


def t7(out):
    # start from a clean T1-style label, then wreck it: rotate, glare, blur
    img, d, y = base_label(
        "OLD TOM\nDISTILLERY",
        ["Kentucky Straight", "Bourbon Whiskey"],
        "45% Alc./Vol. (90 Proof)", "750 mL",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_CORRECT)

    img = img.rotate(14, expand=True, fillcolor=(180, 175, 165))
    img = img.filter(ImageFilter.GaussianBlur(3.5))

    # two hard glare bands
    glare = Image.new("L", img.size, 0)
    gd = ImageDraw.Draw(glare)
    w2, h2 = img.size
    gd.polygon(
        [(w2 * 0.05, 0), (w2 * 0.55, 0), (w2 * 0.30, h2), (w2 * -0.20, h2)],
        fill=235,
    )
    gd.polygon(
        [(w2 * 0.60, 0), (w2 * 0.85, 0), (w2 * 1.05, h2), (w2 * 0.80, h2)],
        fill=200,
    )
    glare = glare.filter(ImageFilter.GaussianBlur(60))
    white = Image.new("RGB", img.size, (255, 255, 255))
    img = Image.composite(white, img, glare)
    img = ImageEnhance.Contrast(img).enhance(0.62)
    img = ImageEnhance.Brightness(img).enhance(1.18)
    finish(img, f"{out}/t7_bad_image_glare.png")


def t8(out):
    img, d, y = base_label(
        "CHATEAU MERIDIAN",
        ["Red Table Wine", "Columbia Valley"],
        None, "750 mL",
        bg=WINE_BG, accent=WINE_ACCENT, est_year="VINTED & BOTTLED",
    )
    draw_warning_block(d, H - 320, WARNING_PREFIX_CORRECT, WARNING_BODY_CORRECT)
    finish(img, f"{out}/t8_wine_no_abv.png")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for fn in (t1, t2, t3, t4, t5, t6, t7, t8):
        fn(out)
    print("done — 8 labels")
