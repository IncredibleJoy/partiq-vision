from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import UploadFile

from .bom import consolidate_bom
from .costing import build_cost_sheet
from .images import create_crop, save_upload
from .prompts import load_prompt
from .schemas import (
    AgentTrace,
    BomItem,
    BomWarehouseRecommendation,
    CostSheet,
    JobResponse,
    PartDetection,
    PartRecommendation,
    TokenUsageItem,
    TokenUsageSummary,
)
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

    def analyze(self, image_path, ctx: AgentContext, token_mode: str = "standard") -> tuple[list[PartDetection], str, str]:
        result, mode, token_usage = analyze_image(image_path, token_mode)
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
                        reason=load_prompt("recommendations/warehouse_cluster_similarity.txt"),
                        recommendation_type="warehouse_cluster_similarity",
                        confidence=min(0.95, confidence),
                        related_parts=related[:3],
                    )
                )
        ctx.trace(self.name, "semantic_part_lookup", "complete", f"{len(recommendations)} database recommendations")
        return recommendations

    def recommend_bom_alternatives(self, bom: list[BomItem], ctx: AgentContext) -> list[PartRecommendation]:
        recommendations: list[PartRecommendation] = []
        for item in bom[:20]:
            matches = search_warehouse_parts(
                f"{item.part_name} {item.category} {item.material} {' '.join(item.visible_part_nos)} {item.notes}",
                limit=5,
            )
            if len(matches) < 2:
                continue
            primary = matches[0]
            primary_cost = float(primary["unit_cost"])
            alternatives = [
                row
                for row in matches[1:]
                if row["sku"] != primary["sku"]
                and int(row["stock_quantity"]) > 0
                and float(row["unit_cost"]) < primary_cost
                and float(row["similarity"]) >= 0.45
            ]
            if alternatives:
                related = [
                    f"{row['part_name']} [{row['sku']}] ${float(row['unit_cost']):.2f}, stock {row['stock_quantity']}"
                    for row in alternatives[:3]
                ]
                recommendations.append(
                    PartRecommendation(
                        part_name=item.part_name,
                        reason=load_prompt("recommendations/cost_optimization.txt"),
                        recommendation_type="cost_optimization",
                        confidence=min(0.9, max(float(row["similarity"]) for row in alternatives)),
                        related_parts=related,
                    )
                )
        ctx.trace(self.name, "bom_cost_alternatives", "complete", f"{len(recommendations)} cost optimization suggestion(s)")
        return recommendations


def attach_bom_warehouse_recommendations(
    bom: list[BomItem],
    agent_recommendations: list[PartRecommendation],
    strategy: str = "semantic_search",
    reset_selection: bool = False,
) -> list[BomItem]:
    if strategy != "semantic_search":
        raise ValueError(f"Unsupported warehouse matching strategy: {strategy}")

    agent_by_part: dict[str, list[PartRecommendation]] = {}
    for recommendation in agent_recommendations:
        agent_by_part.setdefault(recommendation.part_name.lower(), []).append(recommendation)

    def candidates(part_name: str, category: str, material: str, reason: str) -> list[BomWarehouseRecommendation]:
        matches = search_warehouse_parts(f"{part_name} {category} {material}", limit=5)
        agent_reasons = agent_by_part.get(part_name.lower(), [])
        combined_reason = (
            f"{reason} Agent recommendation match: "
            + "; ".join(item.reason for item in agent_reasons[:2])
            if agent_reasons
            else reason
        )
        return [
            BomWarehouseRecommendation(
                sku=row["sku"],
                part_name=row["part_name"],
                score=max(0, min(1, float(row["similarity"]))),
                reason=combined_reason,
                supplier=row["supplier"],
                unit_cost=float(row["unit_cost"]),
                currency=row["currency"],
                stock_quantity=int(row["stock_quantity"]),
                category=row["category"],
                material=row["material"],
                cluster_key=row["cluster_key"],
                fitment_notes=row["fitment_notes"],
            )
            for row in matches
        ]

    for item in bom:
        item.recommendation_reason = (
            "; ".join(item.reason for item in agent_by_part.get(item.part_name.lower(), [])[:2])
            or "Recommendations are ranked by warehouse similarity, stock availability, and part fitment."
        )
        item.warehouse_recommendations = candidates(
            item.part_name,
            item.category,
            item.material,
            "Ranked by semantic warehouse similarity, stock availability, and the agent's related-part signals.",
        )
        valid_item_skus = {candidate.sku for candidate in item.warehouse_recommendations}
        if reset_selection or item.selected_warehouse_sku not in valid_item_skus:
            item.selected_warehouse_sku = item.warehouse_recommendations[0].sku if item.warehouse_recommendations else None
        for child in item.assembly_children:
            child.warehouse_recommendations = candidates(
                child.part_name,
                child.role,
                item.material,
                f"Level-2 recommendation for {item.part_name}: {child.reason}",
            )
            valid_child_skus = {candidate.sku for candidate in child.warehouse_recommendations}
            if reset_selection or child.selected_warehouse_sku not in valid_child_skus:
                child.selected_warehouse_sku = child.warehouse_recommendations[0].sku if child.warehouse_recommendations else None
    return bom


