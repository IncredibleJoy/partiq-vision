from collections import defaultdict
import re

from .schemas import BomAssemblyComponent, BomItem, PartDetection


POSITION_TERMS = {
    "front_left": {"front left", "left front", "driver side", "driver-side", "lh", "left"},
    "front_right": {"front right", "right front", "passenger side", "passenger-side", "rh", "right"},
    "front": {"front"},
    "rear_left": {"rear left", "left rear"},
    "rear_right": {"rear right", "right rear"},
    "rear": {"rear", "back"},
}

PART_SYNONYMS = {
    "bumper reinforcement": "bumper reinforcement beam",
    "reinforcement beam": "bumper reinforcement beam",
    "crash beam": "bumper reinforcement beam",
    "bumper absorber": "bumper energy absorber",
    "energy absorber": "bumper energy absorber",
    "impact absorber": "bumper energy absorber",
    "bumper cover": "bumper cover",
    "bumper fascia": "bumper cover",
    "bumper skin": "bumper cover",
    "front bumper": "bumper cover",
    "grill": "radiator grille assembly",
    "grille": "radiator grille assembly",
    "radiator grille": "radiator grille assembly",
    "headlight": "headlamp assembly",
    "headlamp": "headlamp assembly",
    "lamp assembly": "headlamp assembly",
    "hood": "bonnet hood panel",
    "bonnet": "bonnet hood panel",
    "fender": "fender panel",
    "wing panel": "fender panel",
    "wheel arch liner": "wheel arch liner",
    "splash liner": "wheel arch liner",
    "radiator": "radiator assembly",
    "condenser": "a/c condenser",
    "parking sensor": "parking sensor",
    "sensor": "sensor",
    "harness": "wiring harness",
    "wire harness": "wiring harness",
    "clip": "clip set",
    "retainer": "clip set",
    "screw": "screw set",
    "washer": "washer set",
    "wheel": "wheel assembly",
    "rim": "wheel rim",
    "tyre": "tire",
    "tire": "tire",
    "ecu": "electronic control unit",
    "ecm": "electronic control unit",
    "engine control module": "electronic control unit",
    "control module": "electronic control unit",
}


ASSEMBLY_BREAKDOWN_RULES = {
    "electronic control unit": {
        "reason": "Detected as a complete electronic module; the second-level BOM lists typical manufactured ECU subparts for review, repair, replacement, and calibration costing.",
        "children": [
            ("sealed ECU housing", 1, "Enclosure", "Protects the electronics and provides mounting points."),
            ("printed circuit board assembly", 1, "Core electronics", "Carries processor, memory, power, and driver circuits."),
            ("microcontroller or processor", 1, "Control logic", "Runs the vehicle control firmware."),
            ("memory device", 1, "Configuration storage", "Stores calibration, fault, or vehicle configuration data."),
            ("power regulation circuit", 1, "Electrical supply", "Conditions vehicle battery voltage for internal electronics."),
            ("connector pin header", 1, "Vehicle interface", "Connects wiring harness signals to the module."),
            ("gasket or perimeter seal", 1, "Environmental sealing", "Protects against moisture and dust ingress."),
            ("firmware configuration and calibration", 1, "Process item", "May require programming after replacement or repair."),
        ],
    },
    "headlamp assembly": {
        "reason": "Detected as a complete lamp assembly; second-level items help review included and transferable lighting subparts.",
        "children": [
            ("polycarbonate lens", 1, "Optical cover", "Visible lens condition drives repair or replacement choice."),
            ("lamp housing", 1, "Structure", "Holds optics, seals, and vehicle mounting points."),
            ("reflector or projector module", 1, "Optics", "Controls beam pattern and lighting performance."),
            ("bulb or LED module", 1, "Light source", "May be included, reused, or replaced separately."),
            ("adjuster and mounting tabs", 1, "Fitment", "Damage can require brackets or complete assembly replacement."),
            ("rear dust cap and seal", 1, "Environmental sealing", "Prevents dust and water ingress."),
        ],
    },
    "bumper cover": {
        "reason": "Detected as a body assembly surface; second-level items capture common attached pieces and process items used during repair.",
        "children": [
            ("bumper fascia shell", 1, "Primary panel", "Main visible painted part."),
            ("sensor brackets or blanks", 1, "Fitment", "Needed when parking sensors or ADAS sensors are present."),
            ("side retainers and clips", 1, "Fastening", "Often break during impact or removal."),
            ("lower grille or trim insert", 1, "Trim", "May be separate depending on vehicle variant."),
            ("paint materials", 1, "Process item", "Required when replacing or refinishing a painted bumper cover."),
        ],
    },
    "radiator assembly": {
        "reason": "Detected as a cooling assembly; second-level items help review related cooling parts and service materials.",
        "children": [
            ("radiator core", 1, "Heat exchange", "Primary cooling element."),
            ("plastic end tanks", 2, "Fluid containment", "Common leak or impact area."),
            ("upper and lower hose connections", 2, "Fitment", "Must be inspected during replacement."),
            ("mounting isolators", 1, "Fitment", "Controls vibration and positioning."),
            ("coolant refill", 1, "Consumable", "Required when radiator replacement opens the cooling system."),
        ],
    },
    "wheel assembly": {
        "reason": "Detected as a complete wheel/tire assembly; second-level items separate reusable, damaged, and service parts.",
        "children": [
            ("wheel rim", 1, "Structure", "Supports tire and defines fitment."),
            ("tire", 1, "Wear item", "Condition determines reuse or replacement."),
            ("valve stem", 1, "Service item", "Often replaced when tire is removed."),
            ("tpms sensor", 1, "Electronic sensor", "May need transfer, replacement, or relearn."),
            ("lug nuts or wheel bolts", 1, "Fastening", "Check thread and seating condition."),
        ],
    },
}

