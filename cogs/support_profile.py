import io
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from config import MAX_WARNS
from database import now_str

FONT_BOLD_PATH = "Montserrat-Bold.ttf"
FONT_REG_PATH = "Montserrat-SemiBold.ttf"
FONT_BOLD_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
FONT_REG_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf"


def ensure_fonts_sync():
    """Скачивает шрифты Montserrat с поддержкой кириллицы, если их ещё нет."""
    for path, url in [(FONT_BOLD_PATH, FONT_BOLD_URL), (FONT_REG_PATH, FONT_REG_URL)]:
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp, open(path, "wb") as f:
                    f.write(resp.read())
                print(f"[+] Шрифт {path} успешно скачан.")
            except Exception as e:
                print(f"[!] Не удалось скачать шрифт {path}: {e}")


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in [path, "arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]:
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
    """
    Плавно уменьшает размер шрифта, если никнейм или текст слишком длинный,
    чтобы он идеально поместился в рамку без визуальных несостыковок.
    """
    text = str(text or "").strip() or "Unknown"
    for size in range(start_size, min_size - 1, -1):
        font = get_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return text, font

    # Если ник длиннее 35+ символов, аккуратно обрезаем с троеточием под минимальный шрифт
    font = get_font(font_path, min_size)
    while len(text) > 3:
        text = text[:-1]
        bbox = draw.textbbox((0, 0), text + "...", font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return text + "...", font
    return text, font


def draw_glow_text(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = "#FFFFFF",
    glow: str = "#7B2CBF",
    anchor: str = "mm"
):
    """Рисует текст с мягким неоновым свечением/контуром."""
    x, y = pos
    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1), (0, 2)]:
        draw.text((x + dx, y + dy), str(text), font=font, fill=glow, anchor=anchor)
    draw.text((x, y), str(text), font=font, fill=fill, anchor=anchor)


def draw_inner_pill(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 14):
    """Рисует полупрозрачную темную капсулу с тонкой неоновой обводкой внутри широких блоков."""
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=(14, 6, 28, 180),
        outline=(168, 85, 247, 135),
        width=1
    )


