import os
import time
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class GeminiImageInput(BaseModel):
    prompt: str = Field(..., description="이미지 생성 프롬프트 (영어로 작성)")
    image_index: int = Field(..., description="이미지 번호 (1부터 시작)")


class GeminiImageGeneratorTool(BaseTool):
    name: str = "imagen4_generate"
    description: str = "Google Imagen 4로 블로그용 이미지를 생성하고 로컬에 저장한다. 프롬프트는 영어로 작성한다."
    args_schema: type = GeminiImageInput

    def _run(self, prompt: str, image_index: int) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return "오류: google-genai 라이브러리가 설치되지 않았습니다. pip install google-genai"

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return "오류: GOOGLE_API_KEY 환경변수가 없습니다."

        full_prompt = (
            f"{prompt}. "
            "Do not include any letters, characters, hanja, korean text, "
            "numbers, words, or writing of any kind in the image."
        )

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

                os.makedirs("output/images", exist_ok=True)
                path = f"output/images/img_{image_index}.png"
                response.generated_images[0].image.save(path)
                return path

            except Exception as e:
                if attempt == 2:
                    return f"이미지 생성 오류: {str(e)}"
                time.sleep(3)

        return "이미지 생성 실패"