class ReflectionAgent:
    name = "reflection_agent"

    assembly_rules = {
        "bumper": ["bumper absorber", "bumper reinforcement", "side retainers", "clips", "lower screws"],
        "grille": ["emblem", "upper grille fasteners", "camera bracket"],
        "headlamp": ["mounting brackets", "wiring connector", "dust cap", "dielectric grease"],
        "hood": ["hinges", "latch striker", "washer nozzle", "washer hose", "paint materials"],
        "fender": ["liner clips", "wheel arch liner", "side marker", "paint materials"],
        "wheel": ["tire", "lug nuts", "valve stem", "tpms sensor"],
        "radiator": ["coolant", "upper hose", "lower hose", "isolator mounts"],
        "condenser": ["a/c seals", "receiver drier", "line ports"],
    }

    def verify(
        self,
        detections: list[PartDetection],
        ctx: AgentContext,
        bom: list[BomItem] | None = None,
        cost_sheet: CostSheet | None = None,
    ) -> list[PartRecommendation]:
        bom = bom or consolidate_bom(detections)
        names = {item.part_name.lower() for item in detections}
        bom_names = {item.part_name.lower() for item in bom}
        combined_text = " ".join([*names, *bom_names])
        recommendations: list[PartRecommendation] = []

        for anchor, related_parts in self.assembly_rules.items():
            if anchor in combined_text:
                missing = [part for part in related_parts if part.lower() not in combined_text]
                if missing:
                    recommendations.append(
                        PartRecommendation(
                            part_name=f"{anchor.title()} assembly review",
                            reason=load_prompt("recommendations/missing_related_part.txt"),
                            recommendation_type="missing_related_part",
                            confidence=0.72,
                            related_parts=missing,
                        )
                    )

        pair_checks = [
            ("left headlamp", "right headlamp", "Headlamp side-pair review"),
            ("left fender", "right fender", "Fender side-pair review"),
            ("left wheel", "right wheel", "Wheel side-pair review"),
        ]
        for left, right, label in pair_checks:
            has_left = left in combined_text
            has_right = right in combined_text
            if has_left != has_right:
                recommendations.append(
                    PartRecommendation(
                        part_name=label,
                        reason=load_prompt("recommendations/manual_review_pair.txt"),
                        recommendation_type="manual_review",
                        confidence=0.68,
                        related_parts=[right if has_left else left],
                    )
                )

        family_groups: dict[str, list[BomItem]] = {}
        for item in bom:
            family = self._family_key(item.part_name)
            if family:
                family_groups.setdefault(family, []).append(item)
        for family, items in family_groups.items():
            unspecified = [item for item in items if not self._has_side_or_position(item.part_name)]
            if len(unspecified) > 1:
                recommendations.append(
                    PartRecommendation(
                        part_name=f"{family.title()} duplicate review",
                        reason=load_prompt("recommendations/duplicate_candidate.txt"),
                        recommendation_type="duplicate_candidate",
                        confidence=0.7,
                        related_parts=[item.part_name for item in unspecified[:4]],
                    )
                )

        low_confidence = [item.part_name for item in detections if item.confidence < 0.7]
        if low_confidence:
            recommendations.append(
                PartRecommendation(
                    part_name="Manual review queue",
                    reason=load_prompt("recommendations/low_confidence_detection.txt"),
                    recommendation_type="quality_review",
                    confidence=0.88,
                    related_parts=low_confidence,
                )
            )

        if cost_sheet:
            matched_names = {item.detected_part_name.lower() for item in cost_sheet.items}
            for item in bom:
                if item.part_name.lower() not in matched_names:
                    recommendations.append(
                        PartRecommendation(
                            part_name=item.part_name,
                            reason=load_prompt("recommendations/missing_cost_match.txt"),
                            recommendation_type="missing_cost_match",
                            confidence=0.82,
                            related_parts=item.visible_part_nos or [item.category],
                        )
                    )

            for item in cost_sheet.items:
                if item.match_confidence < 0.55:
                    recommendations.append(
                        PartRecommendation(
                            part_name=item.detected_part_name,
                            reason=load_prompt("recommendations/weak_warehouse_match.txt"),
                            recommendation_type="quality_review",
                            confidence=0.78,
                            related_parts=[f"{item.matched_part_name} [{item.matched_sku}]"],
                        )
                    )
                if item.stock_quantity <= max(2, item.quantity):
                    recommendations.append(
                        PartRecommendation(
                            part_name=item.detected_part_name,
                            reason=load_prompt("recommendations/stock_risk.txt"),
                            recommendation_type="stock_risk",
                            confidence=0.84,
                            related_parts=[f"{item.matched_sku}: stock {item.stock_quantity}, required {item.quantity}"],
                        )
                    )

        ctx.trace(self.name, "verify_bom_completeness", "complete", f"{len(recommendations)} reflection findings")
        return recommendations

    def _family_key(self, name: str) -> str | None:
        lowered = name.lower()
        for family in ["bumper", "headlamp", "fender", "wheel", "radiator", "condenser", "grille", "hood"]:
            if family in lowered:
                return family
        return None

    def _has_side_or_position(self, name: str) -> bool:
        lowered = name.lower()
        return any(term in lowered for term in ["left", "right", "front", "rear", "lh", "rh"])


