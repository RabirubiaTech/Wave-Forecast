import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime
import os

print("Script started - imports OK")
print("Current working dir:", os.getcwd())

# ─────────────────────────────────────────────────────────────
# PART 1: Fetch & Parse AMZ726 Forecast
# ─────────────────────────────────────────────────────────────
URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
ZONE = "726"
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
    print("Fetching AMZ726 forecast")
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    pattern = rf"({ZONE}.*?)(\\d{{3}}|$)"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if m:
        block = m.group(1).replace("feet", "ft").replace("\n\n", "\n")
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        periods = []
        current_label = None
        current_text = []

        for line in lines:
            if re.match(r"^(REST OF TONIGHT|TODAY|MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)", line, re.I):
                if current_label and current_text:
                    periods.append((current_label.upper(), " ".join(current_text)))
                current_label = line
                current_text = []
            else:
                if current_label:
                    current_text.append(line)

        if current_label and current_text:
            periods.append((current_label.upper(), " ".join(current_text)))

        cleaned = []
        for label, txt in periods:
            if label == "REST OF TONIGHT":
                label = "TONIGHT"
            cleaned.append((label, txt))

        cleaned = cleaned[:7]

        final_lines = []
        for label, txt in cleaned:
            wave_match = re.search(r"Wave Detail:\s*(.+?)(?=\.|$|Scattered|Isolated)", txt, re.I | re.DOTALL)
            if wave_match:
                detail = wave_match.group(1).strip()
                final_lines.append(f"{label}: {detail}")
            else:
                seas_match = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*feet", txt, re.I)
                if seas_match:
                    final_lines.append(f"{label}: Seas {seas_match.group(1)}–{seas_match.group(2)} ft")
                else:
                    final_lines.append(f"{label}: {txt[:80]}...")

        if final_lines:
            forecast_text = "\n".join(final_lines)
            print("Forecast parsed OK:", forecast_text[:200] + "...")
except Exception as e:
    print("Forecast parsing ERROR:", str(e))

# ─────────────────────────────────────────────────────────────
# PART 2: Buoy 41043 – FIXED table selection & parsing
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

try:
    print("Fetching buoy 41043")
    buoy_url = "https://www.ndbc.noaa.gov/station_page.php?station=41043"
    buoy_r = requests.get(buoy_url, timeout=15)
    buoy_r.raise_for_status()
    buoy_soup = BeautifulSoup(buoy_r.text, "html.parser")
    print("Buoy page fetched")

    table = None
    for tbl in buoy_soup.find_all("table"):
        tbl_text = tbl.get_text()
        if "WVHT" in tbl_text or "Significant Wave Height" in tbl_text:
            # Extra check: look for table with many columns/rows (main obs table)
            if len(tbl.find_all("tr")) > 5 and len(tbl.find_all("td")) > 20:  # rough size filter
                table = tbl
                break

    if table:
        rows = table.find_all("tr")
        print("Selected table rows:", len(rows))
        if len(rows) >= 2:
            cols = rows[1].find_all("td")  # latest row
            print("Columns in latest row:", len(cols))
            if len(cols) >= 5:
                wvht = cols[1].get_text(strip=True)
                swh  = cols[2].get_text(strip=True)
                swp  = cols[3].get_text(strip=True)
                swd  = cols[4].get_text(strip=True)

                if wvht and wvht not in ["MM", "-"]:
                    sig_height = f"{wvht} ft"
                if swh and swh not in ["MM", "-"]:
                    swell_height = f"{swh} ft"
                if swp and swp not in ["MM", "-"]:
                    swell_period = f"{swp} sec"
                if swd and swd not in ["MM", "-"]:
                    buoy_dir = swd
                print("Buoy data extracted:", sig_height, swell_height, swell_period, buoy_dir)
            else:
                print("Too few columns in selected table")
    else:
        print("No matching wave table found")
except Exception as e:
    print("Buoy fetch error:", str(e))

# ─────────────────────────────────────────────────────────────
# PART 3: Image Generation – with debug
# ─────────────────────────────────────────────────────────────
print("Starting image generation")
try:
    print("Loading background")
    bg_data = requests.get(
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e",
        timeout=20
    ).content
    bg = Image.open(io.BytesIO(bg_data)).convert("RGB")
except Exception as e:
    print("Background load ERROR:", str(e))
    bg = Image.new("RGB", (800, 1000), "#004488")

bg = bg.resize((800, 1000))
enhancer = ImageEnhance.Brightness(bg)
bg = enhancer.enhance(1.12)

overlay = Image.new("RGBA", bg.size, (255, 255, 255, 40))
card = Image.alpha_composite(bg.convert("RGBA"), overlay)
draw = ImageDraw.Draw(card)

# Logo
try:
    print("Loading logo")
    logo_data = requests.get(
        "https://static.wixstatic.com/media/80c250_b1146919dfe046429a96648c59e2c413~mv2.png",
        timeout=20
    ).content
    logo = Image.open(io.BytesIO(logo_data)).convert("RGBA").resize((120, 120))
    card.paste(logo, (40, 40), logo)
except Exception as e:
    print("Logo load ERROR:", str(e))

# Fonts – use default if any fail
print("Loading fonts")
font_title = font_sub = font_location = font_body = font_footer = font_buoy = ImageFont.load_default()
try:
    font_title    = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    font_sub      = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_location = ImageFont.truetype("DejaVuSans.ttf", 26)
    font_body     = ImageFont.truetype("DejaVuSans.ttf", 22)
    font_footer   = ImageFont.truetype("DejaVuSans.ttf", 18)
    font_buoy     = ImageFont.truetype("DejaVuSans.ttf", 18)
    print("Custom fonts loaded")
except Exception as e:
    print("Font load fallback:", str(e))

TEXT = "#0a1a2f"
GRAY = "#aaaaaa"

print("Drawing header")
draw.text((400, 180), "7-Day Wave Forecast", fill=TEXT, font=font_sub, anchor="mm")
draw.text((400, 220), "(Forecast starting from TODAY - Real-time current below)", fill=GRAY, font=font_footer, anchor="mm")
draw.text((400, 240), "Coastal waters east of Puerto Rico (AMZ726)", fill=TEXT, font=font_location, anchor="mm")

print("Drawing forecast text")
draw.multiline_text((100, 300), forecast_text, fill=TEXT, font=font_body, align="left", spacing=28)

print("Drawing buoy section")
buoy_y_title = 700
buoy_y_value = buoy_y_title + 35

draw.rectangle([(60, buoy_y_title - 20), (740, buoy_y_value + 40)], fill=(0, 20, 60, 140))
draw.text((80, buoy_y_title), "Current (Buoy 41043 – NE Puerto Rico)", fill="white", font=font_buoy)

buoy_text = f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}"
draw.text((80, buoy_y_value), buoy_text, fill="#a0d0ff", font=font_buoy)

print("Drawing footer")
footer_line = "NDBC Marine Forecast | RabirubiaWeather.com | Updated every 6 hours"
draw.text((400, 930), footer_line, fill=TEXT, font=font_footer, anchor="mm")

print("All drawing done - saving file")
card.convert("RGB").save("wave_card.png", optimize=True)
print("Card saved! File should be in:", os.path.abspath("wave_card.png"))
