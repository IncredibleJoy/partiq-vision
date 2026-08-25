from .config import settings
from .schemas import BomItem, CostSheet, CostSheetItem
from .warehouse import search_warehouse_parts


def _display_cost(unit_cost: float, source_currency: str) -> tuple[float, str]:
    target_currency = settings.cost_currency.upper()
    if source_currency.upper() == "USD" and target_currency == "INR":
        return round(unit_cost * settings.usd_to_inr_rate, 2), "INR"
    return round(unit_cost, 2), source_currency.upper()


def build_cost_sheet(bom: list[BomItem]) -> CostSheet:
    items: list[CostSheetItem] = []
    for bom_item in bom:
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
        matches = search_warehouse_parts(query, limit=1)
        if not matches:
            continue

        match = matches[0]
        quantity = max(1, bom_item.quantity)
        unit_cost, currency = _display_cost(float(match["unit_cost"]), match["currency"])
        total_cost = round(quantity * unit_cost, 2)
        items.append(
            CostSheetItem(
                detected_part_name=bom_item.part_name,
                matched_part_name=match["part_name"],
                matched_sku=match["sku"],
                category=match["category"],
                material=match["material"],
                supplier=match["supplier"],
                cluster_key=match["cluster_key"],
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                currency=currency,
                stock_quantity=match["stock_quantity"],
                match_confidence=max(0, min(1, float(match["similarity"]))),
                fitment_notes=match["fitment_notes"],
                consumables_required=match["consumables_required"],
            )
        )

    total = round(sum(item.total_cost for item in items), 2)
    currency = items[0].currency if items else settings.cost_currency.upper()
    return CostSheet(currency=currency, items=items, total_cost=total)
