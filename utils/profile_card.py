import io
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from config import MAX_WARNS
from database import now_str

FONT_BOLD_PATH = "Montserrat-Bold.ttf"
FONT_BOLD_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"

FONT_MED_PATH = "Montserrat-Medium.ttf"
FONT_MED_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Medium.ttf"


def ensure_fonts_sync():
    """Скачивает чистые шрифты Montserrat при первом запуске."""
    for path, url in [(FONT_BOLD_PATH, FONT_BOLD_URL), (FONT_MED_PATH, FONT_MED_URL)]:
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp, open(path, "wb") as f:
                    f.write(resp.read())
            except Exception as e:
                print(f"[!] Не удалось скачать шрифт {path}: {e}")


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in [path, FONT_BOLD_PATH, "arialbd.ttf", "arial.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_text_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    max_width: int,
    start_size: int = 24,
    min_size: int = 12
) -> tuple[str, ImageFont.FreeTypeFont]:
    """Уменьшает размер шрифта для длинных ников, чтобы текст не вылезал за рамку."""
    text = str(text or "").strip() or "Unknown"
    for size in range(start_size, min_size - 1, -1):
        font = get_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return text, font

    font = get_font(font_path, min_size)
    while len(text) > 3:
        text = text[:-1]
        bbox = draw.textbbox((0, 0), text + "...", font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return text + "...", font
    return text, font


def draw_clean_box(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 12):
    """Аккуратная матовая полупрозрачная плашка без кричащего неона."""
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=(12, 8, 22, 175),
        outline=(255, 255, 255, 35),
        width=1
    )


