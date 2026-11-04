import io
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def days_since(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return max(0, (datetime.now() - dt).days)
    except Exception:
        return 0

def _load_cyrillic_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates.extend([
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "segoeuib.ttf",
            "arialbd.ttf",
        ])
    else:
        candidates.extend([
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "segoeui.ttf",
            "arial.ttf",
        ])
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def generate_profile_image(username: str, support_data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    width, height = 1080, 540
    img = Image.new("RGBA", (width, height), (16, 12, 28, 255))
    draw = ImageDraw.Draw(img)

    # Космический градиентный фон со свечением
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse((-120, -120, 520, 520), fill=(115, 55, 215, 70))
    g_draw.ellipse((620, 120, 1180, 640), fill=(80, 40, 190, 65))
    g_draw.ellipse((350, -80, 780, 320), fill=(150, 85, 255, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=65))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Декоративные звёздочки на фоне
    star_coords = [(60, 45), (310, 30), (615, 28), (1030, 40), (45, 495), (610, 505), (1040, 500)]
    for sx, sy in star_coords:
        draw.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(210, 190, 255, 160))

    def draw_glass_card(xy, fill=(34, 24, 58, 225), outline=(145, 100, 235, 255), radius=22, width_px=2):
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width_px)

    # 1. Левая карточка (Профиль + Аватар + Прайм-тайм)
    draw_glass_card((30, 30, 345, 510))

    # 2. Центральная карточка (Статистика саппорта)
    draw_glass_card((370, 30, 725, 510))

    # 3. Правые 4 карточки (Токены, Прогноз зарплаты, Отпуск, Выговоры)
    right_y_positions = [30, 155, 280, 405]
    for ry in right_y_positions:
        draw_glass_card((750, ry, 1050, ry + 105), radius=18)

    font_title = _load_cyrillic_font(26, bold=True)
    font_sub = _load_cyrillic_font(17, bold=False)
    font_sec_hdr = _load_cyrillic_font(20, bold=True)
    font_row_lbl = _load_cyrillic_font(17, bold=False)
    font_row_val = _load_cyrillic_font(21, bold=True)
    font_right_lbl = _load_cyrillic_font(16, bold=True)
    font_right_val = _load_cyrillic_font(24, bold=True)

    # --- ЛЕВАЯ КОЛОНКА ---
    av_size = 156
    av_x, av_y = 187 - av_size // 2, 58
    # Внешнее неоновое кольцо вокруг аватара
    draw.ellipse((av_x - 6, av_y - 6, av_x + av_size + 6, av_y + av_size + 6), outline=(170, 125, 255, 255), width=3)
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
            img.paste(av, (av_x, av_y), mask)
        except Exception:
            pass
    else:
        draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), fill=(65, 45, 105, 255))

    disp_name = username if len(username) <= 18 else username[:16] + ".."
    draw.text((187, 248), disp_name, fill=(255, 255, 255), anchor="mm", font=font_title)
    draw.text((187, 278), "Саппорт", fill=(185, 160, 235), anchor="mm", font=font_sub)

    # Разделительная линия
    draw.line((65, 308, 310, 308), fill=(115, 80, 190, 160), width=1)

    # Инфо-блоки в левой карточке
    pt_val = support_data.get("prime_time") or "Не назначен"
    hire_val = support_data.get("hire_date") or "—"
    prob_val = support_data.get("probation_until")

    draw_glass_card((50, 328, 325, 392), fill=(48, 34, 82, 240), outline=(120, 85, 200, 200), radius=14, width_px=1)
    draw.text((187, 348), "Прайм-тайм", fill=(185, 165, 225), anchor="mm", font=font_right_lbl)
    draw.text((187, 374), pt_val, fill=(255, 255, 255), anchor="mm", font=font_row_val)

    draw_glass_card((50, 410, 325, 474), fill=(48, 34, 82, 240), outline=(120, 85, 200, 200), radius=14, width_px=1)
    status_title = "Испытательный срок" if prob_val else "Дата принятия"
    status_val = f"До {prob_val}" if prob_val else hire_val
    draw.text((187, 430), status_title, fill=(185, 165, 225), anchor="mm", font=font_right_lbl)
    draw.text((187, 456), status_val, fill=(255, 255, 255), anchor="mm", font=font_row_val)

    # --- ЦЕНТРАЛЬНАЯ КОЛОНКА (Статистика саппорта) ---
    draw.text((547, 64), "Статистика саппорта", fill=(255, 255, 255), anchor="mm", font=font_sec_hdr)
    draw.line((400, 88, 695, 88), fill=(125, 85, 205, 180), width=1)

    total_days = days_since(support_data.get("hire_date", ""))
    total_mins = f"{support_data.get('total_minutes', 0):,}".replace(",", " ")

    stats = [
        ("Всего на саппорте", f"{total_days} дн."),
        ("Допусков", str(support_data.get("admitted", 0))),
        ("Недопусков", str(support_data.get("rejected", 0))),
        ("Минут в прихожих", total_mins),
        ("Принятых замен", str(support_data.get("swaps_taken", 0))),
        ("Обработано тикетов", str(support_data.get("tickets", 0))),
    ]

    row_y = 106
    for label, val in stats:
        draw_glass_card((392, row_y, 703, row_y + 54), fill=(52, 37, 88, 235), outline=(120, 82, 200, 220), radius=14, width_px=1)
        draw.text((412, row_y + 27), label, fill=(225, 215, 248), anchor="lm", font=font_row_lbl)
        draw.text((683, row_y + 27), val, fill=(255, 255, 255), anchor="rm", font=font_row_val)
        row_y += 65

    # --- ПРАВАЯ КОЛОНКА (4 блока) ---
    tokens = support_data.get("balance", 0)
    salary_forecast = round(tokens * 0.04, 1)
    if salary_forecast.is_integer():
        salary_forecast = int(salary_forecast)
    vacation = f"До {support_data['vacation_until']}" if support_data.get("vacation_until") else "Нет"
    warns = str(support_data.get("warns", 0))

    right_items = [
        ("Токены", str(tokens), 30),
        ("Прогноз зарплаты", str(salary_forecast), 155),
        ("Отпуск", vacation, 280),
        ("Выговоры", warns, 405),
    ]

    for title, value, top_y in right_items:
        draw.text((772, top_y + 24), title, fill=(215, 198, 248), anchor="lm", font=font_right_lbl)
        draw_glass_card(
            (768, top_y + 44, 1032, top_y + 90),
            fill=(24, 16, 44, 245),
            outline=(115, 80, 195, 220),
            radius=12,
            width_px=1
        )
        draw.text((900, top_y + 67), value, fill=(255, 255, 255), anchor="mm", font=font_right_val)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
