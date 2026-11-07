import io
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import MAX_WARNS
from database import now_str

# 1. Шрифт с фэнтезийным характером (для Ника, Заголовков и Крупных цифр)
FONT_FANTASY_BOLD = "Philosopher-Bold.ttf"
FONT_FANTASY_URL = "https://github.com/google/fonts/raw/main/ofl/philosopher/Philosopher-Bold.ttf"

# 2. Сверхчеткий UI-шрифт (для мелких подписей и строк статистики)
FONT_UI_BOLD = "Montserrat-Bold.ttf"
FONT_UI_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"

FONT_UI_SEMI = "Montserrat-SemiBold.ttf"
FONT_UI_SEMI_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf"


def ensure_fonts_sync():
    """Автоматически скачивает фэнтези и UI шрифты с поддержкой кириллицы."""
    fonts_to_download = [
        (FONT_FANTASY_BOLD, FONT_FANTASY_URL),
        (FONT_UI_BOLD, FONT_UI_URL),
        (FONT_UI_SEMI, FONT_UI_SEMI_URL),
    ]
    for path, url in fonts_to_download:
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp, open(path, "wb") as f:
                    f.write(resp.read())
                print(f"[+] Шрифт {path} успешно скачан.")
            except Exception as e:
                print(f"[!] Не удалось скачать шрифт {path}: {e}")


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in [path, FONT_UI_BOLD, "arialbd.ttf", "DejaVuSans-Bold.ttf"]:
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
    start_size: int = 26,
    min_size: int = 12
) -> tuple[str, ImageFont.FreeTypeFont]:
    """
    Автоматически масштабирует шрифт под длину текста (особенно длинных ников),
    чтобы текст никогда не выходил за пределы неоновых рамок.
    """
    text = str(text or "").strip() or "Unknown"
    for size in range(start_size, min_size - 1, -1):
        font = get_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        if (bbox[2] - bbox[0]) <= max_width:
            return text, font

    font = get_font(font_path, min_size)
    while len(text) > 3:
        text = text[:-1]
        bbox = draw.textbbox((0, 0), text + "...", font=font, stroke_width=2)
        if (bbox[2] - bbox[0]) <= max_width:
            return text + "...", font
    return text, font


def draw_magic_text(
    text_layer: Image.Image,
    glow_layer: Image.Image,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = "#FFFFFF",
    glow_color: str = "#A855F7",
    stroke_color: str = "#120324",
    stroke_width: int = 2,
    anchor: str = "mm"
):
    """
    Двухслойная отрисовка:
    1) На нижний слой кладется широкий цветной штамп (который потом размывается в мягкий неон).
    2) На верхний слой кладется идеально четкий текст с темной обводкой (stroke) для 100% читаемости.
    """
    glow_draw = ImageDraw.Draw(glow_layer)
    text_draw = ImageDraw.Draw(text_layer)

    # Слой свечения (будет размыт через GaussianBlur)
    glow_draw.text(
        pos, str(text), font=font, fill=glow_color,
        anchor=anchor, stroke_width=stroke_width + 3, stroke_fill=glow_color
    )
    # Слой четкого текста с темным контуром
    text_draw.text(
        pos, str(text), font=font, fill=fill,
        anchor=anchor, stroke_width=stroke_width, stroke_fill=stroke_color
    )


