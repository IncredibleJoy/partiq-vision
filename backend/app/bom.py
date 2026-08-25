from collections import defaultdict

from .schemas import BomItem, PartDetection


def consolidate_bom(detections: list[PartDetection]) -> list[BomItem]:
    groups: dict[str, list[PartDetection]] = defaultdict(list)
    for detection in detections:
        key = detection.part_name.strip().lower()
        groups[key].append(detection)

    items: list[BomItem] = []
    for grouped in groups.values():
        best = max(grouped, key=lambda item: item.confidence)
        part_nos = sorted({item.visible_part_no for item in grouped if item.visible_part_no})
        crops = [item.crop_url for item in grouped if item.crop_url]
        sources = sorted({item.source_image for item in grouped if item.source_image})
        conditions = sorted({item.condition for item in grouped})
        details = " ".join(item.minute_details for item in grouped[:2])
        quantity = max(1, len(part_nos)) if part_nos else 1
        view_note = f" Seen across {len(sources)} uploaded view(s); repeated views were consolidated as one unique physical part."
        items.append(
            BomItem(
                part_name=best.part_name,
                category=best.category,
                material=best.material,
                condition_summary="; ".join(conditions),
                quantity=quantity,
                best_confidence=best.confidence,
                visible_part_nos=part_nos,
                crop_urls=crops,
                source_images=sources,
                notes=f"{details}{view_note}",
            )
        )

    return sorted(items, key=lambda item: item.best_confidence, reverse=True)
