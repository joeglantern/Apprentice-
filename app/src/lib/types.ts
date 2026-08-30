/** Mirrors the backend's doc 01 section 3 layer shape and the /generate job response. */

export type LayerType = "text" | "shape" | "image";

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Colour {
  hex: string;
  opacity: number;
}

export interface Typography {
  font_family: string;
  font_size: number;
  font_weight: number;
  letter_spacing?: number;
  line_height?: number;
}

export interface Layer {
  layer_id: string;
  name: string;
  type: LayerType;
  z_index: number;
  bbox: BBox;
  visible?: boolean;
  text?: string;
  align?: "left" | "center" | "right";
  typography?: Typography;
  color?: Colour;
  background?: Colour;
  raster_key?: string;
  raster_url?: string;
  image_prompt?: string;
}

export interface DesignPlanElement {
  role: string;
  content: string;
  priority: number;
  image_prompt?: string | null;
  notes?: string;
}

export interface DesignPlan {
  rationale: string;
  canvas: { width: number; height: number };
  mood: string[];
  palette_intent: string[];
  elements: DesignPlanElement[];
  source: "director" | "heuristic";
}

export interface GenerateResult {
  canvas_width: number;
  canvas_height: number;
  aesthetic_version: string;
  renderer: string;
  layers: Layer[];
}

export type JobStatus = "queued" | "planning" | "layout" | "render" | "done" | "error";

export interface Job {
  job_id: string;
  status: JobStatus;
  prompt: string;
  aesthetic_version: string;
  plan: DesignPlan | null;
  result: GenerateResult | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Aesthetic {
  version: string;
  label: string;
  kind: string;
  trained_on?: number | null;
}

export interface GenerateAccepted {
  job_id: string;
  status: string;
}

export interface ProgressEvent {
  job_id: string;
  stage: JobStatus;
  message?: string;
  step?: number;
  total?: number;
}