class OrchestratorAgent:
    def __init__(self) -> None:
        self.vision = VisionToolAgent()
        self.crop = CropToolAgent()
        self.bom = BomToolAgent()
        self.knowledge = KnowledgeSearchAgent()
        self.reflection = ReflectionAgent()

    async def run(self, files: list[UploadFile], token_mode: str = "standard") -> JobResponse:
        ctx = AgentContext(job_id=str(uuid4()))
        ctx.trace("orchestrator_agent", "start_job", "running", f"Received {len(files)} image(s)")
        ctx.trace("orchestrator_agent", "token_optimizer", "complete", f"Vision token mode: {token_mode}")

        image_paths = []
        for file in files:
            image_path = await save_upload(file)
            image_paths.append(image_path)
            ctx.trace("orchestrator_agent", "store_image", "complete", image_path.name)

        validation, validation_mode, validation_usage = validate_image_set(image_paths, token_mode)
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
                model_mode=f"{validation_mode}+token-{token_mode}",
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
        model_modes.add(f"token-{token_mode}")
        for image_path in image_paths:
            detections, vehicle_context, mode = self.vision.analyze(image_path, ctx, token_mode)
            all_detections.extend(self.crop.enrich(image_path, detections, ctx))
            contexts.append(vehicle_context)
            model_modes.add(mode)

        bom = self.bom.consolidate(all_detections, ctx)
        cost_sheet = build_cost_sheet(bom)
        recommendations = self.knowledge.recommend_from_database(all_detections, ctx)
        recommendations.extend(self.knowledge.recommend_bom_alternatives(bom, ctx))
        recommendations.extend(self.reflection.verify(all_detections, ctx, bom, cost_sheet))
        bom = attach_bom_warehouse_recommendations(bom, recommendations)
        cost_sheet = build_cost_sheet(bom)
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
