import base64
import json
from pathlib import Path

from openai import OpenAI, OpenAIError

from .config import settings
from .schemas import BoundingBox, ImageSetValidation, PartDetection, TokenUsageItem, VisionResult


PART_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "vehicle_context": {"type": "string"},
        "detections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "part_name": {"type": "string"},
                    "category": {"type": "string"},
                    "material": {"type": "string"},
                    "condition": {"type": "string"},
                    "visible_part_no": {"type": ["string", "null"]},
                    "minute_details": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "bbox": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "x": {"type": "number", "minimum": 0, "maximum": 1},
                            "y": {"type": "number", "minimum": 0, "maximum": 1},
                            "width": {"type": "number", "minimum": 0, "maximum": 1},
                            "height": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["x", "y", "width", "height"],
                    },
                },
                "required": [
                    "part_name",
                    "category",
                    "material",
                    "condition",
                    "visible_part_no",
                    "minute_details",
                    "confidence",
                    "bbox",
                ],
            },
        },
    },
    "required": ["vehicle_context", "detections"],
}

IMAGE_SET_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_automotive": {"type": "boolean"},
        "same_object": {"type": "boolean"},
        "uploaded_description": {"type": "string"},
        "validation_message": {"type": "string"},
    },
    "required": ["is_automotive", "same_object", "uploaded_description", "validation_message"],
}


def _image_data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def _mock_result(image_name: str) -> VisionResult:
    detections = [
        PartDetection(
            part_name="Front bumper cover",
            category="Exterior body",
            material="Painted PP/EPDM thermoplastic",
            condition="Visible scuffing possible; inspect clips and mounting tabs",
            visible_part_no=None,
            minute_details="Lower edge, fog lamp bezels, grille mating surface, and parking sensor holes should be verified.",
            confidence=0.91,
            bbox=BoundingBox(x=0.08, y=0.58, width=0.84, height=0.25),
        ),
        PartDetection(
            part_name="Radiator grille assembly",
            category="Cooling intake",
            material="ABS plastic with chrome or painted trim",
            condition="Visible front face; check cracks at latch-side tabs",
            visible_part_no=None,
            minute_details="Includes horizontal slats, emblem seat, and fastener points behind upper bumper line.",
            confidence=0.87,
            bbox=BoundingBox(x=0.28, y=0.34, width=0.44, height=0.2),
        ),
        PartDetection(
            part_name="Left headlamp assembly",
            category="Lighting",
            material="Polycarbonate lens, plastic housing, LED/halogen internals",
            condition="Lens visible; verify haze, broken lugs, and moisture ingress",
            visible_part_no=None,
            minute_details="Outer lens, DRL strip, reflector bowl, connector area, and bracket lugs are likely subcomponents.",
            confidence=0.84,
            bbox=BoundingBox(x=0.08, y=0.32, width=0.22, height=0.17),
        ),
        PartDetection(
            part_name="Right headlamp assembly",
            category="Lighting",
            material="Polycarbonate lens, plastic housing, LED/halogen internals",
            condition="Lens visible; verify haze, broken lugs, and moisture ingress",
            visible_part_no=None,
            minute_details="Outer lens, DRL strip, reflector bowl, connector area, and bracket lugs are likely subcomponents.",
            confidence=0.84,
            bbox=BoundingBox(x=0.70, y=0.32, width=0.22, height=0.17),
        ),
        PartDetection(
            part_name="Bonnet hood panel",
            category="Body panel",
            material="Stamped steel or aluminum depending on model",
            condition="Panel gap and leading edge visible; inspect dents and paint mismatch",
            visible_part_no=None,
            minute_details="Leading seam, latch striker zone, hinge alignment, and washer nozzle area need downstream fitment checks.",
            confidence=0.79,
            bbox=BoundingBox(x=0.16, y=0.08, width=0.68, height=0.24),
        ),
    ]
    return VisionResult(vehicle_context=f"Vehicle front view inferred from {image_name}", detections=detections)


