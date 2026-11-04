import io
import math
import os
import ssl
import urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")

# Надёжные CDN-зеркала шрифта Montserrat с полной поддержкой кириллицы
FONT_URLS = {
    "bold": [
        "https://cdn.jsdelivr.net/npm/@bitrix24/b24style@1.0.1/fonts/montserrat/montserrat-bold.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts-ttf@master/ttf/DejaVuSans-Bold.ttf",
    ],
    "semibold": [
        "https://cdn.jsdelivr.net/npm/@bitrix24/b24style@1.0.1/fonts/montserrat/montserrat-semibold.ttf",
        "https://cdn.jsdelivr.net/npm/@bitrix24/b24style@1.0.1/fonts/montserrat/montserrat-bold.ttf",
    ],
    "regular": [
        "https://cdn.jsdelivr.net/npm/@bitrix24/b24style@1.0.1/fonts/montserrat/montserrat-medium.ttf",
        "https://cdn.jsdelivr.net/npm/@bitrix24/b24style@1.0.1/fonts/montserrat/montserrat-regular.ttf",
        "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts-ttf@master/ttf/DejaVuSans.ttf",
    ],
}


def _get_font_path(weight: str = "regular") -> str | None:
    os.makedirs(FONT_DIR, exist_ok=True)
    local_path = os.path.join(FONT_DIR, f"montserrat_{weight}.ttf")

    if os.path.exists(local_path) and os.path.getsize(local_path) > 20_000:
        return local_path

    # 1. Скачиваем дизайнерский шрифт Montserrat с поддержкой кириллицы
    ctx = ssl._create_unverified_context()
    for url in FONT_URLS.get(weight, FONT_URLS["regular"]):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = resp.read()
                if len(data) > 20_000:
                    with open(local_path, "wb") as f:
                        f.write(data)
                    print(f"[+] Шрифт Montserrat ({weight}) успешно загружен!")
                    return local_path
        except Exception as e:
            print(f"[!] Ошибка загрузки шрифта {url}: {e}")

    # 2. Резервный вариант — системные шрифты Windows
    win_dir = os.environ.get("WINDIR", "C:\\Windows")
    fallback_names = (
        ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"]
        if weight in ("bold", "semibold")
        else ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]
    )
    for fn in fallback_names:
        p = os.path.join(win_dir, "Fonts", fn)
        if os.path.exists(p):
            return p

    return None


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = _get_font_path(weight)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def days_since(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return max(0, (datetime.now() - dt).days)
    except Exception:
        return 0


def _draw_sparkle(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color=(235, 215, 255, 230)):
    """Рисует четырёхконечную звезду-блик ✦"""
    pts = [
        (cx, cy - size),
        (cx + size * 0.28, cy - size * 0.28),
        (cx + size, cy),
        (cx + size * 0.28, cy + size * 0.28),
        (cx, cy + size),
        (cx - size * 0.28, cy + size * 0.28),
        (cx - size, cy),
        (cx - size * 0.28, cy - size * 0.28),
    ]
    draw.polygon(pts, fill=color)


def _draw_leaf_cluster(draw: ImageDraw.ImageDraw, x: int, y: int, flip_x: int = 1, flip_y: int = 1):
    """Рисует полупрозрачные декоративные листья по углам как на референсе"""
    leaves = [
        [(0, 0), (18 * flip_x, -38 * flip_y), (42 * flip_x, -48 * flip_y), (24 * flip_x, -12 * flip_y)],
        [(0, 0), (45 * flip_x, -18 * flip_y), (62 * flip_x, -22 * flip_y), (32 * flip_x, 4 * flip_y)],
        [(0, 0), (-12 * flip_x, -42 * flip_y), (-6 * flip_x, -60 * flip_y), (10 * flip_x, -26 * flip_y)],
    ]
    for pts in leaves:
        shifted = [( x + px, y + py) for px, py in pts]
        draw.polygon(shifted, fill=(175, 130, 245, 55), outline=(215, 185, 255, 110))


def _draw_cyber_panel(
    base_img: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int = 22,
    top_notch: bool = False,
):
    """Рисует стеклянную карточку с тенью, внутренним свечением, двойной рамкой и угловыми акцентами"""
    x1, y1, x2, y2 = xy
    w, h = x2 - x1, y2 - y1

    # 1. Мягкая внешняя тень
    shadow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle((x1 + 4, y1 + 8, x2 + 4, y2 + 8), radius=radius, fill=(8, 4, 18, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
    base_img.alpha_composite(shadow)

    # 2. Градиентная полупрозрачная подложка
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card)
    for row in range(h):
        t = row / max(1, h - 1)
        r = int(58 * (1 - t) + 28 * t)
        g = int(38 * (1 - t) + 17 * t)
        b = int(98 * (1 - t) + 52 * t)
        a = int(215 * (1 - t) + 235 * t)
        c_draw.line([(0, row), (w, row)], fill=(r, g, b, a))

    # Верхний диагональный блик стекла
    shine = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh_draw = ImageDraw.Draw(shine)
    sh_draw.polygon([(0, 0), (w, 0), (w, int(h * 0.35)), (0, int(h * 0.55))], fill=(200, 160, 255, 18))
    card = Image.alpha_composite(card, shine)

    mask = Image.new("L", (w, h), 0)
    m_draw = ImageDraw.Draw(mask)
    if top_notch:
        # Фигурный выступ сверху под аватарку (как в оригинальном референсе)
        m_draw.rounded_rectangle((0, 38, w, h), radius=radius, fill=255)
        m_draw.rounded_rectangle((36, 0, w - 36, 90), radius=26, fill=255)
    else:
        m_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)

    base_img.paste(card, (x1, y1), mask)

    # 3. Двойная неоновая обводка
    draw = ImageDraw.Draw(base_img)
    if top_notch:
        draw.rounded_rectangle((x1, y1 + 38, x2, y2), radius=radius, outline=(168, 122, 250, 235), width=2)
        draw.rounded_rectangle((x1 + 5, y1 + 43, x2 - 5, y2 - 5), radius=max(8, radius - 4), outline=(120, 80, 200, 90), width=1)
    else:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=(168, 122, 250, 235), width=2)
        draw.rounded_rectangle((x1 + 5, y1 + 5, x2 - 5, y2 - 5), radius=max(8, radius - 4), outline=(120, 80, 200, 95), width=1)

    # Светящиеся точки-акценты по центрам горизонтальных граней
    mid_x = (x1 + x2) // 2
    _draw_sparkle(draw, mid_x, y2, 5, (225, 200, 255, 210))
    if not top_notch:
        _draw_sparkle(draw, mid_x, y1, 5, (225, 200, 255, 210))


