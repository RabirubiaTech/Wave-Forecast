import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime

print("DEBUG: Starting PART 1")

print("DEBUG: Starting PART 1")

print("DEBUG: Starting PART 1")

# ─────────────────────────────────────────────────────────────
# PART 1: Fetch & Parse AMZ726 Forecast (NWS Marine Page)
# ─────────────────────────────────────────────────────────────
URL = "https://marine.weather.gov/MapClick.php?zoneid=AMZ726"
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # NWS Marine page stores forecast in <div id="detailed-forecast-body">
    container = soup.find("div", id="detailed-forecast-body")

    if container:
        periods = container.find_all("div", class_="row-forecast")

        final_lines = []

        for p in periods[:7]:  # first 7 periods
            name = p.find("div", class_="forecast-label")
            text = p.find("div", class_="forecast-text")

            if not name or not text:
                continue

            label = name.get_text(strip=True)
            txt = text.get_text(" ", strip=True)

            # Normalize feet
            txt = txt.replace("feet", "ft").replace("foot", "ft")

            # Extract seas if present
            seas = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*ft", txt, re.IGNORECASE)
            if seas:
                final_lines.append(f"{label}: Seas {seas.group(1)}–{seas.group(2)} ft")
            else:
                # Shorten long text
                if len(txt) > 120:
                    txt = txt[:120] + "..."
                final_lines.append(f"{label}: {txt}")

        if final_lines:
            forecast_text = "\n".join(final_lines)

except Exception as e:
    print("DEBUG: PART 1 error:", e)

print("DEBUG: Finished PART 1")
print("DEBUG: Forecast text preview:", forecast_text.splitlines()[0] if forecast_text else "EMPTY")


# ─────────────────────────────────────────────────────────────
# PART 2: Fetch Current Buoy 41043 Data from realtime2
#   - Spectral files for 41043 are gone (404)
#   - Use realtime2/41043.txt
#   - Scan backwards to find latest non-MM WVHT (and DPD/MWD)
#   - Use WVHT as Sig + Swell
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

def m_to_ft(m):
    try:
        return round(float(m) * 3.28084, 1)
    except Exception:
        return None

try:
    url_rt = "https://www.ndbc.noaa.gov/data/realtime2/41043.txt"
    r_rt = requests.get(url_rt, timeout=15)
    r_rt.raise_for_status()
    lines_rt = r_rt.text.splitlines()

    header_tokens = None
    data_rows = []

    for ln in lines_rt:
        if ln.startswith("#YY"):
            header_tokens = ln.lstrip("#").split()
            continue
        if header_tokens and not ln.startswith("#") and ln.strip():
            data_rows.append(ln)

    if header_tokens and data_rows:
        print("DEBUG: Realtime2 header:", header_tokens)

        # Build index map
        def idx(name):
            try:
                return header_tokens.index(name)
            except ValueError:
                return None

        i_yy   = idx("YY")
        i_mm   = idx("MM")
        i_dd   = idx("DD")
        i_hh   = idx("hh")
        i_min  = idx("mm")
        i_wvht = idx("WVHT")
        i_dpd  = idx("DPD")
        i_mwd  = idx("MWD")

        parsed_rows = []

        for ln in data_rows:
            parts = ln.split()
            try:
                # Basic timestamp for ordering
                yy  = int(parts[i_yy])   if i_yy  is not None and i_yy  < len(parts) else 0
                mm  = int(parts[i_mm])   if i_mm  is not None and i_mm  < len(parts) else 0
                dd  = int(parts[i_dd])   if i_dd  is not None and i_dd  < len(parts) else 0
                hh  = int(parts[i_hh])   if i_hh  is not None and i_hh  < len(parts) else 0
                mns = int(parts[i_min])  if i_min is not None and i_min < len(parts) else 0
                ts = datetime(yy, mm, dd, hh, mns)
            except Exception:
                continue

            parsed_rows.append((ts, parts))

        parsed_rows.sort(key=lambda x: x[0], reverse=True)

        chosen = None
        for ts, parts in parsed_rows:
            wvht_val = parts[i_wvht] if i_wvht is not None and i_wvht < len(parts) else None
            if wvht_val and wvht_val not in ["MM", "99.00"]:
                chosen = (ts, parts)
                break

        if chosen:
            ts, parts = chosen
            print("DEBUG: Chosen realtime2 row:", " ".join(parts))

            wvht_val = parts[i_wvht] if i_wvht is not None and i_wvht < len(parts) else None
            dpd_val  = parts[i_dpd]  if i_dpd  is not None and i_dpd  < len(parts) else None
            mwd_val  = parts[i_mwd]  if i_mwd  is not None and i_mwd  < len(parts) else None

            if wvht_val and wvht_val not in ["MM", "99.00"]:
                h_ft = m_to_ft(wvht_val)
                if h_ft is not None:
                    sig_height = f"{h_ft} ft"
                    swell_height = sig_height  # no separate SwH in realtime2

            if dpd_val and dpd_val not in ["MM", "99"]:
                swell_period = f"{dpd_val} sec"

            if mwd_val and mwd_val not in ["MM", "999"]:
                buoy_dir = f"{mwd_val}°"
        else:
            print("DEBUG: No valid WVHT row found in realtime2")

