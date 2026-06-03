from pydantic import BaseModel


class ImageItem(BaseModel):
    """프론트가 product-images Storage 버킷에 업로드한 이미지 1건의 매니페스트."""
    original_filename: str   # 품번 토큰 매칭에 사용
    storage_path: str        # 버킷 내 경로(프론트가 직접 업로드 후 전달)


class AttachImagesRequest(BaseModel):
    job_id: str
    images: list[ImageItem]


class MatchRequest(BaseModel):
    image_id: str
    source_p_number: str     # 이 품번의 상품으로 수동 연결
