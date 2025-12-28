import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io

# ─────────────────────────────────────────────────────────────
# PART 1: AMZ726 FORECAST (CORRECT SOURCE + MATCH)
# ─────────────────────────────────────────────────────────────
URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
forecast_text = "Wave forecast temporarily unavailable."

try:
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n")

    pattern = r"(AMZ726-.*?)(?=AMZ\d{3}-|$)"
    m = re.search(pattern, text, re.DOTALL)

    if m:
        block = m.group(1)
        lines = [l.strip() for l in block.splitlines() if l.strip()]

        periods = []
        label = None
        content = []

        for line in lines:
            if re.match(r"^(TODAY|TONIGHT|MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)", line):
                if label:
                    periods.append((label, " ".join(content)))
                label = line
                content = []
            else:
                content.append(line)

        if label:
            periods.append((label, " ".join(content)))

        out = []
        for label, txt in periods[:7]:
            wave = re.search(r"Wave Detail:\s*(.+?)(?=\.|$)", txt)
            seas = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*feet", txt)

            if wave:
                out.append(f"{label}: {wave.group(1)}")
            elif seas:
                out.append(f"{label}: Seas {seas.group(1)}–{seas.group(2)} ft")
            else:
                out.append(f"{label}: {txt[:80]}...")

        if out:
            forecast_text = "\n".join(out)

except Exception as e:
    print("FORECAST ERROR:", e)

# ─────────────────────────────────────────────────────────────
# PART 2: BUOY 41043 (REAL NOAA FIELD FALLBACKS)
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

try:
    r = requests.get("https://www.ndbc.noaa.gov/data/realtime2/41043.txt", timeout=15)
    r.raise_for_status()

    lines = r.text.strip().splitlines()
    header = lines[0].split()
    data = lines[1].split()

    def get(*keys):
        for k in keys:
            if k in header:
                v = data[header.index(k)]
                if v != "MM":
                    return v
        return None

    wvht = get("WVHT")
    swp = get("SwP", "DPD")
    swd = get("SwD", "MWD")

    if wvht:
        sig_height = f"{round(float(wvht) * 3.28084, 1)} ft"
        swell_height = sig_height

    if swp:
        swell_period = f"{swp} sec"

    if swd:
        buoy_dir = f"{swd}°"

except Exception as e:
    print("BUOY ERROR:", e)

# ─────────────────────────────────────────────────────────────
# PART 3: IMAGE (UNCHANGED, WORKING)
# ─────────────────────────────────────────────────────────────
bg = Image.new("RGB", (800, 950), "#004488")
bg = ImageEnhance.Brightness(bg).enhance(1.1)
card = Image.alpha_composite(bg.convert("RGBA"),
                             Image.new("RGBA", bg.size, (255,255,255,40)))
draw = ImageDraw.Draw(card)

font = ImageFont.load_default()

draw.text((400, 80), "7-Day Wave Forecast", anchor="mm", fill="white", font=font)
draw.multiline_text((80, 150), forecast_text, fill="white", font=font, spacing=6)

draw.rectangle([(60,700),(740,760)], fill=(0,20,60,180))
draw.text((80,710), "Current – Buoy 41043", fill="white", font=font)
draw.text((80,735),
          f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}",
          fill="#a0d0ff", font=font)

card.convert("RGB").save("wave_card.png", optimize=True)