LEAF_PART_TERMS = {
    "bolt",
    "clip",
    "fastener",
    "gasket",
    "lug nut",
    "nut",
    "o-ring",
    "paint",
    "pin",
    "retainer",
    "rivet",
    "screw",
    "seal",
    "washer",
}

ASSEMBLY_CUE_TERMS = {
    "actuator",
    "assembly",
    "caliper",
    "camera",
    "condenser",
    "control",
    "display",
    "fan",
    "grille",
    "harness",
    "headlamp",
    "lamp",
    "latch",
    "lock",
    "module",
    "motor",
    "panel",
    "pump",
    "radiator",
    "seat",
    "sensor",
    "strut",
    "tail lamp",
    "turbo",
    "unit",
}

GENERIC_BREAKDOWN_RULES = [
    {
        "match": {"electrical", "electronic", "module", "control unit", "ecu", "ecm"},
        "reason": "Detected as an electrical/electronic level-1 part; second-level items represent common module construction and service dependencies.",
        "children": [
            ("outer housing or case", 1, "Enclosure", "Protects internal electrical components and provides mounting points."),
            ("electronic board or internal module", 1, "Core function", "Carries the control, sensing, or switching electronics."),
            ("connector terminals", 1, "Vehicle interface", "Links the part to the wiring harness."),
            ("seal or gasket", 1, "Environmental sealing", "Protects against dust and moisture."),
            ("programming, calibration, or relearn", 1, "Process item", "May be needed after replacement or repair."),
        ],
    },
    {
        "match": {"sensor", "camera", "radar", "parking"},
        "reason": "Detected as a sensing level-1 part; second-level items capture mounting, connection, and calibration dependencies.",
        "children": [
            ("sensor body", 1, "Primary component", "Main sensing element or module."),
            ("mounting bracket or holder", 1, "Fitment", "Controls position and alignment."),
            ("connector and terminals", 1, "Vehicle interface", "Links sensor signals to the harness."),
            ("seal or retaining ring", 1, "Environmental sealing", "Protects sensor opening and connector."),
            ("calibration or aiming procedure", 1, "Process item", "May be required for ADAS or parking systems."),
        ],
    },
    {
        "match": {"exterior body", "body", "panel", "bumper", "fender", "hood", "bonnet", "door", "tailgate"},
        "reason": "Detected as a body level-1 part; second-level items capture panel construction, attachments, fasteners, and refinishing needs.",
        "children": [
            ("outer panel or shell", 1, "Primary panel", "Main visible structural or cosmetic surface."),
            ("inner reinforcement or mounting tabs", 1, "Structure", "Supports fitment and load paths."),
            ("clips, retainers, or fasteners", 1, "Fastening", "Often required during removal and installation."),
            ("trim, seal, or attached bracket", 1, "Fitment", "May transfer from the old part or require replacement."),
            ("paint and refinishing materials", 1, "Process item", "Required when the visible finish is repaired or replaced."),
        ],
    },
    {
        "match": {"lighting", "lamp", "headlamp", "tail lamp"},
        "reason": "Detected as a lighting level-1 part; second-level items separate optics, housing, light source, sealing, and mounting dependencies.",
        "children": [
            ("lens", 1, "Optical cover", "Visible lens condition drives repair or replacement choice."),
            ("lamp housing", 1, "Structure", "Holds optics, seals, and vehicle mounting points."),
            ("reflector or projector module", 1, "Optics", "Controls beam pattern and lighting performance."),
            ("bulb or LED module", 1, "Light source", "May be included, reused, or replaced separately."),
            ("mounting tabs and adjusters", 1, "Fitment", "Damage can require brackets or full assembly replacement."),
            ("rear dust cap or seal", 1, "Environmental sealing", "Prevents dust and water ingress."),
        ],
    },
    {
        "match": {"cooling", "radiator", "condenser", "intercooler"},
        "reason": "Detected as a cooling level-1 part; second-level items capture heat-exchange construction and service materials.",
        "children": [
            ("heat exchanger core", 1, "Primary component", "Main heat transfer section."),
            ("end tanks or manifolds", 1, "Fluid path", "Common leak or impact area."),
            ("mounting isolators or brackets", 1, "Fitment", "Controls positioning and vibration."),
            ("hose or line connection seals", 1, "Sealing", "Must be inspected during replacement."),
            ("fluid recharge or evacuation service", 1, "Process item", "May be required when the system is opened."),
        ],
    },
    {
        "match": {"wiring", "harness", "connector", "loom"},
        "reason": "Detected as a wiring level-1 part; second-level items capture conductors, connectors, protection, and routing hardware.",
        "children": [
            ("wire bundle or loom", 1, "Primary component", "Carries power, ground, and signal circuits."),
            ("connector shells and terminals", 1, "Vehicle interface", "Links circuits to modules and sensors."),
            ("loom tape or conduit", 1, "Protection", "Protects wires from abrasion and heat."),
            ("routing clips or anchors", 1, "Fitment", "Keeps the harness secured in the correct path."),
            ("continuity test or coding check", 1, "Process item", "Verifies repair quality after installation."),
        ],
    },
    {
        "match": {"motor", "pump", "actuator", "alternator", "starter", "compressor"},
        "reason": "Detected as an electromechanical level-1 part; second-level items capture housing, moving elements, electrical interface, seals, and test work.",
        "children": [
            ("housing", 1, "Enclosure", "Supports internal moving or electrical parts."),
            ("drive mechanism or rotating assembly", 1, "Core function", "Performs the mechanical work."),
            ("electrical connector or brush/coil set", 1, "Electrical interface", "Supplies power or control signals."),
            ("seal, bearing, or gasket", 1, "Service item", "Controls leakage, friction, or contamination."),
            ("bench test or functional test", 1, "Process item", "Confirms operation after repair or replacement."),
        ],
    },
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s/-]", " ", value.lower())).strip()


