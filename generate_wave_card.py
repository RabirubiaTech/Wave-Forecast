import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# PART 1: Fetch & Parse AMZ726 Forecast (FIXED)
# ─────────────────────────────────────────────────────────────
URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
ZONE = "AMZ726"
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
    r = requests.get(URL, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n")

    # FIXED regex (no double escaping)
    block_match = re.search(rf"({ZONE}.*?)(AMZ\d{{3}}|$)", text, re.S)
    if block_match:
        block = block_match.group(1).replace("feet", "ft")
        lines = [l.strip() for l in block.splitlines() if l.strip()]

        final_lines = []
        current_label = None

        for line in lines:
            if re.match(r"^(REST OF TONIGHT|TODAY|TONIGHT|MON|TUE|WED|THU|FRI|SAT|SUN)", line):
                current_label = line
                continue

            if "ft" in line and current_label:
                # Flexible wave extraction
                m = re.search(r"(\d+)\s*ft.*?(\d+)\s*sec", line, re.I)
                if m:
                    h = int(m.group(1))
                    p = m.group(2)
                    final_lines.append(f"{current_label}: {h-1}–{h+1} ft @ {p}s")

        if final_lines:
            final_lines[0] = final_lines[0].replace("REST OF TONIGHT", "Currently")
            forecast_text = "\n".join(final_lines[:6])

except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# PART 2: Fetch Current Buoy 41043 Data (REALTIME – FIXED)
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

try:
    buoy_url = "https://www.ndbc.noaa.gov/data/realtime2/41043.txt"
    r = requests.get(buoy_url, timeout=15)
    r.raise_for_status()

    lines = r.text.strip().splitlines()
    header = lines[0].split()
    data = lines[2].split()

    col = {k: i for i, k in enumerate(header)}

    def get(name):
        if name in col:
            v = data[col[name]]
            return None if v in ["MM", "-", ""] else v
        return None

    if get("WVHT"):
        sig_height = f"{get('WVHT')} ft"
    if get("SwH"):
        swell_height = f"{get('SwH')} ft"
    if get("SwP"):
        swell_period = f"{get('SwP')} sec"
    if get("SwD"):
        buoy_dir = get("SwD")

except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# PART 3: Generate the card image (GUARANTEED SAVE)
# ─────────────────────────────────────────────────────────────
try:
    bg_data = requests.get(
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e",
        timeout=20
    ).content
    bg = Image.open(io.BytesIO(bg_data)).convert("RGB")
except Exception:
    bg = Image.new("RGB", (800, 950), "#003366")

bg = bg.resize((800, 950))
bg = ImageEnhance.Brightness(bg).enhance(1.12)

card = Image.alpha_composite(
    bg.convert("RGBA"),
    Image.new("RGBA", bg.size, (255, 255, 255, 40))
)
draw = ImageDraw.Draw(card)

# Fonts
try:
    font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_small = ImageFont.truetype("DejaVuSans.ttf", 22)
except Exception:
    font_title = font_sub = font_body = font_small = ImageFont.load_default()

TEXT = "#0a1a2f"

draw.text((200, 80), datetime.now().strftime("%b %d, %Y"), fill=TEXT, font=font_title)
draw.text((400, 160), "Wave Forecast", fill=TEXT, font=font_sub, anchor="mm")
draw.text((80, 260), forecast_text, fill=TEXT, font=font_body, spacing=10)

draw.rectangle([(60, 700), (740, 780)], fill=(0, 20, 60, 140))
draw.text((80, 710), "Current – Buoy 41043 (NE PR)", fill="white", font=font_small)
draw.text(
    (80, 740),
    f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}",
    fill="#a0d0ff",
    font=font_small
)

draw.text(
    (400, 900),
    "NDBC Marine Forecast | Updated every 6 hours",
    fill=TEXT,
    font=font_small,
    anchor
