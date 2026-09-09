import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Boxes,
  ChevronDown,
  ChevronRight,
  Download,
  FileSearch,
  ImagePlus,
  Layers3,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Workflow
} from "lucide-react";
import "./styles.css";

type Detection = {
  id: string;
  part_name: string;
  category: string;
  material: string;
  condition: string;
  visible_part_no: string | null;
  minute_details: string;
  confidence: number;
  bbox: BoundingBox;
  crop_url: string | null;
  source_image: string | null;
};

type BoundingBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type BomItem = {
  part_name: string;
  category: string;
  material: string;
  condition_summary: string;
  quantity: number;
  best_confidence: number;
  visible_part_nos: string[];
  crop_urls: string[];
  source_images: string[];
  notes: string;
  is_complete_assembly: boolean;
  assembly_reason: string;
  assembly_children: BomAssemblyComponent[];
  included: boolean;
  selected_warehouse_sku: string | null;
  warehouse_recommendations: BomWarehouseRecommendation[];
  recommendation_reason: string;
};

type BomAssemblyComponent = {
  level: number;
  part_name: string;
  quantity: number;
  role: string;
  reason: string;
  included: boolean;
  selected_warehouse_sku: string | null;
  warehouse_recommendations: BomWarehouseRecommendation[];
};

type BomWarehouseRecommendation = {
  sku: string;
  part_name: string;
  score: number;
  reason: string;
  supplier: string;
  unit_cost: number;
  currency: string;
  stock_quantity: number;
  category: string;
  material: string;
  cluster_key: string;
  fitment_notes: string;
};

type CostSheetItem = {
  detected_part_name: string;
  bom_level: number;
  row_type: string;
  parent_detected_part_name: string | null;
  matched_part_name: string;
  matched_sku: string;
  category: string;
  material: string;
  supplier: string;
  cluster_key: string;
  quantity: number;
  unit_cost: number;
  parts_total_cost: number;
  labor_required: boolean;
  labor_hours: number;
  labor_rate: number;
  labor_cost: number;
  labor_reason: string;
  total_cost: number;
  currency: string;
  stock_quantity: number;
  match_confidence: number;
  fitment_notes: string;
  consumables_required: string[];
  level_2_items: BomAssemblyComponent[];
};

type CostSheet = {
  currency: string;
  items: CostSheetItem[];
  total_cost: number;
};

