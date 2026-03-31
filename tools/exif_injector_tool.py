import os
import random
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


class ExifInput(BaseModel):
    image_path: str = Field(..., description="원본 이미지 경로")
    main_keyword: str = Field(..., description="메인 SEO 키워드")
    sub_keyword: str = Field(..., description="서브 SEO 키워드")
    image_index: int = Field(..., description="이미지 번호")


class ExifInjectorTool(BaseTool):
    name: str = "exif_inject_rename"
    description: str = "이미지에 가짜 촬영 EXIF 정보를 주입하고 SEO에 최적화된 파일명으로 변경한다."
    args_schema: type = ExifInput

    def _run(self, image_path: str, main_keyword: str, sub_keyword: str, image_index: int) -> str:
        try:
            import piexif
            from PIL import Image
        except ImportError:
            return "오류: piexif 또는 pillow 라이브러리가 설치되지 않았습니다."

        if not os.path.exists(image_path):
            return f"오류: 파일이 존재하지 않습니다 - {image_path}"

        fake_date = datetime.now() - timedelta(days=random.randint(1, 30))
        fake_datetime = fake_date.strftime("%Y:%m:%d %H:%M:%S").encode()

        camera_models = [
            (b"Samsung", b"SM-S928B"),
            (b"Apple", b"iPhone 15 Pro"),
            (b"Apple", b"iPhone 16"),
        ]
        make, model = random.choice(camera_models)

        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: make,
                piexif.ImageIFD.Model: model,
                piexif.ImageIFD.DateTime: fake_datetime,
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: fake_datetime,
                piexif.ExifIFD.DateTimeDigitized: fake_datetime,
            },
        }

        safe_main = main_keyword.replace(" ", "-")
        safe_sub = sub_keyword.replace(" ", "-")
        new_filename = f"{safe_main}_{safe_sub}_{image_index}.jpg"
        output_dir = os.path.dirname(image_path)
        new_path = os.path.join(output_dir, new_filename)

        img = Image.open(image_path).convert("RGB")
        exif_bytes = piexif.dump(exif_dict)
        img.save(new_path, "JPEG", quality=92, exif=exif_bytes)

        return new_path
