import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Boxes,
  Download,
  FileSearch,
  ImagePlus,
  Layers3,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
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
};

type CostSheetItem = {
  detected_part_name: string;
  matched_part_name: string;
  matched_sku: string;
  category: string;
  material: string;
  supplier: string;
  cluster_key: string;
  quantity: number;
  unit_cost: number;
  total_cost: number;
  currency: string;
  stock_quantity: number;
  match_confidence: number;
  fitment_notes: string;
  consumables_required: string[];
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

const API_BASE = "";

function confidenceLabel(value: number) {
  if (value >= 0.86) return "High";
  if (value >= 0.7) return "Review";
  return "Low";
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
    item.total_cost.toFixed(2),
    item.currency,
    item.supplier,
    String(item.stock_quantity),
    item.match_confidence.toFixed(2),
    item.consumables_required.join(" | "),
    item.fitment_notes
  ]);
  rows.push(["", "", "", "", "Grand Total", "", "", sheet.total_cost.toFixed(2), sheet.currency, "", "", "", "", ""]);
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
  const [showSettings, setShowSettings] = useState(false);
  const [minDetectionConfidence, setMinDetectionConfidence] = useState(0);
  const [minBomConfidence, setMinBomConfidence] = useState(0);
  const [minMatchConfidence, setMinMatchConfidence] = useState(0);
  const [activeAgentStep, setActiveAgentStep] = useState(-1);
  const [edits, setEdits] = useState<Record<string, EditableDetection>>({});

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
    setShowSettings(false);
    setActiveAgentStep(-1);
    setEdits({});
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function analyze() {
    if (!files.length) return;
    setLoading(true);
    setActiveAgentStep(0);
    setError(null);
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
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

  const filteredDetections = (job?.detections ?? []).filter((item) => {
    const text = `${item.part_name} ${item.category} ${item.material} ${item.condition}`.toLowerCase();
    return text.includes(query.toLowerCase()) && item.confidence >= minDetectionConfidence;
  });
  const sourceImages = Array.from(new Set((job?.detections ?? []).map((item) => item.source_image).filter(Boolean))) as string[];
  const selectedDetections = (job?.detections ?? []).filter(
    (item) => item.source_image === selectedSource && item.confidence >= minDetectionConfidence
  );
  const filteredBom = (job?.bom ?? []).filter((item) => item.best_confidence >= minBomConfidence);
  const filteredCostItems = (job?.cost_sheet?.items ?? []).filter((item) => item.match_confidence >= minMatchConfidence);
  const filteredCostTotal = filteredCostItems.reduce((sum, item) => sum + item.total_cost, 0);
  const resetConfidenceFilters = () => {
    setMinDetectionConfidence(0);
    setMinBomConfidence(0);
    setMinMatchConfidence(0);
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
        <div className={statusClass} title={health?.openai_detail ?? "Backend health check is unavailable"}>
          <Activity size={16} />
          {statusText}
        </div>
      </section>

      <section className="workbench">
        <aside className="uploadPanel">
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

          {error && <div className="errorBox">{error}</div>}

          {(loading || sidebarTrace.length > 0) && (
            <div className="liveTracePanel">
              <div className="liveTraceHeader">
                <Workflow size={17} />
                <strong>{loading ? "Agents running" : "Agent trace"}</strong>
              </div>
              <div className="liveTraceList">
                {sidebarTrace.map((item, index) => (
                  <div className={`liveTraceRow ${item.status}`} key={`${item.agent}-${item.action}-${index}`}>
                    {item.status === "running" ? <Loader2 className="spin" size={15} /> : <ShieldCheck size={15} />}
                    <div>
                      <strong>{item.agent.replaceAll("_", " ")}</strong>
                      <span>{item.action.replaceAll("_", " ")} · {item.status}</span>
                      <p>{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

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
              </div>
            </section>
          )}

          {(showDetectedParts || showBomSheet || showCostSheet || showTokenUsage) && (
            <div className={[showDetectedParts, showBomSheet, showCostSheet, showTokenUsage].filter(Boolean).length > 1 ? "split" : "singleSection"}>
              {showDetectedParts && (
                <section>
                  <h2>Detected Parts</h2>
                  <div className="cardGrid">
                    {filteredDetections.map((item) => (
                      <article
                        className={focusedDetectionId === item.id ? "partCard focused" : "partCard"}
                        id={`part-card-${item.id}`}
                        key={item.id}
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
                </section>
              )}

              {showBomSheet && (
                <section>
                  <h2>Unique BOM Sheet</h2>
                  <div className="bomTable">
                    <div className="bomHead">
                      <span>Part</span><span>Qty</span><span>Confidence</span>
                    </div>
                    {filteredBom.map((item) => (
                      <div className="bomRow" key={item.part_name}>
                        <div>
                          <strong>{item.part_name}</strong>
                          <span>{item.material}</span>
                        </div>
                        <b>{item.quantity}</b>
                        <em>{Math.round(item.best_confidence * 100)}%</em>
                      </div>
                    ))}
                  </div>

                  <div className="bomRecommendations">
                    <h2>Agent Recommendations</h2>
                    <div className="recommendationList">
                      {job.recommendations.map((item, index) => (
                        <article className="recommendation" key={`${item.part_name}-${index}`}>
                          <div>
                            <strong>{item.part_name}</strong>
                            <span>{item.recommendation_type.replaceAll("_", " ")}</span>
                          </div>
                          <p>{item.reason}</p>
                          <em>{item.related_parts.length ? item.related_parts.join(" | ") : "No related part found"}</em>
                        </article>
                      ))}
                      {job.recommendations.length === 0 && (
                        <div className="emptyState">No missing or similar-part recommendation was raised.</div>
                      )}
                    </div>
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
                    {filteredCostItems.map((item) => (
                      <div className="costRow" key={`${item.detected_part_name}-${item.matched_sku}`}>
                        <div>
                          <strong>{item.detected_part_name}</strong>
                          <span>{item.category}</span>
                          <em className="requirementBadge mandatory">Mandatory</em>
                        </div>
                        <div>
                          <strong>{item.matched_part_name}</strong>
                          <span>{item.matched_sku} · {Math.round(item.match_confidence * 100)}% match</span>
                          <em>{item.supplier}</em>
                        </div>
                        <b>{item.quantity}</b>
                        <span>{item.currency} {item.unit_cost.toFixed(2)}</span>
                        <strong>{item.currency} {item.total_cost.toFixed(2)}</strong>
                        <div className="costDetails">
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
                          <div className="wide">
                            <span>Fitment notes</span>
                            <strong>{item.fitment_notes}</strong>
                          </div>
                        </div>
                      </div>
                    ))}
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
