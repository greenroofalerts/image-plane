"""Minimal PDF writer. Pillow + stdlib only. Images keep aspect ratio."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

PAGE_W = 595
PAGE_H = 842
MARGIN = 48


def _escape(text: str) -> bytes:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", "replace")
    )


def _wrap(text: str, width: int = 88) -> list[str]:
    lines = []
    for raw in (text or "").splitlines() or [""]:
        words = raw.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            if len(cur) + 1 + len(w) <= width:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines[:80]


def _jpeg_bytes(path: Path, max_w: int = 480, max_h: int = 320) -> tuple[bytes, int, int] | None:
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue(), img.size[0], img.size[1]
    except Exception:
        return None


def write_pdf(path: Path, pages: list[dict]) -> Path:
    """Write a simple multi-page PDF.

    Each page dict may have: title, lines (list[str]), image (Path), footer.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    objects: list[bytes] = []

    def add(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    page_ids = []
    for page in pages:
        content_ops = []
        y = PAGE_H - MARGIN
        title = page.get("title") or ""
        if title:
            content_ops.append(f"BT /F1 14 Tf {MARGIN} {y} Td ({_escape(title).decode('latin-1')}) Tj ET")
            y -= 22
        for line in _wrap("\n".join(page.get("lines") or []), 92):
            if y < 80:
                break
            content_ops.append(f"BT /F1 10 Tf {MARGIN} {y} Td ({_escape(line).decode('latin-1')}) Tj ET")
            y -= 13
        img_obj = None
        img_w = img_h = 0
        img_path = page.get("image")
        if img_path:
            packed = _jpeg_bytes(Path(img_path))
            if packed:
                data, img_w, img_h = packed
                img_obj = add(
                    b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                    b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                    b"/Length %d >>\nstream\n" % (img_w, img_h, len(data))
                    + data
                    + b"\nendstream"
                )
                y -= 16
                draw_h = img_h * 72 / 96
                draw_w = img_w * 72 / 96
                max_draw_w = PAGE_W - 2 * MARGIN
                if draw_w > max_draw_w:
                    scale = max_draw_w / draw_w
                    draw_w *= scale
                    draw_h *= scale
                y_img = max(MARGIN + 24, y - draw_h)
                content_ops.append(
                    f"q {draw_w:.2f} 0 0 {draw_h:.2f} {MARGIN} {y_img:.2f} cm /Im1 Do Q"
                )
        footer = page.get("footer")
        if footer:
            content_ops.append(
                f"BT /F1 8 Tf {MARGIN} 28 Td ({_escape(footer).decode('latin-1')}) Tj ET"
            )
        stream = ("\n".join(content_ops) + "\n").encode("latin-1")
        contents_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
        page_ids.append((contents_id, img_obj))

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for contents_id, img_obj in page_ids:
        if img_obj:
            res = (
                "<< /Font << /F1 {font} 0 R >> /XObject << /Im1 {img} 0 R >> >>"
            ).format(font=font_id, img=img_obj)
        else:
            res = "<< /Font << /F1 {font} 0 R >> >>".format(font=font_id)
        pid = add(
            (
                "<< /Type /Page /Parent __PAGES__ 0 R /MediaBox [0 0 {w} {h}] "
                "/Contents {c} 0 R /Resources {res} >>"
            ).format(w=PAGE_W, h=PAGE_H, c=contents_id, res=res).encode("latin-1")
        )
        kids.append(pid)
    pages_id = add(
        (
            "<< /Type /Pages /Count %d /Kids [%s] >>"
            % (len(kids), " ".join(f"{k} 0 R" for k in kids))
        ).encode("latin-1")
    )
    # patch parent refs
    for i, kid in enumerate(kids):
        objects[kid - 1] = objects[kid - 1].replace(b"__PAGES__", str(pages_id).encode("ascii"))
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(buf.tell())
        buf.write(f"{i} 0 obj\n".encode("ascii"))
        buf.write(obj)
        buf.write(b"\nendobj\n")
    xref = buf.tell()
    buf.write(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.write(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.write(
        f"trailer << /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(buf.getvalue())
    return path
