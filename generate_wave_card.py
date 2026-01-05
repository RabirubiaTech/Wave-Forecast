import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime

# -------------------------------------------------------------
# Helper: Convert meters → feet
# -------------------------------------------------------------
def m_to_ft(m):
    try:
        return round(float(m) * 3.28084, 1)
    except:
        return None

# -------------------------------------------------------------
# Helper: Wave color scale
# -------------------------------------------------------------
def wave_color(sig_ft):
    try:
        h = float(sig_ft.replace("ft", "").strip())
    except:
        return "#a0d0ff"  # default light blue

    if h < 3:
        return "#00cc66"  # green
    elif h < 6:
        return "#ffcc00"  # yellow
    elif h < 9:
        return "#ff8800"  # orange
    else:
        return "#ff3333"  # red


# -------------------------------------------------------------
# PART 1 — NWS Marine Forecast (AMZ726)
# -------------------------------------------------------------
print("DEBUG: Starting PART 1")

URL = "https://marine.weather.gov/MapClick.php?zoneid=AMZ726"
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    container = soup.find("div", id="detailed-forecast-body")

    if container:
        periods = container.find_all("div", class_="row-forecast")

        final_lines = []

        # Only first 3 periods (Today, Tonight, Tomorrow)
        for p in periods[:3]:
            name = p.find("div", class_="forecast-label")
            text = p.find("div", class_="forecast-text")

            if not name or not text:
                continue

            label = name.get_text(strip=True)
            txt = text.get_text(" ", strip=True)

            txt = txt.replace("feet", "ft").replace("foot", "ft")

            seas = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*ft", txt, re.IGNORECASE)
            if seas:
                final_lines.append(f"{label}: Seas {seas.group(1)}–{seas.group(2)} ft")
            else:
                if len(txt) > 120:
                    txt = txt[:120] + "..."
                final_lines.append(f"{label}: {txt}")

        if final_lines:
            forecast_text = "\n".join(final_lines)

except Exception as e:
    print("DEBUG: PART 1 error:", e)

print("DEBUG: Finished PART 1")
print("DEBUG: Forecast text preview:", forecast_text.splitlines()[0] if forecast_text else "EMPTY")


# -------------------------------------------------------------
# PART 2 — Buoy 41043 realtime2 (WVHT, DPD, MWD)
# -------------------------------------------------------------
print("DEBUG: Starting PART 2")

sig_height = swell_height = swell_period = buoy_dir = "N/A"
last_update_str = "N/A"

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
                yy  = int(parts[i_yy])
                mm  = int(parts[i_mm])
                dd  = int(parts[i_dd])
                hh  = int(parts[i_hh])
                mns = int(parts[i_min])
                ts = datetime(yy, mm, dd, hh, mns)
            except:
                continue

            parsed_rows.append((ts, parts))

        parsed_rows.sort(key=lambda x: x[0], reverse=True)

        chosen = None
        for ts, parts in parsed_rows:
            wvht_val = parts[i_wvht]
            if wvht_val not in ["MM", "99.00"]:
                chosen = (ts, parts)
                break

        if chosen:
            ts, parts = chosen
            print("DEBUG: Chosen realtime2 row:", " ".join(parts))

            last_update_str = ts.strftime("%b %d, %Y at %H:%M AST")

            wvht_val = parts[i_wvht]
            dpd_val  = parts[i_dpd]
            mwd_val  = parts[i_mwd]

            if wvht_val not in ["MM", "99.00"]:
                h_ft = m_to_ft(wvht_val)
                if h_ft is not None:
                    sig_height = f"{h_ft} ft"
                    swell_height = sig_height

            if dpd_val not in ["MM", "99"]:
                swell_period = f"{dpd_val} sec"

            if mwd_val not in ["MM", "999"]:
                buoy_dir = f"{mwd_val}°"

except Exception as e:
    print("DEBUG: PART 2 error:", e)

print("DEBUG: Finished PART 2:", sig_height, swell_height, swell_period, buoy_dir)


# -------------------------------------------------------------
# PART 3 — Card Generation
# -------------------------------------------------------------
print("DEBUG: Starting PART 3")

try:
    bg_data = requests.get(
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        timeout=20
    ).content
    bg = Image.open(io.BytesIO(bg_data)).convert("RGB")
except:
    bg = Image.new("RGB", (800, 950), "#004488")

bg = bg.resize((800, 950))
bg = ImageEnhance.Brightness(bg).enhance(1.12)

overlay = Image.new("RGBA", bg.size, (255, 255, 255, 40))
card = Image.alpha_composite(bg.convert("RGBA"), overlay)
draw = ImageDraw.Draw(card)

# Logo
try:
    logo_data = requests.get(
        "https://static.wixstatic.com/media/80c250_b1146919dfe046429a96648c59e2c413~mv2.png",
        timeout=20
    ).content
    logo = Image.open(io.BytesIO(logo_data)).convert("RGBA").resize((120, 120))
    card.paste(logo, (40, 40), logo)
except:
    pass

# Fonts
try:
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 40)
    font_location = ImageFont.truetype("DejaVuSans.ttf", 26)
    font_body = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_footer = ImageFont.truetype("DejaVuSans.ttf", 18)
    font_buoy = ImageFont.truetype("DejaVuSans.ttf", 22)
except:
    font_sub = font_location = font_body = font_footer = font_buoy = ImageFont.load_default()

TEXT = "#000000"  # high contrast

# Header
draw.text((400, 180), "Marine Forecast | Coastal Waters East of Fajardo (AMZ726)", fill=TEXT, font=ImageFont.truetype("DejaVuSans.ttf", 18), anchor="mm")
draw.text((400, 220), "Today • Tonight • Tomorrow", fill="#555555", font=font_footer, anchor="mm")

# Forecast text
draw.multiline_text((80, 300), forecast_text, fill=TEXT, font=font_body, spacing=12)

# Buoy block
buoy_y_title = 700
buoy_y_value = buoy_y_title + 35

draw.rectangle([(60, buoy_y_title - 20), (740, buoy_y_value + 80)], fill=(0, 20, 60, 140))
draw.text((80, buoy_y_title), "Current (Buoy 41043 – NE of Puerto Rico)", fill="white", font=font_buoy)

sig_color = wave_color(sig_height)
buoy_text = f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}"
draw.text((80, buoy_y_value), buoy_text, fill=sig_color, font=font_buoy)

draw.text((80, buoy_y_value + 35), f"Last updated: {last_update_str}", fill="#ffffff", font=font_footer)

# Footer
draw.text((400, 880), "RabirubiaWeather.com • Auto-updated", fill=TEXT, font=font_footer, anchor="mm")

card.convert("RGB").save("wave_card.png", optimize=True)
print("DEBUG: Card saved successfully as wave_card.png")
