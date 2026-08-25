from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import UploadFile

from .bom import consolidate_bom
from .costing import build_cost_sheet
from .images import create_crop, save_upload
from .schemas import AgentTrace, JobResponse, PartDetection, PartRecommendation, TokenUsageItem, TokenUsageSummary
from .warehouse import search_warehouse_parts
from .vision import analyze_image, validate_image_set


@dataclass
class AgentContext:
    job_id: str
    traces: list[AgentTrace] = field(default_factory=list)
    token_usage_items: list[TokenUsageItem] = field(default_factory=list)

    def trace(self, agent: str, action: str, status: str, detail: str) -> None:
        self.traces.append(AgentTrace(agent=agent, action=action, status=status, detail=detail))

    def add_token_usage(self, item: TokenUsageItem) -> None:
        self.token_usage_items.append(item)

    def token_summary(self) -> TokenUsageSummary:
        return TokenUsageSummary(
            items=self.token_usage_items,
            total_input_tokens=sum(item.input_tokens for item in self.token_usage_items),
            total_output_tokens=sum(item.output_tokens for item in self.token_usage_items),
            total_tokens=sum(item.total_tokens for item in self.token_usage_items),
        )


class VisionToolAgent:
    name = "vision_tool_agent"

    def analyze(self, image_path, ctx: AgentContext) -> tuple[list[PartDetection], str, str]:
        result, mode, token_usage = analyze_image(image_path)
        ctx.add_token_usage(token_usage)
        ctx.trace(self.name, "detect_parts", "complete", f"{len(result.detections)} parts from {image_path.name}")
        return result.detections, result.vehicle_context, mode


class CropToolAgent:
    name = "crop_tool_agent"

    def enrich(self, image_path, detections: list[PartDetection], ctx: AgentContext) -> list[PartDetection]:
        for detection in detections:
            detection.id = str(uuid4())
            detection.source_image = image_path.name
            detection.crop_url = create_crop(image_path, detection)
        ctx.trace(self.name, "crop_detected_regions", "complete", f"Generated crops for {len(detections)} detections")
        return detections


class BomToolAgent:
    name = "bom_tool_agent"

    def consolidate(self, detections: list[PartDetection], ctx: AgentContext):
        bom = consolidate_bom(detections)
        ctx.trace(self.name, "deduplicate_bom", "complete", f"Created {len(bom)} unique BOM rows")
        return bom


class KnowledgeSearchAgent:
    name = "knowledge_search_agent"

    def recommend_from_database(self, detections: list[PartDetection], ctx: AgentContext) -> list[PartRecommendation]:
        recommendations: list[PartRecommendation] = []
        for detection in detections[:20]:
            warehouse_matches = search_warehouse_parts(
                f"{detection.part_name} {detection.material} {detection.category} {detection.visible_part_no or ''}",
                limit=3,
            )
            confidence = max((float(row["similarity"]) for row in warehouse_matches), default=0)
            related = [
                f"{row['part_name']} [{row['sku']}]"
                for row in warehouse_matches
                if detection.part_name.lower() not in row["part_name"].lower()
            ]
            if related:
                recommendations.append(
                    PartRecommendation(
                        part_name=detection.part_name,
                        reason="Similar stock parts are present in the synthetic warehouse and can be clustered for later cost-sheet matching.",
                        recommendation_type="warehouse_cluster_similarity",
                        confidence=min(0.95, confidence),
                        related_parts=related[:3],
                    )
                )
        ctx.trace(self.name, "semantic_part_lookup", "complete", f"{len(recommendations)} database recommendations")
        return recommendations


