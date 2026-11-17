"""Conservative, local recognition of row markers next to a decoded QR.

QR corners provide scale and orientation. Examine a small neighbourhood to either
side, rather than matching unrelated colours or illustrations elsewhere in a photo.
Unknown artwork is intentionally left unclassified for manual review.
"""
import math

import cv2
import numpy as np

ICONS = {"", "bulb", "switch", "plug", "sensor"}
SCALE = 128


def marker_patches(rgb, corners):
    source = np.float32(corners)
    for origin in (2.0, -1.25):
        target = np.float32([(origin * SCALE, .45 * SCALE),
                             ((origin + 1) * SCALE, .45 * SCALE),
                             ((origin + 1) * SCALE, 1.45 * SCALE),
                             (origin * SCALE, 1.45 * SCALE)])
        transform = cv2.getPerspectiveTransform(source, target)
        yield cv2.warpPerspective(rgb, transform, (224, 244),
                                  borderValue=(255, 255, 255))


def filled_colour(patch):
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    lab = cv2.cvtColor(patch, cv2.COLOR_RGB2LAB).astype(np.float32)
    paper = np.median(lab[gray >= np.percentile(gray, 65)], axis=0)
    difference = np.linalg.norm(lab - paper, axis=2)
    mask = ((difference > 18) &
            (gray < np.percentile(gray, 85) - 8)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    candidates = []
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, width, height = cv2.boundingRect(contour)
        area, perimeter = cv2.contourArea(contour), cv2.arcLength(contour, True)
        if not (SCALE * .5 < width < SCALE * 1.7 and SCALE * .5 < height < SCALE * 1.7):
            continue
        if x < 3 or y < 3 or x + width >= 221 or y + height >= 241:
            continue
        if not (.78 < width / height < 1.28) or not perimeter:
            continue
        circularity = 4 * math.pi * area / perimeter ** 2
        if circularity < .72:
            continue
        filled = np.zeros(mask.shape, np.uint8)
        cv2.drawContours(filled, [contour], -1, 255, -1)
        # A dark outlined icon can have a round contour too; require a filled disc.
        if np.mean(mask[filled > 0] > 0) < .8:
            continue
        interior = cv2.erode(filled, np.ones((9, 9), np.uint8)) > 0
        colour = np.median(patch[interior], axis=0)
        # Correct a warm lighting cast using the surrounding paper as neutral.
        white = np.median(patch[gray >= np.percentile(gray, 65)], axis=0)
        colour = np.clip(colour * white.mean() / np.maximum(white, 1), 0, 255)
        candidates.append((circularity, "#" + "".join(f"{int(c):02x}" for c in colour)))
    return max(candidates, default=(0, ""))[1]


def printed_icon(patch):
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    mask = (gray < np.percentile(gray, 85) * .65).astype(np.uint8) * 255
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return ""
    hierarchy = hierarchy[0]
    for index, contour in enumerate(contours):
        if hierarchy[index, 3] != -1:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if not (40 < width < 145 and 55 < height < 195 and area > 1500):
            continue
        if x < 6 or y < 6 or x + width >= 218 or y + height >= 238:
            continue
        holes = [i for i, h in enumerate(hierarchy) if h[3] == index]
        large_holes = [i for i in holes if .4 < cv2.contourArea(contours[i]) / area < .88]
        if not large_holes:
            continue
        # Bulb: rounded outline with a separate screw-base bar underneath.
        if .9 < height / width < 1.5:
            bars = []
            for other_index, other in enumerate(contours):
                if hierarchy[other_index, 3] != -1 or other_index == index:
                    continue
                bx, by, bw, bh = cv2.boundingRect(other)
                if (y + height <= by < y + height + width * .6 and
                        .2 * width < bw < .85 * width and 2 < bh < width * .25 and
                        abs(bx + bw / 2 - x - width / 2) < width * .2):
                    bars.append(other)
            if bars:
                return "bulb"
        # Switch/remote: tall capsule outline with a small inset button/indicator.
        if 1.45 < height / width < 2.6:
            for hole in large_holes:
                for child, relation in enumerate(hierarchy):
                    if relation[3] != hole:
                        continue
                    bx, by, bw, bh = cv2.boundingRect(contours[child])
                    if (.08 * width < bw < .4 * width and .65 < bw / max(bh, 1) < 1.5 and
                            abs(bx + bw / 2 - x - width / 2) < width * .2 and
                            (by < y + height * .4 or by > y + height * .6)):
                        return "switch"
    return ""


def detect_appearance(rgb, corners):
    matches = []
    for patch in marker_patches(rgb, corners):
        colour = filled_colour(patch)
        icon = "" if colour else printed_icon(patch)
        if colour or icon:
            matches.append({"color": colour, "icon": icon})
    result = {}
    for field in ("color", "icon"):
        values = {match[field] for match in matches if match[field]}
        # Conflicting suggestions for the same field are left for manual review.
        result[field] = values.pop() if len(values) == 1 else ""
    if any(result.values()):
        result["appearance_source"] = "label"
    return result