def _position_key(text: str) -> str:
    normalized = _clean_text(text)
    for position, terms in POSITION_TERMS.items():
        if any(term in normalized for term in terms):
            return position
    return "unspecified"


def _canonical_part_name(detection: PartDetection) -> str:
    text = _clean_text(f"{detection.part_name} {detection.category} {detection.minute_details}")
    for synonym, canonical in PART_SYNONYMS.items():
        if synonym in text:
            return canonical
    return _clean_text(detection.part_name)


def _bom_key(detection: PartDetection) -> str:
    part_no = _clean_text(detection.visible_part_no or "")
    if part_no:
        return f"part_no::{part_no}"
    position = _position_key(f"{detection.part_name} {detection.category} {detection.minute_details}")
    return f"{_canonical_part_name(detection)}::{position}"


def _display_name(canonical_name: str, position: str, best: PartDetection) -> str:
    if position in {"front_left", "front_right", "rear_left", "rear_right"}:
        words = position.replace("_", " ").title()
        if canonical_name not in _clean_text(best.part_name):
            return f"{words} {canonical_name}".title()
    return best.part_name


def _assembly_key(part_name: str, category: str, notes: str) -> str | None:
    text = _clean_text(f"{part_name} {category}")
    for key in ASSEMBLY_BREAKDOWN_RULES:
        if key in text:
            return key
    for synonym, canonical in PART_SYNONYMS.items():
        if synonym in text and canonical in ASSEMBLY_BREAKDOWN_RULES:
            return canonical
    return None


