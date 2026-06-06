import io

from PIL import Image

from app.services.image_process import process_image_bytes, thumb_path


def _jpeg(w, h, orientation=None) -> bytes:
    img = Image.new("RGB", (w, h), (200, 50, 50))
    buf = io.BytesIO()
    if orientation is not None:
        exif = img.getexif()
        exif[0x0112] = orientation        # EXIF Orientation 태그
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


def test_exif_orientation_is_corrected():
    # 세로(60x100) 저장 + orientation=6(90° 회전 필요) → 정면 보정 후 가로로 스왑돼야 함
    raw = _jpeg(60, 100, orientation=6)
    out = process_image_bytes(raw)
    assert out.status == "ok"
    assert out.width > out.height            # 보정으로 가로 방향이 됨(치수 스왑)


def test_no_exif_keeps_orientation():
    raw = _jpeg(60, 100)                      # orientation 없음 → 세로 유지
    out = process_image_bytes(raw)
    assert out.status == "ok"
    assert (out.width, out.height) == (60, 100)


def test_thumbnail_caps_long_edge_and_keeps_ratio():
    raw = _jpeg(2000, 1000)                   # 상한(800) 초과 → 비율 유지 축소
    out = process_image_bytes(raw, box=(800, 800))
    assert out.status == "ok"
    assert max(out.width, out.height) == 800
    assert (out.width, out.height) == (800, 400)


def test_no_upscale_for_small_image():
    raw = _jpeg(120, 80)                      # 박스보다 작으면 확대 안 함
    out = process_image_bytes(raw, box=(800, 800))
    assert (out.width, out.height) == (120, 80)


def test_broken_bytes_returns_error_not_raise():
    out = process_image_bytes(b"\x00\x01 this is not an image \xff")
    assert out.status == "error"             # 예외 전파 없이 상태로 보고
    assert out.data is None


def test_output_is_jpeg():
    out = process_image_bytes(_jpeg(300, 300))
    assert out.data[:2] == b"\xff\xd8"       # JPEG SOI 매직


def test_thumb_path_normalizes_extension():
    assert thumb_path("w1/1001_front.png") == "thumbs/w1/1001_front.jpg"
    assert thumb_path("w1/1001.jpg") == "thumbs/w1/1001.jpg"
    assert thumb_path("w1/noext") == "thumbs/w1/noext.jpg"
