import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# PART 1: Fetch & Parse AMZ726 Forecast – improved Wave Detail capture
# ─────────────────────────────────────────────────────────────
URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
ZONE = "726"
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
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
            # Capture everything after "Wave Detail:" (more flexible)
            wave_match = re.search(r"Wave Detail:\s*(.+?)(?=\.|$|Scattered|Isolated)", txt, re.I | re.DOTALL)
            if wave_match:
                detail = wave_match.group(1).strip()
                final_lines.append(f"{label}: {detail}")
            else:
                # Fallback to seas if present
                seas_match = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*feet", txt, re.I)
                if seas_match:
                    final_lines.append(f"{label}: Seas {seas_match.group(1)}–{seas_match.group(2)} ft")
                else:
                    final_lines.append(f"{label}: {txt[:80]}...")

        if final_lines:
            forecast_text = "\n".join(final_lines)
except Exception:
    pass

# ─────────────────────────────────────────────────────────────
# PART 2: Fetch Current Buoy 41043 Data (robust version)
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

try:
    buoy_url = "https://www.ndbc.noaa.gov/station_page.php?station=41043"
    buoy_r = requests.get(buoy_url, timeout=15)
    buoy_r.raise_for_status()
    soup = BeautifulSoup(buoy_r.text, "html.parser")

    # Look for any table containing WVHT, SwH, SwP, SwD
    target_table = None
    for tbl in soup.find_all("table"):
        header = tbl.find("tr")
        if not header:
            continue

        header_text = header.get_text().lower()

        if any(key in header_text for key in ["wvht", "swh", "swp", "swd"]):
            target_table = tbl
            break

    if target_table:
        rows = target_table.find_all("tr")
        if len(rows) >= 2:
            headers = [h.get_text(strip=True).lower() for h in rows[0].find_all(["th", "td"])]
            values = [v.get_text(strip=True) for v in rows[1].find_all("td")]

            def get(col):
                if col in headers:
                    return values[headers.index(col)]
                return None

            wvht = get("wvht") or get("wvht (ft)") or get("wvht (m)")
            swh  = get("swh") or get("swh (ft)") or get("swh (m)")
            swp  = get("swp") or get("swp (s)")
            swd  = get("swd") or get("swd (deg)")

            if wvht and wvht not in ["MM", "-", ""]:
                sig_height = f"{wvht} ft" if "m" not in wvht else f"{wvht} m"

            if swh and swh not in ["MM", "-", ""]:
                swell_height = f"{swh} ft" if "m" not in swh else f"{swh} m"

            if swp and swp not in ["MM", "-", ""]:
                swell_period = f"{swp} sec"

            if swd and swd not in ["MM", "-", ""]:
                buoy_dir = swd

except Exception as e:
    print("Buoy parse error:", e)


# ─────────────────────────────────────────────────────────────
# PART 3: Image Generation (fixed, safe, guaranteed output)
# ─────────────────────────────────────────────────────────────

# 1. Load background safely
try:
    bg_url = "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80"
    bg_data = requests.get(bg_url, timeout=20).content
    bg = Image.open(io.BytesIO(bg_data)).convert("RGB")
except Exception as e:
    print("Background failed:", e)
    bg = Image.new("RGB", (800, 950), "#004488")

bg = bg.resize((800, 950))
bg = ImageEnhance.Brightness(bg).enhance(1.12)

# 2. Create overlay + card
overlay = Image.new("RGBA", bg.size, (255, 255, 255, 40))
card = Image.alpha_composite(bg.convert("RGBA"), overlay)
draw = ImageDraw.Draw(card)

# 3. Load logo safely
try:
    logo_url = "https://static.wixstatic.com/media/80c250_b1146919dfe046429a96648c59e2c413~mv2.png"
    logo_data = requests.get(logo_url, timeout=20).content
    logo = Image.open(io.BytesIO(logo_data)).convert("RGBA").resize((120, 120))
    card.paste(logo, (40, 40), logo)
except Exception as e:
    print("Logo failed:", e)

