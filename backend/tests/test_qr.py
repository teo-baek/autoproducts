from app.services.qr import qr_target_url, generate_qr_png

def test_qr_target_url():
    # 정적 export 프론트 → ?code= 쿼리 형식
    assert qr_target_url("EZM-000001", "https://shop.ezmerce.io") == "https://shop.ezmerce.io/p?code=EZM-000001"

def test_generate_qr_png_returns_png_bytes():
    data = generate_qr_png("https://x/p/EZM-1")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 시그니처
