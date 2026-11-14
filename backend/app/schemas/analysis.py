from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    """Schema dasar dengan konfigurasi camelCase untuk frontend."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AnalyzeResponse(BaseSchema):
    """Respons setelah mengunggah audio untuk dianalisis."""
    job_id: str = Field(..., description="ID unik antrean pekerjaan analisis")


class JobStatusResponse(BaseSchema):
    """Respons status pekerjaan analisis."""
    job_id: str
    status: str = Field(..., description="uploading, transcribing, analyzing, done, atau failed")
    progress: int = Field(..., ge=0, le=100, description="Persentase kemajuan analisis (0-100)")
    error_message: Optional[str] = None


class IndicatorItem(BaseSchema):
    """Item indikator yang terdeteksi."""
    code: str
    label: str
    weight: int
    quote: str


class TranscriptSegment(BaseSchema):
    """Segmen transkrip berstempel waktu."""
    start: float
    end: float
    text: str
    flagged: bool = False


class ResultResponse(BaseSchema):
    """Hasil analisis lengkap."""
    job_id: str
    label: str = Field(..., description="NORMAL, SUSPICIOUS, atau SCAM")
    scam_category: Optional[str] = None
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str = Field(..., description="Low, Medium, High, atau Critical")
    explanation: str
    indicators: List[IndicatorItem] = []
    transcript: List[TranscriptSegment] = []
    override_applied: Optional[bool] = False
