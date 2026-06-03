from app.services.platform_code import format_platform_code

def test_format_zero_pads_with_prefix():
    assert format_platform_code(1, prefix="EZM") == "EZM-000001"
    assert format_platform_code(123456, prefix="EZM") == "EZM-123456"

def test_format_overflow_keeps_full_number():
    assert format_platform_code(12345678, prefix="EZM") == "EZM-12345678"
