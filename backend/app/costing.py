from .config import settings
from .schemas import BomItem, CostSheet, CostSheetItem
from .warehouse import get_warehouse_part, search_warehouse_parts

LABOR_RATE_USD = 55.0
DEFECT_TERMS = {
    "bent",
    "broken",
    "burnt",
    "cracked",
    "crushed",
    "damaged",
    "dent",
    "dented",
    "fractured",
    "leak",
    "missing",
    "scratched",
    "torn",
}
LABOR_HOURS_BY_CATEGORY = {
    "electrical": 1.4,
    "lighting": 1.1,
    "exterior body": 1.8,
    "structural body": 2.8,
    "cooling": 1.6,
    "wiring": 1.5,
    "sensor": 1.0,
    "wheel/tire": 0.7,
    "fastener": 0.2,
}


def _display_cost(unit_cost: float, source_currency: str) -> tuple[float, str]:
    target_currency = settings.cost_currency.upper()
    if source_currency.upper() == "USD" and target_currency == "INR":
        return round(unit_cost * settings.usd_to_inr_rate, 2), "INR"
    return round(unit_cost, 2), source_currency.upper()


def _contains_defect(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in DEFECT_TERMS)


def _labor_rate(currency: str) -> float:
    if currency.upper() == "INR":
        return round(LABOR_RATE_USD * settings.usd_to_inr_rate, 2)
    return LABOR_RATE_USD


def _labor_estimate(bom_item: BomItem, matched_category: str, currency: str) -> tuple[bool, float, float, float, str]:
    text = " ".join(
        [
            bom_item.part_name,
            bom_item.category,
            matched_category,
            bom_item.condition_summary,
            bom_item.notes,
        ]
    ).lower()
    defect_visible = _contains_defect(text)
    assembly_work = bool(bom_item.assembly_children)
    category_key = next((key for key in LABOR_HOURS_BY_CATEGORY if key in text), "")

    if not defect_visible and not assembly_work:
        return False, 0, 0, 0, "No visible defect or assembly/process work was identified for this BOM row."

    base_hours = LABOR_HOURS_BY_CATEGORY.get(category_key, 0.8)
    if assembly_work:
        base_hours += min(1.2, 0.15 * len(bom_item.assembly_children))
    if defect_visible:
        base_hours += 0.5

    hours = round(base_hours * max(1, bom_item.quantity), 2)
    rate = _labor_rate(currency)
    cost = round(hours * rate, 2)
    reasons = []
    if defect_visible:
        reasons.append("visible defect/damage requires repair, removal, replacement, or inspection labor")
    if assembly_work:
        reasons.append("complete assembly has second-level subparts/process items that may require construction, transfer, calibration, or fitment labor")
    return True, hours, rate, cost, "; ".join(reasons)


def _match_level_2_item(child_name: str, parent: BomItem):
    query = " ".join(
        [
            child_name,
            parent.part_name,
            parent.category,
            parent.material,
            parent.condition_summary,
            parent.notes,
        ]
    )
    matches = search_warehouse_parts(query, limit=1)
    if not matches:
        return None
    match = matches[0]
    return match if float(match["similarity"]) >= 0.45 else None


def _selected_or_best_match(sku: str | None, query: str, selected_score: float | None = None):
    if sku:
        selected = get_warehouse_part(sku)
        if selected:
            return {**selected, "similarity": max(0, min(1, selected_score or 0))}
    matches = search_warehouse_parts(query, limit=1)
    return matches[0] if matches else None


def _allocated_child_unit_cost(parent_unit_cost: float, child_index: int, child_count: int) -> float:
    if child_count <= 0:
        return 0
    weights = [0.34, 0.22, 0.16, 0.12, 0.08, 0.04, 0.025, 0.015]
    if child_count <= len(weights):
        selected = weights[:child_count]
        total_weight = sum(selected)
        return round(parent_unit_cost * (selected[child_index] / total_weight), 2)
    return round(parent_unit_cost / child_count, 2)


