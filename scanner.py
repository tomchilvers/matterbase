"""Local QR and text recognition. No images are persisted or sent off-server."""
import re
import shutil
import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
import pytesseract
import zxingcpp
import numpy as np
from matter import parse_code, format_code
from label_features import detect_appearance
from text_recognition import ocr_lines, recognise_identity

Image.MAX_IMAGE_PIXELS = 30_000_000

def extract_text_codes(text):
    found = []
    for match in re.finditer(r"(?<!\d)(?:\d{4}[\s\-–—·:]+\d{3}[\s\-–—·:]+\d{4}|\d{11}|\d{21})(?!\d)", text):
        value = re.sub(r"\D", "", match.group())
        try:
            found.append({**parse_code(value), "source": "text"})
        except ValueError:
            continue
    return found

def scan_image(content, with_text=True):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = ImageOps.exif_transpose(Image.open(BytesIO(content)))
            image.load()
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Choose a supported JPG, PNG, or WebP image under 30 megapixels.") from None
    image.thumbnail((3200, 3200))
    codes, ignored = {}, 0
    # Decode the whole image, then overlapping tiles to find small labels in wide photos.
    views = [(image, 0, 0)]
    rgb = np.asarray(image)
    if with_text:
        w, h = image.size
        for y in (0, h // 3):
            for x in (0, w // 3):
                views.append((image.crop((x, y, min(w, x + w * 2 // 3), min(h, y + h * 2 // 3))), x, y))
    seen_payloads = set()
    for view, offset_x, offset_y in views:
        for barcode in zxingcpp.read_barcodes(view, formats=zxingcpp.BarcodeFormat.QRCode):
            if barcode.text in seen_payloads:
                continue
            seen_payloads.add(barcode.text)
            if not barcode.text.upper().startswith("MT:"):
                ignored += 1
                continue
            position = barcode.position
            corners = [(point.x + offset_x, point.y + offset_y) for point in
                       (position.top_left, position.top_right, position.bottom_right, position.bottom_left)]
            appearance = detect_appearance(rgb, corners)
            xs, ys = [p[0] for p in corners], [p[1] for p in corners]
            bounds = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
            # Matter labels can contain concatenated onboarding payloads.
            for payload in barcode.text.split("*"):
                try:
                    parsed = parse_code(payload if payload.upper().startswith("MT:") else "MT:" + payload)
                    codes[parsed["manual_code"]] = {**parsed, **appearance, "_bounds": bounds, "source": "qr"}
                except ValueError:
                    ignored += 1
    text, notice, lines = "", "", []
    if with_text:
        if shutil.which("tesseract"):
            try:
                data = pytesseract.image_to_data(image, config="--psm 11", timeout=25,
                                                 output_type=pytesseract.Output.DICT)
                lines = ocr_lines(data)
                initial = recognise_identity(lines, [], image.size)
                # Sparse mode can fragment a large heading or miss a logo. A
                # contrast-enhanced page pass provides a second local reading.
                if not initial["brand"] or not initial["products"]:
                    enhanced = ImageOps.autocontrast(ImageOps.grayscale(image))
                    scale = min(2, 2400 / max(image.size))
                    if scale > 1:
                        enhanced = enhanced.resize(tuple(round(n * scale) for n in image.size), Image.Resampling.LANCZOS)
                    else:
                        scale = 1
                    try:
                        fallback = ocr_lines(pytesseract.image_to_data(enhanced, config="--psm 3", timeout=20,
                                                                    output_type=pytesseract.Output.DICT))
                        for line in fallback:
                            for key in ("x", "y", "w", "h"):
                                line[key] = round(line[key] / scale)
                        # Retain confident alternatives without repeating the same
                        # line from both passes in the original-text review.
                        seen = {line["text"].casefold() for line in lines}
                        for line in fallback:
                            if line["text"].casefold() not in seen:
                                lines.append(line)
                                seen.add(line["text"].casefold())
                    except (RuntimeError, pytesseract.TesseractError):
                        notice = "Extra text recognition failed. Review the available results or enter missing details."
                text = "\n".join(line["text"] for line in lines)
                for code in extract_text_codes(text):
                    codes.setdefault(code["manual_code"], code)
            except (RuntimeError, pytesseract.TesseractError):
                notice = "Text recognition timed out or failed. QR results are available; enter product details manually."
        else:
            notice = "Text recognition requires Tesseract (included in the Docker image)."
    for code in codes.values():
        code["display_code"] = format_code(code["manual_code"])
    identity = recognise_identity(lines, codes.values(), image.size)
    return {"codes": list(codes.values()), "text": text, "suggestions": identity["products"], "identity": identity,
            "ignored": ignored, "notice": notice}