def _is_leaf_part(text: str) -> bool:
    return any(term in text for term in LEAF_PART_TERMS) and not any(term in text for term in ASSEMBLY_CUE_TERMS)


def _assembly_breakdown(part_name: str, category: str, notes: str) -> tuple[str, list[BomAssemblyComponent]]:
    text = _clean_text(f"{part_name} {category} {notes}")
    if _is_leaf_part(text):
        return "", []

    assembly_key = _assembly_key(part_name, category, notes)
    if assembly_key:
        rule = ASSEMBLY_BREAKDOWN_RULES[assembly_key]
        return rule["reason"], [
            BomAssemblyComponent(level=2, part_name=name, quantity=quantity, role=role, reason=reason)
            for name, quantity, role, reason in rule["children"]
        ]

    has_assembly_cue = any(term in text for term in ASSEMBLY_CUE_TERMS)
    for rule in GENERIC_BREAKDOWN_RULES:
        if has_assembly_cue and any(term in text for term in rule["match"]):
            return rule["reason"], [
                BomAssemblyComponent(level=2, part_name=name, quantity=quantity, role=role, reason=reason)
                for name, quantity, role, reason in rule["children"]
            ]

    return "", []


def consolidate_bom(detections: list[PartDetection]) -> list[BomItem]:
    groups: dict[str, list[PartDetection]] = defaultdict(list)
    for detection in detections:
        key = _bom_key(detection)
        groups[key].append(detection)

    items: list[BomItem] = []
    for key, grouped in groups.items():
        best = max(grouped, key=lambda item: item.confidence)
        part_nos = sorted({item.visible_part_no for item in grouped if item.visible_part_no})
        crops = [item.crop_url for item in grouped if item.crop_url]
        sources = sorted({item.source_image for item in grouped if item.source_image})
        conditions = sorted({item.condition for item in grouped})
        details = " ".join(item.minute_details for item in grouped[:2])
        quantity = max(1, len(part_nos)) if part_nos else 1
        canonical_name, _, position = key.partition("::")
        display_name = _display_name(canonical_name, position, best)
        assembly_reason, assembly_children = _assembly_breakdown(display_name, best.category, details)
        merge_note = (
            f" Canonical BOM key: {canonical_name.replace('part_no::', '')}"
            f" / {position or 'matched part number'}."
        )
        view_note = f" Seen across {len(sources)} uploaded view(s); repeated views were consolidated as one unique physical part."
        assembly_note = f" Second-level assembly breakdown added: {assembly_reason}" if assembly_reason else ""
        items.append(
            BomItem(
                part_name=display_name,
                category=best.category,
                material=best.material,
                condition_summary="; ".join(conditions),
                quantity=quantity,
                best_confidence=best.confidence,
                visible_part_nos=part_nos,
                crop_urls=crops,
                source_images=sources,
                notes=f"{details}{view_note}{merge_note}{assembly_note}",
                is_complete_assembly=bool(assembly_children),
                assembly_reason=assembly_reason,
                assembly_children=assembly_children,
            )
        )

    return sorted(items, key=lambda item: item.best_confidence, reverse=True)