def _usage_item(step: str, model: str, purpose: str, usage: object | None = None) -> TokenUsageItem:
    input_tokens = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens)
    return TokenUsageItem(
        step=step,
        model=model,
        purpose=purpose,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def validate_image_set(paths: list[Path]) -> tuple[ImageSetValidation, str, TokenUsageItem]:
    purpose = (
        "Pre-analysis upload validation: confirm images contain automotive parts and, for multi-image uploads, "
        "confirm they are different views/details of the same vehicle or automotive object."
    )
    if not settings.openai_api_key:
        return (
            ImageSetValidation(
                is_automotive=True,
                same_object=True,
                uploaded_description="Demo mode assumes the uploaded image set is an automotive object.",
                validation_message="Upload accepted in demo mode.",
            ),
            "demo",
            _usage_item("image_set_validation", "demo-local", purpose),
        )

    client = OpenAI(api_key=settings.openai_api_key)
    image_count = len(paths)
    prompt = (
        "Validate this upload for an automotive BOM analysis workflow. "
        "If the image does not depict a vehicle or automotive part, set is_automotive=false and describe the visible object simply. "
        "If multiple images are provided, they must be the same vehicle/object from different views or detail shots; "
        "if they are different objects, set same_object=false. "
        "Do not perform part detection here. Return a concise user-facing validation_message."
    )
    try:
        response = client.responses.create(
            model=settings.vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": f"{prompt} Number of uploaded images: {image_count}."},
                        *[
                            {"type": "input_image", "image_url": _image_data_url(path)}
                            for path in paths
                        ],
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "automotive_upload_validation",
                    "schema": IMAGE_SET_SCHEMA,
                    "strict": True,
                }
            },
        )
        usage = _usage_item("image_set_validation", settings.vision_model, purpose, response.usage)
        return ImageSetValidation.model_validate(json.loads(response.output_text)), "openai", usage
    except OpenAIError:
        return (
            ImageSetValidation(
                is_automotive=False,
                same_object=False,
                uploaded_description="The Vision LLM validation step failed before the image contents could be verified.",
                validation_message="Vision validation failed. Analysis was skipped so the system does not produce unreliable or demo detections.",
            ),
            "openai-validation-error",
            _usage_item(
                "image_set_validation_error",
                settings.vision_model,
                "OpenAI validation failed, so analysis was stopped to avoid incorrect fallback detections.",
            ),
        )


def analyze_image(path: Path) -> tuple[VisionResult, str, TokenUsageItem]:
    purpose = "Vision LLM part detection from uploaded vehicle image, including labels, material, condition, details, confidence, and bounding boxes."
    if not settings.openai_api_key:
        return _mock_result(path.name), "demo", _usage_item("vision_detection", "demo-local", purpose)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "You are an automotive BOM vision analyst for collision and spare-part estimation. "
        "Detect only automotive parts that are directly visible in the image. Do not infer hidden parts, "
        "internal parts, fasteners, fluids, or consumables unless they are visibly present. "
        "Use conservative standard vehicle-part names such as front bumper cover, grille, headlamp assembly, "
        "hood panel, fender, wheel arch liner, radiator, condenser, sensor, harness, bracket, clip, screw, or washer. "
        "If a region is uncertain, use a lower confidence and explain the uncertainty in minute_details. "
        "Return part name, category, likely material, visible condition, visible part number or OCR text, "
        "minute inspection details, confidence, and tight normalized bounding box. "
        "The bounding box must surround the visible part only, not the entire vehicle."
    )
    try:
        response = client.responses.create(
            model=settings.vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": _image_data_url(path)},
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "vehicle_part_detection",
                    "schema": PART_SCHEMA,
                    "strict": True,
                }
            },
        )
        raw = response.output_text
        usage = _usage_item("vision_detection", settings.vision_model, purpose, response.usage)
        return VisionResult.model_validate(json.loads(raw)), "openai", usage
    except OpenAIError:
        return VisionResult(
            vehicle_context=(
                f"Vision LLM detection failed for {path.name}. Analysis was skipped for this image "
                "so the system does not return demo or guessed automotive parts."
            ),
            detections=[],
        ), "openai-detection-error", _usage_item(
            "vision_detection_error",
            settings.vision_model,
            "OpenAI vision detection failed, so no fallback detections were generated.",
        )
