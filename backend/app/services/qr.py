import io
import qrcode


def qr_target_url(platform_code: str, base_url: str) -> str:
    # 프론트 공개 카드 페이지. 정적 export(서버 없음)라 동적 경로 대신 ?code= 쿼리로 전달.
    return f"{base_url.rstrip('/')}/p?code={platform_code}"


def generate_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