except Exception as e:
    print("DEBUG: PART 2 error:", e)

print("DEBUG: Finished PART 2:", sig_height, swell_height, swell_period, buoy_dir)

print("DEBUG: Starting PART 3")

# ─────────────────────────────────────────────────────────────
# PART 3: Image Generation
# ─────────────────────────────────────────────────────────────
try:
    print("DEBUG: Fetching background image")
    bg_data = requests.get(
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        timeout=20
    ).content
    bg = Image.open(io.BytesIO(bg_data)).convert("RGB")
except Exception as e:
    print("DEBUG: Background load failed, using solid color:", e)
    bg = Image.new("RGB", (800, 950), "#004488")

bg = bg.resize((800, 950))
enhancer = ImageEnhance.Brightness(bg)
bg = enhancer.enhance(1.12)

overlay = Image.new("RGBA", bg.size, (255, 255, 255, 40))
card = Image.alpha_composite(bg.convert("RGBA"), overlay)
draw = ImageDraw.Draw(card)

# Logo
try:
    print("DEBUG: Fetching logo")
    logo_data = requests.get(
        "https://static.wixstatic.com/media/80c250_b1146919dfe046429a96648c59e2c413~mv2.png",
        timeout=20
    ).content
    logo = Image.open(io.BytesIO(logo_data)).convert("RGBA").resize((120, 120))
    card.paste(logo, (40, 40), logo)
except Exception as e:
    print("DEBUG: Logo load failed, continuing without logo:", e)

# Fonts
try:
    print("DEBUG: Loading fonts")
    font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_location = ImageFont.truetype("DejaVuSans.ttf", 26)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_footer = ImageFont.truetype("DejaVuSans.ttf", 18)
    font_buoy = ImageFont.truetype("DejaVuSans.ttf", 22)
except Exception as e:
    print("DEBUG: Font load failed, using default fonts:", e)
    font_title = font_sub = font_location = font_body = font_footer = font_buoy = ImageFont.load_default()

TEXT = "#0a1a2f"
GRAY = "#aaaaaa"

# Header
draw.text((400, 180), "7-Day Wave Forecast", fill=TEXT, font=font_sub, anchor="mm")
draw.text(
    (400, 220),
    "(Forecast from NWS TJSJ – AMZ726)",
    fill=GRAY,
    font=font_footer,
    anchor="mm"
)
draw.text((400, 240), "Coastal waters east of Puerto Rico (AMZ726)", fill=TEXT, font=font_location, anchor="mm")

# Forecast text
draw.multiline_text((80, 300), forecast_text, fill=TEXT, font=font_body, align="left", spacing=12)

# Bottom section: Current Buoy 41043
buoy_y_title = 700
buoy_y_value = buoy_y_title + 35
draw.rectangle([(60, buoy_y_title - 20), (740, buoy_y_value + 40)], fill=(0, 20, 60, 140))
draw.text((80, buoy_y_title), "Current (Buoy 41043 – NE of Puerto Rico)", fill="white", font=font_buoy)

buoy_text = f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}"
draw.text((80, buoy_y_value), buoy_text, fill="#a0d0ff", font=font_buoy)

# Footer
footer_line = "NDBC / NWS Marine • RabirubiaWeather.com • Auto-updated"
draw.text(
    (400, 880),
    footer_line,
    fill=TEXT,
    font=font_footer,
    anchor="mm"
)

print("DEBUG: Saving card now")

try:
    card.convert("RGB").save("wave_card.png", optimize=True)
    print("DEBUG: Card saved successfully as wave_card.png")
except Exception as e:
    print("DEBUG: Error saving card:", e)