def find_bg_file() -> str | None:
    candidates = [
        "profile_bg.png", "profile_bg.jpg", "profile_bg.webp",
        "bg.png", "bg.jpg", "background.png", "template.png",
        "assets/profile_bg.png", "assets/bg.png"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def generate_profile_image(display_name: str, data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    ensure_fonts_sync()
    d = dict(data) if data else {}

    W, H = 1408, 792
    bg_path = find_bg_file()
    if bg_path:
        bg = Image.open(bg_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    else:
        bg = Image.new("RGBA", (W, H), (18, 10, 30, 255))

    # Координаты центра круга аватара и малого кружка статуса на вашем шаблоне
    AV_CX, AV_CY = 176, 256
    AV_SIZE = 216
    ST_CX, ST_CY = 262, 336

    avatar_img = None
    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            pass

    if avatar_img is None:
        avatar_img = Image.new("RGBA", (AV_SIZE, AV_SIZE), (45, 25, 80, 255))
    else:
        avatar_img = avatar_img.resize((AV_SIZE, AV_SIZE), Image.Resampling.LANCZOS)

    mask = Image.new("L", (AV_SIZE, AV_SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, AV_SIZE, AV_SIZE), fill=255)

    # Аккуратный вырез под кружок статуса на шаблоне
    rel_sx = ST_CX - (AV_CX - AV_SIZE // 2)
    rel_sy = ST_CY - (AV_CY - AV_SIZE // 2)
    mask_draw.ellipse((rel_sx - 28, rel_sy - 28, rel_sx + 28, rel_sy + 28), fill=0)

    bg.paste(avatar_img, (AV_CX - AV_SIZE // 2, AV_CY - AV_SIZE // 2), mask)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Данные из БД
    prime_time = d.get("prime_time") or "Не назначен"
    date_val = d.get("joined_at") or d.get("created_at") or now_str()

    balance = d.get("balance", d.get("tokens", 0))
    tickets = d.get("tickets", d.get("closed_tickets", 0))
    vacation = d.get("vacation_until") or "Нет"
    warns = d.get("warns", 0)
    warns_str = f"{warns} / {MAX_WARNS}"

    primes_done = d.get("primes_done", d.get("completed_primes", d.get("pt_done", 0)))
    swaps_taken = d.get("swaps_taken", 0)

    admits = d.get("admits", d.get("verifications", d.get("passes", 0)))
    misses = d.get("misses", d.get("absences", 0))
    extra_pts = d.get("extra_primes", d.get("extra_pt", 0))
    total_mins = d.get("total_minutes", d.get("voice_minutes", d.get("minutes", 0)))

    # Строгие цвета: чистый белый для значений и спокойный светло-серый для подписей
    WHITE = (255, 255, 255, 255)
    SUBTEXT = (220, 220, 230, 255)

    f_sec_title = get_font(FONT_BOLD_PATH, 16)
    f_row_label = get_font(FONT_MED_PATH, 16)
    f_row_val = get_font(FONT_BOLD_PATH, 18)

    # =========================================================================
    # ЛЕВАЯ КОЛОНКА (ровно по центру левых рамок шаблона: X = 176)
    # =========================================================================
    LEFT_CX = 176

    fitted_name, f_name = fit_text_to_box(draw, display_name, FONT_BOLD_PATH, max_width=285, start_size=22, min_size=12)
    draw.text((LEFT_CX, 444), fitted_name, font=f_name, fill=WHITE, anchor="mm")

    pt_label = f"ПТ: {prime_time}" if prime_time != "Не назначен" else "ПТ не назначен"
    fitted_pt, f_pt = fit_text_to_box(draw, pt_label, FONT_MED_PATH, max_width=190, start_size=15, min_size=11)
    draw.text((LEFT_CX, 513), fitted_pt, font=f_pt, fill=WHITE, anchor="mm")

    fitted_date, f_date = fit_text_to_box(draw, str(date_val), FONT_MED_PATH, max_width=190, start_size=15, min_size=11)
    draw.text((LEFT_CX, 571), fitted_date, font=f_date, fill=WHITE, anchor="mm")

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 1: 4 верхних окошка (X центры: 562, 795, 1028, 1261)
    # =========================================================================
    top_cards = [
        (562, "ТОКЕНЫ", str(balance)),
        (795, "ЗАКРЫТЫЕ ТИКЕТЫ", str(tickets)),
        (1028, "ОТПУСК", str(vacation)),
        (1261, "ВЫГОВОРЫ", warns_str),
    ]
    for cx, title, val in top_cards:
        draw_clean_box(draw, (cx - 86, 286, cx + 86, 342), radius=12)
        t_txt, t_font = fit_text_to_box(draw, title, FONT_BOLD_PATH, max_width=190, start_size=13, min_size=10)
        v_txt, v_font = fit_text_to_box(draw, val, FONT_BOLD_PATH, max_width=155, start_size=22, min_size=13)

        draw.text((cx, 258), t_txt, font=t_font, fill=SUBTEXT, anchor="mm")
        draw.text((cx, 314), v_txt, font=v_font, fill=WHITE, anchor="mm")

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 2: Средняя широкая панель
    # =========================================================================
    draw.text((911, 415), "СТАТИСТИКА ПРАЙМ-ТАЙМОВ", font=f_sec_title, fill=WHITE, anchor="mm")

    mid_pills = [
        (476, 438, 895, 488, "Выполнено ПТ", f"{primes_done} дн."),
        (925, 438, 1344, 488, "Принято замен", f"{swaps_taken} шт."),
    ]
    for x1, y1, x2, y2, label, val in mid_pills:
        draw_clean_box(draw, (x1, y1, x2, y2), radius=12)
        cy = (y1 + y2) // 2
        draw.text((x1 + 22, cy), label, font=f_row_label, fill=SUBTEXT, anchor="lm")
        draw.text((x2 - 22, cy), val, font=f_row_val, fill=WHITE, anchor="rm")

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 3: Нижняя большая панель (4 капсулы)
    # =========================================================================
    bottom_slots = [
        (476, 548, 895, 602, "Допусков в прихожей", f"{admits} чел."),
        (925, 548, 1344, 602, "Прогулы ПТ", f"{misses} дн."),
        (476, 622, 895, 676, "Дополнительные ПТ", f"{extra_pts} шт."),
        (925, 622, 1344, 676, "Онлайн в лобби", f"{total_mins} мин."),
    ]
    for x1, y1, x2, y2, label, val in bottom_slots:
        draw_clean_box(draw, (x1, y1, x2, y2), radius=12)
        cy = (y1 + y2) // 2
        draw.text((x1 + 22, cy), label, font=f_row_label, fill=SUBTEXT, anchor="lm")
        draw.text((x2 - 22, cy), val, font=f_row_val, fill=WHITE, anchor="rm")

    final_img = Image.alpha_composite(bg, overlay).convert("RGB")
    output = io.BytesIO()
    final_img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