# 4. Fonts
try:
    font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_location = ImageFont.truetype("DejaVuSans.ttf", 26)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_footer = ImageFont.truetype("DejaVuSans.ttf", 18)
    font_buoy = ImageFont.truetype("DejaVuSans.ttf", 22)
except:
    font_title = font_sub = font_location = font_body = font_footer = font_buoy = ImageFont.load_default()

TEXT = "#0a1a2f"
GRAY = "#aaaaaa"

# 5. Header
draw.text((400, 180), "7-Day Wave Forecast", fill=TEXT, font=font_sub, anchor="mm")
draw.text((400, 220), "(Forecast starting from TODAY - Real-time current below)", fill=GRAY, font=font_footer, anchor="mm")
draw.text((400, 240), "Coastal waters east of Puerto Rico (AMZ726)", fill=TEXT, font=font_location, anchor="mm")

# 6. Forecast text
draw.multiline_text((80, 300), forecast_text, fill=TEXT, font=font_body, align="left", spacing=12)

# 7. Buoy box
buoy_y_title = 700
buoy_y_value = buoy_y_title + 35
draw.rectangle([(60, buoy_y_title - 20), (740, buoy_y_value + 40)], fill=(0, 20, 60, 140))
draw.text((80, buoy_y_title), "Current (Buoy 41043 – NE Puerto Rico)", fill="white", font=font_buoy)
buoy_text = f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}"
draw.text((80, buoy_y_value), buoy_text, fill="#a0d0ff", font=font_buoy)

# 8. Footer
footer_line = "NDBC Marine Forecast | RabirubiaWeather.com | Updated every 6 hours"
draw.text((400, 880), footer_line, fill=TEXT, font=font_footer, anchor="mm")

# 9. Save card
card.convert("RGB").save("wave_card.png", optimize=True)
print("Card generated successfully.")


# Logo
try:
    logo_data = requests.get(
        "https://static.wixstatic.com/media/80c250_b1146919dfe046429a96648c59e2c413~mv2.png",
        timeout=20
    ).content
    logo = Image.open(io.BytesIO(logo_data)).convert("RGBA").resize((120, 120))
    card.paste(logo, (40, 40), logo)
except Exception:
    pass

# Fonts
try:
    font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_location = ImageFont.truetype("DejaVuSans.ttf", 26)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_footer = ImageFont.truetype("DejaVuSans.ttf", 18)
    font_buoy = ImageFont.truetype("DejaVuSans.ttf", 22)
except Exception:
    font_title = font_sub = font_location = font_body = font_footer = font_buoy = ImageFont.load_default()

TEXT = "#0a1a2f"
GRAY = "#aaaaaa"

# Header with clarification
draw.text((400, 180), "7-Day Wave Forecast", fill=TEXT, font=font_sub, anchor="mm")
draw.text(
    (400, 220),
    "(Forecast starting from TODAY - Real-time current below)",
    fill=GRAY,
    font=font_footer,
    anchor="mm"
)
draw.text((400, 240), "Coastal waters east of Puerto Rico (AMZ726)", fill=TEXT, font=font_location, anchor="mm")

# Forecast text
draw.multiline_text((80, 300), forecast_text, fill=TEXT, font=font_body, align="left", spacing=12)

# Bottom section: Current Buoy 41043
buoy_y_title = 700 # Increase to 740–780 if overlap occurs
buoy_y_value = buoy_y_title + 35
draw.rectangle([(60, buoy_y_title - 20), (740, buoy_y_value + 40)], fill=(0, 20, 60, 140))
draw.text((80, buoy_y_title), "Current (Buoy 41043 – NE Puerto Rico)", fill="white", font=font_buoy)
buoy_text = f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}"
draw.text((80, buoy_y_value), buoy_text, fill="#a0d0ff", font=font_buoy)

# Footer
footer_line = "NDBC Marine Forecast | RabirubiaWeather.com | Updated every 6 hours"
draw.text(
    (400, 880),
    footer_line,
    fill=TEXT,
    font=font_footer,
    anchor="mm"
)
card.convert("RGB").save("wave_card.png", optimize=True)
