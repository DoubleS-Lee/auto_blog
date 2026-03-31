from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SajuDataInput(BaseModel):
    year: int = Field(..., description="태어난 연도 (예: 1990)")
    month: int = Field(..., description="태어난 월 (1~12)")
    day: int = Field(..., description="태어난 일 (1~31)")
    hour: int = Field(..., description="태어난 시 (0~23)")
    minute: int = Field(default=0, description="태어난 분 (0~59)")
    gender: str = Field(default="male", description="성별 (male / female)")


class SajuDataTool(BaseTool):
    name: str = "saju_data_calculator"
    description: str = (
        "생년월일시를 입력받아 사주팔자(년주/월주/일주/시주)와 오행 구성을 계산한다. "
        "서울 기준 진태양시 보정이 자동 적용된다. "
        "LLM이 직접 계산하지 말고 반드시 이 툴을 사용할 것."
    )
    args_schema: type = SajuDataInput

    def _run(self, year: int, month: int, day: int, hour: int, minute: int = 0, gender: str = "male") -> str:
        try:
            from sajupy import Saju

            saju = Saju(year, month, day, hour, minute, gender, city="Seoul")

            year_pillar = f"{saju.year_heavenly_stem}{saju.year_earthly_branch}"
            month_pillar = f"{saju.month_heavenly_stem}{saju.month_earthly_branch}"
            day_pillar = f"{saju.day_heavenly_stem}{saju.day_earthly_branch}"
            hour_pillar = f"{saju.hour_heavenly_stem}{saju.hour_earthly_branch}"

            result_lines = [
                f"[사주팔자]",
                f"년주(年柱): {year_pillar}",
                f"월주(月柱): {month_pillar}",
                f"일주(日柱): {day_pillar}",
                f"시주(時柱): {hour_pillar}",
            ]

            if hasattr(saju, 'five_elements'):
                result_lines.append(f"\n[오행 구성]")
                result_lines.append(str(saju.five_elements))

            return "\n".join(result_lines)

        except ImportError:
            return "오류: sajupy 라이브러리가 설치되지 않았습니다. pip install sajupy"
        except Exception as e:
            return f"사주 계산 오류: {str(e)}"
