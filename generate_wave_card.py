#!/usr/bin/env python3
import sys

def main():
    try:
        import requests
        import re
        from bs4 import BeautifulSoup
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
        import io
        from datetime import datetime
    except Exception as e:
        print(f"IMPORT ERROR: {e}")
        return

    # ─────────────────────────────────────────────────────────────
    # PART 1: Forecast (SAFE)
    # ─────────────────────────────────────────────────────────────
    URL = "https://www.ndbc.noaa.gov/data/Forecasts/FZCA52.TJSJ.html"
    ZONE = "AMZ726"
    forecast_text = "Wave forecast temporarily unavailable."

    try:
        r = requests.get(URL, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text("\n")

        m = re.search(rf"({ZONE}.*?)(AMZ\d{{3}}|$)", text, re.S)
        if m:
            lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
            out = []
            label = None
            for l in lines:
                if re.match(r"^(REST|TODAY|TONIGHT|MON|TUE|WED|THU|FRI|SAT|SUN)", l):
                    label = l
                elif "ft" in l and label:
                    m2 = re.search(r"(\d+)\s*ft.*?(\d+)\s*sec", l, re.I)
                    if m2:
                        h, p = int(m2.group(1)), m2.group(2)
                        out.append(f"{label}: {h-1}–{h+1} ft @ {p}s")
            if out:
                out[0] = out[0].replace("REST OF TONIGHT", "Currently")
                forecast_text = "\n".join(out[:6])
    except Exception as e:
        print(f"Forecast error: {e}")

    # ─────────────────────────────────────────────────────────────
    # PART 2: Buoy 41043 (REALTIME)
    # ─────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────
# FIXED Buoy 41043 parsing – matches current table as of Dec 28 2025
# ─────────────────────────────────────────────────────────────
sig_height = swell_height = swell_period = buoy_dir = "N/A"

try:
    buoy_url = "https://www.ndbc.noaa.gov/station_page.php?station=41043"
    buoy_r = requests.get(buoy_url, timeout=15)
    buoy_r.raise_for_status()
    buoy_soup = BeautifulSoup(buoy_r.text, "html.parser")

    # Find wave table by searching for 'WVHT' in content
    table = None
    for tbl in buoy_soup.find_all("table"):
        if "WVHT" in tbl.get_text():
            table = tbl
            break

    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:  # header + data rows
            # Most recent observation = first data row (index 1)
            cols = rows[1].find_all("td")
            if len(cols) >= 5:
                # Correct indices (0-based):
                wvht = cols[1].get_text(strip=True)  # WVHT ft
                swh  = cols[2].get_text(strip=True)  # SwH ft
                swp  = cols[3].get_text(strip=True)  # SwP sec
                swd  = cols[4].get_text(strip=True)  # SwD

                if wvht and wvht not in ["MM", "-", ""]: 
                    sig_height = f"{wvht} ft"
                if swh and swh not in ["MM", "-", ""]: 
                    swell_height = f"{swh} ft"
                if swp and swp not in ["MM", "-", ""]: 
                    swell_period = f"{swp} sec"
                if swd and swd not in ["MM", "-", ""]: 
                    buoy_dir = swd
except Exception:
    pass  # Keep N/A on failure

    # ─────────────────────────────────────────────────────────────
    # PART 3: IMAGE (NEVER FAIL)
    # ─────────────────────────────────────────────────────────────
    try:
        bg = Image.new("RGB", (800, 950), "#003366")
        draw = ImageDraw.Draw(bg)

        try:
            f_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
            f_med = ImageFont.truetype("DejaVuSans.ttf", 28)
            f_sm  = ImageFont.truetype("DejaVuSans.ttf", 22)
        except:
            f_big = f_med = f_sm = ImageFont.load_default()

        draw.text((400, 80), datetime.now().strftime("%b %d, %Y"),
                  anchor="mm", fill="white", font=f_big)
        draw.text((400, 150), "Wave Forecast – AMZ726",
                  anchor="mm", fill="white", font=f_big)

        draw.multiline_text((80, 220), forecast_text,
                            fill="white", font=f_med, spacing=8)

        draw.rectangle([(60, 700), (740, 780)], fill="#001a33")
        draw.text((80, 715), "Current – Buoy 41043",
                  fill="white", font=f_sm)
        draw.text((80, 745),
                  f"Sig: {sig_height} | Swell: {swell_height} | {swell_period} | {buoy_dir}",
                  fill="#a0d0ff", font=f_sm)

        bg.save("wave_card.png", optimize=True)
        print("wave_card.png generated")

    except Exception as e:
        print(f"Image error: {e}")

if __name__ == "__main__":
    main()
    sys.exit(0)
