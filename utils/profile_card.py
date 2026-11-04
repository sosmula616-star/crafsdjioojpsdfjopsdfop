import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

def days_since(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        return max(0, (datetime.now() - dt).days)
    except Exception:
        return 0

def generate_profile_image(username: str, support_data: dict, avatar_bytes: bytes | None = None) -> io.BytesIO:
    width, height = 920, 460
    img = Image.new("RGBA", (width, height), (24, 18, 38, 255))
    draw = ImageDraw.Draw(img)

    def draw_box(xy, fill=(43, 31, 68, 255), outline=(128, 90, 213, 255), radius=16):
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=2)

    # Левая панель (Аватар + Ник)
    draw_box((25, 25, 295, 435))
    # Средняя панель (Статистика саппорта)
    draw_box((315, 25, 615, 435))
    # Правые 4 блока
    draw_box((635, 25, 895, 115))
    draw_box((635, 130, 895, 220))
    draw_box((635, 235, 895, 325))
    draw_box((635, 340, 895, 435))

    try:
        font_lg = ImageFont.truetype("arial.ttf", 22)
        font_md = ImageFont.truetype("arial.ttf", 18)
        font_sm = ImageFont.truetype("arial.ttf", 15)
    except Exception:
        font_lg = ImageFont.load_default()
        font_md = ImageFont.load_default()
        font_sm = ImageFont.load_default()

    # Аватарка
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((140, 140))
            mask = Image.new("L", (140, 140), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 140, 140), fill=255)
            img.paste(av, (90, 55), mask)
        except Exception:
            pass
    draw.ellipse((90, 55, 230, 195), outline=(180, 140, 255, 255), width=3)

    draw.text((160, 225), username[:18], fill=(255, 255, 255), anchor="mm", font=font_lg)
    draw.text((160, 252), "Саппорт", fill=(180, 165, 210), anchor="mm", font=font_sm)

    pt_text = f"Прайм-тайм: {support_data.get('prime_time') or 'Не назначен'}"
    draw.text((160, 320), pt_text, fill=(215, 200, 245), anchor="mm", font=font_sm)
    draw.text((160, 355), f"Принят: {support_data.get('hire_date')}", fill=(175, 160, 205), anchor="mm", font=font_sm)

    # Центральная колонка
    draw.text((465, 52), "Статистика саппорта", fill=(255, 255, 255), anchor="mm", font=font_md)
    stats = [
        ("Всего на саппорте", f"{days_since(support_data.get('hire_date', ''))} дней"),
        ("Допусков", str(support_data.get("admitted", 0))),
        ("Недопусков", str(support_data.get("rejected", 0))),
        ("Всего минут в прихожих", str(support_data.get("total_minutes", 0))),
        ("Принятых замен", str(support_data.get("swaps_taken", 0))),
        ("Обработано тикетов", str(support_data.get("tickets", 0))),
    ]
    y = 90
    for label, val in stats:
        draw_box((335, y, 595, y + 44), fill=(58, 42, 92, 255), outline=(105, 75, 170, 255), radius=10)
        draw.text((350, y + 22), label, fill=(215, 205, 235), anchor="lm", font=font_sm)
        draw.text((580, y + 22), val, fill=(255, 255, 255), anchor="rm", font=font_md)
        y += 55

    # Правая колонка
    tokens = support_data.get("balance", 0)
    salary_forecast = round(tokens * 0.04, 1)
    vacation = f"До {support_data['vacation_until']}" if support_data.get("vacation_until") else "Нет"
    warns = str(support_data.get("warns", 0))

    right_blocks = [
        ("Токены", str(tokens), 25),
        ("Прогноз зарплаты", str(salary_forecast), 130),
        ("Отпуск", vacation, 235),
        ("Выговоры", warns, 340),
    ]
    for title, value, top_y in right_blocks:
        draw.text((655, top_y + 25), title, fill=(205, 190, 230), anchor="lm", font=font_sm)
        draw_box((650, top_y + 42, 880, top_y + 78), fill=(32, 22, 52, 255), outline=(110, 80, 180, 255), radius=8)
        draw.text((765, top_y + 60), value, fill=(255, 255, 255), anchor="mm", font=font_md)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
