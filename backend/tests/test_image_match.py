from app.services.image_match import match_filename_to_product


def test_match_by_source_p_number():
    products = {"1001": "p1", "1002": "p2"}
    assert match_filename_to_product("1001.jpg", products) == "p1"
    assert match_filename_to_product("1001_main.png", products) == "p1"


def test_no_match_returns_none():
    assert match_filename_to_product("zzz.jpg", {"1001": "p1"}) is None


def test_strip_trailing_dot_zero():
    # 포스기/판다스가 붙인 '5015.0' 표기 → '5015' 로 매칭
    assert match_filename_to_product("5015.0.jpg", {"5015": "p1"}) == "p1"
    assert match_filename_to_product("5015.0.png", {"5015": "p1"}) == "p1"


def test_case_insensitive_fallback():
    # 정확 일치 실패 시 대소문자 무시 폴백
    assert match_filename_to_product("f-slk-001.jpg", {"F-SLK-001": "p1"}) == "p1"


def test_exact_match_wins_over_case_fallback():
    # 정확 일치가 있으면 그쪽을 — 대소문자 폴백보다 우선
    products = {"ABC": "p_upper", "abc": "p_lower"}
    assert match_filename_to_product("abc.jpg", products) == "p_lower"
    assert match_filename_to_product("ABC.jpg", products) == "p_upper"


def test_multitoken_filename():
    # '5015_blue.jpg' → 토큰 '5015' 로 매칭(전체 정규화 실패 후 토큰)
    assert match_filename_to_product("5015_blue.jpg", {"5015": "p1"}) == "p1"
    assert match_filename_to_product("5015-blue main.jpg", {"5015": "p1"}) == "p1"


def test_full_normalized_before_tokens():
    # 전체 정규화 문자열을 토큰보다 먼저 — 둘 다 키에 있으면 전체가 이김
    products = {"5015-blue": "p_full", "5015": "p_token"}
    assert match_filename_to_product("5015-blue.jpg", products) == "p_full"


def test_glued_numeric_via_digit_run():
    # 구분자 없이 글자+숫자가 붙은 경우('상품5015') → 숫자런 추출로 매칭
    assert match_filename_to_product("상품5015.jpg", {"5015": "p1"}) == "p1"
    assert match_filename_to_product("img20240501.jpg", {"20240501": "p1"}) == "p1"


def test_glued_alnum_via_bounded_substring():
    # 영숫자 품번이 글자에 붙은 경우('셔츠ABC123') → 경계 가드 부분일치
    assert match_filename_to_product("셔츠ABC123.jpg", {"ABC123": "p1"}) == "p1"


def test_no_false_short_substring():
    # '501' 이 '5015' 안에 우연히 들어가도 (뒤가 숫자) 매칭하지 않음
    assert match_filename_to_product("5015.jpg", {"501": "p1"}) is None
    assert match_filename_to_product("abcd.jpg", {"abc": "p1"}) is None


def test_substring_longest_wins():
    # 부분일치 후보가 여럿이면 가장 긴 품번을 택함
    products = {"abc": "p_short", "abc12": "p_long"}
    assert match_filename_to_product("셔츠abc12.jpg", products) == "p_long"
