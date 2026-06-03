from app.services.image_match import match_filename_to_product

def test_match_by_source_p_number():
    products = {"1001": "p1", "1002": "p2"}
    assert match_filename_to_product("1001.jpg", products) == "p1"
    assert match_filename_to_product("1001_main.png", products) == "p1"

def test_no_match_returns_none():
    assert match_filename_to_product("zzz.jpg", {"1001": "p1"}) is None
