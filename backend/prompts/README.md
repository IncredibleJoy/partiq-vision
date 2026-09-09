# Backend Prompts

Prompt text files live here so backend code stays small and prompts can be edited without touching Python logic.

## Files

- `image_set_validation.txt`: validates whether uploads are automotive and whether multi-image uploads show the same object.
- `vision_detection.txt`: detects visible automotive parts and returns BOM-ready structured detections.
- `agents/*.txt`: describes each backend agent's role, input, task, and output.
- `recommendations/*.txt`: user-facing recommendation reason templates used by knowledge search and reflection.

## Runtime

`backend/app/prompts.py` loads these files by name. The backend container copies this folder into `/app/prompts`.

Keep prompt files as plain text. Do not add JSON schema definitions here; schemas remain in Python because they are application contracts.

## BOM Cost Analysis Themes

The current prompts are tuned for PartIQ Vision's BOM workflow:

- Multi-level BOM readiness: assemblies, sub-assemblies, components, fasteners, consumables, and fitment notes.
- Two-level reasoning: first-level visible detections stay grounded in the image, while second-level BOM children capture derived assembly/manufacturing/service items.
- Better cost analysis: warehouse matching, supplier/SKU comparison, lower-cost alternatives, stock risk, and missing pricing.
- Labor reasoning: cost rows can explain when defect, repair, construction, transfer, calibration, inspection, or fitment labor is included.
- Stronger vision output: visible-only part detection with material, damage, side/position, OCR, and confidence.
- Data quality and governance: standard names, duplicate review, weak-match review, explainable recommendations, and human approval before procurement decisions.
- Token visibility: prompts support comparing current and optimized vision settings through trace and usage summaries.

## Agent Prompt Files

Current agent instruction files:

- `agents/orchestrator_agent.txt`
- `agents/validation_agent.txt`
- `agents/vision_tool_agent.txt`
- `agents/crop_tool_agent.txt`
- `agents/bom_tool_agent.txt`
- `agents/knowledge_search_agent.txt`
- `agents/reflection_agent.txt`
- `agents/costing_agent.txt`
- `agents/vector_indexing_agent.txt`