type TokenUsageItem = {
  step: string;
  model: string;
  purpose: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

type TokenUsageSummary = {
  items: TokenUsageItem[];
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
};

type JobResponse = {
  job_id: string;
  model_mode: string;
  vehicle_context: string;
  detections: Detection[];
  bom: BomItem[];
  cost_sheet: CostSheet;
  token_usage: TokenUsageSummary;
  recommendations: PartRecommendation[];
  agent_trace: AgentTrace[];
};

type MatchingStrategy = "semantic_search";

type WarehouseMatchResponse = {
  strategy: MatchingStrategy;
  bom: BomItem[];
  cost_sheet: CostSheet;
};

type PartRecommendation = {
  part_name: string;
  reason: string;
  recommendation_type: string;
  confidence: number;
  related_parts: string[];
};

type AgentTrace = {
  agent: string;
  action: string;
  status: string;
  detail: string;
};

type HealthStatus = {
  status: string;
  database: string;
  vector_store: string;
  openai: "online" | "offline";
  openai_detail: string;
};

type EditableDetection = {
  part_name: string;
  category: string;
  material: string;
  condition: string;
  visible_part_no: string;
  minute_details: string;
};

type VisionTokenMode = "standard" | "optimized";

type TraceExplanation = {
  asked: string;
  why: string;
};

const API_BASE = "";

const VISION_TOKEN_MODES: Record<
  VisionTokenMode,
  {
    label: string;
    detail: string;
    responseBudget: string;
    badge: string;
  }
> = {
  standard: {
    label: "Current",
    detail: "Auto",
    responseBudget: "Default",
    badge: "Full detection"
  },
  optimized: {
    label: "Optimized",
    detail: "Low",
    responseBudget: "Default",
    badge: "Low image detail"
  }
};

const TRACE_EXPLANATIONS: Record<string, TraceExplanation> = {
  start_job: {
    asked: "Start a new BOM analysis run for the uploaded image set.",
    why: "The workflow needs one job id to connect uploads, detections, BOM rows, costs, recommendations, token usage, and trace history."
  },
  token_optimizer: {
    asked: "Apply the selected vision token mode.",
    why: "This keeps Current and Optimized runs comparable while letting Optimized reduce vision image detail."
  },
  store_image: {
    asked: "Save the uploaded image before analysis.",
    why: "The backend needs a stable image file for validation, part detection, crop generation, and later image review."
  },
  validate_upload_set: {
    asked: "Check whether the upload is automotive and whether multiple images show the same object.",
    why: "Validation prevents the BOM agent from producing unreliable parts for unrelated or mismatched images."
  },
  detect_parts: {
    asked: "Detect visible automotive parts, labels, materials, conditions, confidence, and bounding boxes.",
    why: "These detections are the source evidence used by crop generation, BOM consolidation, costing, and review."
  },
  crop_detected_regions: {
    asked: "Create image crops for each detected part.",
    why: "Crops make manual review faster and help users verify whether each BOM row is grounded in visible image evidence."
  },
  deduplicate_bom: {
    asked: "Merge repeated or synonym-based detections into unique BOM rows.",
    why: "The cost sheet should count physical parts, not duplicate labels from multiple views or wording differences."
  },
  warehouse_cost_sheet: {
    asked: "Match BOM rows to warehouse stock and calculate the estimate.",
    why: "The BOM becomes actionable only after parts are mapped to SKUs, quantities, inventory, suppliers, and costs."
  },
  semantic_part_lookup: {
    asked: "Find similar stocked parts for detected labels.",
    why: "Similar matches help with alternate part discovery, fitment review, and downstream cost optimization."
  },
  bom_cost_alternatives: {
    asked: "Search consolidated BOM rows for lower-cost in-stock alternatives.",
    why: "Procurement review benefits from cheaper or more available alternatives before the final BOM is approved."
  },
  verify_bom_completeness: {
    asked: "Review the BOM for missing related items, duplicates, quality issues, stock risks, and cost gaps.",
    why: "Reflection catches likely estimating risks that pure visual detection or direct costing can miss."
  },
  finalize_job: {
    asked: "Return the completed job response.",
    why: "The frontend needs one final payload with detections, BOM rows, cost sheet, recommendations, token usage, and trace."
  },
  rerun_with_user_labels: {
    asked: "Recompute the BOM from user-edited labels.",
    why: "Human corrections should refresh BOM grouping, costs, and recommendations instead of leaving stale analysis results."
  }
};

function traceKey(item: AgentTrace, index: number) {
  return `${item.agent}-${item.action}-${index}`;
}

function traceExplanation(item: AgentTrace): TraceExplanation {
  return (
    TRACE_EXPLANATIONS[item.action] ?? {
      asked: `Run ${item.action.replaceAll("_", " ")}.`,
      why: "This step contributes to the analysis workflow and records what changed."
    }
  );
}

function confidenceLabel(value: number) {
  if (value >= 0.86) return "High";
  if (value >= 0.7) return "Review";
  return "Low";
}

function normalizedPartText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function findBomForDetection(detection: Detection, bom: BomItem[]) {
  const editedName = normalizedPartText(detection.part_name);
  const partNo = detection.visible_part_no?.toLowerCase();
  return bom.find((item) => {
    const bomName = normalizedPartText(item.part_name);
    const cropMatch = Boolean(detection.crop_url && item.crop_urls.includes(detection.crop_url));
    const partNoMatch = Boolean(partNo && item.visible_part_nos.some((value) => value.toLowerCase() === partNo));
    const nameMatch = bomName === editedName || bomName.includes(editedName) || editedName.includes(bomName);
    return cropMatch || partNoMatch || nameMatch;
  });
}

function findBomForCostItem(costItem: CostSheetItem, bom: BomItem[]) {
  const detectedName = normalizedPartText(costItem.detected_part_name);
  return bom.find((item) => {
    const bomName = normalizedPartText(item.part_name);
    return bomName === detectedName || bomName.includes(detectedName) || detectedName.includes(bomName);
  });
}

function treeChildLabel(index: number) {
  const alphabet = "abcdefghijklmnopqrstuvwxyz";
  if (index < alphabet.length) return alphabet[index];
  return `a${index - alphabet.length + 1}`;
}

function levelOneIndex(items: CostSheetItem[], index: number) {
  return items.slice(0, index + 1).filter((item) => (item.bom_level ?? 1) === 1).length;
}

function childIndexForParent(items: CostSheetItem[], index: number) {
  const parent = items[index].parent_detected_part_name;
  return items.slice(0, index + 1).filter(
    (item) => (item.bom_level ?? 1) > 1 && item.parent_detected_part_name === parent,
  ).length;
}

function findFirstAssemblyDetection(detections: Detection[], bom: BomItem[]) {
  return detections.find((detection) => Boolean(findBomForDetection(detection, bom)?.assembly_children?.length));
}

function confidenceTone(value: number) {
  if (value >= 0.75) return "high";
  if (value >= 0.5) return "medium";
  return "low";
}

function AssemblyTree({
  item,
  compact = false,
  level2Items,
  title,
  reason,
  parentLabel = "1"
}: {
  item?: BomItem;
  compact?: boolean;
  level2Items?: BomAssemblyComponent[];
  title?: string;
  reason?: string;
  parentLabel?: string;
}) {
  const children = level2Items ?? item?.assembly_children ?? [];
  if (children.length === 0) return null;
  const heading = title ?? `${parentLabel}. ${item?.part_name ?? "Assembly"}`;
  const detail = reason ?? item?.assembly_reason ?? "";
  return (
    <div className={compact ? "assemblyTree compactTree" : "assemblyTree"}>
      <strong className="treeRoot">{heading}</strong>
      {detail && <p>{detail}</p>}
      <ul>
        {children.map((child, index) => (
          <li key={`${heading}-${child.part_name}`}>
            <strong>{treeChildLabel(index)}. {child.part_name}</strong>
            <span>x{child.quantity} · {child.role}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function exportBom(items: BomItem[]) {
  const headers = [
    "Part Name",
    "Category",
    "Material",
    "Condition",
    "Quantity",
    "Best Confidence",
    "Visible Part Numbers",
    "Source Images",
    "Assembly",
    "Level 2 Breakdown",
    "Notes"
  ];
  const rows = items.map((item) => [
    item.part_name,
    item.category,
    item.material,
    item.condition_summary,
    String(item.quantity),
    item.best_confidence.toFixed(2),
    item.visible_part_nos.join(" | "),
    item.source_images.join(" | "),
    item.is_complete_assembly ? "Yes" : "No",
    (item.assembly_children ?? []).map((child) => `L${child.level} ${child.part_name} x${child.quantity} (${child.role})`).join(" | "),
    item.notes
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "partiq-bom.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportCostSheet(sheet: CostSheet) {
  const headers = [
    "Detected Part",
    "Matched Warehouse Part",
    "SKU",
    "Category",
    "Material",
    "Quantity",
    "Unit Cost",
    "Parts Total",
    "Labor Required",
    "Labor Hours",
    "Labor Rate",
    "Labor Cost",
    "Labor Reason",
    "Level 2 Cost Items",
    "Total Cost",
    "Currency",
    "Supplier",
    "Stock Quantity",
    "Match Confidence",
    "Consumables",
    "Fitment Notes"
  ];
  const rows = sheet.items.map((item) => [
    item.detected_part_name,
    item.matched_part_name,
    item.matched_sku,
    item.category,
    item.material,
    String(item.quantity),
    item.unit_cost.toFixed(2),
    (item.parts_total_cost ?? item.total_cost).toFixed(2),
    item.labor_required ? "Yes" : "No",
    (item.labor_hours ?? 0).toFixed(2),
    (item.labor_rate ?? 0).toFixed(2),
    (item.labor_cost ?? 0).toFixed(2),
    item.labor_reason ?? "",
    (item.level_2_items ?? []).map((child) => `L${child.level} ${child.part_name} x${child.quantity} (${child.role})`).join(" | "),
    item.total_cost.toFixed(2),
    item.currency,
    item.supplier,
    String(item.stock_quantity),
    item.match_confidence.toFixed(2),
    item.consumables_required.join(" | "),
    item.fitment_notes
  ]);
  rows.push(["", "", "", "", "Grand Total", "", "", "", "", "", "", "", "", sheet.total_cost.toFixed(2), sheet.currency, "", "", "", "", ""]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "partiq-cost-sheet.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

const LIVE_AGENT_STEPS = [
  {
    agent: "orchestrator_agent",
    action: "start_job",
    detail: "Receiving uploaded image set"
  },
  {
    agent: "validation_agent",
    action: "validate_upload_set",
    detail: "Checking automotive relevance and same-object views"
  },
  {
    agent: "vision_tool_agent",
    action: "detect_parts",
    detail: "Detecting visible parts, materials, condition, labels, and boxes"
  },
  {
    agent: "crop_tool_agent",
    action: "crop_detected_regions",
    detail: "Creating part crop images from detected regions"
  },
  {
    agent: "bom_tool_agent",
    action: "deduplicate_bom",
    detail: "Consolidating repeated views into a unique BOM"
  },
  {
    agent: "costing_agent",
    action: "warehouse_cost_sheet",
    detail: "Matching BOM rows to warehouse stock and calculating INR estimate"
  },
  {
    agent: "knowledge_search_agent",
    action: "semantic_part_lookup",
    detail: "Finding similar warehouse parts and recommendations"
  },
  {
    agent: "reflection_agent",
    action: "verify_bom_completeness",
    detail: "Checking missing related parts, consumables, and review risks"
  }
];

function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [hoveredDetectionId, setHoveredDetectionId] = useState<string | null>(null);
  const [focusedDetectionId, setFocusedDetectionId] = useState<string | null>(null);
  const [showImageReview, setShowImageReview] = useState(false);
  const [showDetectedParts, setShowDetectedParts] = useState(false);
  const [showBomSheet, setShowBomSheet] = useState(false);
  const [showCostSheet, setShowCostSheet] = useState(false);
  const [showTokenUsage, setShowTokenUsage] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showAgentTrace, setShowAgentTrace] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showReflectionSummary, setShowReflectionSummary] = useState(false);
  const [visionMode, setVisionMode] = useState<VisionTokenMode>("standard");
  const [minDetectionConfidence, setMinDetectionConfidence] = useState(0);
  const [minBomConfidence, setMinBomConfidence] = useState(0);
  const [minMatchConfidence, setMinMatchConfidence] = useState(0);
  const [activeAgentStep, setActiveAgentStep] = useState(-1);
  const [expandedTraceRows, setExpandedTraceRows] = useState<Set<string>>(new Set());
  const [expandedBomRows, setExpandedBomRows] = useState<Set<number>>(new Set());
  const [edits, setEdits] = useState<Record<string, EditableDetection>>({});
  const [bomSaving, setBomSaving] = useState(false);
  const [matchingStrategy, setMatchingStrategy] = useState<MatchingStrategy>("semantic_search");
  const [rerunningMatches, setRerunningMatches] = useState(false);
  const [selectedBomIndex, setSelectedBomIndex] = useState<number | null>(null);

  const stats = useMemo(() => {
    const detections = job?.detections ?? [];
    const avg =
      detections.length === 0
        ? 0
        : detections.reduce((sum, item) => sum + item.confidence, 0) / detections.length;
    const review = detections.filter((item) => item.confidence < 0.7).length;
    return { avg, review };
  }, [job]);

  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviewUrls(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);

  useEffect(() => {
    if (!loading) return;
    setActiveAgentStep(0);
    const timer = window.setInterval(() => {
      setActiveAgentStep((step) => Math.min(step + 1, LIVE_AGENT_STEPS.length - 1));
    }, 900);
    return () => window.clearInterval(timer);
  }, [loading]);

  async function refreshHealth() {
    setCheckingHealth(true);
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      if (!response.ok) throw new Error("Health check failed");
      const nextHealth: HealthStatus = await response.json();
      setHealth(nextHealth);
    } catch {
      setHealth(null);
    } finally {
      setCheckingHealth(false);
    }
  }

  useEffect(() => {
    refreshHealth();
    const timer = window.setInterval(refreshHealth, 30000);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  function resetUpload() {
    setFiles([]);
    setJob(null);
    setError(null);
    setQuery("");
    setSelectedSource(null);
    setHoveredDetectionId(null);
    setFocusedDetectionId(null);
    setShowImageReview(false);
    setShowDetectedParts(false);
    setShowBomSheet(false);
    setShowCostSheet(false);
    setShowTokenUsage(false);
    setShowAgentTrace(false);
    setShowSettings(false);
    setShowReflectionSummary(false);
    setActiveAgentStep(-1);
    setExpandedTraceRows(new Set());
    setExpandedBomRows(new Set());
    setEdits({});
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function analyze() {
    if (!files.length) return;
    setLoading(true);
    setActiveAgentStep(0);
    setShowAgentTrace(true);
    setError(null);
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("vision_token_mode", visionMode);
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await response.text());
      const nextJob: JobResponse = await response.json();
      setJob(nextJob);
      hydrateEdits(nextJob);
      setSelectedSource(nextJob.detections[0]?.source_image ?? null);
      setShowImageReview(false);
      setShowDetectedParts(false);
      setShowBomSheet(false);
      setShowCostSheet(false);
      setShowTokenUsage(false);
      setShowReflectionSummary(false);
      setExpandedTraceRows(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  function hydrateEdits(nextJob: JobResponse) {
    setEdits(
      Object.fromEntries(
        nextJob.detections.map((item) => [
          item.id,
          {
            part_name: item.part_name,
            category: item.category,
            material: item.material,
            condition: item.condition,
            visible_part_no: item.visible_part_no ?? "",
            minute_details: item.minute_details
          }
        ])
      )
    );
  }

  function updateEdit(id: string, field: keyof EditableDetection, value: string) {
    setEdits((current) => ({
      ...current,
      [id]: {
        ...current[id],
        [field]: value
      }
    }));
  }

  function jumpToDetectionDetails(id: string) {
    setQuery("");
    setFocusedDetectionId(id);
    window.setTimeout(() => {
      const card = document.getElementById(`part-card-${id}`);
      card?.scrollIntoView({ behavior: "smooth", block: "center" });
      const input = card?.querySelector<HTMLInputElement>("[data-part-name-input='true']");
      input?.focus({ preventScroll: true });
      input?.select();
    }, 50);
    window.setTimeout(() => setFocusedDetectionId(null), 2600);
  }

  async function refineWithLabels() {
    if (!job) return;
    setRefining(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${job.job_id}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates: Object.entries(edits).map(([id, values]) => ({
            id,
            ...values,
            visible_part_no: values.visible_part_no || null
          }))
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const nextJob: JobResponse = await response.json();
      setJob(nextJob);
      hydrateEdits(nextJob);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Label refinement failed");
    } finally {
      setRefining(false);
    }

  }

  function updateBomItem(index: number, update: Partial<BomItem>) {
    setJob((current) => current ? { ...current, bom: current.bom.map((item, itemIndex) => itemIndex === index ? { ...item, ...update } : item) } : current);
  }

  function updateBomChild(parentIndex: number, childIndex: number, update: Partial<BomAssemblyComponent>) {
    setJob((current) => current ? {
      ...current,
      bom: current.bom.map((item, itemIndex) => itemIndex === parentIndex
        ? { ...item, assembly_children: item.assembly_children.map((child, index) => index === childIndex ? { ...child, ...update } : child) }
        : item)
    } : current);
  }

  function addWarehousePart(candidate: BomWarehouseRecommendation) {
    setJob((current) => current ? {
      ...current,
      bom: [...current.bom, {
        part_name: candidate.part_name,
        category: candidate.category,
        material: candidate.material,
        condition_summary: "Warehouse recommendation",
        quantity: 1,
        best_confidence: candidate.score,
        visible_part_nos: [],
        crop_urls: [],
        source_images: [],
        notes: candidate.fitment_notes,
        is_complete_assembly: false,
        assembly_reason: "",
        assembly_children: [],
        included: true,
        selected_warehouse_sku: candidate.sku,
        warehouse_recommendations: [candidate],
        recommendation_reason: "Manually added from the ranked warehouse recommendations."
      }]
    } : current);
  }

  function toggleSelectedBomRow() {
    if (selectedBomIndex === null) return;
    const item = job?.bom[selectedBomIndex];
    if (item) updateBomItem(selectedBomIndex, { included: item.included === false });
  }

  function addSelectedRecommendation() {
    if (selectedBomIndex === null) return;
    const candidate = job?.bom[selectedBomIndex]?.warehouse_recommendations[0];
    if (candidate) addWarehousePart(candidate);
  }

  async function confirmBom() {
    if (!job) return;
    setBomSaving(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${job.job_id}/cost-sheet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bom: job.bom })
      });
      if (!response.ok) throw new Error(await response.text());
      const costSheet: CostSheet = await response.json();
      setJob((current) => current ? { ...current, cost_sheet: costSheet } : current);
      setShowCostSheet(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the cost sheet");
    } finally {
      setBomSaving(false);
    }
  }

  async function rerunWarehouseMatches() {
    if (!job) return;
    setRerunningMatches(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/jobs/${job.job_id}/warehouse-matches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bom: job.bom, strategy: matchingStrategy })
      });
      if (!response.ok) throw new Error(await response.text());
      const result: WarehouseMatchResponse = await response.json();
      setJob((current) => current ? { ...current, bom: result.bom, cost_sheet: result.cost_sheet } : current);
      setSelectedBomIndex(null);
      setExpandedBomRows(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not rerun warehouse matching");
    } finally {
      setRerunningMatches(false);
    }
  }

  const filteredDetections = (job?.detections ?? []).filter((item) => {
    const text = `${item.part_name} ${item.category} ${item.material} ${item.condition}`.toLowerCase();
    return text.includes(query.toLowerCase()) && item.confidence >= minDetectionConfidence;
  });
  const sourceImages = Array.from(new Set((job?.detections ?? []).map((item) => item.source_image).filter(Boolean))) as string[];
  const selectedDetections = (job?.detections ?? []).filter(
    (item) => item.source_image === selectedSource && item.confidence >= minDetectionConfidence
  );
  const filteredBom = (job?.bom ?? []).filter((item) => item.best_confidence >= minBomConfidence);
  const visibleParentCostNames = new Set(
    (job?.cost_sheet?.items ?? [])
      .filter((item) => (item.bom_level ?? 1) === 1 && item.match_confidence >= minMatchConfidence)
      .map((item) => item.detected_part_name),
  );
  const filteredCostItems = (job?.cost_sheet?.items ?? []).filter((item) => {
    if ((item.bom_level ?? 1) === 1) return item.match_confidence >= minMatchConfidence;
    return Boolean(item.parent_detected_part_name && visibleParentCostNames.has(item.parent_detected_part_name));
  });
  const filteredCostTotal = filteredCostItems.reduce((sum, item) => sum + item.total_cost, 0);
  const activeReviewDetection =
    selectedDetections.find((item) => item.id === hoveredDetectionId) ??
    findFirstAssemblyDetection(selectedDetections, job?.bom ?? []) ??
    selectedDetections[0];
  const activeReviewBom = activeReviewDetection ? findBomForDetection(activeReviewDetection, job?.bom ?? []) : undefined;
  const activeDetectedPart =
    filteredDetections.find((item) => item.id === hoveredDetectionId || item.id === focusedDetectionId) ??
    findFirstAssemblyDetection(filteredDetections, job?.bom ?? []) ??
    filteredDetections[0];
  const activeDetectedBom = activeDetectedPart ? findBomForDetection(activeDetectedPart, job?.bom ?? []) : undefined;
  const reflectionItems = (job?.recommendations ?? []).filter((item) =>
    [
      "missing_related_part",
      "manual_review",
      "duplicate_candidate",
      "quality_review",
      "missing_cost_match",
      "stock_risk"
    ].includes(item.recommendation_type)
  );
  const reflectionCounts = reflectionItems.reduce<Record<string, number>>((counts, item) => {
    counts[item.recommendation_type] = (counts[item.recommendation_type] ?? 0) + 1;
    return counts;
  }, {});
  const resetConfidenceFilters = () => {
    setMinDetectionConfidence(0);
    setMinBomConfidence(0);
    setMinMatchConfidence(0);
  };
  const toggleTraceRow = (key: string) => {
    setExpandedTraceRows((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };
  const sidebarTrace =
    loading
      ? LIVE_AGENT_STEPS.map((step, index) => ({
          ...step,
          status: index < activeAgentStep ? "complete" : index === activeAgentStep ? "running" : "pending"
        }))
      : job?.agent_trace ?? [];
  const statusText = job
    ? `Job ${job.job_id.slice(0, 8)}`
    : health?.openai === "online"
      ? "Online"
      : health
        ? "OpenAI Offline"
        : "Offline";
  const statusClass = job ? "statusPill ready" : health?.openai === "online" ? "statusPill online" : "statusPill offline";

  return (
    <main className="shell">
      <section className="commandBar">
        <div>
          <div className="brand">
            <Boxes size={22} />
            <span className="wordmark">
              <span className="brandTop">
                <span className="brandPart"><span>P</span><small>art</small></span>
                <span className="brandIq">IQ</span>
                <span className="brandVision">Vision</span>
              </span>
              <span className="brandTagline">Parts intelligence, powered by vision</span>
            </span>
          </div>
        </div>
        <div className="commandActions">
          <button
            aria-label={showSidebar ? "Hide upload sidebar" : "Show upload sidebar"}
            aria-pressed={!showSidebar}
            className="sidebarToggle"
            onClick={() => setShowSidebar((value) => !value)}
            title={showSidebar ? "Hide upload sidebar" : "Show upload sidebar"}
            type="button"
          >
            {showSidebar ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}
          </button>
          <div className={statusClass} title={health?.openai_detail ?? "Backend health check is unavailable"}>
            <Activity size={16} />
            {statusText}
          </div>
        </div>
      </section>

      <section className={showSidebar ? "workbench" : "workbench sidebarHidden"}>
        {showSidebar && <aside className="uploadPanel">
          <label className="dropzone">
            <ImagePlus size={32} />
            <strong>Upload single or multiple vehicle images</strong>
            <span>Front, side, accidental, or detail shots</span>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            />
          </label>

          {files.length > 0 && (
            <div className="uploadPreviewGrid">
              {files.map((file, index) => (
                <figure className="uploadPreview" key={`${file.name}-${file.size}`}>
                  <img src={previewUrls[index]} alt={file.name} />
                  <figcaption>{file.name}</figcaption>
                </figure>
              ))}
            </div>
          )}
          <div className="fileStack">
            {files.map((file) => (
              <div className="fileRow" key={`${file.name}-${file.size}`}>
                <FileSearch size={16} />
                <span>{file.name}</span>
              </div>
            ))}
          </div>

          <div className="uploadControls">
            <div className="optimizerPanel">
              <div className="optimizerHeader">
                <SlidersHorizontal size={17} />
                <strong>Vision Token Mode</strong>
              </div>
              <div className="optimizerModes" role="radiogroup" aria-label="Vision token mode">
                {(Object.keys(VISION_TOKEN_MODES) as VisionTokenMode[]).map((mode) => {
                  const config = VISION_TOKEN_MODES[mode];
                  return (
                    <button
                      aria-checked={visionMode === mode}
                      className={visionMode === mode ? "optimizerMode active" : "optimizerMode"}
                      key={mode}
                      onClick={() => setVisionMode(mode)}
                      role="radio"
                      type="button"
                    >
                      <span>{config.label}</span>
                      <em>{config.badge}</em>
                      <small>Image {config.detail}</small>
                      <small>Output {config.responseBudget}</small>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="uploadActions">
              <button className="primary" disabled={!files.length || loading} onClick={analyze}>
                {loading ? <Loader2 className="spin" size={18} /> : <Sparkles size={18} />}
                Analyze Parts
              </button>
              <button
                aria-label="Clear current upload and start again"
                className="refreshUpload"
                disabled={loading || (!files.length && !job && !error)}
                onClick={resetUpload}
                title="Clear current upload"
                type="button"
              >
                <RefreshCw size={17} />
              </button>
            </div>
          </div>

          {error && <div className="errorBox">{error}</div>}

          {(loading || sidebarTrace.length > 0) && (
            <div className="liveTracePanel">
              <button
                aria-expanded={showAgentTrace}
                className={showAgentTrace ? "liveTraceHeader active" : "liveTraceHeader"}
                onClick={() => setShowAgentTrace((value) => !value)}
                type="button"
              >
                <span className="liveTraceTitle">
                  <Workflow size={17} />
                  <strong>{loading ? "Agents running" : "Agent trace"}</strong>
                </span>
                <span className="liveTraceMeta">
                  <em>{loading ? "Live" : `${sidebarTrace.length} steps`}</em>
                  <ChevronDown size={15} />
                </span>
              </button>
              {showAgentTrace && (
                <div className="traceContents">
                  <div className="liveTraceList">
                    {sidebarTrace.map((item, index) => {
                      const key = traceKey(item, index);
                      const isExpanded = expandedTraceRows.has(key);
                      const explanation = traceExplanation(item);
                      return (
                        <div className={`liveTraceRow ${item.status}`} key={key}>
                          {item.status === "running" ? <Loader2 className="spin" size={15} /> : <ShieldCheck size={15} />}
                          <div>
                            <div className="liveTraceTop">
                              <div>
                                <strong>{item.agent.replaceAll("_", " ")}</strong>
                                <span>{item.action.replaceAll("_", " ")} · {item.status}</span>
                              </div>
                              <button
                                aria-expanded={isExpanded}
                                aria-label={`${isExpanded ? "Hide" : "Show"} ${item.action.replaceAll("_", " ")} explanation`}
                                className="traceExpandButton"
                                onClick={() => toggleTraceRow(key)}
                                title={isExpanded ? "Hide explanation" : "Show explanation"}
                                type="button"
                              >
                                <ChevronDown size={15} />
                              </button>
                            </div>
                            <p>{item.detail}</p>
                            {isExpanded && (
                              <div className="traceMiniExplain">
                                <div>
                                  <span>Asked</span>
                                  <strong>{explanation.asked}</strong>
                                </div>
                                <div>
                                  <span>Why</span>
                                  <strong>{explanation.why}</strong>
                                </div>
                                <div>
                                  <span>Output</span>
                                  <strong>{item.status === "pending" ? "Waiting for this step to run." : item.detail}</strong>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {!loading && job && (
                    <div className="reflectionSummary">
                      <button
                        aria-expanded={showReflectionSummary}
                        className="reflectionSummaryToggle"
                        onClick={() => setShowReflectionSummary((value) => !value)}
                        type="button"
                      >
                        <span>Reflection Summary</span>
                        <em>{reflectionItems.length} finding{reflectionItems.length === 1 ? "" : "s"}</em>
                        <ChevronDown size={15} />
                      </button>
                      {showReflectionSummary && (
                        <div className="reflectionSummaryBody">
                          <p>
                            The Reflection Agent reviewed the consolidated BOM and cost sheet for missing fitment items,
                            one-sided components, duplicate candidates, low-confidence rows, missing prices, and stock risk.
                          </p>
                          <div className="reflectionTypeGrid">
                            {Object.entries(reflectionCounts).map(([type, count]) => (
                              <div key={type}>
                                <span>{type.replaceAll("_", " ")}</span>
                                <strong>{count}</strong>
                              </div>
                            ))}
                            {reflectionItems.length === 0 && <div className="emptyState">No reflection risk was raised.</div>}
                          </div>
                          {reflectionItems.slice(0, 4).map((item, index) => (
                            <article className="reflectionFinding" key={`${item.recommendation_type}-${item.part_name}-${index}`}>
                              <strong>{item.part_name}</strong>
                              <span>{item.recommendation_type.replaceAll("_", " ")}</span>
                              <p>{item.reason}</p>
                            </article>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </aside>}

        <section className="results">
          <div className="metricGrid">
            <div className="metric">
              <span>Total detections</span>
              <strong>{job?.detections.length ?? 0}</strong>
            </div>
            <div className="metric">
              <span>Unique BOM rows</span>
              <strong>{job?.bom.length ?? 0}</strong>
            </div>
            <div className="metric">
              <span>Avg confidence</span>
              <strong>{Math.round(stats.avg * 100)}%</strong>
            </div>
            <div className="metric">
              <span>Total estimate</span>
              <strong>
                {job?.cost_sheet ? `${job.cost_sheet.currency} ${Math.round(job.cost_sheet.total_cost)}` : "0"}
              </strong>
            </div>
            <div className="metric">
              <span>Tokens used</span>
              <strong>{job?.token_usage?.total_tokens ?? 0}</strong>
            </div>
            <div className="metric">
              <span>Vision mode</span>
              <strong>{VISION_TOKEN_MODES[visionMode].label}</strong>
            </div>
          </div>

          <div className="toolStrip">
            <div className="searchBox">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter parts" />
            </div>
            <button className="secondary" disabled={!job?.bom.length} onClick={() => job && exportBom(job.bom)}>
              <Download size={17} />
              Export BOM
            </button>
            <button className="secondary" disabled={!job?.cost_sheet?.items.length} onClick={() => job?.cost_sheet && exportCostSheet(job.cost_sheet)}>
              <Download size={17} />
              Export Cost
            </button>
            <button className={showSettings ? "secondary activeTool" : "secondary"} onClick={() => setShowSettings((value) => !value)}>
              <SlidersHorizontal size={17} />
              Settings
            </button>
            <button className="primary compact" disabled={!job?.detections.length || refining} onClick={refineWithLabels}>
              {refining ? <Loader2 className="spin" size={17} /> : <Sparkles size={17} />}
              Re-run Labels
            </button>
          </div>

          <div className="contextLine">{job?.vehicle_context ?? "No analysis yet. Upload images to build a BOM sheet."}</div>

          {showSettings && (
            <section className="settingsPanel">
              <div className="settingsHeader">
                <h2>Confidence Tuning</h2>
                <button className="secondary compactButton" onClick={resetConfidenceFilters} type="button">
                  Reset
                </button>
              </div>
              <div className="confidenceControls">
                <label>
                  <span>Detected parts</span>
                  <strong>{Math.round(minDetectionConfidence * 100)}%+</strong>
                  <input
                    max="1"
                    min="0"
                    step="0.05"
                    type="range"
                    value={minDetectionConfidence}
                    onChange={(event) => setMinDetectionConfidence(Number(event.target.value))}
                  />
                </label>
                <label>
                  <span>Unique BOM rows</span>
                  <strong>{Math.round(minBomConfidence * 100)}%+</strong>
                  <input
                    max="1"
                    min="0"
                    step="0.05"
                    type="range"
                    value={minBomConfidence}
                    onChange={(event) => setMinBomConfidence(Number(event.target.value))}
                  />
                </label>
                <label>
                  <span>Warehouse matches</span>
                  <strong>{Math.round(minMatchConfidence * 100)}%+</strong>
                  <input
                    max="1"
                    min="0"
                    step="0.05"
                    type="range"
                    value={minMatchConfidence}
                    onChange={(event) => setMinMatchConfidence(Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="settingsSummary">
                Showing {filteredDetections.length}/{job?.detections.length ?? 0} detections, {filteredBom.length}/{job?.bom.length ?? 0} BOM rows, and {filteredCostItems.length}/{job?.cost_sheet?.items.length ?? 0} cost matches.
              </div>
              <div className="settingsSummary">
                Vision mode: {VISION_TOKEN_MODES[visionMode].label}; image detail {VISION_TOKEN_MODES[visionMode].detail.toLowerCase()}; output budget {VISION_TOKEN_MODES[visionMode].responseBudget.toLowerCase()}.
              </div>
            </section>
          )}

          {job && job.detections.length > 0 && (
            <div className="sectionToggleRow">
              <button
                className={showImageReview ? "sectionToggle active" : "sectionToggle"}
                onClick={() => setShowImageReview((value) => !value)}
              >
                <span>Image Review</span>
                <em>{showImageReview ? "Hide" : `${sourceImages.length} image${sourceImages.length === 1 ? "" : "s"}`}</em>
              </button>
              <button
                className={showDetectedParts ? "sectionToggle active" : "sectionToggle"}
                onClick={() => setShowDetectedParts((value) => !value)}
              >
                <span>Detected Parts</span>
                <em>{showDetectedParts ? "Hide" : `${filteredDetections.length} parts`}</em>
              </button>
              <button
                className={showBomSheet ? "sectionToggle active" : "sectionToggle"}
                onClick={() => setShowBomSheet((value) => !value)}
              >
                <span>Unique BOM Sheet</span>
                <em>{showBomSheet ? "Hide" : `${filteredBom.length} rows`}</em>
              </button>
              <button
                className={showCostSheet ? "sectionToggle active" : "sectionToggle"}
                onClick={() => setShowCostSheet((value) => !value)}
              >
                <span>Cost Sheet</span>
                <em>
                  {showCostSheet
                    ? "Hide"
                  : `${job.cost_sheet?.currency ?? "USD"} ${Math.round(filteredCostTotal)}`}
                </em>
              </button>
              <button
                className={showTokenUsage ? "sectionToggle active" : "sectionToggle"}
                onClick={() => setShowTokenUsage((value) => !value)}
              >
                <span>Token Usage</span>
                <em>{showTokenUsage ? "Hide" : `${job.token_usage?.total_tokens ?? 0} tokens`}</em>
              </button>
            </div>
          )}

          {job && selectedSource && showImageReview && (
            <section className="annotationPanel">
              <div className="annotationHeader">
                <h2>Image Review</h2>
                <div className="sourceTabs">
                  {sourceImages.map((source) => (
                    <button
                      className={source === selectedSource ? "sourceTab active" : "sourceTab"}
                      key={source}
                      onClick={() => setSelectedSource(source)}
                    >
                      {source.slice(0, 8)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="annotationBody">
                <div className="annotatedImage">
                  <img src={`/storage/uploads/${selectedSource}`} alt={selectedSource} />
                  {selectedDetections.map((item, index) => (
                    <button
                      aria-label={`${index + 1}: ${edits[item.id]?.part_name || item.part_name}`}
                      className={hoveredDetectionId === item.id ? "boxOverlay active" : "boxOverlay"}
                      key={item.id}
                      onMouseEnter={() => setHoveredDetectionId(item.id)}
                      onMouseLeave={() => setHoveredDetectionId(null)}
                      style={{
                        left: `${item.bbox.x * 100}%`,
                        top: `${item.bbox.y * 100}%`,
                        width: `${item.bbox.width * 100}%`,
                        height: `${item.bbox.height * 100}%`
                      }}
                      type="button"
                    >
                      <span>{index + 1}</span>
                    </button>
                  ))}
                </div>
                <div className="boxLegend">
                  {selectedDetections.map((item, index) => (
                    <button
                      className={hoveredDetectionId === item.id ? "legendItem active" : "legendItem"}
                      key={item.id}
                      onDoubleClick={() => jumpToDetectionDetails(item.id)}
                      onMouseEnter={() => setHoveredDetectionId(item.id)}
                      onMouseLeave={() => setHoveredDetectionId(null)}
                      type="button"
                    >
                      <b>{index + 1}</b>
                      <span>{edits[item.id]?.part_name || item.part_name}</span>
                      <em>{Math.round(item.confidence * 100)}%</em>
                    </button>
                  ))}
                </div>
                <aside className="treeSidePanel">
                  <div>
                    <span>Assembly graph</span>
                    <strong>{activeReviewDetection ? `${selectedDetections.indexOf(activeReviewDetection) + 1}. ${edits[activeReviewDetection.id]?.part_name || activeReviewDetection.part_name}` : "No part selected"}</strong>
                  </div>
                  <AssemblyTree
                    item={activeReviewBom}
                    compact
                    parentLabel={String(activeReviewDetection ? selectedDetections.indexOf(activeReviewDetection) + 1 : 1)}
                  />
                  {!activeReviewBom?.assembly_children?.length && (
                    <p className="treeEmpty">This level-1 part is treated as a leaf item for BOM review.</p>
                  )}
                </aside>
              </div>
            </section>
          )}

          {(showDetectedParts || showBomSheet || showCostSheet || showTokenUsage) && (
            <div className={[showDetectedParts, showBomSheet, showCostSheet, showTokenUsage].filter(Boolean).length > 1 ? "split" : "singleSection"}>
              {showDetectedParts && (
                <section>
                  <h2>Detected Parts</h2>
                  <div className="detectedReviewLayout">
                    <div className="cardGrid compactCards">
                      {filteredDetections.map((item) => (
                        <article
                          className={focusedDetectionId === item.id ? "partCard focused" : "partCard"}
                          id={`part-card-${item.id}`}
                          key={item.id}
                          onMouseEnter={() => setHoveredDetectionId(item.id)}
                          onMouseLeave={() => setHoveredDetectionId(null)}
                        >
                          <div className="crop">
                            {item.crop_url ? <img src={item.crop_url} alt={item.part_name} /> : <span>No crop</span>}
                          </div>
                          <div className="partMeta">
                            <div className="partTop">
                              <input
                                data-part-name-input="true"
                                className="labelInput titleInput"
                                value={edits[item.id]?.part_name ?? item.part_name}
                                onChange={(event) => updateEdit(item.id, "part_name", event.target.value)}
                              />
                              <span className={`conf ${confidenceLabel(item.confidence).toLowerCase()}`}>
                                {Math.round(item.confidence * 100)}%
                              </span>
                            </div>
                            <input
                              className="labelInput"
                              value={edits[item.id]?.category ?? item.category}
                              onChange={(event) => updateEdit(item.id, "category", event.target.value)}
                            />
                            <textarea
                              className="labelTextarea"
                              value={edits[item.id]?.minute_details ?? item.minute_details}
                              onChange={(event) => updateEdit(item.id, "minute_details", event.target.value)}
                            />
                            <dl>
                              <div>
                                <dt>Material</dt>
                                <dd>
                                  <input
                                    className="labelInput"
                                    value={edits[item.id]?.material ?? item.material}
                                    onChange={(event) => updateEdit(item.id, "material", event.target.value)}
                                  />
                                </dd>
                              </div>
                              <div>
                                <dt>Condition</dt>
                                <dd>
                                  <input
                                    className="labelInput"
                                    value={edits[item.id]?.condition ?? item.condition}
                                    onChange={(event) => updateEdit(item.id, "condition", event.target.value)}
                                  />
                                </dd>
                              </div>
                              <div>
                                <dt>Part no.</dt>
                                <dd>
                                  <input
                                    className="labelInput"
                                    placeholder="Not visible"
                                    value={edits[item.id]?.visible_part_no ?? item.visible_part_no ?? ""}
                                    onChange={(event) => updateEdit(item.id, "visible_part_no", event.target.value)}
                                  />
                                </dd>
                              </div>
                            </dl>
                          </div>
                        </article>
                      ))}
                    </div>
                    <aside className="treeSidePanel stickyTree">
                      <div>
                        <span>Assembly graph</span>
                        <strong>{activeDetectedPart ? `${filteredDetections.indexOf(activeDetectedPart) + 1}. ${edits[activeDetectedPart.id]?.part_name || activeDetectedPart.part_name}` : "No part selected"}</strong>
                      </div>
                      <AssemblyTree
                        item={activeDetectedBom}
                        parentLabel={String(activeDetectedPart ? filteredDetections.indexOf(activeDetectedPart) + 1 : 1)}
                      />
                      {!activeDetectedBom?.assembly_children?.length && (
                        <p className="treeEmpty">This level-1 part is treated as a leaf item for BOM review.</p>
                      )}
                    </aside>
                  </div>
                </section>
              )}

              {showBomSheet && (
                <section>
                  <div className="sectionTitleRow">
                    <h2>Unique BOM Sheet</h2>
                    <div className="bomToolbar">
                      <label className="matchingStrategyControl">
                        <Search size={15} />
                        <span>Matching strategy</span>
                        <select
                          aria-label="Warehouse matching strategy"
                          value={matchingStrategy}
                          onChange={(event) => setMatchingStrategy(event.target.value as MatchingStrategy)}
                        >
                          <option value="semantic_search">Semantic search</option>
                        </select>
                      </label>
                      <button className="secondary rerunMatches" disabled={rerunningMatches} onClick={rerunWarehouseMatches} type="button">
                        {rerunningMatches ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
                        {rerunningMatches ? "Matching..." : "Rerun"}
                      </button>
                      <span className="selectionHint">
                        {selectedBomIndex === null ? "Select a row to edit" : `Row ${selectedBomIndex + 1} selected`}
                      </span>
                      <button aria-label="Add top warehouse recommendation" className="iconButton compactIcon" disabled={selectedBomIndex === null} onClick={addSelectedRecommendation} title="Add top warehouse recommendation" type="button">
                        <Plus size={16} />
                      </button>
                      <button aria-label="Remove or restore selected BOM row" className="iconButton compactIcon danger" disabled={selectedBomIndex === null} onClick={toggleSelectedBomRow} title="Remove or restore selected BOM row" type="button">
                        {selectedBomIndex !== null && job?.bom[selectedBomIndex]?.included === false ? <RefreshCw size={16} /> : <Trash2 size={16} />}
                      </button>
                      <button className="primary" disabled={bomSaving} onClick={confirmBom} type="button">
                      {bomSaving ? "Updating..." : "Confirm BOM & Update Cost"}
                      </button>
                    </div>
                  </div>
                  <div className="bomTable">
                    <div className="bomHead">
                      <span>Row</span><span>Part</span><span>BOM details</span><span>Selected warehouse match</span><span>Confidence</span><span>Actions</span>
                    </div>
                    {filteredBom.map((item) => {
                      const index = job?.bom.indexOf(item) ?? -1;
                      const isSelected = selectedBomIndex === index;
                      const isExpanded = expandedBomRows.has(index);
                      const selectedCandidate = item.warehouse_recommendations.find(
                        (candidate) => candidate.sku === item.selected_warehouse_sku
                      ) ?? item.warehouse_recommendations[0];
                      const matchConfidence = selectedCandidate?.score ?? 0;
                      const isAiBest = Boolean(selectedCandidate && selectedCandidate.sku === item.warehouse_recommendations[0]?.sku);
                      return (
                      <div
                        className={`${item.included !== false ? "bomRow" : "bomRow excluded"}${isSelected ? " selected" : ""}`}
                        key={`${item.part_name}-${index}`}
                      >
                        <div className="bomSelectCell">
                          <button
                            aria-expanded={isExpanded}
                            aria-label={`${isExpanded ? "Collapse" : "Expand"} row ${index + 1}`}
                            className="rowDisclosure"
                            onClick={() => setExpandedBomRows((current) => {
                              const next = new Set(current);
                              if (next.has(index)) next.delete(index); else next.add(index);
                              return next;
                            })}
                            title={isExpanded ? "Collapse row details" : "Expand row details"}
                            type="button"
                          >
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          </button>
                          <button
                            aria-label={`Select BOM row ${index + 1}`}
                            className="rowSelectButton"
                            onClick={() => setSelectedBomIndex(index)}
                            title="Select row for editing"
                            type="button"
                          >
                            <span className={isSelected ? "rowRadio selected" : "rowRadio"} aria-hidden="true" />
                          </button>
                          <span className="rowNumber">#{index + 1}</span>
                        </div>
                        <div className="bomPartCell">
                          <strong className="partName">{item.part_name}</strong>
                          <span className="partMeta">{item.category}</span>
                          <div className="bomStatusLine">
                            <span>{item.assembly_children.length ? "L1 assembly" : "L1 part"}</span>
                            <span>{item.included !== false ? "Included" : "Excluded"}</span>
                            {item.assembly_children.length > 0 && <span>{item.assembly_children.length} L2 items</span>}
                          </div>
                        </div>
                        <div className="bomDataCell">
                          <span><b>Material</b>{item.material || "Not identified"}</span>
                          <span><b>Condition</b>{item.condition_summary || "Not recorded"}</span>
                          <span><b>Quantity</b>{item.quantity}</span>
                          <span><b>Evidence</b>{item.source_images.length} image{item.source_images.length === 1 ? "" : "s"}{item.visible_part_nos.length ? ` · ${item.visible_part_nos.join(", ")}` : ""}</span>
                        </div>
                        <div className="selectedCandidate">
                          {selectedCandidate ? (
                            <>
                              <div className="matchSelectionHeader">
                                <span className={isAiBest ? "matchSource aiBest" : "matchSource userChoice"}>{isAiBest ? "AI best match" : "User selected"}</span>
                                <select
                                  aria-label={`Selected warehouse match for ${item.part_name}`}
                                  value={selectedCandidate.sku}
                                  onChange={(event) => updateBomItem(index, { selected_warehouse_sku: event.target.value })}
                                >
                                  {item.warehouse_recommendations.map((candidate, candidateIndex) => (
                                    <option key={candidate.sku} value={candidate.sku}>
                                      {candidateIndex === 0 ? "Best · " : "Alternative · "}{candidate.part_name} · {Math.round(candidate.score * 100)}%
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <strong>{selectedCandidate.part_name}</strong>
                              <span>{selectedCandidate.sku}</span>
                              <span>{selectedCandidate.supplier} · {selectedCandidate.currency} {selectedCandidate.unit_cost.toFixed(2)}</span>
                              <span>Stock {selectedCandidate.stock_quantity} · {item.warehouse_recommendations.length} option{item.warehouse_recommendations.length === 1 ? "" : "s"}</span>
                            </>
                          ) : <span className="emptyCandidate">No warehouse match</span>}
                        </div>
                        <div className="bomConfidenceCell">
                          <div>
                            <span>Detection</span>
                            <strong className={`confidenceValue ${confidenceTone(item.best_confidence)}`}>{Math.round(item.best_confidence * 100)}%</strong>
                          </div>
                          <div>
                            <span>Match</span>
                            <strong className={`confidenceValue ${confidenceTone(matchConfidence)}`}>{selectedCandidate ? `${Math.round(matchConfidence * 100)}%` : "N/A"}</strong>
                          </div>
                        </div>
                        <div className="rowActions">
                          <button aria-label={`${item.included !== false ? "Remove" : "Restore"} row ${index + 1}`} className="rowAction compactIcon danger" title={item.included !== false ? "Remove row" : "Restore row"} type="button" onClick={() => {
                            updateBomItem(index, { included: item.included === false });
                          }}>
                            {item.included !== false ? <Trash2 size={15} /> : <RefreshCw size={15} />}
                          </button>
                        </div>
                        {isExpanded && (
                          <div className="bomExpandedDetails">
                            <section className="bomDetailSection">
                              <h3>Assembly structure</h3>
                              {item.assembly_children.length ? <AssemblyTree item={item} parentLabel={String(index + 1)} /> : <p>This is treated as a standalone Level 1 part.</p>}
                              {item.assembly_children.map((child, childIndex) => (
                                <div className={child.included !== false ? "bomChildControl" : "bomChildControl excluded"} key={`${child.part_name}-${childIndex}`}>
                                  <span><strong>{treeChildLabel(childIndex)}. {child.part_name}</strong>x{child.quantity} · {child.role}</span>
                                  <select
                                    aria-label={`Warehouse match for ${child.part_name}`}
                                    value={child.selected_warehouse_sku ?? ""}
                                    onChange={(event) => updateBomChild(index, childIndex, { selected_warehouse_sku: event.target.value || null })}
                                  >
                                    <option value="">Best match</option>
                                    {child.warehouse_recommendations.map((candidate) => (
                                      <option key={candidate.sku} value={candidate.sku}>{candidate.part_name} · {candidate.sku}</option>
                                    ))}
                                  </select>
                                  <button aria-label={`${child.included !== false ? "Remove" : "Restore"} ${child.part_name}`} className="compactIcon" title={child.included !== false ? "Remove Level 2 item" : "Restore Level 2 item"} type="button" onClick={() => {
                                    updateBomChild(index, childIndex, { included: child.included === false });
                                  }}>
                                    {child.included !== false ? <Trash2 size={14} /> : <Plus size={14} />}
                                  </button>
                                </div>
                              ))}
                            </section>
                            <section className="bomDetailSection">
                              <h3>Warehouse alternatives</h3>
                              <div className="bomCandidates">
                                {item.warehouse_recommendations.map((candidate) => (
                                  <button
                                    className={selectedCandidate?.sku === candidate.sku ? "candidate active" : "candidate"}
                                    key={candidate.sku}
                                    onClick={() => updateBomItem(index, { selected_warehouse_sku: candidate.sku })}
                                    type="button"
                                  >
                                    <strong>{candidate.part_name}</strong>
                                    <span>{candidate.sku} · {candidate.supplier}</span>
                                    <span>{candidate.currency} {candidate.unit_cost.toFixed(2)} · stock {candidate.stock_quantity} · match {Math.round(candidate.score * 100)}%</span>
                                    {candidate.fitment_notes && <small>{candidate.fitment_notes}</small>}
                                  </button>
                                ))}
                                {!item.warehouse_recommendations.length && <span className="emptyCandidate">No warehouse alternatives found.</span>}
                              </div>
                            </section>
                            <section className="bomDetailSection reviewDetail">
                              <h3>Review reasoning</h3>
                              <p>{item.recommendation_reason || "No additional recommendation reason available."}</p>
                              {item.notes && <p><strong>Detection notes</strong>{item.notes}</p>}
                              {item.assembly_reason && <p><strong>Assembly decision</strong>{item.assembly_reason}</p>}
                            </section>
                          </div>
                        )}
                      </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {showCostSheet && (
                <section>
                  <div className="sectionTitleRow">
                    <h2>Cost Sheet</h2>
                    <strong>{job.cost_sheet?.currency ?? "USD"} {filteredCostTotal.toFixed(2)}</strong>
                  </div>
                  <div className="costTable">
                    <div className="costHead">
                      <span>Found part</span>
                      <span>Similar warehouse part</span>
                      <span>Qty</span>
                      <span>Unit</span>
                      <span>Total</span>
                    </div>
                    {filteredCostItems.map((item, index) => {
                      const isLevel2 = (item.bom_level ?? 1) > 1;
                      const parentNumber = levelOneIndex(filteredCostItems, index);
                      const linkedLabel = isLevel2 ? treeChildLabel(childIndexForParent(filteredCostItems, index) - 1) : String(parentNumber);
                      return (
                      <div
                        className={isLevel2 ? "costRow level2CostRow" : "costRow"}
                        key={`${item.detected_part_name}-${item.matched_sku}`}
                      >
                        <div>
                          <strong>{linkedLabel}. {item.detected_part_name}</strong>
                          <span>{isLevel2 ? `Linked to ${parentNumber}. ${item.parent_detected_part_name}` : item.category}</span>
                          <em className={isLevel2 ? "requirementBadge linked" : "requirementBadge mandatory"}>
                            {isLevel2 ? "Level 2" : "Mandatory"}
                          </em>
                        </div>
                        <div>
                          <strong>{item.matched_part_name}</strong>
                          <span>{item.matched_sku} · {isLevel2 ? item.row_type.replaceAll("_", " ") : `${Math.round(item.match_confidence * 100)}% match`}</span>
                          <em>{item.supplier}</em>
                        </div>
                        <b>{item.quantity}</b>
                        <span>{item.currency} {item.unit_cost.toFixed(2)}</span>
                        <strong>{item.currency} {item.total_cost.toFixed(2)}</strong>
                        {!isLevel2 && <div className="costDetails">
                          <div>
                            <span>SKU</span>
                            <strong>{item.matched_sku}</strong>
                          </div>
                          <div>
                            <span>Category</span>
                            <strong>{item.category}</strong>
                          </div>
                          <div>
                            <span>Material</span>
                            <strong>{item.material}</strong>
                          </div>
                          <div>
                            <span>Currency</span>
                            <strong>{item.currency}</strong>
                          </div>
                          <div>
                            <span>Parts total</span>
                            <strong>{item.currency} {(item.parts_total_cost ?? item.total_cost).toFixed(2)}</strong>
                          </div>
                          <div>
                            <span>Labor required</span>
                            <strong>{item.labor_required ? "Yes" : "No"}</strong>
                          </div>
                          <div>
                            <span>Labor hours</span>
                            <strong>{(item.labor_hours ?? 0).toFixed(2)}</strong>
                          </div>
                          <div>
                            <span>Labor cost</span>
                            <strong>{item.currency} {(item.labor_cost ?? 0).toFixed(2)}</strong>
                          </div>
                          <div>
                            <span>Supplier</span>
                            <strong>{item.supplier}</strong>
                          </div>
                          <div>
                            <span>Stock quantity</span>
                            <strong>{item.stock_quantity}</strong>
                          </div>
                          <div>
                            <span>Match confidence</span>
                            <strong>{Math.round(item.match_confidence * 100)}%</strong>
                          </div>
                          <div>
                            <span>Cluster</span>
                            <strong>{item.cluster_key}</strong>
                          </div>
                          <div className="wide">
                            <span>Mandatory item</span>
                            <strong>{item.matched_part_name} · {item.matched_sku}</strong>
                          </div>
                          <div className="wide">
                            <span>Additional / good to have</span>
                            <strong>{item.consumables_required.length ? item.consumables_required.join(" | ") : "No additional item listed"}</strong>
                          </div>
                          <div className="wide full">
                            <span>Level 2 BOM tree</span>
                            <AssemblyTree
                              item={findBomForCostItem(item, job.bom)}
                              level2Items={item.level_2_items}
                              title={`${linkedLabel}. ${item.detected_part_name}`}
                              reason="Level-2 items are included for cost review and labor reasoning; price them separately only when procurement requires separate SKU matching."
                              parentLabel={linkedLabel}
                            />
                          </div>
                          <div className="wide">
                            <span>Labor reason</span>
                            <strong>{item.labor_reason || "No labor reasoning available"}</strong>
                          </div>
                          <div className="wide">
                            <span>Fitment notes</span>
                            <strong>{item.fitment_notes}</strong>
                          </div>
                        </div>}
                        {isLevel2 && (
                          <div className="level2CostDetail">
                            <span>Parent</span>
                            <strong>{item.parent_detected_part_name}</strong>
                            <span>Reason</span>
                            <strong>{item.fitment_notes}</strong>
                          </div>
                        )}
                      </div>
                    )})}
                    {filteredCostItems.length === 0 && (
                      <div className="emptyState">No warehouse match passes the current confidence setting.</div>
                    )}
                    <div className="costTotal">
                      <span>Grand total</span>
                      <strong>{job.cost_sheet?.currency ?? "USD"} {filteredCostTotal.toFixed(2)}</strong>
                    </div>
                  </div>
                </section>
              )}

              {showTokenUsage && (
                <section>
                  <div className="sectionTitleRow">
                    <h2>Token Usage</h2>
                    <strong>{job.token_usage?.total_tokens ?? 0} tokens</strong>
                  </div>
                  <div className="tokenModeSummary">
                    <span>{VISION_TOKEN_MODES[visionMode].label}</span>
                    <strong>Image detail {VISION_TOKEN_MODES[visionMode].detail}</strong>
                    <strong>Output {VISION_TOKEN_MODES[visionMode].responseBudget}</strong>
                  </div>
                  <div className="tokenTable">
                    <div className="tokenHead">
                      <span>Step</span>
                      <span>Model</span>
                      <span>Used for</span>
                      <span>Input</span>
                      <span>Output</span>
                      <span>Total</span>
                    </div>
                    {(job.token_usage?.items ?? []).map((item, index) => (
                      <div className="tokenRow" key={`${item.step}-${index}`}>
                        <strong>{item.step.replaceAll("_", " ")}</strong>
                        <span>{item.model}</span>
                        <p>{item.purpose}</p>
                        <b>{item.input_tokens}</b>
                        <b>{item.output_tokens}</b>
                        <b>{item.total_tokens}</b>
                      </div>
                    ))}
                    {(job.token_usage?.items.length ?? 0) === 0 && (
                      <div className="emptyState">No external model tokens were used for this analysis.</div>
                    )}
                    <div className="tokenTotal">
                      <span>Input {job.token_usage?.total_input_tokens ?? 0}</span>
                      <span>Output {job.token_usage?.total_output_tokens ?? 0}</span>
                      <strong>Total {job.token_usage?.total_tokens ?? 0}</strong>
                    </div>
                  </div>
                </section>
              )}
            </div>
          )}

        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
