import os
import time
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class GeminiImageInput(BaseModel):
    prompt: str = Field(..., description="이미지 생성 프롬프트 (영어로 작성)")
    image_index: int = Field(..., description="이미지 번호 (1부터 시작)")
    main_keyword: str = Field(..., description="SEO 파일명에 쓸 메인 키워드 (한국어)")
    sub_keyword: str = Field(..., description="SEO 파일명에 쓸 서브 키워드 (한국어)")


class GeminiImageGeneratorTool(BaseTool):
    name: str = "imagen4_generate"
    description: str = (
        "Google Imagen 4로 블로그용 이미지를 생성하고 SEO 파일명(.jpg)으로 저장한다. "
        "프롬프트는 영어로 작성한다."
    )
    args_schema: type = GeminiImageInput

    def _run(self, prompt: str, image_index: int, main_keyword: str, sub_keyword: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return "오류: google-genai 라이브러리가 설치되지 않았습니다. pip install google-genai"

        try:
            from PIL import Image
        except ImportError:
            return "오류: Pillow 라이브러리가 설치되지 않았습니다. pip install pillow"

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return "오류: GOOGLE_API_KEY 환경변수가 없습니다."

        full_prompt = (
            f"{prompt}. "
            "Do not include any letters, characters, hanja, korean text, "
            "numbers, words, or writing of any kind in the image."
        )

        # SEO 파일명 생성 (공백 → 하이픈)
        main_slug = main_keyword.replace(" ", "-")
        sub_slug = sub_keyword.replace(" ", "-")
        seo_filename = f"{main_slug}_{sub_slug}_{image_index}.jpg"

        os.makedirs("output/images", exist_ok=True)
        tmp_path = f"output/images/tmp_{image_index}.png"
        final_path = f"output/images/{seo_filename}"

        client = genai.Client(api_key=api_key)

        for attempt in range(3):
            try:
                response = client.models.generate_images(
                    model="imagen-4.0-generate-001",
                    prompt=full_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1",
                        safety_filter_level="block_low_and_above",
                    ),
                )

                response.generated_images[0].image.save(tmp_path)

                # PNG → JPEG 변환
                img = Image.open(tmp_path).convert("RGB")
                img.save(final_path, "JPEG", quality=92)
                os.remove(tmp_path)

                return final_path

            except Exception as e:
                if attempt == 2:
                    return f"이미지 생성 오류: {str(e)}"
                time.sleep(3)

        return "이미지 생성 실패"
