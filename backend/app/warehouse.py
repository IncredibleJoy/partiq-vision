from decimal import Decimal
import re
from typing import Any

from psycopg.types.json import Jsonb

from .db import get_conn
from .vector_store import EMBEDDING_DIM, embed_text_local


WAREHOUSE_SEED: list[dict[str, Any]] = [
    {
        "sku": "PIQ-BDY-FRT-BUMPER-CVR-001",
        "part_name": "Front bumper cover",
        "category": "Exterior body",
        "vehicle_system": "Body",
        "material": "Thermoplastic olefin",
        "material_grade": "TPO bumper-grade paintable",
        "condition_baseline": "new primed",
        "unit_cost": "185.00",
        "stock_quantity": 18,
        "reorder_level": 4,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["FB-CVR-001", "BPR-FT-9921"],
        "aliases": ["front bumper fascia", "bumper skin", "bumper cover"],
        "compatible_positions": ["front"],
        "minute_details": "Paintable outer bumper fascia with molded grille opening, fog lamp pockets, parking sensor knockouts, lower lip tabs, and side retainer slots.",
        "included_subparts": ["tow hook cover blank", "sensor knockout caps"],
        "consumables_required": ["paint primer", "clear coat", "panel wipe"],
        "fitment_notes": "Requires bumper absorber, reinforcement, side retainers, clips, and lower screws for complete fitment.",
    },
    {
        "sku": "PIQ-BDY-FRT-BUMPER-ABS-002",
        "part_name": "Front bumper energy absorber",
        "category": "Impact absorber",
        "vehicle_system": "Body",
        "material": "Expanded polypropylene foam",
        "material_grade": "EPP impact foam",
        "condition_baseline": "new",
        "unit_cost": "42.50",
        "stock_quantity": 32,
        "reorder_level": 8,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["EPP-ABS-FT-12"],
        "aliases": ["bumper foam", "impact absorber", "crash foam"],
        "compatible_positions": ["front"],
        "minute_details": "Foam absorber seated between bumper cover and reinforcement beam; includes locating grooves and crush zones.",
        "included_subparts": [],
        "consumables_required": [],
        "fitment_notes": "Replace after frontal impact even when bumper cover is repairable.",
    },
    {
        "sku": "PIQ-BDY-FRT-REINF-BEAM-003",
        "part_name": "Front bumper reinforcement beam",
        "category": "Structural body",
        "vehicle_system": "Body",
        "material": "High strength steel",
        "material_grade": "HSLA galvanized",
        "condition_baseline": "new e-coated",
        "unit_cost": "126.75",
        "stock_quantity": 11,
        "reorder_level": 3,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["REINF-FRT-778"],
        "aliases": ["bumper bar", "crash beam", "reinforcement bar"],
        "compatible_positions": ["front"],
        "minute_details": "Stamped steel cross beam with boxed section, mounting flanges, crush-can interfaces, and corrosion protection coating.",
        "included_subparts": ["left mounting plate", "right mounting plate"],
        "consumables_required": ["anti-corrosion wax"],
        "fitment_notes": "Check frame rail/crash box alignment before installation.",
    },
    {
        "sku": "PIQ-LGT-HEADLAMP-LH-004",
        "part_name": "Left headlamp assembly",
        "category": "Lighting",
        "vehicle_system": "Electrical",
        "material": "Polycarbonate lens and ABS housing",
        "material_grade": "UV hard-coated lens",
        "condition_baseline": "new sealed",
        "unit_cost": "214.90",
        "stock_quantity": 9,
        "reorder_level": 3,
        "supplier": "Synthetic Lighting Parts",
        "visible_part_nos": ["HL-LH-404A", "LAMP-L-88"],
        "aliases": ["left headlight", "LH headlamp", "driver side lamp"],
        "compatible_positions": ["front left"],
        "minute_details": "Clear polycarbonate lens, reflector/projector bowl, adjuster screws, rear dust caps, DRL guide, lower locator pin, and mounting tabs.",
        "included_subparts": ["rear dust cap", "manual adjuster", "locator bracket"],
        "consumables_required": ["dielectric grease"],
        "fitment_notes": "Inspect wiring connector and upper/lower mounting brackets after impact.",
    },
    {
        "sku": "PIQ-LGT-HEADLAMP-RH-005",
        "part_name": "Right headlamp assembly",
        "category": "Lighting",
        "vehicle_system": "Electrical",
        "material": "Polycarbonate lens and ABS housing",
        "material_grade": "UV hard-coated lens",
        "condition_baseline": "new sealed",
        "unit_cost": "214.90",
        "stock_quantity": 10,
        "reorder_level": 3,
        "supplier": "Synthetic Lighting Parts",
        "visible_part_nos": ["HL-RH-405A", "LAMP-R-88"],
        "aliases": ["right headlight", "RH headlamp", "passenger side lamp"],
        "compatible_positions": ["front right"],
        "minute_details": "Clear polycarbonate lens, reflector/projector bowl, adjuster screws, rear dust caps, DRL guide, lower locator pin, and mounting tabs.",
        "included_subparts": ["rear dust cap", "manual adjuster", "locator bracket"],
        "consumables_required": ["dielectric grease"],
        "fitment_notes": "Inspect wiring connector and upper/lower mounting brackets after impact.",
    },
    {
        "sku": "PIQ-BDY-HOOD-PANEL-006",
        "part_name": "Bonnet hood panel",
        "category": "Exterior body",
        "vehicle_system": "Body",
        "material": "Aluminum sheet",
        "material_grade": "AA6016 paintable",
        "condition_baseline": "new e-coated",
        "unit_cost": "295.00",
        "stock_quantity": 7,
        "reorder_level": 2,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["HD-PNL-6016"],
        "aliases": ["hood", "bonnet", "engine hood"],
        "compatible_positions": ["front upper"],
        "minute_details": "Outer and inner crimped aluminum panel with latch striker reinforcement, hinge pads, washer nozzle holes, and mastic points.",
        "included_subparts": [],
        "consumables_required": ["panel adhesive", "seam sealer", "paint materials"],
        "fitment_notes": "Transfer insulation pad, washer hose, nozzles, striker, and hinges when reusable.",
    },
    {
        "sku": "PIQ-BDY-GRILLE-ASSY-007",
        "part_name": "Radiator grille assembly",
        "category": "Exterior trim",
        "vehicle_system": "Body",
        "material": "ABS plastic",
        "material_grade": "chrome plated ABS",
        "condition_baseline": "new",
        "unit_cost": "96.40",
        "stock_quantity": 14,
        "reorder_level": 4,
        "supplier": "Synthetic Trim Parts",
        "visible_part_nos": ["GRL-RAD-77"],
        "aliases": ["front grille", "radiator grille", "grill assembly"],
        "compatible_positions": ["front center"],
        "minute_details": "Upper grille with honeycomb mesh, chrome surround, emblem land, latch access opening, and snap-fit tabs.",
        "included_subparts": ["emblem pad", "upper tab clips"],
        "consumables_required": [],
        "fitment_notes": "May require separate emblem, camera bracket, and upper fasteners.",
    },
    {
        "sku": "PIQ-CLP-BUMPER-PUSH-008",
        "part_name": "Bumper push clip set",
        "category": "Fastener",
        "vehicle_system": "Body",
        "material": "Nylon 66",
        "material_grade": "black automotive nylon",
        "condition_baseline": "new",
        "unit_cost": "8.75",
        "stock_quantity": 160,
        "reorder_level": 40,
        "supplier": "Synthetic Fastener Bin",
        "visible_part_nos": ["CLP-8MM-BLK"],
        "aliases": ["bumper clips", "push rivets", "plastic retainers"],
        "compatible_positions": ["front", "rear", "wheel arch"],
        "minute_details": "8 mm reusable-style push rivets for bumper cover, splash shield, and wheel arch liner retention.",
        "included_subparts": ["20 clips per pack"],
        "consumables_required": [],
        "fitment_notes": "Always add clips when bumper or liner is removed because impact and age often break retainers.",
    },
    {
        "sku": "PIQ-FST-M6-FLANGE-SCREW-009",
        "part_name": "M6 flange screw set",
        "category": "Fastener",
        "vehicle_system": "Body",
        "material": "Zinc plated steel",
        "material_grade": "class 8.8",
        "condition_baseline": "new",
        "unit_cost": "6.40",
        "stock_quantity": 240,
        "reorder_level": 60,
        "supplier": "Synthetic Fastener Bin",
        "visible_part_nos": ["M6X20-FLG-ZN"],
        "aliases": ["bumper screws", "flange bolts", "undertray screws"],
        "compatible_positions": ["front lower", "underbody"],
        "minute_details": "M6 x 20 mm flange-head screws used for undertray, bumper lower lip, brackets, and splash shield mounting.",
        "included_subparts": ["12 screws per pack"],
        "consumables_required": ["anti-seize compound"],
        "fitment_notes": "Use correct torque to avoid stripping plastic inserts or speed nuts.",
    },
    {
        "sku": "PIQ-FST-WASHER-M6-010",
        "part_name": "M6 body washer pack",
        "category": "Fastener",
        "vehicle_system": "Body",
        "material": "Zinc plated steel",
        "material_grade": "wide OD washer",
        "condition_baseline": "new",
        "unit_cost": "3.85",
        "stock_quantity": 300,
        "reorder_level": 70,
        "supplier": "Synthetic Fastener Bin",
        "visible_part_nos": ["WSH-M6-WIDE"],
        "aliases": ["body washers", "wide washers", "panel washers"],
        "compatible_positions": ["bumper", "fender", "undertray"],
        "minute_details": "Wide outside-diameter flat washers for plastic panel load spreading and bracket retention.",
        "included_subparts": ["20 washers per pack"],
        "consumables_required": [],
        "fitment_notes": "Recommended for cracked bumper tabs and splash shield mounting repairs.",
    },
    {
        "sku": "PIQ-ELEC-FRT-HARNESS-011",
        "part_name": "Front bumper wiring harness",
        "category": "Wiring",
        "vehicle_system": "Electrical",
        "material": "Copper wire with PVC insulation",
        "material_grade": "automotive TXL wire",
        "condition_baseline": "new",
        "unit_cost": "72.30",
        "stock_quantity": 13,
        "reorder_level": 4,
        "supplier": "Synthetic Electrical Parts",
        "visible_part_nos": ["HRN-FRT-BPR-11"],
        "aliases": ["bumper harness", "sensor wiring", "front harness"],
        "compatible_positions": ["front bumper"],
        "minute_details": "Branch harness with loom tape, parking sensor connectors, fog lamp connectors, temperature sensor plug, grounding eyelet, and clip anchors.",
        "included_subparts": ["loom clips", "ground eyelet"],
        "consumables_required": ["cloth harness tape", "dielectric grease"],
        "fitment_notes": "Check connector locks and chafing near impact zone before reuse.",
    },
    {
        "sku": "PIQ-SNS-PARK-012",
        "part_name": "Parking sensor",
        "category": "Sensor",
        "vehicle_system": "Electrical",
        "material": "Paintable plastic housing",
        "material_grade": "ultrasonic transducer module",
        "condition_baseline": "new paintable",
        "unit_cost": "34.20",
        "stock_quantity": 36,
        "reorder_level": 8,
        "supplier": "Synthetic Electrical Parts",
        "visible_part_nos": ["PDC-SNS-4P"],
        "aliases": ["PDC sensor", "bumper sensor", "ultrasonic sensor"],
        "compatible_positions": ["front bumper", "rear bumper"],
        "minute_details": "Four-pin ultrasonic parking distance sensor with paintable cap, indexing key, sealing ring, and clip-lock body.",
        "included_subparts": ["rubber sealing ring"],
        "consumables_required": ["dielectric grease", "paint materials"],
        "fitment_notes": "Requires matching bracket and calibration on some vehicles.",
    },
    {
        "sku": "PIQ-HVAC-RADIATOR-013",
        "part_name": "Radiator assembly",
        "category": "Cooling",
        "vehicle_system": "Powertrain cooling",
        "material": "Aluminum core with plastic tanks",
        "material_grade": "brazed aluminum",
        "condition_baseline": "new pressure tested",
        "unit_cost": "148.60",
        "stock_quantity": 8,
        "reorder_level": 3,
        "supplier": "Synthetic Cooling Parts",
        "visible_part_nos": ["RAD-ALU-26"],
        "aliases": ["engine radiator", "cooling radiator", "radiator core"],
        "compatible_positions": ["front cooling pack"],
        "minute_details": "Aluminum tube-fin core with crimped plastic tanks, upper/lower hose necks, drain plug, fan shroud mounts, and isolator pins.",
        "included_subparts": ["drain plug", "rubber isolators"],
        "consumables_required": ["coolant", "hose clamp"],
        "fitment_notes": "Pressure test after installation and inspect condenser clearance.",
    },
    {
        "sku": "PIQ-HVAC-CONDENSER-014",
        "part_name": "A/C condenser",
        "category": "Cooling",
        "vehicle_system": "HVAC",
        "material": "Aluminum",
        "material_grade": "parallel-flow condenser",
        "condition_baseline": "new sealed",
        "unit_cost": "132.80",
        "stock_quantity": 6,
        "reorder_level": 2,
        "supplier": "Synthetic Cooling Parts",
        "visible_part_nos": ["COND-AC-14"],
        "aliases": ["aircon condenser", "AC condenser", "condenser core"],
        "compatible_positions": ["front cooling pack"],
        "minute_details": "Parallel-flow aluminum condenser with receiver/drier tube, mounting tabs, line ports, and protective shipping plugs.",
        "included_subparts": ["receiver drier", "port plugs"],
        "consumables_required": ["PAG oil", "R134a refrigerant", "O-ring kit"],
        "fitment_notes": "Evacuate and recharge A/C system after replacement.",
    },
    {
        "sku": "PIQ-FLD-COOLANT-015",
        "part_name": "Long life coolant",
        "category": "Fluid",
        "vehicle_system": "Powertrain cooling",
        "material": "Ethylene glycol premix",
        "material_grade": "50/50 OAT coolant",
        "condition_baseline": "new sealed",
        "unit_cost": "18.95",
        "stock_quantity": 80,
        "reorder_level": 20,
        "supplier": "Synthetic Consumables",
        "visible_part_nos": ["COOL-OAT-1GAL"],
        "aliases": ["engine coolant", "antifreeze", "radiator coolant"],
        "compatible_positions": ["cooling system"],
        "minute_details": "One gallon premixed organic-acid coolant used after radiator, hose, thermostat, or cooling pack repair.",
        "included_subparts": [],
        "consumables_required": [],
        "fitment_notes": "Match coolant specification and bleed air pockets after refill.",
    },
    {
        "sku": "PIQ-FLD-ENGINE-OIL-016",
        "part_name": "Synthetic engine oil 5W-30",
        "category": "Fluid",
        "vehicle_system": "Powertrain lubrication",
        "material": "Synthetic base oil",
        "material_grade": "API SP 5W-30",
        "condition_baseline": "new sealed",
        "unit_cost": "31.50",
        "stock_quantity": 95,
        "reorder_level": 24,
        "supplier": "Synthetic Consumables",
        "visible_part_nos": ["OIL-5W30-SP"],
        "aliases": ["engine oil", "motor oil", "lubricant"],
        "compatible_positions": ["engine"],
        "minute_details": "Five-quart synthetic oil container for oil service after engine bay repair, oil cooler damage, or leakage.",
        "included_subparts": [],
        "consumables_required": ["oil drain washer"],
        "fitment_notes": "Use vehicle-specific viscosity and capacity.",
    },
    {
        "sku": "PIQ-FLD-GREASE-017",
        "part_name": "White lithium grease",
        "category": "Consumable",
        "vehicle_system": "Body",
        "material": "Lithium soap grease",
        "material_grade": "NLGI 2",
        "condition_baseline": "new tube",
        "unit_cost": "7.25",
        "stock_quantity": 52,
        "reorder_level": 12,
        "supplier": "Synthetic Consumables",
        "visible_part_nos": ["GRS-LITH-WHT"],
        "aliases": ["hinge grease", "latch grease", "assembly grease"],
        "compatible_positions": ["hood latch", "door hinge", "seat track"],
        "minute_details": "Multipurpose grease for hood latch, hinges, striker points, seat tracks, and sliding brackets.",
        "included_subparts": [],
        "consumables_required": [],
        "fitment_notes": "Apply thin film after alignment and wipe excess from painted surfaces.",
    },
    {
        "sku": "PIQ-BDY-FENDER-LH-018",
        "part_name": "Left front fender panel",
        "category": "Exterior body",
        "vehicle_system": "Body",
        "material": "Mild steel sheet",
        "material_grade": "galvanized paintable",
        "condition_baseline": "new e-coated",
        "unit_cost": "118.00",
        "stock_quantity": 12,
        "reorder_level": 3,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["FND-LH-18"],
        "aliases": ["left wing", "left fender", "driver side fender"],
        "compatible_positions": ["front left"],
        "minute_details": "Stamped front fender with wheel arch lip, bumper bracket holes, rocker flange, A-pillar edge, and headlamp side gap flange.",
        "included_subparts": [],
        "consumables_required": ["paint materials", "seam sealer", "anti-corrosion wax"],
        "fitment_notes": "Requires liner clips, bumper side bracket, and alignment with hood and door gaps.",
    },
    {
        "sku": "PIQ-BDY-FENDER-RH-019",
        "part_name": "Right front fender panel",
        "category": "Exterior body",
        "vehicle_system": "Body",
        "material": "Mild steel sheet",
        "material_grade": "galvanized paintable",
        "condition_baseline": "new e-coated",
        "unit_cost": "118.00",
        "stock_quantity": 12,
        "reorder_level": 3,
        "supplier": "Synthetic OEM Warehouse",
        "visible_part_nos": ["FND-RH-19"],
        "aliases": ["right wing", "right fender", "passenger side fender"],
        "compatible_positions": ["front right"],
        "minute_details": "Stamped front fender with wheel arch lip, bumper bracket holes, rocker flange, A-pillar edge, and headlamp side gap flange.",
        "included_subparts": [],
        "consumables_required": ["paint materials", "seam sealer", "anti-corrosion wax"],
        "fitment_notes": "Requires liner clips, bumper side bracket, and alignment with hood and door gaps.",
    },
    {
        "sku": "PIQ-SPLASH-LINER-LH-020",
        "part_name": "Left front wheel arch liner",
        "category": "Underbody shield",
        "vehicle_system": "Body",
        "material": "Polypropylene",
        "material_grade": "textured PP",
        "condition_baseline": "new",
        "unit_cost": "36.90",
        "stock_quantity": 22,
        "reorder_level": 5,
        "supplier": "Synthetic Trim Parts",
        "visible_part_nos": ["LINER-LH-FRT"],
        "aliases": ["fender liner", "splash liner", "wheel liner"],
        "compatible_positions": ["front left wheel arch"],
        "minute_details": "Molded splash liner with screw bosses, clip holes, brake duct opening, and bumper edge overlap.",
        "included_subparts": [],
        "consumables_required": ["push clips", "M6 screws"],
        "fitment_notes": "Often replaced with bumper clips after front corner damage.",
    },
    {
        "sku": "PIQ-WHL-ALLOY-LH-021",
        "part_name": "Front-left alloy wheel rim",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Cast aluminum alloy",
        "material_grade": "painted machined alloy",
        "condition_baseline": "new balanced",
        "unit_cost": "168.50",
        "stock_quantity": 16,
        "reorder_level": 4,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["ALY-RIM-FL-17"],
        "aliases": ["alloy wheel", "front left rim", "wheel rim", "road wheel"],
        "compatible_positions": ["front left", "front", "wheel hub"],
        "minute_details": "Cast alloy rim with spoke face, bead seat, valve stem hole, center bore, lug nut holes, painted/machined finish, and balance weight area.",
        "included_subparts": ["center cap"],
        "consumables_required": ["wheel weights", "valve stem"],
        "fitment_notes": "Verify rim diameter, width, offset, PCD, center bore, TPMS compatibility, and lug nut seat type.",
    },
    {
        "sku": "PIQ-WHL-TIRE-ASSY-022",
        "part_name": "Tire with alloy wheel assembly",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Rubber tire with aluminum alloy rim",
        "material_grade": "radial tire on alloy rim",
        "condition_baseline": "new mounted",
        "unit_cost": "236.00",
        "stock_quantity": 14,
        "reorder_level": 4,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["TIRE-ALY-ASSY-17"],
        "aliases": ["wheel assembly", "tire assembly", "tyre assembly", "alloy wheel and tire"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Mounted road wheel assembly including tire tread, sidewall, alloy rim, bead interface, valve stem, center cap location, lug holes, and balance weights.",
        "included_subparts": ["alloy rim", "tire", "valve stem"],
        "consumables_required": ["wheel weights", "bead lubricant"],
        "fitment_notes": "Match tire size, load index, speed rating, rim offset, bolt pattern, and TPMS requirements before costing.",
    },
    {
        "sku": "PIQ-WHL-TPMS-023",
        "part_name": "TPMS valve sensor",
        "category": "Wheel and tire",
        "vehicle_system": "Electrical",
        "material": "Plastic sensor body with aluminum valve stem",
        "material_grade": "315/433 MHz TPMS module",
        "condition_baseline": "new programmed",
        "unit_cost": "38.75",
        "stock_quantity": 38,
        "reorder_level": 8,
        "supplier": "Synthetic Electrical Parts",
        "visible_part_nos": ["TPMS-VLV-23"],
        "aliases": ["tire pressure sensor", "tyre pressure sensor", "valve sensor", "wheel sensor"],
        "compatible_positions": ["wheel", "tire valve"],
        "minute_details": "Wheel-mounted pressure sensor with valve stem, sealing grommet, retaining nut, cap, and programmable sensor body.",
        "included_subparts": ["sealing grommet", "valve cap", "retaining nut"],
        "consumables_required": ["TPMS service kit"],
        "fitment_notes": "Program sensor ID and relearn vehicle after tire or wheel replacement.",
    },
    {
        "sku": "PIQ-WHL-STEEL-RIM-024",
        "part_name": "Steel wheel rim",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Pressed steel",
        "material_grade": "painted steel wheel",
        "condition_baseline": "new painted",
        "unit_cost": "74.50",
        "stock_quantity": 34,
        "reorder_level": 8,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["STL-RIM-16"],
        "aliases": ["steel wheel", "steel rim", "road wheel", "plain wheel"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right", "spare"],
        "minute_details": "Pressed steel rim with bead seat, valve hole, center bore, lug holes, painted face, rim flange, and balancing weight edges.",
        "included_subparts": [],
        "consumables_required": ["wheel weights", "valve stem"],
        "fitment_notes": "Verify diameter, rim width, PCD, offset, center bore, and wheel cover compatibility.",
    },
    {
        "sku": "PIQ-WHL-ALLOY-RIM-025",
        "part_name": "Machined alloy wheel rim",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Aluminum alloy",
        "material_grade": "diamond-cut machined alloy",
        "condition_baseline": "new clear coated",
        "unit_cost": "192.00",
        "stock_quantity": 18,
        "reorder_level": 5,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["ALY-RIM-MCH-18"],
        "aliases": ["machined alloy wheel", "diamond cut alloy", "alloy rim", "premium wheel"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Machined alloy rim with clear-coated spoke face, lug seats, valve stem hole, center cap bore, bead seat, and offset casting marks.",
        "included_subparts": ["center cap"],
        "consumables_required": ["wheel weights", "valve stem"],
        "fitment_notes": "Inspect for curb rash, cracks, bent rim lip, clear-coat lift, and TPMS valve compatibility.",
    },
    {
        "sku": "PIQ-WHL-SPACE-SAVER-026",
        "part_name": "Space saver spare wheel assembly",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Rubber tire with steel rim",
        "material_grade": "temporary-use compact spare",
        "condition_baseline": "new inflated",
        "unit_cost": "118.00",
        "stock_quantity": 21,
        "reorder_level": 5,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["SPARE-TEMP-16"],
        "aliases": ["temporary spare", "space saver wheel", "donut spare", "compact spare"],
        "compatible_positions": ["trunk spare well", "temporary wheel"],
        "minute_details": "Compact spare tire mounted on narrow steel rim with high-pressure sidewall, warning label, valve stem, lug holes, and hub bore.",
        "included_subparts": ["temporary spare tire", "steel spare rim"],
        "consumables_required": [],
        "fitment_notes": "Use only as temporary replacement; verify rolling diameter, bolt pattern, inflation pressure, and speed restriction.",
    },
    {
        "sku": "PIQ-TYR-ALL-SEASON-027",
        "part_name": "All-season radial tire",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Synthetic rubber compound",
        "material_grade": "touring all-season radial",
        "condition_baseline": "new unmounted",
        "unit_cost": "104.00",
        "stock_quantity": 48,
        "reorder_level": 12,
        "supplier": "Synthetic Tire Depot",
        "visible_part_nos": ["TYR-AS-20555R16"],
        "aliases": ["all season tire", "all-season tyre", "radial tire", "touring tire"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Passenger radial tire with circumferential grooves, siped tread blocks, sidewall size marking, bead bundle, load index, and speed rating.",
        "included_subparts": [],
        "consumables_required": ["valve stem", "wheel weights", "bead lubricant"],
        "fitment_notes": "Match tire size, load index, speed rating, tread pattern axle pairing, and manufacturer fitment guidance.",
    },
    {
        "sku": "PIQ-TYR-SUMMER-028",
        "part_name": "Summer performance tire",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Silica rubber compound",
        "material_grade": "performance summer radial",
        "condition_baseline": "new unmounted",
        "unit_cost": "138.00",
        "stock_quantity": 30,
        "reorder_level": 8,
        "supplier": "Synthetic Tire Depot",
        "visible_part_nos": ["TYR-SUM-22545R17"],
        "aliases": ["summer tire", "performance tyre", "sport tire", "low profile tire"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Low-profile summer tire with asymmetric tread, reinforced shoulder blocks, sidewall size marking, rim protector lip, and directional fitment markings.",
        "included_subparts": [],
        "consumables_required": ["valve stem", "wheel weights", "bead lubricant"],
        "fitment_notes": "Check rim width, speed rating, load index, rotation direction, and avoid winter temperature use.",
    },
    {
        "sku": "PIQ-TYR-WINTER-029",
        "part_name": "Winter snow tire",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Cold-weather rubber compound",
        "material_grade": "siped winter radial",
        "condition_baseline": "new unmounted",
        "unit_cost": "126.00",
        "stock_quantity": 26,
        "reorder_level": 7,
        "supplier": "Synthetic Tire Depot",
        "visible_part_nos": ["TYR-WIN-21560R16"],
        "aliases": ["winter tire", "snow tyre", "cold weather tire", "siped tire"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Winter tire with dense siping, deep tread grooves, snow traction blocks, three-peak mountain marking, sidewall size, and bead area.",
        "included_subparts": [],
        "consumables_required": ["valve stem", "wheel weights", "bead lubricant"],
        "fitment_notes": "Install as complete axle or vehicle set; verify speed rating, load index, and seasonal fitment rules.",
    },
    {
        "sku": "PIQ-TYR-RUN-FLAT-030",
        "part_name": "Run-flat tire",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Reinforced rubber compound",
        "material_grade": "self-supporting run-flat radial",
        "condition_baseline": "new unmounted",
        "unit_cost": "172.00",
        "stock_quantity": 19,
        "reorder_level": 5,
        "supplier": "Synthetic Tire Depot",
        "visible_part_nos": ["TYR-RFT-22550R17"],
        "aliases": ["run flat tire", "run-flat tyre", "self supporting tire", "reinforced sidewall tire"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "Run-flat radial with reinforced sidewalls, heat-resistant bead area, sidewall RFT marking, tread grooves, and load/speed markings.",
        "included_subparts": [],
        "consumables_required": ["TPMS service kit", "wheel weights", "bead lubricant"],
        "fitment_notes": "Use only on compatible vehicles with TPMS; check rim profile, load index, speed rating, and axle matching.",
    },
    {
        "sku": "PIQ-TYR-AT-031",
        "part_name": "All-terrain SUV tire",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Reinforced rubber compound",
        "material_grade": "all-terrain radial",
        "condition_baseline": "new unmounted",
        "unit_cost": "156.00",
        "stock_quantity": 24,
        "reorder_level": 6,
        "supplier": "Synthetic Tire Depot",
        "visible_part_nos": ["TYR-AT-26565R17"],
        "aliases": ["all terrain tire", "SUV tire", "off road tire", "A/T tyre"],
        "compatible_positions": ["front left", "front right", "rear left", "rear right"],
        "minute_details": "All-terrain tire with aggressive shoulder lugs, deep void tread pattern, reinforced sidewall, bead protector, load range marking, and traction blocks.",
        "included_subparts": [],
        "consumables_required": ["valve stem", "wheel weights", "bead lubricant"],
        "fitment_notes": "Verify wheel well clearance, load range, rolling diameter, speed rating, and spare tire match.",
    },
    {
        "sku": "PIQ-WHL-COVER-032",
        "part_name": "Wheel cover hubcap",
        "category": "Wheel and tire",
        "vehicle_system": "Body",
        "material": "ABS plastic",
        "material_grade": "painted silver ABS",
        "condition_baseline": "new",
        "unit_cost": "22.00",
        "stock_quantity": 64,
        "reorder_level": 14,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["HUBCAP-16-SLV"],
        "aliases": ["hubcap", "wheel cover", "rim cover", "plastic wheel trim"],
        "compatible_positions": ["steel wheel", "front left", "front right", "rear left", "rear right"],
        "minute_details": "Plastic wheel cover with retaining ring, spoke-style face, valve stem clearance, snap clips, outer lip, and painted finish.",
        "included_subparts": ["retaining ring"],
        "consumables_required": [],
        "fitment_notes": "Match wheel diameter and clip style; inspect retaining clips after curb impact.",
    },
    {
        "sku": "PIQ-WHL-LUG-NUT-033",
        "part_name": "Wheel lug nut set",
        "category": "Wheel and tire",
        "vehicle_system": "Chassis",
        "material": "Chrome plated steel",
        "material_grade": "conical seat wheel nut",
        "condition_baseline": "new",
        "unit_cost": "18.50",
        "stock_quantity": 110,
        "reorder_level": 25,
        "supplier": "Synthetic Wheel Depot",
        "visible_part_nos": ["LUG-M12-15"],
        "aliases": ["lug nuts", "wheel nuts", "alloy wheel nuts", "wheel fasteners"],
        "compatible_positions": ["wheel hub", "alloy wheel", "steel wheel"],
        "minute_details": "Set of chrome plated wheel lug nuts with conical seat, threaded bore, hex drive, corrosion-resistant finish, and wheel retention profile.",
        "included_subparts": ["20 lug nuts per set"],
        "consumables_required": ["anti-seize compound"],
        "fitment_notes": "Match thread pitch, seat type, shank length, torque specification, and wheel material.",
    },
    {
        "sku": "PIQ-GLS-WINDSHIELD-034",
        "part_name": "Windshield glass",
        "category": "Glass",
        "vehicle_system": "Body",
        "material": "Laminated safety glass",
        "material_grade": "acoustic laminated",
        "condition_baseline": "new",
        "unit_cost": "240.00",
        "stock_quantity": 5,
        "reorder_level": 2,
        "supplier": "Synthetic Glass Parts",
        "visible_part_nos": ["WS-ACOUSTIC-34"],
        "aliases": ["front glass", "windscreen", "laminated glass"],
        "compatible_positions": ["front cabin"],
        "minute_details": "Laminated windshield with ceramic frit band, mirror mount pad, VIN window, and rain sensor bracket land.",
        "included_subparts": ["mirror mount pad"],
        "consumables_required": ["urethane adhesive", "glass primer", "pinchweld primer"],
        "fitment_notes": "ADAS camera calibration may be required after replacement.",
    },
    {
        "sku": "PIQ-ADH-SEAM-SEALER-035",
        "part_name": "Automotive seam sealer",
        "category": "Consumable",
        "vehicle_system": "Body",
        "material": "MS polymer sealant",
        "material_grade": "paintable body sealer",
        "condition_baseline": "new cartridge",
        "unit_cost": "14.80",
        "stock_quantity": 44,
        "reorder_level": 10,
        "supplier": "Synthetic Consumables",
        "visible_part_nos": ["SEAL-BODY-MS"],
        "aliases": ["body sealer", "joint sealer", "panel seam sealer"],
        "compatible_positions": ["body panels", "floor pan", "fender seams"],
        "minute_details": "Paintable seam sealer cartridge for panel joints, fender flanges, wheel wells, and repaired crimp seams.",
        "included_subparts": ["applicator nozzle"],
        "consumables_required": [],
        "fitment_notes": "Apply over clean primed metal and reproduce factory bead shape where visible.",
    },
]

WAREHOUSE_TARGET_SIZE = 2500
WAREHOUSE_VECTOR_VERSION = "local-token-cluster-v5"

WAREHOUSE_FAMILY_TERMS = {
    "wheel_tire": {
        "wheel",
        "wheels",
        "tire",
        "tires",
        "tyre",
        "tyres",
        "alloy",
        "steel",
        "rim",
        "rims",
        "tpms",
        "hubcap",
        "lug",
        "nuts",
        "spare",
        "summer",
        "winter",
        "snow",
        "season",
        "terrain",
        "run",
        "flat",
    },
    "grille": {"grille", "grill"},
    "bumper": {"bumper", "fascia", "absorber", "reinforcement"},
    "lighting": {"headlamp", "headlight", "lamp", "lighting", "drl"},
    "fender": {"fender", "wing"},
    "glass": {"windshield", "windscreen", "glass"},
    "cooling": {"radiator", "coolant", "condenser", "fan"},
    "fastener": {"clip", "clips", "screw", "screws", "bolt", "washer", "fastener", "rivet"},
    "wiring": {"wire", "wiring", "harness", "connector"},
}

WAREHOUSE_PLATFORMS = [
    "compact hatchback",
    "mid-size sedan",
    "executive sedan",
    "compact SUV",
    "mid-size SUV",
    "full-size SUV",
    "pickup truck",
    "electric crossover",
    "hybrid sedan",
    "premium coupe",
    "commercial van",
    "small city car",
    "performance hatch",
    "luxury SUV",
    "fleet taxi sedan",
    "off-road utility",
]

WAREHOUSE_TRIMS = [
    "base",
    "comfort",
    "sport",
    "premium",
    "limited",
    "fleet",
    "hybrid",
    "EV",
    "ADAS",
    "chrome",
    "black pack",
    "export",
]

WAREHOUSE_SUPPLIERS = [
    "Synthetic OEM Warehouse",
    "Synthetic Aftermarket Hub",
    "Synthetic Collision Parts",
    "Synthetic Fastener Bin",
    "Synthetic Electrical Parts",
    "Synthetic Consumables",
    "Synthetic Regional Depot",
]


def _cluster_key(part: dict[str, Any]) -> str:
    material_family = part["material"].split()[0].lower()
    return f"{part['vehicle_system'].lower()}::{part['category'].lower()}::{material_family}"


def _embedding_content(part: dict[str, Any]) -> str:
    fields = [
        part["sku"],
        part["part_name"],
        part["category"],
        part["vehicle_system"],
        part["material"],
        part["material_grade"],
        part["condition_baseline"],
        " ".join(part["visible_part_nos"]),
        " ".join(part["aliases"]),
        " ".join(part["compatible_positions"]),
        part["minute_details"],
        " ".join(part["included_subparts"]),
        " ".join(part["consumables_required"]),
        part["fitment_notes"],
    ]
    return " | ".join(fields)


def _query_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _query_families(text: str) -> set[str]:
    tokens = _query_tokens(text)
    return {
        family
        for family, terms in WAREHOUSE_FAMILY_TERMS.items()
        if tokens.intersection(terms)
    }


def _family_terms(families: set[str]) -> set[str]:
    terms: set[str] = set()
    for family in families:
        terms.update(WAREHOUSE_FAMILY_TERMS[family])
    return terms


def _lexical_similarity(query: str, content: str) -> float:
    query_tokens = _query_tokens(query)
    content_tokens = _query_tokens(content)
    if not query_tokens or not content_tokens:
        return 0
    return len(query_tokens.intersection(content_tokens)) / max(1, len(query_tokens))


def _expanded_seed_parts() -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    index = 0
    while len(parts) < WAREHOUSE_TARGET_SIZE:
        base = WAREHOUSE_SEED[index % len(WAREHOUSE_SEED)]
        platform = WAREHOUSE_PLATFORMS[(index // len(WAREHOUSE_SEED)) % len(WAREHOUSE_PLATFORMS)]
        trim = WAREHOUSE_TRIMS[(index // (len(WAREHOUSE_SEED) * len(WAREHOUSE_PLATFORMS))) % len(WAREHOUSE_TRIMS)]
        supplier = base["supplier"]
        variant_no = index + 1
        cost_multiplier = Decimal("0.82") + (Decimal(index % 37) * Decimal("0.011"))
        part = {**base}
        part["sku"] = f"{base['sku']}-SYN-{variant_no:04d}"
        part["part_name"] = f"{base['part_name']} ({platform}, {trim})"
        part["unit_cost"] = str((Decimal(base["unit_cost"]) * cost_multiplier).quantize(Decimal("0.01")))
        part["stock_quantity"] = 2 + ((index * 13) % 185)
        part["reorder_level"] = 2 + ((index * 5) % 24)
        part["supplier"] = supplier
        part["visible_part_nos"] = [
            *base["visible_part_nos"],
            f"PIQ-SYN-{variant_no:05d}",
            f"{platform[:3].upper().replace(' ', '')}-{trim[:3].upper()}-{variant_no:04d}",
        ]
        part["aliases"] = [
            *base["aliases"],
            platform,
            trim,
            f"{base['part_name']} replacement",
            f"{base['category']} spare",
        ]
        part["compatible_positions"] = [
            *base["compatible_positions"],
            platform,
            trim,
        ]
        part["minute_details"] = (
            f"{base['minute_details']} Synthetic warehouse variant for {platform} {trim} fitment; "
            f"captures estimating notes, alternate supplier geometry, clip locations, finish constraints, "
            f"and compatibility tags for clustering search."
        )
        part["fitment_notes"] = (
            f"{base['fitment_notes']} Variant profile {variant_no:04d}; verify VIN, model year, trim package, "
            f"mounting points, connector count, and paint/finish before final cost sheet approval."
        )
        parts.append(part)
        index += 1
    return parts


def _vector_literal(text: str) -> str:
    embedding = embed_text_local(text)
    return "[" + ",".join(f"{value:.8f}" for value in embedding[:EMBEDDING_DIM]) + "]"


def seed_warehouse() -> int:
    inserted = 0
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) AS count FROM warehouse_parts").fetchone()
        metadata = conn.execute(
            "SELECT value FROM app_metadata WHERE key = 'warehouse_vector_version'"
        ).fetchone()
        if (
            existing
            and existing["count"] == WAREHOUSE_TARGET_SIZE
            and metadata
            and metadata["value"] == WAREHOUSE_VECTOR_VERSION
        ):
            return 0

        if existing and existing["count"] > 0:
            conn.execute("DELETE FROM warehouse_parts")

        for raw_part in _expanded_seed_parts():
            part = {**raw_part}
            part["cluster_key"] = _cluster_key(part)
            part["embedding_content"] = _embedding_content(part)
            conn.execute(
                """
                INSERT INTO warehouse_parts (
                  sku, part_name, category, vehicle_system, material, material_grade,
                  condition_baseline, unit_cost, currency, stock_quantity, reorder_level,
                  supplier, cluster_key, visible_part_nos, aliases, compatible_positions,
                  minute_details, included_subparts, consumables_required, fitment_notes,
                  embedding_content
                )
                VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, 'USD', %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (sku) DO NOTHING
                """,
                (
                    part["sku"],
                    part["part_name"],
                    part["category"],
                    part["vehicle_system"],
                    part["material"],
                    part["material_grade"],
                    part["condition_baseline"],
                    Decimal(part["unit_cost"]),
                    part["stock_quantity"],
                    part["reorder_level"],
                    part["supplier"],
                    part["cluster_key"],
                    Jsonb(part["visible_part_nos"]),
                    Jsonb(part["aliases"]),
                    Jsonb(part["compatible_positions"]),
                    part["minute_details"],
                    Jsonb(part["included_subparts"]),
                    Jsonb(part["consumables_required"]),
                    part["fitment_notes"],
                    part["embedding_content"],
                ),
            )
            conn.execute(
                """
                INSERT INTO warehouse_part_vectors (sku, embedding)
                VALUES (%s, %s::vector)
                ON CONFLICT (sku) DO UPDATE
                SET embedding = EXCLUDED.embedding, updated_at = NOW()
                """,
                (part["sku"], _vector_literal(part["embedding_content"])),
            )
            inserted += 1
        conn.execute(
            """
            INSERT INTO app_metadata (key, value, updated_at)
            VALUES ('warehouse_vector_version', %s, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (WAREHOUSE_VECTOR_VERSION,),
        )
        conn.commit()
    return inserted


def list_warehouse_parts(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT *
            FROM warehouse_parts
            ORDER BY vehicle_system, category, part_name
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()


def get_warehouse_part(sku: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM warehouse_parts WHERE sku = %s",
            (sku,),
        ).fetchone()


def warehouse_summary() -> dict[str, Any]:
    with get_conn() as conn:
        totals = conn.execute(
            """
            SELECT
              COUNT(*) AS total_parts,
              COALESCE(SUM(stock_quantity), 0) AS total_stock_units,
              COALESCE(SUM(stock_quantity * unit_cost), 0) AS inventory_value
            FROM warehouse_parts
            """
        ).fetchone()
        clusters = conn.execute(
            """
            SELECT cluster_key, COUNT(*) AS parts, COALESCE(SUM(stock_quantity), 0) AS stock_units
            FROM warehouse_parts
            GROUP BY cluster_key
            ORDER BY parts DESC, cluster_key ASC
            """
        ).fetchall()
        low_stock = conn.execute(
            """
            SELECT sku, part_name, stock_quantity, reorder_level
            FROM warehouse_parts
            WHERE stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC, part_name ASC
            """
        ).fetchall()
    return {"totals": totals, "clusters": clusters, "low_stock": low_stock}


def search_warehouse_parts(query: str, limit: int = 10) -> list[dict[str, Any]]:
    vector = _vector_literal(query)
    families = _query_families(query)
    terms = sorted(_family_terms(families))
    where_sql = ""
    params: list[Any] = [vector]
    if terms:
        where_sql = "WHERE " + " OR ".join(["LOWER(wp.embedding_content) LIKE %s"] * len(terms))
        params.extend([f"%{term}%" for term in terms])
    params.extend([vector, max(limit * 8, 40)])

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT
              wp.*,
              1 - (wpv.embedding <=> %s::vector) AS similarity,
              COUNT(*) OVER (PARTITION BY wp.cluster_key) AS cluster_size
            FROM warehouse_part_vectors wpv
            JOIN warehouse_parts wp ON wp.sku = wpv.sku
            {where_sql}
            ORDER BY wpv.embedding <=> %s::vector
            LIMIT %s
            """,
            params,
        ).fetchall()

    ranked: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        vector_similarity = float(item["similarity"])
        lexical_boost = _lexical_similarity(query, item["embedding_content"]) * 0.18
        family_boost = 0.1 if families and _query_families(item["embedding_content"]).intersection(families) else 0
        item["similarity"] = min(0.99, vector_similarity + lexical_boost + family_boost)
        ranked.append(item)

    ranked.sort(key=lambda item: float(item["similarity"]), reverse=True)
    return ranked[:limit]