class ReflectionAgent:
    name = "reflection_agent"

    front_view_expected = {
        "Front bumper cover": ["bumper absorber", "bumper reinforcement", "clips", "parking sensors"],
        "Radiator grille assembly": ["upper grille fasteners", "emblem", "hood latch cover"],
        "Left headlamp assembly": ["headlamp brackets", "bulbs or LED module", "wiring connector"],
        "Right headlamp assembly": ["headlamp brackets", "bulbs or LED module", "wiring connector"],
        "Bonnet hood panel": ["hood hinges", "hood latch striker", "washer nozzle"],
    }

    def verify(self, detections: list[PartDetection], ctx: AgentContext) -> list[PartRecommendation]:
        names = {item.part_name.lower() for item in detections}
        recommendations: list[PartRecommendation] = []

        for anchor, related_parts in self.front_view_expected.items():
            if anchor.lower() in names:
                missing = [part for part in related_parts if not any(part.lower() in name for name in names)]
                if missing:
                    recommendations.append(
                        PartRecommendation(
                            part_name=anchor,
                            reason="Reflection pass found likely associated parts or consumables that should be checked for BOM completeness.",
                            recommendation_type="missing_related_part",
                            confidence=0.72,
                            related_parts=missing,
                        )
                    )

        low_confidence = [item.part_name for item in detections if item.confidence < 0.7]
        if low_confidence:
            recommendations.append(
                PartRecommendation(
                    part_name="Manual review queue",
                    reason="Some detections are below the confidence threshold and should be verified by an estimator.",
                    recommendation_type="quality_review",
                    confidence=0.88,
                    related_parts=low_confidence,
                )
            )

        ctx.trace(self.name, "verify_bom_completeness", "complete", f"{len(recommendations)} reflection findings")
        return recommendations


class OrchestratorAgent:
    def __init__(self) -> None:
        self.vision = VisionToolAgent()
        self.crop = CropToolAgent()
        self.bom = BomToolAgent()
        self.knowledge = KnowledgeSearchAgent()
        self.reflection = ReflectionAgent()

    async def run(self, files: list[UploadFile]) -> JobResponse:
        ctx = AgentContext(job_id=str(uuid4()))
        ctx.trace("orchestrator_agent", "start_job", "running", f"Received {len(files)} image(s)")

        image_paths = []
        for file in files:
            image_path = await save_upload(file)
            image_paths.append(image_path)
            ctx.trace("orchestrator_agent", "store_image", "complete", image_path.name)

        validation, validation_mode, validation_usage = validate_image_set(image_paths)
        ctx.add_token_usage(validation_usage)
        ctx.trace(
            "validation_agent",
            "validate_upload_set",
            "complete" if validation.is_automotive and validation.same_object else "rejected",
            validation.validation_message,
        )

        if not validation.is_automotive or not validation.same_object:
            reason = validation.validation_message
            if validation_mode == "openai-validation-error":
                reason = f"{validation.validation_message} {validation.uploaded_description}"
            elif not validation.is_automotive:
                reason = (
                    f"Image does not depict any vehicle or automotive part; {validation.uploaded_description} "
                    "No automotive parts are present, so part detection, BOM, and cost-sheet analysis were skipped."
                )
            elif not validation.same_object:
                reason = (
                    f"Multiple images do not appear to show the same vehicle/object; {validation.uploaded_description} "
                    "Please upload front, back, top, side, and detail views of the same vehicle/object for a unique BOM."
                )
            return JobResponse(
                job_id=ctx.job_id,
                model_mode=validation_mode,
                vehicle_context=reason,
                detections=[],
                bom=[],
                cost_sheet=build_cost_sheet([]),
                token_usage=ctx.token_summary(),
                recommendations=[],
                agent_trace=ctx.traces,
            )

        all_detections: list[PartDetection] = []
        contexts: list[str] = []
        model_modes: set[str] = set()

        model_modes.add(validation_mode)
        for image_path in image_paths:
            detections, vehicle_context, mode = self.vision.analyze(image_path, ctx)
            all_detections.extend(self.crop.enrich(image_path, detections, ctx))
            contexts.append(vehicle_context)
            model_modes.add(mode)

        bom = self.bom.consolidate(all_detections, ctx)
        cost_sheet = build_cost_sheet(bom)
        recommendations = self.knowledge.recommend_from_database(all_detections, ctx)
        recommendations.extend(self.reflection.verify(all_detections, ctx))
        ctx.trace("costing_agent", "warehouse_cost_sheet", "complete", f"{len(cost_sheet.items)} priced BOM row(s)")
        ctx.trace("orchestrator_agent", "finalize_job", "complete", "BOM, cost sheet, recommendations, and trace ready")

        return JobResponse(
            job_id=ctx.job_id,
            model_mode="+".join(sorted(model_modes)),
            vehicle_context=" | ".join(contexts),
            detections=all_detections,
            bom=bom,
            cost_sheet=cost_sheet,
            token_usage=ctx.token_summary(),
            recommendations=recommendations,
            agent_trace=ctx.traces,
        )
