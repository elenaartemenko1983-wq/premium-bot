"""
Smart Sender Bot — Visual Asset Generator
Generates: avatar, welcome banner, subscription GIF, mailing progress GIF, payment GIF
"""

import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = "bot_assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── ПАЛІТРА ──────────────────────────────────────────────────
DARK_BG    = (10, 12, 20)
DARK_CARD  = (18, 22, 38)
ACCENT     = (99, 102, 241)     # фиолетовый
ACCENT2    = (139, 92, 246)     # светло-фиолетовый
ACCENT3    = (236, 72, 153)     # розовый
GOLD       = (251, 191, 36)
GREEN      = (52, 211, 153)
RED        = (239, 68, 68)
WHITE      = (255, 255, 255)
GRAY       = (100, 116, 139)
LIGHT_GRAY = (148, 163, 184)

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

def hex_col(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=outline_width)

def draw_glow(img, center, radius, color, intensity=0.4):
    glow = Image.new('RGBA', img.size, (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    cx, cy = center
    for r in range(radius, 0, -1):
        alpha = int(255 * intensity * (r / radius) ** 0.5)
        alpha = min(alpha, 80)
        gd.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*color, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 3))
    img.paste(glow, mask=glow)

def draw_gradient_bg(img, c1, c2, angle_deg=135):
    w, h = img.size
    draw = ImageDraw.Draw(img)
    angle = math.radians(angle_deg)
    for y in range(h):
        t = y / h
        color = lerp_color(c1, c2, t)
        draw.line([(0, y), (w, y)], fill=color)

def draw_stars(draw, w, h, count=60, seed=42):
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        r = rng.choice([1, 1, 1, 2])
        alpha_v = rng.randint(80, 200)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(*WHITE, alpha_v))

def add_noise_overlay(img, intensity=8):
    rng = random.Random(7)
    overlay = Image.new('RGBA', img.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, img.width, 2):
        for y in range(0, img.height, 2):
            v = rng.randint(-intensity, intensity)
            v = max(0, min(255, 128 + v))
            od.point((x, y), fill=(v, v, v, 10))
    img.paste(overlay, mask=overlay)

