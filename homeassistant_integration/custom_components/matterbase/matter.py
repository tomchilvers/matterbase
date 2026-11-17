"""Matter onboarding payloads. Bit layout follows project-chip/connectedhomeip.

https://github.com/project-chip/connectedhomeip/tree/master/src/setup_payload
"""
import re

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-."
D = (
    (0,1,2,3,4,5,6,7,8,9), (1,2,3,4,0,6,7,8,9,5),
    (2,3,4,0,1,7,8,9,5,6), (3,4,0,1,2,8,9,5,6,7),
    (4,0,1,2,3,9,5,6,7,8), (5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2), (7,6,5,9,8,2,1,0,4,3),
    (8,7,6,5,9,3,2,1,0,4), (9,8,7,6,5,4,3,2,1,0),
)
P = (
    (0,1,2,3,4,5,6,7,8,9), (1,5,7,6,2,8,3,0,9,4),
    (5,8,0,3,7,9,6,1,4,2), (8,9,1,6,0,4,3,5,2,7),
    (9,4,5,3,1,2,6,8,7,0), (4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5), (7,0,4,6,9,1,3,2,5,8),
)
INV = (0,4,3,2,1,5,6,7,8,9)

def checksum(code):
    c = 0
    for i, digit in enumerate(reversed(code)):
        c = D[c][P[(i + 1) % 8][int(digit)]]
    return str(INV[c])

def valid_pin(pin):
    return 1 <= pin <= 99999998 and pin not in {
        int(str(n) * 8) for n in range(1, 10)
    } | {12345678, 87654321}

def format_code(code):
    if len(code) == 11:
        return f"{code[:4]}-{code[4:7]}-{code[7:]}"
    return code

def parse_manual(value):
    code = re.sub(r"[\s\-–—]", "", value)
    if not re.fullmatch(r"(?:[0-9]{11}|[0-9]{21})", code):
        raise ValueError("Enter an 11-digit Matter code (XXXX-XXX-XXXX) or a 21-digit code.")
    if checksum(code[:-1]) != code[-1]:
        raise ValueError("The code’s check digit does not match. Please check the printed code.")
    first, second, third = int(code[0]), int(code[1:6]), int(code[6:10])
    if first > 7 or bool(first & 4) != (len(code) == 21) or second > 65535 or third > 8191:
        raise ValueError("This is not a valid Matter manual pairing code.")
    if len(code) == 21 and (int(code[10:15]) > 65535 or int(code[15:20]) > 65535):
        raise ValueError("Invalid vendor or product ID in Matter code.")
    if not valid_pin((second & 16383) | (third << 14)):
        raise ValueError("Invalid Matter setup PIN.")
    return {"manual_code": code, "qr_payload": "", "vendor_id": None, "product_id": None}

def parse_qr(value):
    value = value.strip().upper()
    if not value.startswith("MT:"):
        raise ValueError("Only Matter QR payloads beginning MT: are supported.")
    encoded = value[3:]
    if len(encoded) > 4096 or len(encoded) % 5 not in (0, 2, 4):
        raise ValueError("Invalid Matter QR payload length.")
    data = bytearray()
    try:
        for offset in range(0, len(encoded), 5):
            chunk = encoded[offset:offset+5]
            size = {2: 1, 4: 2, 5: 3}[len(chunk)]
            number = sum(ALPHABET.index(c) * 38 ** i for i, c in enumerate(chunk))
            data.extend(number.to_bytes(size, "little"))
    except (ValueError, OverflowError, KeyError):
        raise ValueError("Invalid Matter Base38 QR payload.") from None
    if len(data) < 11:
        raise ValueError("Matter QR payload is incomplete.")
    bits = int.from_bytes(data[:11], "little")
    version = bits & 7
    vendor, product = (bits >> 3) & 65535, (bits >> 19) & 65535
    flow = (bits >> 35) & 3
    discriminator, pin = (bits >> 45) & 4095, (bits >> 57) & ((1 << 27) - 1)
    if version != 0 or flow == 3 or bits >> 84 or not valid_pin(pin):
        raise ValueError("Unsupported or invalid Matter QR payload.")
    short = discriminator >> 8
    # Non-standard commissioning flows include vendor/product in the manual code.
    digits = f"{(short >> 2) | (4 if flow else 0)}{((short & 3) << 14) | (pin & 16383):05d}{pin >> 14:04d}"
    if flow:
        digits += f"{vendor:05d}{product:05d}"
    return {"manual_code": digits + checksum(digits), "qr_payload": value,
            "vendor_id": vendor, "product_id": product}

def parse_code(value):
    if not isinstance(value, str):
        raise ValueError("A pairing code is required.")
    return parse_qr(value) if value.strip().upper().startswith("MT:") else parse_manual(value)