def draw_glass_capsule(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 14):
    """Рисует темную полупрозрачную стеклянную капсулу с двойной неоновой гранью."""
    x1, y1, x2, y2 = box
    # Глубокая темная подложка (гарантирует, что блики фона не помешают читать текст)
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=(11, 4, 24, 205),
        outline=(175, 95, 255, 160),
        width=1
    )
    # Внутренняя мягкая грань для объема
    draw.rounded_rectangle(
        (x1 + 2, y1 + 2, x2 - 2, y2 - 2),
        radius=max(1, radius - 2),
        fill=None,
        outline=(230, 190, 255, 35),
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

    # 1. Загружаем ваш фон с замком (1408x792)
    W, H = 1408, 792
    bg_path = find_bg_file()
    if bg_path:
        bg = Image.open(bg_path).convert("RGBA").resize((W, H), Image.Resampling.LANCZOS)
    else:
        print("⚠️ [ПРОФИЛЬ] Файл profile_bg.png не найден в корне! Положите картинку в корень проекта.")
        bg = Image.new("RGBA", (W, H), (18, 7, 35, 255))

    # 2. Загружаем и вписываем аватарку в магическое кольцо
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

    # Вырезаем на маске место под малое кольцо статуса (X: 349, Y: 363)
    rel_status_x = 349 - (246 - avatar_size // 2)
    rel_status_y = 363 - (281 - avatar_size // 2)
    mask_draw.ellipse(
        (rel_status_x - 32, rel_status_y - 32, rel_status_x + 32, rel_status_y + 32),
        fill=0
    )

    bg.paste(avatar_img, (246 - avatar_size // 2, 281 - avatar_size // 2), mask)

    # Создаем слои:
    # - ui_layer: для полупрозрачных капсул
    # - glow_layer: для размытого неонового свечения вокруг букв
    # - text_layer: для идеально четкого текста поверх свечения
    ui_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    ui_draw = ImageDraw.Draw(ui_layer)

    # Светящаяся кристаллическая сфера в кольце статуса
    ui_draw.ellipse((349 - 18, 363 - 18, 349 + 18, 363 + 18), fill=(185, 105, 255, 255))
    ui_draw.ellipse((349 - 10, 363 - 12, 349 - 2, 363 - 4), fill=(245, 230, 255, 210))  # Блик

    # 3. Данные из БД
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

    # 4. Палитра и шрифты
    COLOR_PURE_WHITE = "#FFFFFF"         # Чистый белый для цифр и ника
    COLOR_CRYSTAL_LAVENDER = "#F3E8FF"   # Очень светлый лавандовый (почти белый, но с оттенком магии) для подписей
    COLOR_HEADER_GOLD_LILAC = "#E9D5FF"  # Светло-сиреневый для заголовков секций
    GLOW_PURPLE = "#9333EA"              # Насыщенный неон для ореола
    GLOW_BRIGHT = "#C084FC"              # Яркий неон для главных цифр
    STROKE_DARK = "#0F0322"              # Чернильно-темный контур для 100% читаемости

    f_sec_title = get_font(FONT_FANTASY_BOLD, 19)
    f_row_label = get_font(FONT_UI_SEMI, 16)
    f_row_val = get_font(FONT_FANTASY_BOLD, 21)

    # =========================================================================
    # ЛЕВАЯ КОЛОНКА (Никнейм фэнтези-шрифтом + ПТ + Дата)
    # =========================================================================
    # Подгоняем размер шрифта ника так, чтобы он идеально вошел в плашку (max_width=270px)
    fitted_name, f_name = fit_text_to_box(
        ui_draw, display_name, FONT_FANTASY_BOLD, max_width=270, start_size=27, min_size=14
    )
    draw_magic_text(
        text_layer, glow_layer, (249, 453), fitted_name, f_name,
        fill=COLOR_PURE_WHITE, glow_color=GLOW_BRIGHT, stroke_color=STROKE_DARK, stroke_width=2
    )

    pt_label = f"ПТ: {prime_time}" if prime_time != "Не назначен" else "ПТ не назначен"
    fitted_pt, f_pt = fit_text_to_box(
        ui_draw, pt_label, FONT_UI_BOLD, max_width=182, start_size=16, min_size=11
    )
    draw_magic_text(
        text_layer, glow_layer, (249, 524), fitted_pt, f_pt,
        fill=COLOR_CRYSTAL_LAVENDER, glow_color=GLOW_PURPLE, stroke_color=STROKE_DARK, stroke_width=2
    )

    fitted_date, f_date = fit_text_to_box(
        ui_draw, str(date_val), FONT_UI_BOLD, max_width=182, start_size=16, min_size=11
    )
    draw_magic_text(
        text_layer, glow_layer, (249, 581), fitted_date, f_date,
        fill=COLOR_PURE_WHITE, glow_color=GLOW_PURPLE, stroke_color=STROKE_DARK, stroke_width=2
    )

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 1: 4 верхних окошка
    # =========================================================================
    top_cards = [
        (569, "ТОКЕНЫ", str(balance)),
        (796, "ЗАКРЫТЫЕ ТИКЕТЫ", str(tickets)),
        (1024, "ОТПУСК", str(vacation)),
        (1252, "ВЫГОВОРЫ", warns_str),
    ]
    for cx, title, val in top_cards:
        draw_glass_capsule(ui_draw, (cx - 84, 290, cx + 84, 344), radius=14)
        t_txt, t_font = fit_text_to_box(ui_draw, title, FONT_UI_BOLD, max_width=185, start_size=14, min_size=10)
        v_txt, v_font = fit_text_to_box(ui_draw, val, FONT_FANTASY_BOLD, max_width=152, start_size=27, min_size=14)

        draw_magic_text(
            text_layer, glow_layer, (cx, 264), t_txt, t_font,
            fill=COLOR_HEADER_GOLD_LILAC, glow_color=GLOW_PURPLE, stroke_color=STROKE_DARK, stroke_width=2
        )
        draw_magic_text(
            text_layer, glow_layer, (cx, 317), v_txt, v_font,
            fill=COLOR_PURE_WHITE, glow_color=GLOW_BRIGHT, stroke_color=STROKE_DARK, stroke_width=2
        )

    # =========================================================================
    # ПРАВАЯ КОЛОНКА — РЯД 2: Средняя широкая панель
    # =========================================================================
    draw_magic_text(
        text_layer, glow_layer, (910, 417), "✦ СТАТИСТИКА ПРАЙМ-ТАЙМОВ ✦", f_sec_title,
        fill=COLOR_HEADER_GOLD_LILAC, glow_color=GLOW_BRIGHT, stroke_color=STROKE_DARK, stroke_width=2
    )
    mid_pills = [
        (476, 438, 895, 488, "Выполнено ПТ", f"{primes_done} дн."),
        (925, 438, 1344, 488, "Принято замен", f"{swaps_taken} шт."),
    ]
    for x1, y1, x2, y2, label, val in mid_pills:
        draw_glass_capsule(ui_draw, (x1, y1, x2, y2), radius=14)
        cy = (y1 + y2) // 2
        draw_magic_text(
            text_layer, glow_layer, (x1 + 22, cy), label, f_row_label,
            fill=COLOR_CRYSTAL_LAVENDER, glow_color=GLOW_PURPLE, stroke_color=STROKE_DARK, stroke_width=2, anchor="lm"
        )
        draw_magic_text(
            text_layer, glow_layer, (x2 - 22, cy), val, f_row_val,
            fill=COLOR_PURE_WHITE, glow_color=GLOW_BRIGHT, stroke_color=STROKE_DARK, stroke_width=2, anchor="rm"
        )

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
        draw_glass_capsule(ui_draw, (x1, y1, x2, y2), radius=14)
        cy = (y1 + y2) // 2
        draw_magic_text(
            text_layer, glow_layer, (x1 + 22, cy), label, f_row_label,
            fill=COLOR_CRYSTAL_LAVENDER, glow_color=GLOW_PURPLE, stroke_color=STROKE_DARK, stroke_width=2, anchor="lm"
        )
        draw_magic_text(
            text_layer, glow_layer, (x2 - 22, cy), val, f_row_val,
            fill=COLOR_PURE_WHITE, glow_color=GLOW_BRIGHT, stroke_color=STROKE_DARK, stroke_width=2, anchor="rm"
        )

    # Размываем слой свечения для настоящего мягкого неона
    glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=4))

    # Собираем все слои в финальную картинку
    final_img = Image.alpha_composite(bg, ui_layer)
    final_img = Image.alpha_composite(final_img, glow_blurred)
    final_img = Image.alpha_composite(final_img, text_layer).convert("RGB")

    output = io.BytesIO()
    final_img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
