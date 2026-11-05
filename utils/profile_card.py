import io
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import MAX_WARNS

BG_TEMPLATE_PATHS = [
    "assets/profile_bg.png",
    "assets/profile_bg.jpg",
    "assets/profile_bg.webp",
    "profile_bg.png",
]

def days_since(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return max(0, (datetime.now() - dt).days)
    except Exception:
        return 0

def _plural_days(n: int) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 10 < n_abs < 20:
        return f"{n} дней"
    if n1 == 1:
        return f"{n} день"
    if 2 <= n1 <= 4:
        return f"{n} дня"
    return f"{n} дней"

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates.extend([
            "assets/font_bold.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ])
    else:
        candidates.extend([
            "assets/font_regular.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    center_xy: tuple[int, int],
    text: str,
    max_width: int,
    max_size: int,
    min_size: int = 13,
    bold: bool = True,
    fill=(255, 255, 255, 255),
    stroke_fill=(25, 10, 45, 220),
    stroke_width: int = 2
):
    clean_text = text.strip() or "Support"
    chosen_font = _load_font(min_size, bold=bold)

    for sz in range(max_size, min_size - 1, -1):
        font = _load_font(sz, bold=bold)
        bbox = draw.textbbox((0, 0), clean_text, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            chosen_font = font
            break
    else:
        while len(clean_text) > 4:
            clean_text = clean_text[:-1]
            bbox = draw.textbbox((0, 0), clean_text + "...", font=chosen_font)
            if (bbox[2] - bbox[0]) <= max_width:
                clean_text += "..."
                break

    draw.text(
        center_xy,
        clean_text,
        font=chosen_font,
        fill=fill,
        anchor="mm",
        stroke_width=stroke_width,
        stroke_fill=stroke_fill
    )

def _build_fallback_background(W: int, H: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), (11, 5, 24, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)

    g_draw.ellipse((40, 60, 420, 440), fill=(155, 55, 255, 95))
    g_draw.ellipse((820, -40, 1220, 290), fill=(175, 85, 255, 85))
    g_draw.ellipse((400, 220, 1250, 720), fill=(115, 30, 210, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=55))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    def glass_box(xy, radius=20, outline=(165, 90, 255, 235), fill=(22, 10, 44, 210), width_px=2):
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width_px)

    cx, cy, r = 223, 250, 114
    draw.ellipse((cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), outline=(185, 110, 255, 255), width=3)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(15, 7, 30, 240), outline=(140, 75, 235, 220), width=2)

    glass_box((75, 381, 380, 439), radius=18)
    glass_box((130, 456, 326, 493), radius=15)
    glass_box((130, 509, 326, 546), radius=15)

    top_boxes = [(415, 206, 622, 330), (634, 206, 842, 330), (854, 206, 1062, 330), (1074, 206, 1245, 330)]
    for b in top_boxes:
        glass_box(b, radius=20)

    glass_box((415, 355, 1245, 456), radius=22)
    glass_box((415, 478, 1245, 646), radius=24)
    return img

def generate_profile_image(username: str, support_data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    W, H = 1280, 720

    bg_img = None
    for p in BG_TEMPLATE_PATHS:
        if os.path.exists(p):
            try:
                bg_img = Image.open(p).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
                break
            except Exception:
                pass

    if bg_img is None:
        img = _build_fallback_background(W, H)
    else:
        img = bg_img.copy()

    cx, cy, av_r = 223, 250, 108
    av_diam = av_r * 2
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((av_diam, av_diam), Image.Resampling.LANCZOS)
            mask = Image.new("L", (av_diam, av_diam), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_diam, av_diam), fill=255)
            img.paste(av, (cx - av_r, cy - av_r), mask)
        except Exception:
            pass

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    dot_color = (250, 175, 60, 255) if support_data.get("vacation_until") else (165, 95, 255, 255)
    odraw.ellipse((306, 303, 332, 329), fill=dot_color)

    _draw_fitted_text(
        odraw,
        center_xy=(227, 410),
        text=username,
        max_width=278,
        max_size=28,
        min_size=14,
        bold=True,
        fill=(255, 255, 255, 255)
    )

    pt_val = support_data.get("prime_time") or "ПТ не назначен"
    _draw_fitted_text(
        odraw,
        center_xy=(228, 474),
        text=f"ПТ: {pt_val}" if support_data.get("prime_time") else "ПТ не назначен",
        max_width=180,
        max_size=17,
        min_size=12,
        bold=True,
        fill=(235, 215, 255, 255)
    )

    prob_val = support_data.get("probation_until")
    hire_val = support_data.get("hire_date") or "—"
    third_pill_text = f"Исп. до {prob_val}" if prob_val else f"С {hire_val}"
    _draw_fitted_text(
        odraw,
        center_xy=(228, 527),
        text=third_pill_text,
        max_width=180,
        max_size=16,
        min_size=11,
        bold=True,
        fill=(215, 190, 250, 255)
    )

    tokens = support_data.get("balance", 0)
    salary_forecast = round(tokens * 0.04, 1)
    if isinstance(salary_forecast, float) and salary_forecast.is_integer():
        salary_forecast = int(salary_forecast)
    vacation_str = f"До {support_data['vacation_until']}" if support_data.get("vacation_until") else "Нет"
    warns_count = min(MAX_WARNS, max(0, int(support_data.get("warns", 0))))
    warns_str = f"{warns_count} / {MAX_WARNS}"

    top_cards_info = [
        ((415, 206, 622, 330), "Токены", str(tokens), (255, 235, 255, 255)),
        ((634, 206, 842, 330), "Прогноз зарплаты", str(salary_forecast), (255, 235, 255, 255)),
        ((854, 206, 1062, 330), "Отпуск", vacation_str, (255, 235, 255, 255)),
        ((1074, 206, 1245, 330), "Выговоры", warns_str, (255, 120, 145, 255) if warns_count > 0 else (255, 235, 255, 255)),
    ]

    font_card_title = _load_font(16, bold=True)
    for (x1, y1, x2, y2), title, val, val_color in top_cards_info:
        mid_x = (x1 + x2) // 2
        odraw.text(
            (mid_x, y1 + 32),
            title,
            font=font_card_title,
            fill=(220, 195, 255, 255),
            anchor="mm",
            stroke_width=2,
            stroke_fill=(20, 8, 40, 220)
        )
        pill_x1, pill_y1, pill_x2, pill_y2 = x1 + 14, y1 + 58, x2 - 14, y2 - 14
        odraw.rounded_rectangle(
            (pill_x1, pill_y1, pill_x2, pill_y2),
            radius=13,
            fill=(30, 12, 58, 175),
            outline=(170, 95, 255, 190),
            width=1
        )
        _draw_fitted_text(
            odraw,
            center_xy=(mid_x, (pill_y1 + pill_y2) // 2),
            text=val,
            max_width=(pill_x2 - pill_x1 - 14),
            max_size=26,
            min_size=14,
            bold=True,
            fill=val_color
        )

    font_sec_title = _load_font(20, bold=True)
    odraw.text(
        (830, 376),
        "✦  Статистика саппорта  ✦",
        font=font_sec_title,
        fill=(245, 225, 255, 255),
        anchor="mm",
        stroke_width=2,
        stroke_fill=(20, 8, 40, 230)
    )

    total_days_str = _plural_days(days_since(support_data.get("hire_date", "")))
    total_mins_str = f"{support_data.get('total_minutes', 0):,}".replace(",", " ")

    mid_pills = [
        ((435, 396, 820, 444), "Всего на саппорте", f"{total_days_str} ✦"),
        ((840, 396, 1225, 444), "Всего минут в прихожих", f"{total_mins_str} ✦"),
    ]
    font_stat_lbl = _load_font(17, bold=True)
    for (px1, py1, px2, py2), lbl, val in mid_pills:
        odraw.rounded_rectangle(
            (px1, py1, px2, py2),
            radius=14,
            fill=(34, 14, 65, 185),
            outline=(175, 100, 255, 200),
            width=1
        )
        ym = (py1 + py2) // 2
        odraw.text(
            (px1 + 20, ym),
            lbl,
            font=font_stat_lbl,
            fill=(230, 210, 255, 255),
            anchor="lm",
            stroke_width=1,
            stroke_fill=(15, 5, 30, 200)
        )
        _draw_fitted_text(
            odraw,
            center_xy=(px2 - 65, ym),
            text=val,
            max_width=130,
            max_size=21,
            min_size=14,
            bold=True,
            fill=(255, 255, 255, 255)
        )

    bottom_stats = [
        ((435, 496, 820, 554), "Допусков", f"{support_data.get('admitted', 0)} ✦"),
        ((840, 496, 1225, 554), "Недопусков", f"{support_data.get('rejected', 0)} ✦"),
        ((435, 570, 820, 628), "Принятых замен", f"{support_data.get('swaps_taken', 0)} ✦"),
        ((840, 570, 1225, 628), "Обработано тикетов", f"{support_data.get('tickets', 0)} ✦"),
    ]

    for (bx1, by1, bx2, by2), lbl, val in bottom_stats:
        odraw.rounded_rectangle(
            (bx1, by1, bx2, by2),
            radius=15,
            fill=(34, 14, 65, 185),
            outline=(175, 100, 255, 205),
            width=1
        )
        ym = (by1 + by2) // 2
        odraw.text(
            (bx1 + 22, ym),
            lbl,
            font=font_stat_lbl,
            fill=(230, 210, 255, 255),
            anchor="lm",
            stroke_width=1,
            stroke_fill=(15, 5, 30, 200)
        )
        _draw_fitted_text(
            odraw,
            center_xy=(bx2 - 65, ym),
            text=val,
            max_width=125,
            max_size=23,
            min_size=14,
            bold=True,
            fill=(255, 255, 255, 255)
        )

    img = Image.alpha_composite(img, overlay)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
