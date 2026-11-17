"""Turn local OCR words into conservative, spatially matched identity suggestions."""
import re
from collections import defaultdict

BRANDS = {
    "IKEA": ("IKEA", "1KEA", "LKEA"),
    "Philips Hue": ("PHILIPS HUE",),
    "Philips": ("PHILIPS",),
    "Aqara": ("AQARA",),
    "Eve": ("EVE",),
    "Nanoleaf": ("NANOLEAF",),
    "Shelly": ("SHELLY",),
    "Tapo": ("TAPO",),
    "TP-Link": ("TP-LINK", "TP LINK"),
    "Meross": ("MEROSS",),
    "SONOFF": ("SONOFF",),
    "SwitchBot": ("SWITCHBOT", "SWITCH BOT"),
}
NOISE = re.compile(
    r"\b(?:matter|copyright|systems|sweden|design|quality|command|option|shift|control|"
    r"keyboard|warning|caution|instructions|manual|pairing|scan|code|voltage|watt|"
    r"manufactured|made in|www|https?|serial|model no|article no|inter)\b|©|^AA-", re.I
)


def ocr_lines(data):
    groups = defaultdict(list)
    for i, value in enumerate(data.get("text", [])):
        word = value.strip()
        if not word:
            continue
        confidence = float(data["conf"][i])
        key = tuple(data[field][i] for field in ("block_num", "par_num", "line_num"))
        groups[key].append({"text": word, "confidence": confidence,
                            "x": int(data["left"][i]), "y": int(data["top"][i]),
                            "w": int(data["width"][i]), "h": int(data["height"][i])})
    lines = []
    for words in groups.values():
        words.sort(key=lambda word: word["x"])
        left, top = min(w["x"] for w in words), min(w["y"] for w in words)
        lines.append({"text": " ".join(w["text"] for w in words), "words": words,
                      "confidence": sum(w["confidence"] * len(w["text"]) for w in words) /
                                    sum(len(w["text"]) for w in words),
                      "x": left, "y": top,
                      "w": max(w["x"] + w["w"] for w in words) - left,
                      "h": max(w["y"] + w["h"] for w in words) - top})
    return lines


def recognise_identity(lines, codes, image_size):
    """Return editable suggestions. A heading must align with its QR's column."""
    brands = []
    for line in lines:
        text = " ".join(w["text"] for w in line["words"] if w["confidence"] >= 45).upper()
        for brand, aliases in BRANDS.items():
            if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text) for alias in aliases):
                if brand not in brands:
                    brands.append(brand)
    if "Philips Hue" in brands:
        brands = [brand for brand in brands if brand != "Philips"]
    candidates = []
    for line in lines:
        text = line["text"].strip(" ~|:;,.®™•-_—–")
        if line["confidence"] < 65 or NOISE.search(text) or not 3 <= len(text) <= 100:
            continue
        if sum(c.isalpha() for c in text) / max(len(text), 1) < .65:
            continue
        if re.search(r"[^\w\s+&/().\-]", text) or line["h"] < 10:
            continue
        # A product must be readable text, rather than isolated OCR fragments.
        words = text.split()
        if not any(len(word) >= 4 for word in words):
            continue
        if len(words) == 1 and not (text.isupper() or text.istitle()):
            continue
        if text.upper() in {alias for aliases in BRANDS.values() for alias in aliases}:
            continue
        for brand, aliases in BRANDS.items():
            for alias in sorted(aliases, key=len, reverse=True):
                text = re.sub(r"^" + re.escape(alias) + r"\s+", "", text, flags=re.I)
        # This heading is often split into separate words by Tesseract.
        compact = re.sub(r"\s+", "", text).upper()
        if compact in ("KAJPLATS", "KAJPLATSKIT"):
            text = "KAJPLATS KIT" if compact.endswith("KIT") else "KAJPLATS"
        if len(text) >= 3:
            candidates.append({**line, "text": text})
    # Headings carry the most useful product signal; discard small background text.
    if candidates:
        largest = max(line["h"] for line in candidates)
        candidates = [line for line in candidates if line["h"] >= largest * .45]
    candidates.sort(key=lambda line: (-line["h"], -line["confidence"]))
    products = list(dict.fromkeys(line["text"] for line in candidates))[:6]
    default_brand = brands[0] if len(brands) == 1 else ""
    default_product = products[0] if len(products) == 1 else ""
    for code in codes:
        bounds = code.pop("_bounds", None)
        matches = []
        if bounds:
            x, y, width, height = bounds
            for line in candidates:
                gap = y - (line["y"] + line["h"])
                aligned = line["x"] - width * .15 <= x + width / 2 <= line["x"] + line["w"] + width * .15
                if aligned and -height * .1 <= gap <= min(height * 5, image_size[1] * .35):
                    matches.append((max(0, gap) / max(height, 1), line["text"]))
        code["brand"] = default_brand
        code["product"] = min(matches)[1] if matches else default_product
        if code["brand"] or code["product"]:
            code["identity_source"] = "label"
    return {"brands": brands, "products": products, "brand": default_brand, "product": default_product}
