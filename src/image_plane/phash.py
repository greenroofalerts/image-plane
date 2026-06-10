"""Perceptual hashing, dependency-free (Pillow only).

dHash (difference hash): resize to 9x8 greyscale, compare horizontal
neighbours → 64-bit hash. Robust to re-encoding, resizing and mild
brightness shifts; sensitive to crops beyond a few percent. Hamming
distance <= threshold (default 8) is treated as a near-duplicate.
"""

from __future__ import annotations

from PIL import Image

HASH_BITS = 64


def dhash_hex(img: Image.Image) -> str:
    """64-bit dHash of an image as a 16-char hex string."""
    grey = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    px = grey.tobytes()  # L mode: one byte per pixel, row-major
    bits = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(hex_a: str, hex_b: str) -> int:
    return (int(hex_a, 16) ^ int(hex_b, 16)).bit_count()