def build_cost_sheet(bom: list[BomItem]) -> CostSheet:
    items: list[CostSheetItem] = []
    for bom_item in bom:
        if not bom_item.included:
            continue
        query = " ".join(
            [
                bom_item.part_name,
                bom_item.category,
                bom_item.material,
                bom_item.condition_summary,
                " ".join(bom_item.visible_part_nos),
                bom_item.notes,
            ]
        )
        selected_score = next(
            (candidate.score for candidate in bom_item.warehouse_recommendations if candidate.sku == bom_item.selected_warehouse_sku),
            None,
        )
        match = _selected_or_best_match(bom_item.selected_warehouse_sku, query, selected_score)
        if not match:
            continue

        quantity = max(1, bom_item.quantity)
        unit_cost, currency = _display_cost(float(match["unit_cost"]), match["currency"])
        parts_total_cost = round(quantity * unit_cost, 2)
        labor_required, labor_hours, labor_rate, labor_cost, labor_reason = _labor_estimate(
            bom_item,
            match["category"],
            currency,
        )
        total_cost = round(parts_total_cost + labor_cost, 2)
        parent_item = CostSheetItem(
            bom_level=1,
            row_type="level_1_part",
            parent_detected_part_name=None,
            detected_part_name=bom_item.part_name,
            matched_part_name=match["part_name"],
            matched_sku=match["sku"],
            category=match["category"],
            material=match["material"],
            supplier=match["supplier"],
            cluster_key=match["cluster_key"],
            quantity=quantity,
            unit_cost=unit_cost,
            parts_total_cost=parts_total_cost,
            labor_required=labor_required,
            labor_hours=labor_hours,
            labor_rate=labor_rate,
            labor_cost=labor_cost,
            labor_reason=labor_reason,
            total_cost=total_cost,
            currency=currency,
            stock_quantity=match["stock_quantity"],
            match_confidence=max(0, min(1, float(match["similarity"]))),
            fitment_notes=match["fitment_notes"],
            consumables_required=match["consumables_required"],
            level_2_items=bom_item.assembly_children,
        )
        items.append(parent_item)

        included_children = [child for child in bom_item.assembly_children if child.included]
        child_count = len(included_children)
        for index, child in enumerate(included_children, start=1):
            child_quantity = max(1, child.quantity) * quantity
            child_selected_score = next(
                (candidate.score for candidate in child.warehouse_recommendations if candidate.sku == child.selected_warehouse_sku),
                None,
            )
            child_match = _selected_or_best_match(
                child.selected_warehouse_sku,
                f"{child.part_name} {bom_item.part_name} {bom_item.category} {bom_item.material} {bom_item.notes}",
                child_selected_score,
            )
            child_unit_cost = 0.0
            child_currency = currency
            child_sku = f"{match['sku']}-L2-{index:02d}"
            child_matched_name = f"Allocated from {match['part_name']}"
            child_supplier = "Derived from parent warehouse cost"
            child_cluster = f"{match['cluster_key']}::level_2"
            child_stock = 0
            child_confidence = round(parent_item.match_confidence * 0.6, 4)
            child_material = bom_item.material
            child_fitment = f"{child.reason} Cost allocated from the matched level-1 warehouse assembly because no strong child SKU match was found."
            if child_match:
                child_unit_cost, child_currency = _display_cost(float(child_match["unit_cost"]), child_match["currency"])
                child_sku = child_match["sku"]
                child_matched_name = child_match["part_name"]
                child_supplier = child_match["supplier"]
                child_cluster = child_match["cluster_key"]
                child_stock = child_match["stock_quantity"]
                child_confidence = max(0, min(1, float(child_match["similarity"])))
                child_material = child_match["material"]
                child_fitment = child.reason
            else:
                child_unit_cost = _allocated_child_unit_cost(unit_cost, index - 1, child_count)
            child_parts_total = round(child_quantity * child_unit_cost, 2)
            items.append(
                CostSheetItem(
                    bom_level=2,
                    row_type="level_2_warehouse_item" if child_match else "level_2_allocated_item",
                    parent_detected_part_name=bom_item.part_name,
                    detected_part_name=child.part_name,
                    matched_part_name=child_matched_name,
                    matched_sku=child_sku,
                    category=child.role,
                    material=child_material,
                    supplier=child_supplier,
                    cluster_key=child_cluster,
                    quantity=child_quantity,
                    unit_cost=child_unit_cost,
                    parts_total_cost=child_parts_total,
                    labor_required=False,
                    labor_hours=0,
                    labor_rate=0,
                    labor_cost=0,
                    labor_reason=f"Included for level-2 BOM review under {bom_item.part_name}; parent labor reason: {labor_reason}",
                    total_cost=child_parts_total,
                    currency=child_currency,
                    stock_quantity=child_stock,
                    match_confidence=child_confidence,
                    fitment_notes=child_fitment,
                    consumables_required=[],
                    level_2_items=[],
                )
            )

    total = round(sum(item.total_cost for item in items if item.bom_level == 1), 2)
    currency = items[0].currency if items else settings.cost_currency.upper()
    return CostSheet(currency=currency, items=items, total_cost=total)
