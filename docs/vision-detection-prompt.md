# Vision Detection Prompt

This document summarizes the PartIQ Vision detection prompt in `backend/prompts/vision_detection.txt`.

## Purpose

The prompt asks the vision model to produce BOM-ready automotive part detections from uploaded images.

The output feeds:

- crop generation
- BOM consolidation
- warehouse cost matching
- Reflection Agent review
- frontend image review

## Prompt Strategy

The detection prompt is designed around five rules.

## 1. Visible Evidence Only

The model must detect only parts directly visible in the image.

It must not add hidden related items such as clips, brackets, fluids, fasteners, or consumables unless they are visible. Those missing-but-likely items are handled later by the Reflection Agent.

## 2. BOM-Friendly Names

The model should use repair-estimation part names instead of vague labels.

Examples:

```text
front bumper cover
bumper reinforcement beam
bumper energy absorber
radiator grille assembly
left headlamp assembly
right headlamp assembly
bonnet hood panel
fender panel
wheel arch liner
radiator assembly
a/c condenser
parking sensor
wiring harness
clip set
screw set
washer set
wheel assembly
```

## 3. Side And Position

The model should include side and position when visible or strongly implied:

```text
left
right
front
rear
upper
lower
inner
outer
```

This improves BOM grouping because left and right parts often need separate rows.

## 4. Structured Field Quality

Each detection should include:

- `part_name`: standard estimating name
- `category`: short category such as Exterior body, Lighting, Cooling, Electrical, Fastener
- `material`: likely visible material
- `condition`: visible status or damage only
- `visible_part_no`: OCR/stamped number if visible, otherwise null
- `minute_details`: concise inspection note
- `confidence`: lower when partly visible or uncertain
- `bbox`: tight normalized box around the visible part

## 5. Tight Bounding Boxes

Bounding boxes should surround the visible part only, not the whole vehicle.

For partly visible parts, the box should cover only the visible region.

## Why This Helps

The improved prompt reduces downstream cleanup by:

- producing cleaner BOM candidate names
- avoiding hidden-part hallucinations
- preserving left/right position evidence
- improving crop usefulness
- giving the Reflection Agent a cleaner distinction between visible detections and likely missing items

## Future Prompt Experiments

Possible next iterations:

- add vehicle-view detection before part detection
- ask for a maximum number of high-value detections
- split detection into assembly pass and detail pass
- add special prompts for front collision, wheel/tire, engine bay, and interior images
- add a text-only second pass to normalize names before BOM consolidation
