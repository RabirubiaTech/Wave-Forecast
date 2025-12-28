import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
from datetime import datetime

print("DEBUG: Starting PART 1")

# ─────────────────────────────────────────────────────────────
# PART 1: Fetch & Parse AMZ726 Forecast (robust + safe fallback)
# ─────────────────────────────────────────────────────────────
URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
ZONE = "AMZ726"  # use actual marine zone code string, not just 726
FALLBACK = "Wave forecast temporarily unavailable."

forecast_text = FALLBACK

try:
    r = requests.get(URL, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # NOAA often puts the forecast in <pre> or plain text; this is robust enough
    page_text = soup.get_text("\n")

    # Try to locate the block that starts with the zone name (AMZ726) and goes until the next AMZ7xx
    pattern = r"(AMZ726[\s\S]*?)(AMZ7\d{2}\b|$$)"
    m = re.search(pattern, page_text, re.IGNORECASE)
    if m:
        block = m.group(1)
        block = block.replace("feet", "ft")
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

        # Remove the first line if it's just the zone header
        if lines and lines[0].upper().startswith("AMZ726"):
            lines = lines[1:]

        # Simple segmenting into forecast periods by common labels
        periods = []
        current_label = None
        current_text = []

        def is_label(line: str) -> bool:
            return bool(re.match(
                r"^(REST OF TONIGHT|TONIGHT|TODAY|THIS AFTERNOON|MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)",
                line,
                re.IGNORECASE,
            ))

        for line in lines:
            if is_label(line):
                if current_label and current_text:
                    periods.append((current_label.upper(), " ".join(current_text)))
                current_label = line.strip()
                current_text = []
            else:
                if current_label:
                    current_text.append(line.strip())

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
            # Try to extract "Wave Detail:" if present
            wave_match = re.search(r"Wave Detail:\s*(.+?)(?=\.|$)", txt, re.IGNORECASE | re.DOTALL)
            if wave_match:
                detail = wave_match.group(1).strip()
                final_lines.append(f"{label}: {detail}")
            else:
                # Fallback to general seas if present
                seas_match = re.search(r"Seas\s*(\d+)\s*to\s*(\d+)\s*ft", txt, re.IGNORECASE)
                if seas_match:
                    final_lines.append(f"{label}: Seas {seas_match.group(1)}–{seas_match.group(2)} ft")
                else:
                    # Last-resort short text
                    short = txt.replace("\n", " ")
                    if len(short) > 90:
                        short = short[:90] + "..."
                    final_lines.append(f"{label}: {short}")

        if final_lines:
            forecast_text = "\n".join(final_lines)

except Exception as e:
    print("DEBUG: PART 1 error:", e)

print("DEBUG: Finished PART 1")
print("DEBUG: Forecast text preview:", forecast_text.splitlines()[0] if forecast_text else "EMPTY")

print("DEBUG: Starting PART 2")

# ─────────────────────────────────────────────────────────────
# PART 2: Fetch Current Buoy 41043 Data
#   1) Try spectral file 41043.data_spec (WVHT + SwH + SwP + SwD)
#   2) Fallback to realtime2 41043.txt (WVHT + DPD + MWD)
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

def m_to_ft(m):
    try:
        return round(float(m) * 3.28084, 1)
    except Exception:
        return None

# First: try spectral data
try:
    url_spec = "https://www.ndbc.noaa.gov/data/spec/41043.data_spec"
    r_spec = requests.get(url_spec, timeout=15)
    r_spec.raise_for_status()

    lines = r_spec.text.splitlines()

    header = None
    rows = []

    for ln in lines:
        if ln.startswith("#YY"):
            header = ln.lstrip("#").split()
            continue

        if header and ln.strip() and not ln.startswith("#"):
            parts = ln.split()
            if len(parts) < len(header):
                continue
            rows.append(parts)

    if header and rows:
        parsed = []

        for parts in rows:
            row = {header[i]: parts[i] for i in range(len(header))}
            try:
                ts = datetime(
                    int(row.get("YY", "0")),
                    int(row.get("MM", "0")),
                    int(row.get("DD", "0")),
                    int(row.get("hh", "0")),
                    int(row.get("mm", "0"))
                )
                parsed.append((ts, row))
            except Exception:
                continue

        parsed.sort(key=lambda x: x[0], reverse=True)

        if parsed:
            latest = parsed[0][1]

            wvht = latest.get("WVHT")  # m
            swh  = latest.get("SwH")   # m
            swp  = latest.get("SwP")   # s
            swd  = latest.get("SwD")   # deg

            # Significant height
            if wvht and wvht not in ["MM", "99.00"]:
                h_ft = m_to_ft(wvht)
                if h_ft is not None:
                    sig_height = f"{h_ft} ft"

            # Swell height
            if swh and swh not in ["MM", "99.00"]:
                swh_ft = m_to_ft(swh)
                if swh_ft is not None:
                    swell_height = f"{swh_ft} ft"
            elif sig_height != "N/A":
                # Fallback: use significant height if swell not provided
                swell_height = sig_height

            # Swell period
            if swp and swp not in ["MM", "99"]:
                swell_period = f"{swp} sec"

            # Swell direction
            if swd and swd not in ["MM", "999"]:
                buoy_dir = f"{swd}°"

    print("DEBUG: PART 2 used spectral data")

except Exception as e:
    print("DEBUG: PART 2 spectral error, will try realtime2:", e)

    # Fallback: realtime2 text file
    try:
        url_rt = "https://www.ndbc.noaa.gov/data/realtime2/41043.txt"
        r_rt = requests.get(url_rt, timeout=15)
        r_rt.raise_for_status()
        lines_rt = r_rt.text.splitlines()

        header_tokens = None
        data_line = None

        for ln in lines_rt:
            if ln.startswith("#YY"):
                header_tokens = ln.lstrip("#").split()
                continue
            if header_tokens and not ln.startswith("#") and ln.strip():
                data_line = ln
                break

        if header_tokens and data_line:
            parts = data_line.split()

            def idx(name):
                try:
                    return header_tokens.index(name)
                except ValueError:
                    return None

            i_wvht = idx("WVHT")
            i_dpd  = idx("DPD")
            i_mwd  = idx("MWD")

            wvht = parts[i_wvht] if i_wvht is not None and i_wvht < len(parts) else None
            dpd  = parts[i_dpd] if i_dpd is not None and i_dpd < len(parts) else None
            mwd  = parts[i_mwd] if i_mwd is not None and i_mwd < len(parts) else None

            if wvht and wvht not in ["MM", "99.00"]:
                h_ft = m_to_ft(wvht)
                if h_ft is not None:
                    sig_height = f"{h_ft} ft"
                    swell_height = sig_height

            if dpd and dpd not in ["MM", "99"]:
                swell_period = f"{dpd} sec"

            if mwd and mwd not in ["MM", "999"]:
                buoy_dir = f"{mwd}°"

        print("DEBUG: PART 2 used realtime2 fallback")

    except Exception as e2:
        print("DEBUG: PART 2 realtime2 error:", e2)

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