def _draw_mini_icon(draw: ImageDraw.ImageDraw, kind: str, cx: int, cy: int, color=(225, 205, 255, 255)):
    """Рисует аккуратные векторные иконки для пунктов статистики"""
    if kind == "shield":
        pts = [(cx, cy - 9), (cx + 8, cy - 5), (cx + 7, cy + 3), (cx, cy + 9), (cx - 7, cy + 3), (cx - 8, cy - 5)]
        draw.polygon(pts, outline=color, width=2)
        draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=color)
    elif kind == "user_plus":
        draw.ellipse((cx - 7, cy - 8, cx + 1, cy), outline=color, width=2)
        draw.arc((cx - 10, cy + 1, cx + 4, cy + 13), start=180, end=360, fill=color, width=2)
        draw.line((cx + 7, cy - 3, cx + 7, cy + 5), fill=color, width=2)
        draw.line((cx + 3, cy + 1, cx + 11, cy + 1), fill=color, width=2)
    elif kind == "user_minus":
        draw.ellipse((cx - 7, cy - 8, cx + 1, cy), outline=color, width=2)
        draw.arc((cx - 10, cy + 1, cx + 4, cy + 13), start=180, end=360, fill=color, width=2)
        draw.line((cx + 3, cy + 1, cx + 11, cy + 1), fill=color, width=2)
    elif kind == "clock":
        draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), outline=color, width=2)
        draw.line((cx, cy, cx, cy - 5), fill=color, width=2)
        draw.line((cx, cy, cx + 4, cy + 2), fill=color, width=2)
    elif kind == "swap":
        draw.arc((cx - 8, cy - 8, cx + 8, cy + 8), start=20, end=160, fill=color, width=2)
        draw.arc((cx - 8, cy - 8, cx + 8, cy + 8), start=200, end=340, fill=color, width=2)
        draw.polygon([(cx + 8, cy - 3), (cx + 4, cy - 7), (cx + 10, cy - 7)], fill=color)
        draw.polygon([(cx - 8, cy + 3), (cx - 4, cy + 7), (cx - 10, cy + 7)], fill=color)
    elif kind == "ticket":
        draw.rounded_rectangle((cx - 10, cy - 6, cx + 10, cy + 6), radius=3, outline=color, width=2)
        draw.line((cx - 2, cy - 6, cx - 2, cy + 6), fill=color, width=1)
    elif kind == "token":
        draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), outline=color, width=2)
        draw.rounded_rectangle((cx - 5, cy - 4, cx + 5, cy + 4), radius=2, outline=color, width=1)
    elif kind == "chart":
        draw.line((cx - 8, cy + 7, cx + 9, cy + 7), fill=color, width=2)
        draw.line((cx - 6, cy + 3, cx - 1, cy - 2), fill=color, width=2)
        draw.line((cx - 1, cy - 2, cx + 3, cy + 1), fill=color, width=2)
        draw.line((cx + 3, cy + 1, cx + 8, cy - 6), fill=color, width=2)
    elif kind == "palm":
        draw.line((cx, cy + 8, cx + 2, cy - 3), fill=color, width=2)
        draw.arc((cx - 9, cy - 8, cx + 2, cy + 2), start=180, end=360, fill=color, width=2)
        draw.arc((cx, cy - 8, cx + 11, cy + 2), start=180, end=360, fill=color, width=2)
    elif kind == "warn":
        pts = [(cx, cy - 9), (cx + 10, cy + 8), (cx - 10, cy + 8)]
        draw.polygon(pts, outline=color, width=2)
        draw.line((cx, cy - 3, cx, cy + 2), fill=color, width=2)
        draw.ellipse((cx - 1, cy + 4, cx + 1, cy + 6), fill=color)
    elif kind == "headset":
        draw.arc((cx - 10, cy - 10, cx + 10, cy + 8), start=180, end=360, fill=color, width=2)
        draw.rounded_rectangle((cx - 11, cy - 2, cx - 6, cy + 7), radius=2, fill=color)
        draw.rounded_rectangle((cx + 6, cy - 2, cx + 11, cy + 7), radius=2, fill=color)