def find_bg_file() -> str | None:
    """Ищет вашу картинку фона в корне проекта или папке assets."""
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

    # Приводим row/dict из БД к обычному словарю
    d = dict(data) if data else {}

    # 1. Загружаем ваш шаблон 1408x792
    W, H = 1408, 792
    bg_path = find_bg_file()
    if bg_path:
        bg = Image.open(bg_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    else:
        print("⚠️ [ПРОФИЛЬ] Файл profile_bg.png не найден в корне! Положите картинку в корень проекта.")
        bg = Image.new("RGBA", (W, H), (18, 7, 35, 255))

    # 2. Загружаем и кругло вырезаем аватарку под кольцо шаблона
    avatar_size = 240
    avatar_img = None
    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            pass

    if avatar_img is None:
        avatar_img = Image.new("RGBA", (avatar_size, avatar_size), (60, 25, 110, 255))
    else:
        avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

    # Вырезаем правый нижний край под кружок онлайн-статуса на шаблоне (X: 349, Y: 363)
    rel_status_x = 349 - (246 - avatar_size // 2)
    rel_status_y = 363 - (281 - avatar_size // 2)
    mask_draw.ellipse(
        (rel_status_x - 32, rel_status_y - 32, rel_status_x + 32, rel_status_y + 32),
        fill=0
    )

    bg.paste(avatar_img, (246 - avatar_size // 2, 281 - avatar_size // 2), mask)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Заливаем кружок статуса ярким неоново-фиолетовым цветом
    draw.ellipse((349 - 18, 363 - 18, 349 + 18, 363 + 18), fill=(175, 95, 255, 255))

    # 3. Извлекаем значения из таблицы supports (с поддержкой всех возможных ключей БД)
    prime_time = d.get("prime_time") or "Не назначен"
    date_val = d.get("joined_at") or d.get("created_at") or now_str()

    balance = d.get("balance", d.get("tokens", 0))
    tickets = d.get("tickets", d.get("closed_tickets", 0))
    vacation = d.get("vacation_until") or "Нет"
    warns = d.get("warns", 0)
    warns_str = f"{warns} / {MAX_WARNS}"

    # Средний блок (активность и замены)
    primes_done = d.get("primes_done", d.get("completed_primes", d.get("pt_done", 0)))
    swaps_taken = d.get("swaps_taken", 0)

    # Нижний блок (4 показателя)
    admits = d.get("admits", d.get("verifications", d.get("passes", 0)))
    misses = d.get("misses", d.get("absences", 0))
    extra_pts = d.get("extra_primes", d.get("extra_pt", 0))
    total_mins = d.get("total_minutes", d.get("voice_minutes", d.get("minutes", 0)))

    # 4. Настраиваем цвета и шрифты
    f_sec_title = get_font(FONT_BOLD_PATH, 17)
    f_row_label = get_font(FONT_REG_PATH, 16)
    f_row_val = get_font(FONT_BOLD_PATH, 18)

    COLOR_WHITE = "#FFFFFF"
    COLOR_LABEL = "#E0AAFF"       # Светло-лавандовый
    COLOR_GLOW_DARK = "#240046"   # Темно-фиолетовый контур для четкости
    COLOR_GLOW_NEON = "#7B2CBF"   # Яркое неоновое свечение

    # =========================================================================
    # ЛЕВАЯ КОЛОНКА (Ник, Прайм-тайм, Дата)
    # =========================================================================
    # Безопасная ширина плашки ника = 270px (сама плашка ~305px). Длинный ник сам уменьшит шрифт!
    fitted_name, f_name = fit_text_to_box(draw, display_name, FONT_BOLD_PATH, max_width=270, start_size=24, min_size=12)
    draw_glow_text(draw, (249, 453), fitted_name, f_name, COLOR_WHITE, COLOR_GLOW_NEON)

    # Безопасная ширина средних/нижних плашек слева = 180px
    pt_label = f"ПТ: {prime_time}" if prime_time != "Не назначен" else "ПТ не назначен"
    fitted_pt, f_pt = fit_text_to_box(draw, pt_label, FONT_REG_PATH, max_width=180, start_size=16, min_size=11)
    draw_glow_text(draw, (249, 524), fitted_pt, f_pt, COLOR_LABEL, COLOR_GLOW_DARK)

    fitted_date, f_date = fit_text_to_box(draw, str(date_val), FONT_REG_PATH, max_width=180, start_size=16, min_size=11)
    draw_glow_text(draw, (249, 581), fitted_date, f_date, COLOR_WHITE, COLOR_GLOW_DARK)

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 1: 4 верхних окошка (центры X: 569, 796, 1024, 1252)
    # =========================================================================
    top_cards = [
        (569, "ТОКЕНЫ", str(balance)),
        (796, "ЗАКРЫТЫЕ ТИКЕТЫ", str(tickets)),
        (1024, "ОТПУСК", str(vacation)),
        (1252, "ВЫГОВОРЫ", warns_str),
    ]
    for cx, title, val in top_cards:
        draw_inner_pill(draw, (cx - 82, 290, cx + 82, 342), radius=14)
        t_txt, t_font = fit_text_to_box(draw, title, FONT_REG_PATH, max_width=185, start_size=14, min_size=10)
        v_txt, v_font = fit_text_to_box(draw, val, FONT_BOLD_PATH, max_width=150, start_size=24, min_size=13)
        draw_glow_text(draw, (cx, 265), t_txt, t_font, COLOR_LABEL, COLOR_GLOW_DARK)
        draw_glow_text(draw, (cx, 316), v_txt, v_font, COLOR_WHITE, COLOR_GLOW_NEON)

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 2: Средняя широкая панель
    # =========================================================================
    draw_glow_text(draw, (910, 418), "• СТАТИСТИКА ПРАЙМ-ТАЙМОВ •", f_sec_title, COLOR_LABEL, COLOR_GLOW_DARK)
    mid_pills = [
        (476, 438, 895, 488, "Выполнено ПТ", f"{primes_done} дн."),
        (925, 438, 1344, 488, "Принято замен", f"{swaps_taken} шт."),
    ]
    for x1, y1, x2, y2, label, val in mid_pills:
        draw_inner_pill(draw, (x1, y1, x2, y2), radius=14)
        cy = (y1 + y2) // 2
        draw_glow_text(draw, (x1 + 22, cy), label, f_row_label, COLOR_LABEL, COLOR_GLOW_DARK, anchor="lm")
        draw_glow_text(draw, (x2 - 22, cy), val, f_row_val, COLOR_WHITE, COLOR_GLOW_NEON, anchor="rm")

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
        draw_inner_pill(draw, (x1, y1, x2, y2), radius=14)
        cy = (y1 + y2) // 2
        draw_glow_text(draw, (x1 + 22, cy), label, f_row_label, COLOR_LABEL, COLOR_GLOW_DARK, anchor="lm")
        draw_glow_text(draw, (x2 - 22, cy), val, f_row_val, COLOR_WHITE, COLOR_GLOW_NEON, anchor="rm")

    final_img = Image.alpha_composite(bg, overlay).convert("RGB")
    output = io.BytesIO()
    final_img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
