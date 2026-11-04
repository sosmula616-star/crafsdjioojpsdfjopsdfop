import io
import os
import ssl
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")

FONT_URLS = {
    "bold": [
        "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts-ttf@master/ttf/DejaVuSans-Bold.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    ],
    "regular": [
        "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts-ttf@master/ttf/DejaVuSans.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    ],
}

def _ensure_downloaded_font(bold: bool = False) -> str | None:
    os.makedirs(FONT_DIR, exist_ok=True)
    key = "bold" if bold else "regular"
    local_path = os.path.join(FONT_DIR, f"cyrillic_{key}.ttf")

    if os.path.exists(local_path) and os.path.getsize(local_path) > 10_000:
        return local_path

    # 1. Пробуем скопировать из системной папки Windows, если она есть
    win_dir = os.environ.get("WINDIR", "C:\\Windows")
    win_candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf", "verdanab.ttf"]
        if bold else
        ["segoeui.ttf", "arial.ttf", "tahoma.ttf", "verdana.ttf"]
    )
    for fname in win_candidates:
        p = os.path.join(win_dir, "Fonts", fname)
        if os.path.exists(p):
            return p

    # 2. Если системного шрифта нет — автоматически скачиваем кириллический TTF
    ctx = ssl._create_unverified_context()
    for url in FONT_URLS[key]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = resp.read()
                if len(data) > 10_000:
                    with open(local_path, "wb") as f:
                        f.write(data)
                    print(f"[+] Кириллический шрифт ({key}) успешно скачан: {local_path}")
                    return local_path
        except Exception as e:
            print(f"[!] Попытка скачивания шрифта с {url} не удалась: {e}")

    return None


def _load_cyrillic_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = _ensure_downloaded_font(bold=bold)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def days_since(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return max(0, (datetime.now() - dt).days)
    except Exception:
        return 0


def generate_profile_image(username: str, support_data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    width, height = 1080, 540
    img = Image.new("RGBA", (width, height), (18, 13, 31, 255))
    draw = ImageDraw.Draw(img)

    # Космический градиентный фон со свечением
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse((-100, -100, 520, 520), fill=(125, 65, 230, 75))
    g_draw.ellipse((600, 100, 1180, 620), fill=(90, 45, 200, 70))
    g_draw.ellipse((340, -60, 760, 320), fill=(165, 95, 255, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=65))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Декоративные звёздочки
    for sx, sy in [(65, 42), (320, 26), (620, 24), (1035, 38), (48, 502), (615, 512), (1040, 505)]:
        draw.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(225, 205, 255, 180))

    def draw_glass_card(xy, fill=(36, 25, 62, 230), outline=(150, 105, 240, 255), radius=22, width_px=2):
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width_px)

    # 1. Левая карточка
    draw_glass_card((30, 30, 345, 510))
    # 2. Центральная карточка
    draw_glass_card((370, 30, 725, 510))
    # 3. Правые 4 карточки
    for ry in (30, 155, 280, 405):
        draw_glass_card((750, ry, 1050, ry + 105), radius=18)

    font_title = _load_cyrillic_font(25, bold=True)
    font_sub = _load_cyrillic_font(16, bold=False)
    font_sec_hdr = _load_cyrillic_font(20, bold=True)
    font_row_lbl = _load_cyrillic_font(16, bold=False)
    font_row_val = _load_cyrillic_font(20, bold=True)
    font_right_lbl = _load_cyrillic_font(15, bold=True)
    font_right_val = _load_cyrillic_font(22, bold=True)

    # --- ЛЕВАЯ КОЛОНКА ---
    av_size = 152
    av_x, av_y = 187 - av_size // 2, 54

    # Декоративная орбита вокруг аватарки
    draw.arc((av_x - 28, av_y + 20, av_x + av_size + 28, av_y + av_size - 20), start=150, end=390, fill=(160, 120, 245, 120), width=2)
    draw.ellipse((av_x - 5, av_y - 5, av_x + av_size + 5, av_y + av_size + 5), outline=(185, 140, 255, 255), width=3)

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
    draw.text((187, 240), disp_name, fill=(255, 255, 255), anchor="mm", font=font_title)
    draw.text((187, 268), "Саппорт", fill=(190, 168, 238), anchor="mm", font=font_sub)

    draw.line((65, 298, 310, 298), fill=(125, 88, 205, 170), width=1)

    pt_val = support_data.get("prime_time") or "Не назначен"
    hire_val = support_data.get("hire_date") or "—"
    prob_val = support_data.get("probation_until")

    draw_glass_card((50, 318, 325, 392), fill=(50, 35, 86, 240), outline=(128, 90, 210, 210), radius=14, width_px=1)
    draw.text((187, 340), "Прайм-тайм", fill=(195, 175, 235), anchor="mm", font=font_right_lbl)
    draw.text((187, 368), pt_val, fill=(255, 255, 255), anchor="mm", font=font_row_val)

    draw_glass_card((50, 408, 325, 482), fill=(50, 35, 86, 240), outline=(128, 90, 210, 210), radius=14, width_px=1)
    status_title = "Испытательный срок" if prob_val else "Дата принятия"
    status_val = f"До {prob_val}" if prob_val else hire_val
    draw.text((187, 430), status_title, fill=(195, 175, 235), anchor="mm", font=font_right_lbl)
    draw.text((187, 458), status_val, fill=(255, 255, 255), anchor="mm", font=font_row_val)

    # --- ЦЕНТРАЛЬНАЯ КОЛОНКА (Статистика саппорта) ---
    draw.text((547, 62), "Статистика саппорта", fill=(255, 255, 255), anchor="mm", font=font_sec_hdr)
    draw.line((400, 88, 695, 88), fill=(125, 88, 205, 180), width=1)

    total_days = days_since(support_data.get("hire_date", ""))
    total_mins = f"{support_data.get('total_minutes', 0):,}".replace(",", " ")

    stats = [
        ("Всего на саппорте", f"{total_days} дней"),
        ("Допусков", str(support_data.get("admitted", 0))),
        ("Недопусков", str(support_data.get("rejected", 0))),
        ("Всего минут в прихожих", total_mins),
        ("Принятых замен", str(support_data.get("swaps_taken", 0))),
        ("Обработано тикетов", str(support_data.get("tickets", 0))),
    ]

    row_y = 106
    for label, val in stats:
        draw_glass_card((392, row_y, 703, row_y + 54), fill=(54, 38, 92, 235), outline=(125, 86, 205, 220), radius=14, width_px=1)
        draw.text((412, row_y + 27), label, fill=(230, 220, 250), anchor="lm", font=font_row_lbl)
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
        draw.text((772, top_y + 24), title, fill=(220, 205, 250), anchor="lm", font=font_right_lbl)
        draw_glass_card(
            (768, top_y + 44, 1032, top_y + 90),
            fill=(22, 14, 42, 245),
            outline=(118, 82, 198, 220),
            radius=12,
            width_px=1
        )
        draw.text((900, top_y + 67), value, fill=(255, 255, 255), anchor="mm", font=font_right_val)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