def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                continue
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════
#  1. АВАТАРКА БОТА (640×640)
# ══════════════════════════════════════════════════════════════
def make_avatar():
    W, H = 640, 640
    img = Image.new('RGBA', (W, H), (0,0,0,0))

    # Круглая маска
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, W, H], fill=255)

    # Фон — градиент
    bg = Image.new('RGB', (W, H))
    draw_gradient_bg(bg, (14, 10, 40), (40, 20, 80))
    bg = bg.convert('RGBA')

    # Звёзды
    sd = ImageDraw.Draw(bg)
    draw_stars(sd, W, H, count=80)

    # Большое внешнее свечение по центру
    draw_glow(bg, (W//2, H//2), 280, ACCENT, intensity=0.5)
    draw_glow(bg, (W//2, H//2), 160, ACCENT2, intensity=0.6)

    # Орбитальные кольца
    rd = ImageDraw.Draw(bg)
    for radius, alpha, width in [(220, 40, 2), (190, 60, 1), (260, 25, 1)]:
        ring_overlay = Image.new('RGBA', (W, H), (0,0,0,0))
        rio = ImageDraw.Draw(ring_overlay)
        rio.ellipse(
            [W//2-radius, H//2-radius, W//2+radius, H//2+radius],
            outline=(*ACCENT2, alpha), width=width
        )
        bg.paste(ring_overlay, mask=ring_overlay)

    # Центральный шестиугольник
    cx, cy, cr = W//2, H//2, 140
    hex_pts = [(cx + cr*math.cos(math.radians(60*i-30)),
                cy + cr*math.sin(math.radians(60*i-30))) for i in range(6)]
    hex_fill = Image.new('RGBA', (W, H), (0,0,0,0))
    hfd = ImageDraw.Draw(hex_fill)
    hfd.polygon(hex_pts, fill=(*ACCENT, 200))
    # Обводка
    for thick, alpha_v in [(6, 255), (12, 80), (20, 30)]:
        hfd.polygon(hex_pts, outline=(*ACCENT2, alpha_v), width=thick)
    bg.paste(hex_fill, mask=hex_fill)

    # Иконка — ракета ✦ нарисованная вручную
    # Ракетное тело (закруглённый прямоугольник)
    rocket = Image.new('RGBA', (W, H), (0,0,0,0))
    rkt = ImageDraw.Draw(rocket)
    # Тело
    rkt.rounded_rectangle([cx-28, cy-60, cx+28, cy+40], radius=28, fill=(*WHITE, 255))
    # Окно
    rkt.ellipse([cx-14, cy-42, cx+14, cy-14], fill=(*ACCENT, 255))
    rkt.ellipse([cx-10, cy-38, cx+10, cy-18], fill=(*ACCENT2, 255))
    # Крылья
    rkt.polygon([(cx-28, cy+10),(cx-55, cy+45),(cx-28, cy+40)], fill=(*ACCENT3, 230))
    rkt.polygon([(cx+28, cy+10),(cx+55, cy+45),(cx+28, cy+40)], fill=(*ACCENT3, 230))
    # Сопло
    rkt.rounded_rectangle([cx-16, cy+38, cx+16, cy+58], radius=6, fill=(*GRAY, 200))
    # Огонь
    for i, (fc, fy, fr) in enumerate([
        (GOLD, cy+75, 18),
        ((255,140,0), cy+65, 12),
        ((255,80,0), cy+58, 7),
    ]):
        fire_o = Image.new('RGBA', (W,H),(0,0,0,0))
        fd = ImageDraw.Draw(fire_o)
        fd.ellipse([cx-fr, fy-fr, cx+fr, fy+fr], fill=(*fc, 200-i*40))
        fire_o = fire_o.filter(ImageFilter.GaussianBlur(3))
        rocket.paste(fire_o, mask=fire_o)

    bg.paste(rocket, mask=rocket)

    # Частицы вокруг
    pd = ImageDraw.Draw(bg)
    rng = random.Random(99)
    for _ in range(16):
        angle = rng.uniform(0, 2*math.pi)
        dist = rng.uniform(155, 210)
        px = cx + int(dist * math.cos(angle))
        py = cy + int(dist * math.sin(angle))
        pr = rng.choice([2, 3, 4])
        pc = rng.choice([ACCENT, ACCENT2, ACCENT3, GOLD, GREEN])
        pd.ellipse([px-pr, py-pr, px+pr, py+pr], fill=(*pc, rng.randint(150, 255)))

    # Применяем круглую маску
    out = Image.new('RGBA', (W, H), (0,0,0,0))
    out.paste(bg, mask=mask)

    path = f"{OUTPUT_DIR}/avatar.png"
    out.save(path, 'PNG')
    print(f"✅ Avatar → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  2. WELCOME BANNER — анимированный GIF (800×420, 24 frames)
# ══════════════════════════════════════════════════════════════
def make_welcome_gif():
    W, H = 800, 420
    frames = []
    N = 30  # frames

    font_big   = get_font(52, bold=True)
    font_med   = get_font(28, bold=True)
    font_small = get_font(20)

    for fi in range(N):
        t = fi / N  # 0..1
        img = Image.new('RGBA', (W, H), DARK_BG)
        d = ImageDraw.Draw(img)

        # Фоновый градиент
        for y in range(H):
            ty = y / H
            c = lerp_color((12, 8, 35), (22, 15, 55), ty)
            d.line([(0, y), (W, y)], fill=c)

        # Анимированные звёзды (мерцание)
        rng = random.Random(42)
        for _ in range(55):
            sx = rng.randint(0, W)
            sy = rng.randint(0, H)
            sr = rng.choice([1,1,2])
            phase = rng.uniform(0, 2*math.pi)
            alpha_v = int(80 + 120 * (0.5 + 0.5*math.sin(t*2*math.pi + phase)))
            d.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(*WHITE, alpha_v))

        # Пульсирующее свечение слева (иконка)
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi)
        glow_img = Image.new('RGBA', (W, H), (0,0,0,0))
        draw_glow(glow_img, (105, H//2), int(90 + 15*pulse), ACCENT, intensity=0.55+0.15*pulse)
        draw_glow(glow_img, (105, H//2), int(50 + 8*pulse), ACCENT2, intensity=0.8)
        img.paste(glow_img, mask=glow_img)

        # Иконка — ракетка (маленькая)
        ric = Image.new('RGBA', (W, H), (0,0,0,0))
        rid = ImageDraw.Draw(ric)
        rx, ry = 105, H//2
        # Шестиугольник
        cr2 = int(54 + 4*pulse)
        hx = [(rx + cr2*math.cos(math.radians(60*i-30)),
               ry + cr2*math.sin(math.radians(60*i-30))) for i in range(6)]
        rid.polygon(hx, fill=(*ACCENT, 210))
        # Ракета мини
        rid.rounded_rectangle([rx-11, ry-24, rx+11, ry+16], radius=11, fill=(*WHITE, 255))
        rid.ellipse([rx-6, ry-20, rx+6, ry-6], fill=(*ACCENT2, 255))
        rid.polygon([(rx-11, ry+2),(rx-22, ry+18),(rx-11, ry+16)], fill=(*ACCENT3, 220))
        rid.polygon([(rx+11, ry+2),(rx+22, ry+18),(rx+11, ry+16)], fill=(*ACCENT3, 220))
        # Огонь ракеты
        ff_alpha = int(200 + 55*pulse)
        rid.ellipse([rx-7, ry+18, rx+7, ry+30], fill=(*GOLD, ff_alpha))
        rid.ellipse([rx-4, ry+24, rx+4, ry+34], fill=(255,160,0, ff_alpha))
        img.paste(ric, mask=ric)

        # Вертикальный разделитель
        sep_x = 185
        for dy in range(H):
            alpha_v = int(60 * math.sin(math.pi * dy / H))
            d.line([(sep_x, dy), (sep_x, dy)], fill=(*ACCENT, alpha_v))

        # Главный заголовок с анимацией появления
        title = "Smart Sender"
        subtitle = "Розумна розсилка в Telegram"
        # Slide-in: первые 8 кадров
        offset_x = max(0, int(40 * (1 - fi / 8))) if fi < 8 else 0
        alpha_title = min(255, int(255 * fi / 8))

        title_img = Image.new('RGBA', (W, H), (0,0,0,0))
        td = ImageDraw.Draw(title_img)
        td.text((210 + offset_x, 100), title, font=font_big, fill=(*WHITE, alpha_title))
        td.text((213 + offset_x, 103), title, font=font_big, fill=(*ACCENT2, alpha_title//3))  # тень
        img.paste(title_img, mask=title_img)

        # Подзаголовок
        sub_img = Image.new('RGBA', (W, H), (0,0,0,0))
        sbd = ImageDraw.Draw(sub_img)
        sub_alpha = min(255, int(255 * max(0, fi-4) / 8))
        sbd.text((212 + offset_x, 168), subtitle, font=font_med, fill=(*LIGHT_GRAY, sub_alpha))
        img.paste(sub_img, mask=sub_img)

        # Анимированная полоска под заголовком
        bar_w = int(380 * min(1.0, fi / 12))
        bar_img = Image.new('RGBA', (W, H), (0,0,0,0))
        bd = ImageDraw.Draw(bar_img)
        for bx in range(bar_w):
            tc = bx / max(bar_w, 1)
            bc = lerp_color(ACCENT, ACCENT3, tc)
            bd.line([(210+bx, 210), (210+bx, 213)], fill=(*bc, 200))
        img.paste(bar_img, mask=bar_img)

        # Фичи — появляются последовательно
        features = [
            ("🛡", "Захист від банів"),
            ("⚡", "Швидка розсилка"),
            ("📊", "Детальна статистика"),
            ("💎", "Гнучкі тарифи"),
        ]
        for i, (icon, feat) in enumerate(features):
            appear_frame = 10 + i * 4
            fa = min(255, int(255 * max(0, fi - appear_frame) / 5))
            fy = 240 + i * 36
            feat_img = Image.new('RGBA', (W, H), (0,0,0,0))
            fid = ImageDraw.Draw(feat_img)
            fid.text((215, fy), icon, font=font_small, fill=(*ACCENT2, fa))
            fid.text((248, fy), feat, font=font_small, fill=(*LIGHT_GRAY, fa))
            img.paste(feat_img, mask=feat_img)

        # TON Badge — правый нижний угол
        badge_img = Image.new('RGBA', (W, H), (0,0,0,0))
        bad = ImageDraw.Draw(badge_img)
        bx1, by1, bx2, by2 = W-150, H-55, W-15, H-15
        pulse_a = int(200 + 55 * pulse)
        bad.rounded_rectangle([bx1, by1, bx2, by2], radius=12,
                               fill=(*DARK_CARD, 220), outline=(*ACCENT, pulse_a), width=2)
        bad.text((bx1+14, by1+9), "⟡ TON оплата", font=get_font(16), fill=(*GOLD, pulse_a))
        img.paste(badge_img, mask=badge_img)

        # Конвертируем для GIF
        frames.append(img.convert('RGB'))

    path = f"{OUTPUT_DIR}/welcome_banner.gif"
    frames[0].save(
        path, format='GIF', append_images=frames[1:],
        save_all=True, duration=80, loop=0, optimize=False
    )
    print(f"✅ Welcome GIF → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  3. GIF "PAYMENT" — анимация оплаты (500×300, 40 frames)
# ══════════════════════════════════════════════════════════════
def make_payment_gif():
    W, H = 500, 300
    frames = []
    N = 40
    font_big   = get_font(38, bold=True)
    font_med   = get_font(22, bold=True)
    font_small = get_font(17)

    for fi in range(N):
        t = fi / N
        img = Image.new('RGBA', (W, H), DARK_BG)
        d = ImageDraw.Draw(img)

        # Фон
        for y in range(H):
            ty = y / H
            c = lerp_color((8, 6, 28), (20, 12, 50), ty)
            d.line([(0, y), (W, y)], fill=c)

        # Звёзды
        rng = random.Random(13)
        for _ in range(30):
            sx, sy = rng.randint(0,W), rng.randint(0,H)
            phase = rng.uniform(0, 2*math.pi)
            sa = int(60 + 90 * (0.5 + 0.5*math.sin(t*2*math.pi + phase)))
            d.point((sx, sy), fill=(*WHITE, sa))

        cx, cy = W//2, H//2 - 20
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi)

        # Фаза 1: монета летит (0..0.5)
        # Фаза 2: галочка появляется (0.5..1)
        phase_coin = min(1.0, t / 0.45)
        phase_check = max(0.0, (t - 0.55) / 0.45)

        # --- МОНЕТА ---
        coin_y = int(cy - 60 + 60 * phase_coin)
        coin_alpha = int(255 * (1 - phase_check))
        coin_r = 48

        glow_c = Image.new('RGBA', (W, H), (0,0,0,0))
        draw_glow(glow_c, (cx, coin_y), int(coin_r + 20 + 10*pulse), GOLD, intensity=0.4 * (1-phase_check))
        img.paste(glow_c, mask=glow_c)

        coin_img = Image.new('RGBA', (W, H), (0,0,0,0))
        cid = ImageDraw.Draw(coin_img)
        # Монета
        cid.ellipse([cx-coin_r, coin_y-coin_r, cx+coin_r, coin_y+coin_r],
                    fill=(*GOLD, coin_alpha))
        cid.ellipse([cx-coin_r+4, coin_y-coin_r+4, cx+coin_r-4, coin_y+coin_r-4],
                    fill=(*(218, 165, 32), coin_alpha))
        # Буква T
        if coin_alpha > 50:
            cid.text((cx-11, coin_y-18), "⟡", font=get_font(28, True), fill=(*DARK_BG, coin_alpha))
        img.paste(coin_img, mask=coin_img)

        # Стрелочки летящие
        for ai in range(3):
            aw = W//2 - 80 + ai * 40
            ay = coin_y - 15 + int(10 * math.sin(t*4*math.pi + ai))
            aa = int(180 * (1-phase_check) * phase_coin)
            arrow_img = Image.new('RGBA', (W, H), (0,0,0,0))
            ard = ImageDraw.Draw(arrow_img)
            ard.text((aw, ay), "→", font=get_font(20), fill=(*GREEN, aa))
            img.paste(arrow_img, mask=arrow_img)

        # --- ГАЛОЧКА ---
        if phase_check > 0:
            check_r = int(56 * phase_check)
            cg = Image.new('RGBA', (W, H), (0,0,0,0))
            draw_glow(cg, (cx, cy-10), check_r+30, GREEN, intensity=0.6*phase_check)
            img.paste(cg, mask=cg)

            ck_img = Image.new('RGBA', (W, H), (0,0,0,0))
            ckd = ImageDraw.Draw(ck_img)
            ckd.ellipse([cx-check_r, cy-10-check_r, cx+check_r, cy-10+check_r],
                        fill=(*GREEN, int(220*phase_check)))
            # Галочка внутри
            if phase_check > 0.5:
                cp = phase_check
                ckd.line([
                    (cx-18, cy-10), (cx-4, cy+10), (cx+18, cy-18)
                ], fill=(*WHITE, int(255*cp)), width=5)
            img.paste(ck_img, mask=ck_img)

        # Текст снизу
        txt_img = Image.new('RGBA', (W, H), (0,0,0,0))
        txd = ImageDraw.Draw(txt_img)
        if phase_check < 0.5:
            ta = int(255 * (1-phase_check*2))
            txd.text((cx-115, H-80), "Відправ TON оплату", font=font_med, fill=(*LIGHT_GRAY, ta))
            txd.text((cx-75, H-50), "і отримай доступ", font=font_small, fill=(*GRAY, ta))
        else:
            ta = int(255 * (phase_check-0.5)*2)
            txd.text((cx-88, H-80), "Оплату прийнято!", font=font_med, fill=(*GREEN, ta))
            txd.text((cx-100, H-50), "Підписку активовано ✓", font=font_small, fill=(*LIGHT_GRAY, ta))
        img.paste(txt_img, mask=txt_img)

        frames.append(img.convert('RGB'))

    path = f"{OUTPUT_DIR}/payment_animation.gif"
    frames[0].save(
        path, format='GIF', append_images=frames[1:],
        save_all=True, duration=90, loop=0
    )
    print(f"✅ Payment GIF → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  4. GIF "MAILING" — прогресс отправки (500×280, 35 frames)
# ══════════════════════════════════════════════════════════════
def make_mailing_gif():
    W, H = 500, 280
    frames = []
    N = 35
    font_med   = get_font(24, bold=True)
    font_small = get_font(17)
    font_tiny  = get_font(14)

    for fi in range(N):
        t = fi / (N-1)
        img = Image.new('RGBA', (W, H), DARK_BG)
        d = ImageDraw.Draw(img)

        for y in range(H):
            c = lerp_color((8, 10, 28), (18, 20, 48), y/H)
            d.line([(0,y),(W,y)], fill=c)

        rng = random.Random(55)
        for _ in range(25):
            sx, sy = rng.randint(0,W), rng.randint(0,H)
            phase = rng.uniform(0,2*math.pi)
            sa = int(50 + 80*(0.5+0.5*math.sin(t*3*math.pi+phase)))
            d.point((sx,sy), fill=(*WHITE,sa))

        # Прогресс-бар
        bar_x, bar_y = 50, 130
        bar_w, bar_h = W-100, 22
        # Фон бара
        d.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h],
                             radius=11, fill=(*DARK_CARD, 255), outline=(*ACCENT, 80), width=1)
        # Заполнение
        fill_w = int(bar_w * t)
        if fill_w > 0:
            fill_img = Image.new('RGBA', (W, H), (0,0,0,0))
            fid = ImageDraw.Draw(fill_img)
            for bx in range(fill_w):
                tc = bx / max(fill_w, 1)
                bc = lerp_color(ACCENT, ACCENT3, tc)
                fid.rounded_rectangle([bar_x+bx, bar_y+1, bar_x+bx+1, bar_y+bar_h-1],
                                      radius=0, fill=(*bc, 230))
            fill_img.paste(Image.new('RGBA',(W,H),(0,0,0,0)))
            # Glow at leading edge
            if fill_w > 10:
                glo = Image.new('RGBA', (W, H), (0,0,0,0))
                draw_glow(glo, (bar_x+fill_w, bar_y+bar_h//2), 25, ACCENT3, intensity=0.5)
                img.paste(glo, mask=glo)
            # Draw filled bar
            for bx in range(fill_w):
                tc = bx / max(fill_w, 1)
                bc = lerp_color(ACCENT, ACCENT3, tc)
                d.line([(bar_x+bx, bar_y+2), (bar_x+bx, bar_y+bar_h-2)], fill=(*bc, 220))

        # Процент
        pct = int(t * 100)
        d.text((bar_x + bar_w//2 - 20, bar_y + 2), f"{pct}%",
               font=get_font(15, True), fill=(*WHITE, 220))

        # Заголовок
        title_img = Image.new('RGBA', (W, H), (0,0,0,0))
        tid = ImageDraw.Draw(title_img)
        tid.text((50, 55), "🚀 Розсилка в процесі...", font=font_med, fill=(*WHITE, 255))
        img.paste(title_img, mask=title_img)

        # Лети-сообщения анимация
        total_msgs = 150
        sent_count = int(total_msgs * t)
        fail_count = int(sent_count * 0.05)

        stats_img = Image.new('RGBA', (W, H), (0,0,0,0))
        std = ImageDraw.Draw(stats_img)
        std.text((50, 175),  f"✅ Успішно: {sent_count - fail_count}", font=font_small, fill=(*GREEN, 230))
        std.text((50, 203),  f"❌ Помилки: {fail_count}", font=font_small, fill=(*RED, 200))
        std.text((270, 175), f"👥 Всього: {total_msgs}", font=font_small, fill=(*LIGHT_GRAY, 200))
        std.text((270, 203), f"📨 Залишилось: {total_msgs - sent_count}", font=font_small, fill=(*LIGHT_GRAY, 200))
        img.paste(stats_img, mask=stats_img)

        # Летящие точки-сообщения
        msg_layer = Image.new('RGBA', (W, H), (0,0,0,0))
        mld = ImageDraw.Draw(msg_layer)
        rng2 = random.Random(fi * 7 + 3)
        for _ in range(6):
            mx = rng2.randint(60, W-60)
            my = rng2.randint(20, 115)
            mr = rng2.randint(3, 6)
            mc = rng2.choice([ACCENT, ACCENT2, ACCENT3, GREEN])
            ma = rng2.randint(100, 220)
            mld.ellipse([mx-mr, my-mr, mx+mr, my+mr], fill=(*mc, ma))
        img.paste(msg_layer, mask=msg_layer)

        frames.append(img.convert('RGB'))

    path = f"{OUTPUT_DIR}/mailing_progress.gif"
    frames[0].save(
        path, format='GIF', append_images=frames[1:],
        save_all=True, duration=100, loop=0
    )
    print(f"✅ Mailing GIF → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  5. SUBSCRIPTION CARD (статичная, 600×320)
# ══════════════════════════════════════════════════════════════
def make_sub_card(plan_name="Місяць", days_left=30, is_forever=False):
    W, H = 600, 320
    img = Image.new('RGBA', (W, H), (0,0,0,0))

    # Карточка с закруглёнными углами
    card = Image.new('RGBA', (W, H), (0,0,0,0))
    cd = ImageDraw.Draw(card)

    # Фон карточки
    for y in range(H):
        ty = y / H
        c = lerp_color((22, 18, 55), (14, 10, 40), ty)
        cd.line([(0, y), (W, y)], fill=c)

    # Маска
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, W, H], radius=20, fill=255)

    card.putalpha(mask)

    # Звёзды
    sd = ImageDraw.Draw(card)
    rng = random.Random(77)
    for _ in range(40):
        sx, sy = rng.randint(0,W), rng.randint(0,H)
        sa = rng.randint(50, 180)
        sd.point((sx,sy), fill=(*WHITE, sa))

    # Свечение
    draw_glow(card, (80, H//2), 100, ACCENT, intensity=0.4)

    # Иконка статуса
    status_icon = "♾" if is_forever else "✦"
    status_color = GOLD if is_forever else GREEN

    icon_img = Image.new('RGBA', (W, H), (0,0,0,0))
    icd = ImageDraw.Draw(icon_img)
    icd.ellipse([30, H//2-45, 120, H//2+45], fill=(*ACCENT, 180))
    icd.text((52, H//2-28), status_icon, font=get_font(44, True), fill=(*status_color, 255))
    card.paste(icon_img, mask=icon_img)

    # Вертикальный разделитель
    for y in range(40, H-40):
        alpha_v = int(80 * math.sin(math.pi*(y-40)/(H-80)))
        sd.line([(140, y),(140, y)], fill=(*ACCENT, alpha_v))

    font_title = get_font(32, True)
    font_sub   = get_font(20, True)
    font_info  = get_font(17)

    # Название тарифа
    title_img = Image.new('RGBA', (W, H), (0,0,0,0))
    td = ImageDraw.Draw(title_img)
    td.text((160, 55), "📊 Моя підписка", font=font_sub, fill=(*LIGHT_GRAY, 200))

    if is_forever:
        td.text((160, 95), "∞  Назавжди", font=font_title, fill=(*GOLD, 255))
        td.text((160, 155), "Безстроковий доступ активний", font=font_info, fill=(*GREEN, 230))
    else:
        td.text((160, 95), f"✅  {plan_name}", font=font_title, fill=(*WHITE, 255))
        td.text((160, 155), f"Залишилось: {days_left} днів", font=font_info, fill=(*LIGHT_GRAY, 220))

    # Бейджи фич
    features = ["🚀 Розсилка", "👤 Акаунти", "📈 Статистика"]
    for i, feat in enumerate(features):
        fx = 160 + i * 145
        fy = 210
        badge_img = Image.new('RGBA', (W, H), (0,0,0,0))
        bad = ImageDraw.Draw(badge_img)
        bad.rounded_rectangle([fx, fy, fx+130, fy+34], radius=8,
                               fill=(*DARK_CARD, 200), outline=(*ACCENT, 120), width=1)
        bad.text((fx+8, fy+7), feat, font=get_font(15), fill=(*LIGHT_GRAY, 220))
        card.paste(badge_img, mask=badge_img)

    card.paste(title_img, mask=title_img)

    # Граница карточки
    border = Image.new('RGBA', (W, H), (0,0,0,0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([0, 0, W-1, H-1], radius=20, outline=(*ACCENT, 100), width=2)
    card.paste(border, mask=border)

    path = f"{OUTPUT_DIR}/subscription_card.png"
    card.save(path, 'PNG')
    print(f"✅ Sub Card → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  6. GIF "SUCCESS" — успешная рассылка (400×300, 30 frames)
# ══════════════════════════════════════════════════════════════
def make_success_gif():
    W, H = 400, 300
    frames = []
    N = 30
    font_big   = get_font(34, True)
    font_small = get_font(18)

    for fi in range(N):
        t = fi / (N-1)
        img = Image.new('RGBA', (W, H), DARK_BG)
        d = ImageDraw.Draw(img)

        for y in range(H):
            c = lerp_color((8, 18, 12), (14, 30, 22), y/H)
            d.line([(0,y),(W,y)], fill=c)

        cx, cy = W//2, H//2 - 20

        # Взрыв конфетти
        rng = random.Random(fi * 13)
        for _ in range(int(40 * t)):
            angle = rng.uniform(0, 2*math.pi)
            speed = rng.uniform(30, 130) * t
            px = int(cx + speed * math.cos(angle))
            py = int(cy + speed * math.sin(angle))
            pr = rng.randint(3, 7)
            pc = rng.choice([ACCENT, ACCENT3, GOLD, GREEN, ACCENT2, (255,100,100)])
            pa = int(255 * (1 - t * 0.6))
            d.ellipse([px-pr, py-pr, px+pr, py+pr], fill=(*pc, pa))

        # Большой зелёный круг
        cr = int(65 * min(1.0, t * 2.5))
        glo = Image.new('RGBA', (W, H), (0,0,0,0))
        draw_glow(glo, (cx, cy), cr+35, GREEN, intensity=0.6*min(1,t*2))
        img.paste(glo, mask=glo)

        ck_img = Image.new('RGBA', (W, H), (0,0,0,0))
        ckd = ImageDraw.Draw(ck_img)
        ckd.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill=(*GREEN, int(230*min(1,t*2))))
        if cr > 20:
            cp = min(1.0, (t-0.2)/0.4)
            if cp > 0:
                ckd.line([
                    (cx-22, cy), (cx-6, cy+18), (cx+22, cy-18)
                ], fill=(*WHITE, int(255*cp)), width=6)
        img.paste(ck_img, mask=ck_img)

        # Текст
        txt_img = Image.new('RGBA', (W, H), (0,0,0,0))
        txd = ImageDraw.Draw(txt_img)
        ta = min(255, int(255*(t-0.3)/0.4)) if t > 0.3 else 0
        txd.text((cx-115, H-115), "🎉 Розсилку завершено!", font=font_big, fill=(*WHITE, ta))
        img.paste(txt_img, mask=txt_img)

        # Мелкие звёзды
        for _ in range(8):
            sx = rng.randint(20, W-20)
            sy = rng.randint(20, H-20)
            sa = rng.randint(100, 200)
            d.text((sx, sy), "✦", font=get_font(12), fill=(*GOLD, sa))

        frames.append(img.convert('RGB'))

    path = f"{OUTPUT_DIR}/mailing_success.gif"
    frames[0].save(
        path, format='GIF', append_images=frames[1:],
        save_all=True, duration=80, loop=0
    )
    print(f"✅ Success GIF → {path}")
    return path


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🎨 Генерація візуальних ресурсів Smart Sender Bot...\n")
    make_avatar()
    make_welcome_gif()
    make_payment_gif()
    make_mailing_gif()
    make_sub_card()
    make_success_gif()
    print(f"\n✅ Всі файли збережено в папку '{OUTPUT_DIR}/'")