def generate_profile_image(username: str, support_data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    width, height = 1220, 620
    img = Image.new("RGBA", (width, height), (14, 9, 26, 255))

    # --- 1. КОСМИЧЕСКИЙ ФОН С ТУМАННОСТЯМИ И СОЗВЕЗДИЯМИ ---
    nebula = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    n_draw = ImageDraw.Draw(nebula)
    n_draw.ellipse((-140, -120, 560, 540), fill=(138, 68, 245, 90))
    n_draw.ellipse((460, -160, 960, 320), fill=(185, 95, 255, 65))
    n_draw.ellipse((680, 140, 1340, 720), fill=(95, 42, 205, 95))
    n_draw.ellipse((220, 320, 720, 700), fill=(120, 55, 220, 60))
    nebula = nebula.filter(ImageFilter.GaussianBlur(radius=75))
    img = Image.alpha_composite(img, nebula)

    bg_draw = ImageDraw.Draw(img)
    # Диагональные световые лучи на фоне
    bg_draw.line([(0, 140), (380, 0)], fill=(190, 145, 255, 28), width=2)
    bg_draw.line([(850, 620), (1220, 380)], fill=(190, 145, 255, 28), width=2)

    # Звёздная пыль и блики
    sparkles = [(48, 46, 7), (392, 26, 6), (822, 28, 6), (1182, 44, 7), (38, 580, 6), (815, 592, 7), (1188, 585, 6)]
    for sx, sy, sr in sparkles:
        _draw_sparkle(bg_draw, sx, sy, sr, (230, 210, 255, 200))

    dots = [
        (95, 22), (280, 18), (520, 20), (690, 15), (960, 22), (1120, 18),
        (22, 260), (395, 290), (825, 310), (1198, 240), (540, 602), (980, 604)
    ]
    for dx, dy in dots:
        bg_draw.ellipse((dx - 2, dy - 2, dx + 2, dy + 2), fill=(215, 190, 255, 150))

    # Декоративные листья позади карточек (как на референсе)
    _draw_leaf_cluster(bg_draw, 370, 125, flip_x=1, flip_y=1)
    _draw_leaf_cluster(bg_draw, 42, 565, flip_x=-1, flip_y=-1)
    _draw_leaf_cluster(bg_draw, 1175, 575, flip_x=1, flip_y=-1)

    # --- 2. ОСНОВНЫЕ КАРТОЧКИ ---
    # Левая карточка (с верхним подиумом под аватар)
    _draw_cyber_panel(img, (36, 36, 404, 584), radius=24, top_notch=True)
    # Центральная карточка (Статистика саппорта)
    _draw_cyber_panel(img, (432, 36, 838, 584), radius=24, top_notch=False)
    # Правые 4 карточки
    right_tops = [36, 178, 320, 462]
    for ry in right_tops:
        _draw_cyber_panel(img, (866, ry, 1184, ry + 122), radius=20, top_notch=False)

    draw = ImageDraw.Draw(img)

    # Шрифты Montserrat
    f_name = _font(28, "bold")
    f_role = _font(16, "regular")
    f_hdr = _font(21, "bold")
    f_stat_lbl = _font(16, "semibold")
    f_stat_val = _font(22, "bold")
    f_right_lbl = _font(16, "semibold")
    f_right_val = _font(25, "bold")
    f_bar_lbl = _font(14, "semibold")
    f_bar_val = _font(14, "bold")
    f_tag = _font(13, "bold")

    # --- 3. ЛЕВАЯ КОЛОНКА (АВАТАР С ОРБИТОЙ + ПРОФИЛЬ + БАРЫ) ---
    av_size = 166
    av_cx, av_cy = 220, 142
    av_x, av_y = av_cx - av_size // 2, av_cy - av_size // 2

    # Задняя часть планетарной орбиты
    orbit_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(orbit_layer)
    o_draw.arc((av_cx - 135, av_cy - 44, av_cx + 135, av_cy + 44), start=175, end=365, fill=(195, 155, 255, 130), width=2)
    orbit_layer = orbit_layer.rotate(18, center=(av_cx, av_cy), resample=Image.Resampling.BICUBIC)
    img = Image.alpha_composite(img, orbit_layer)

    # Неоновое свечение вокруг аватара
    av_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ag_draw = ImageDraw.Draw(av_glow)
    ag_draw.ellipse((av_x - 8, av_y - 8, av_x + av_size + 8, av_y + av_size + 8), outline=(195, 145, 255, 200), width=6)
    av_glow = av_glow.filter(ImageFilter.GaussianBlur(radius=6))
    img = Image.alpha_composite(img, av_glow)
    draw = ImageDraw.Draw(img)

    # Сам аватар
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((av_size, av_size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
            img.paste(av, (av_x, av_y), mask)
        except Exception:
            draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), fill=(70, 45, 115, 255))
    else:
        draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), fill=(70, 45, 115, 255))

    draw.ellipse((av_x - 3, av_y - 3, av_x + av_size + 3, av_y + av_size + 3), outline=(235, 215, 255, 255), width=3)

    # Передняя дуга планетарной орбиты поверх аватарки
    front_orbit = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fo_draw = ImageDraw.Draw(front_orbit)
    fo_draw.arc((av_cx - 135, av_cy - 44, av_cx + 135, av_cy + 44), start=355, end=185, fill=(235, 210, 255, 210), width=2)
    fo_draw.ellipse((av_cx - 135 - 4, av_cy - 4, av_cx - 135 + 4, av_cy + 4), fill=(255, 240, 255, 255))
    front_orbit = front_orbit.rotate(18, center=(av_cx, av_cy), resample=Image.Resampling.BICUBIC)
    img = Image.alpha_composite(img, front_orbit)
    draw = ImageDraw.Draw(img)

    # Никнейм и должность
    disp_name = username if len(username) <= 17 else username[:15] + ".."
    draw.text((220, 258), disp_name, fill=(255, 255, 255), anchor="mm", font=f_name)
    draw.text((220, 288), "Саппорт", fill=(198, 175, 245), anchor="mm", font=f_role)

    # Разделитель со звездой ✦
    draw.line((76, 314, 198, 314), fill=(155, 115, 235, 180), width=1)
    draw.line((242, 314, 364, 314), fill=(155, 115, 235, 180), width=1)
    _draw_sparkle(draw, 220, 314, 6, (235, 210, 255, 240))

    # Инфо-капсула (Прайм-тайм + Дата принятия)
    pt_val = support_data.get("prime_time") or "Не назначен"
    hire_val = support_data.get("hire_date") or "—"
    draw.text((220, 336), "РАСПИСАНИЕ И СТАТУС", fill=(185, 160, 235), anchor="mm", font=f_tag)

    draw.rounded_rectangle((62, 354, 378, 424), radius=14, fill=(32, 20, 58, 220), outline=(140, 96, 225, 200), width=1)
    draw.text((80, 375), "Прайм-тайм:", fill=(200, 182, 240), anchor="lm", font=f_bar_lbl)
    draw.text((360, 375), pt_val, fill=(255, 255, 255), anchor="rm", font=f_bar_val)
    draw.line((78, 390, 362, 390), fill=(110, 75, 180, 110), width=1)
    draw.text((80, 406), "Дата принятия:", fill=(200, 182, 240), anchor="lm", font=f_bar_lbl)
    draw.text((360, 406), hire_val, fill=(255, 255, 255), anchor="rm", font=f_bar_val)

    # 3 стильных прогресс-бара (как в нижней части левой карточки референса)
    misses = support_data.get("weekly_misses", 0)
    reliability = max(0, 100 - misses * 20)
    adm = support_data.get("admitted", 0)
    rej = support_data.get("rejected", 0)
    adm_rate = int((adm / max(1, adm + rej)) * 100) if (adm + rej) > 0 else 100
    mins_num = support_data.get("total_minutes", 0)
    act_pct = min(100, int((mins_num / 420) * 100)) if mins_num > 0 else 15

    bars = [
        ("Надёжность ПТ", f"{reliability} / 100", reliability / 100.0, 444),
        ("Рейтинг допусков", f"{adm_rate} / 100", adm_rate / 100.0, 488),
        ("Активность", f"{act_pct} / 100", act_pct / 100.0, 532),
    ]
    for b_label, b_txt, ratio, by in bars:
        draw.text((66, by), b_label, fill=(215, 200, 248), anchor="lm", font=f_bar_lbl)
        draw.text((374, by), b_txt, fill=(255, 255, 255), anchor="rm", font=f_bar_val)
        bar_x1, bar_y1, bar_x2, bar_y2 = 66, by + 14, 374, by + 24
        draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=5, fill=(24, 15, 44, 255), outline=(110, 75, 180, 160), width=1)
        fill_w = max(12, int((bar_x2 - bar_x1) * max(0.05, min(1.0, ratio))))
        draw.rounded_rectangle((bar_x1, bar_y1, bar_x1 + fill_w, bar_y2), radius=5, fill=(195, 135, 255, 255))

    # --- 4. ЦЕНТРАЛЬНАЯ КОЛОНКА (СТАТИСТИКА САППОРТА) ---
    _draw_mini_icon(draw, "headset", 488, 76, (235, 215, 255, 255))
    draw.text((648, 76), "Статистика саппорта", fill=(255, 255, 255), anchor="mm", font=f_hdr)
    draw.line((464, 104, 806, 104), fill=(150, 105, 235, 170), width=1)

    total_days = days_since(support_data.get("hire_date", ""))
    total_mins_str = f"{support_data.get('total_minutes', 0):,}".replace(",", " ")

    stats = [
        ("shield", "Всего на саппорте", f"{total_days} дней"),
        ("user_plus", "Допусков", str(support_data.get("admitted", 0))),
        ("user_minus", "Недопусков", str(support_data.get("rejected", 0))),
        ("clock", "Всего минут в прихожих", total_mins_str),
        ("swap", "Принятых замен", str(support_data.get("swaps_taken", 0))),
        ("ticket", "Обработано тикетов", str(support_data.get("tickets", 0))),
    ]

    ry = 124
    for icon_name, label, val in stats:
        # Плашка строки статистики
        draw.rounded_rectangle(
            (458, ry, 812, ry + 60),
            radius=16,
            fill=(62, 42, 106, 215),
            outline=(155, 110, 240, 225),
            width=1,
        )
        # Круглый бейдж под иконку
        draw.ellipse((472, ry + 13, 506, ry + 47), fill=(40, 26, 74, 240), outline=(165, 120, 250, 200), width=1)
        _draw_mini_icon(draw, icon_name, 489, ry + 30, (235, 215, 255, 255))

        draw.text((520, ry + 30), label, fill=(235, 225, 255), anchor="lm", font=f_stat_lbl)
        draw.text((792, ry + 30), val, fill=(255, 255, 255), anchor="rm", font=f_stat_val)
        ry += 74

    # --- 5. ПРАВАЯ КОЛОНКА (4 КАРТОЧКИ) ---
    tokens = support_data.get("balance", 0)
    salary_forecast = round(tokens * 0.04, 1)
    if salary_forecast.is_integer():
        salary_forecast = int(salary_forecast)
    vacation = f"До {support_data['vacation_until']}" if support_data.get("vacation_until") else "Нет"
    warns = str(support_data.get("warns", 0))

    right_cards = [
        ("token", "Токены", str(tokens), 36),
        ("chart", "Прогноз зарплаты", str(salary_forecast), 178),
        ("palm", "Отпуск", vacation, 320),
        ("warn", "Выговоры", warns, 462),
    ]

    for icon_name, title, value, top_y in right_cards:
        # Иконка + заголовок
        draw.ellipse((886, top_y + 14, 916, top_y + 44), fill=(44, 28, 82, 240), outline=(165, 120, 250, 200), width=1)
        _draw_mini_icon(draw, icon_name, 901, top_y + 29, (235, 215, 255, 255))
        draw.text((928, top_y + 29), title, fill=(235, 225, 255), anchor="lm", font=f_right_lbl)
        _draw_sparkle(draw, 1158, top_y + 26, 4, (220, 195, 255, 190))

        # Тёмная внутренняя капсула со значением
        draw.rounded_rectangle(
            (886, top_y + 54, 1164, top_y + 104),
            radius=14,
            fill=(22, 13, 42, 245),
            outline=(140, 95, 225, 215),
            width=1,
        )
        draw.text((1025, top_y + 79), value, fill=(255, 255, 255), anchor="mm", font=f_right_val)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
