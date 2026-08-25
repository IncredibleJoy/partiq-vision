from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class PartDetection(BaseModel):
    part_name: str
    category: str
    material: str
    condition: str
    visible_part_no: str | None = None
    minute_details: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox
    source_image: str | None = None
    crop_url: str | None = None
    id: str | None = None


class VisionResult(BaseModel):
    vehicle_context: str
    detections: list[PartDetection]


class ImageSetValidation(BaseModel):
    is_automotive: bool
    same_object: bool
    uploaded_description: str
    validation_message: str


class BomItem(BaseModel):
    part_name: str
    category: str
    material: str
    condition_summary: str
    quantity: int
    best_confidence: float
    visible_part_nos: list[str]
    crop_urls: list[str]
    source_images: list[str]
    notes: str


class CostSheetItem(BaseModel):
    detected_part_name: str
    matched_part_name: str
    matched_sku: str
    category: str
    material: str
    supplier: str
    cluster_key: str
    quantity: int
    unit_cost: float
    total_cost: float
    currency: str
    stock_quantity: int
    match_confidence: float = Field(ge=0, le=1)
    fitment_notes: str
    consumables_required: list[str] = Field(default_factory=list)


class CostSheet(BaseModel):
    currency: str = "USD"
    items: list[CostSheetItem] = Field(default_factory=list)
    total_cost: float = 0


class TokenUsageItem(BaseModel):
    step: str
    model: str
    purpose: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class TokenUsageSummary(BaseModel):
    items: list[TokenUsageItem] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0


class PartRecommendation(BaseModel):
    part_name: str
    reason: str
    recommendation_type: str
    confidence: float = Field(ge=0, le=1)
    related_parts: list[str] = []


class AgentTrace(BaseModel):
    agent: str
    action: str
    status: str
    detail: str


class DetectionLabelUpdate(BaseModel):
    id: str
    part_name: str | None = None
    category: str | None = None
    material: str | None = None
    condition: str | None = None
    visible_part_no: str | None = None
    minute_details: str | None = None


class RefineJobRequest(BaseModel):
    updates: list[DetectionLabelUpdate]


class WarehousePart(BaseModel):
    sku: str
    part_name: str
    category: str
    vehicle_system: str
    material: str
    material_grade: str
    condition_baseline: str
    unit_cost: float
    currency: str
    stock_quantity: int
    reorder_level: int
    supplier: str
    cluster_key: str
    visible_part_nos: list[str]
    aliases: list[str]
    compatible_positions: list[str]
    minute_details: str
    included_subparts: list[str]
    consumables_required: list[str]
    fitment_notes: str


class WarehouseSearchResult(WarehousePart):
    similarity: float
    cluster_size: int


class JobResponse(BaseModel):
    job_id: str
    model_mode: str
    vehicle_context: str
    detections: list[PartDetection]
    bom: list[BomItem]
    cost_sheet: CostSheet = Field(default_factory=CostSheet)
    token_usage: TokenUsageSummary = Field(default_factory=TokenUsageSummary)
    recommendations: list[PartRecommendation] = []
    agent_trace: list[AgentTrace] = []
