from pydantic import BaseModel


class ImageItem(BaseModel):
    """이미지 1건의 매니페스트(프론트 직접 업로드 또는 zip staging 산출)."""
    original_filename: str             # 품번 토큰 매칭에 사용
    storage_path: str                  # 버킷 내 원본 경로
    thumbnail_path: str | None = None  # staging 등에서 서버 가공된 썸네일 경로(있으면 재가공 생략)


class AttachImagesRequest(BaseModel):
    job_id: str
    images: list[ImageItem]


class MatchRequest(BaseModel):
    image_id: str
    source_p_number: str     # 이 품번의 상품으로 수동 연결
