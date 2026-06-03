import io
import qrcode


def qr_target_url(platform_code: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}/p/{platform_code}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
