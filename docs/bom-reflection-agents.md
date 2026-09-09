# BOM And Reflection Agent Improvements

This note documents the BOM and Reflection Agent changes inspired by the AI-powered BOM cost-analysis reference paper.

## Goal

The application should produce a cleaner, more reviewable automotive BOM by:

- merging obvious duplicate detections into stable BOM rows
- preserving side and position differences such as left/right parts
- checking likely missing subparts, consumables, and fitment items
- flagging cost, stock, and quality risks before a user approves the BOM
- recommending lower-cost in-stock warehouse alternatives when available

## BOM Agent

`BomToolAgent` delegates to `consolidate_bom()` in `backend/app/bom.py`.

The BOM consolidation now uses a canonical key instead of grouping only by exact part name.

Examples:

```text
headlight -> headlamp assembly
bumper fascia -> bumper cover
bumper skin -> bumper cover
grill -> radiator grille assembly
hood -> bonnet hood panel
wire harness -> wiring harness
retainer -> clip set
```

The key also considers position:

```text
headlamp assembly::front_left
headlamp assembly::front_right
bumper cover::front
```

Visible part numbers still take priority because a part number is stronger evidence than wording.

## Reflection Agent

`ReflectionAgent` now reviews the BOM and cost sheet, not just raw detections.

The agent instruction prompt lives in `backend/prompts/agents/reflection_agent.txt`, and its user-facing recommendation reason text lives under `backend/prompts/recommendations/`.

It raises recommendations for:

- `missing_related_part`: likely subparts, consumables, or fitment items are absent
- `manual_review`: one side of a paired component appears without the other side
- `duplicate_candidate`: multiple unsided BOM rows may describe the same physical family
- `quality_review`: low-confidence detections or weak warehouse matches need confirmation
- `missing_cost_match`: a BOM row did not receive a warehouse price match
- `stock_risk`: matched inventory is near or below required quantity

Rule examples:

```text
bumper -> absorber, reinforcement, side retainers, clips, lower screws
headlamp -> mounting brackets, wiring connector, dust cap, dielectric grease
hood -> hinges, latch striker, washer nozzle, washer hose, paint materials
wheel -> tire, lug nuts, valve stem, TPMS sensor
radiator -> coolant, hoses, isolator mounts
```

## Knowledge Search Agent

`KnowledgeSearchAgent` still provides similar warehouse matches for detected parts. It also checks consolidated BOM rows for lower-cost, in-stock alternatives.

This supports procurement review without making another vision call or spending extra image tokens.

## Design Notes

These improvements are deterministic and local:

- no extra OpenAI call is added
- no database schema migration is required
- frontend recommendation rendering continues to use the existing `PartRecommendation` shape
- edited labels trigger the same improved BOM and reflection checks when the user reruns labels

## Next Improvements

Good next steps:

- add a structured `BomReviewFinding` schema with severity and action owner
- store canonical BOM keys as first-class fields
- add supplier reliability and lead-time data to warehouse rows
- add an optional text-only LLM reflection pass over compact BOM JSON
- show recommendation severity filters in the frontend
