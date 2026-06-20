"""GCS 키리스 서명 자격증명 캐시(`_signing_kwargs`) 단위 테스트.

업로드 속도 최적화: 매 서명마다 `default()`+`refresh()` 하던 것을, ADC 자격증명을 모듈 캐시(`_signer`)로
재사용하고 토큰이 `not valid`(없음/만료, google-auth 는 실제 만료 3분45초 전 미리 invalid 처리)일 때만 refresh.
여기서 캐시 적중(= default() 1회만)·만료 시 refresh·SA 미설정 시 무동작을 검증한다. (실제 GCP 호출 없이 mock)
"""
from types import SimpleNamespace

import app.core.gcs as g


class FakeCreds:
    """google.auth Credentials 대역 — .valid/.refresh()/.token 만 흉내."""
    def __init__(self, valid=True, token="tok-1"):
        self._valid = valid
        self.token = token
        self.refresh_calls = 0

    @property
    def valid(self):
        return self._valid

    def refresh(self, _request):
        self.refresh_calls += 1
        self._valid = True
        self.token = "tok-refreshed"


def _patch_common(monkeypatch, sa="signer@proj.iam.gserviceaccount.com"):
    monkeypatch.setattr(g, "_signer", None)                              # 캐시 리셋(테스트 격리)
    monkeypatch.setattr(g, "_GoogleAuthRequest", lambda: object())       # refresh 인자(네트워크 없음)
    monkeypatch.setattr(g, "get_settings", lambda: SimpleNamespace(gcs_signing_sa=sa))


def test_signing_kwargs_caches_creds_and_refreshes_on_expiry(monkeypatch):
    _patch_common(monkeypatch)
    calls = {"default": 0}
    fake = FakeCreds(valid=True, token="tok-1")

    def fake_default(scopes=None):
        calls["default"] += 1
        return fake, "proj"

    monkeypatch.setattr(g, "_google_auth_default", fake_default)

    # 1회차: default() 1번, 토큰 valid → refresh 없음
    kw1 = g._signing_kwargs()
    assert kw1 == {"service_account_email": "signer@proj.iam.gserviceaccount.com", "access_token": "tok-1"}
    assert calls["default"] == 1 and fake.refresh_calls == 0

    # 2회차: 캐시 적중 → default() 재호출 X, 여전히 valid → refresh X (= 최적화 핵심)
    kw2 = g._signing_kwargs()
    assert kw2["access_token"] == "tok-1"
    assert calls["default"] == 1 and fake.refresh_calls == 0

    # 토큰 만료 → refresh 1회(여전히 default() 재호출은 없음, 캐시된 creds 객체에서 갱신)
    fake._valid = False
    kw3 = g._signing_kwargs()
    assert calls["default"] == 1 and fake.refresh_calls == 1
    assert kw3["access_token"] == "tok-refreshed"


def test_signing_kwargs_empty_and_untouched_when_sa_unset(monkeypatch):
    # SA 미설정(빈값) → {} 반환, ADC 자격증명은 절대 건드리지 않음(자격증명 자체 키 서명 경로).
    monkeypatch.setattr(g, "get_settings", lambda: SimpleNamespace(gcs_signing_sa=""))

    def boom(scopes=None):
        raise AssertionError("SA 미설정 시 default() 를 호출하면 안 됨")

    monkeypatch.setattr(g, "_google_auth_default", boom)
    assert g._signing_kwargs() == {}
