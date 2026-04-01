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

        # ── 카메라 프로파일 (제조사별 실제 렌즈/펌웨어 세트) ──
        camera_profiles = [
            {
                "make": b"Samsung",
                "model": b"SM-S928B",
                "lens": b"Samsung 23mm F1.7",
                "firmware": b"S928BXXS3AXL1",
                "focal_length": (23, 1),
                "aperture": (17, 10),   # F1.7
                "iso_range": (50, 3200),
                "software": b"Samsung Camera 12.0.01.73",
            },
            {
                "make": b"Apple",
                "model": b"iPhone 15 Pro",
                "lens": b"iPhone 15 Pro back triple camera 6.765mm f/1.78",
                "firmware": b"17.3.1",
                "focal_length": (677, 100),
                "aperture": (178, 100),  # F1.78
                "iso_range": (32, 2500),
                "software": b"17.3.1",
            },
            {
                "make": b"Apple",
                "model": b"iPhone 16",
                "lens": b"iPhone 16 back dual wide camera 4.28mm f/1.6",
                "firmware": b"18.1.1",
                "focal_length": (428, 100),
                "aperture": (160, 100),  # F1.6
                "iso_range": (32, 2000),
                "software": b"18.1.1",
            },
        ]
        profile = random.choice(camera_profiles)

        # ── 가짜 촬영 시각 ──
        fake_date = datetime.now() - timedelta(days=random.randint(1, 30),
                                               hours=random.randint(0, 23),
                                               minutes=random.randint(0, 59))
        fake_datetime = fake_date.strftime("%Y:%m:%d %H:%M:%S").encode()

        # ── GPS (서울 근방 랜덤) ──
        lat = 37.5 + random.uniform(-0.05, 0.05)
        lon = 127.0 + random.uniform(-0.05, 0.05)
        alt = random.randint(10, 80)

        def to_dms(deg):
            d = int(deg)
            m = int((deg - d) * 60)
            s = round(((deg - d) * 60 - m) * 60 * 100)
            return ((d, 1), (m, 1), (s, 100))

        # ── 셔터스피드 / ISO / 노출 ──
        iso = random.randint(*profile["iso_range"])
        shutter_choices = [(1, 1000), (1, 500), (1, 250), (1, 120), (1, 60)]
        shutter = random.choice(shutter_choices)
        exposure_bias = (0, 1)  # 0 EV

        # ── EXIF 딕셔너리 조립 ──
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: profile["make"],
                piexif.ImageIFD.Model: profile["model"],
                piexif.ImageIFD.Software: profile["software"],
                piexif.ImageIFD.DateTime: fake_datetime,
                piexif.ImageIFD.XResolution: (72, 1),
                piexif.ImageIFD.YResolution: (72, 1),
                piexif.ImageIFD.ResolutionUnit: 2,  # inch
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: fake_datetime,
                piexif.ExifIFD.DateTimeDigitized: fake_datetime,
                piexif.ExifIFD.LensModel: profile["lens"],
                piexif.ExifIFD.FirmwareVersion: profile["firmware"],
                piexif.ExifIFD.FocalLength: profile["focal_length"],
                piexif.ExifIFD.FNumber: profile["aperture"],
                piexif.ExifIFD.ISOSpeedRatings: iso,
                piexif.ExifIFD.ExposureTime: shutter,
                piexif.ExifIFD.ExposureBiasValue: exposure_bias,
                piexif.ExifIFD.Flash: 0,             # 플래시 미사용
                piexif.ExifIFD.WhiteBalance: 0,      # 자동 화이트밸런스
                piexif.ExifIFD.MeteringMode: 2,      # 중앙 중점 측광
                piexif.ExifIFD.ColorSpace: 1,        # sRGB
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"N",
                piexif.GPSIFD.GPSLatitude: to_dms(lat),
                piexif.GPSIFD.GPSLongitudeRef: b"E",
                piexif.GPSIFD.GPSLongitude: to_dms(lon),
                piexif.GPSIFD.GPSAltitudeRef: 0,
                piexif.GPSIFD.GPSAltitude: (alt, 1),
            },
        }

        # ── SEO 파일명 + PNG→JPEG 변환 + EXIF 주입 ──
        safe_main = main_keyword.replace(" ", "-")
        safe_sub = sub_keyword.replace(" ", "-")
        new_filename = f"{safe_main}_{safe_sub}_{image_index}.jpg"
        output_dir = os.path.dirname(image_path)
        new_path = os.path.join(output_dir, new_filename)

        img = Image.open(image_path).convert("RGB")
        exif_bytes = piexif.dump(exif_dict)
        img.save(new_path, "JPEG", quality=92, exif=exif_bytes)

        return new_path
