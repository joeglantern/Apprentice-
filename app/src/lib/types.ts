/** Mirrors the backend's doc 01 section 3 layer shape and the /generate job response. */

export type LayerType = "text" | "shape" | "image" | "icon";

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
  letter_spacing?: number; // px, as layout.py emits it
  line_height?: number; // multiplier of font_size
}

export interface Layer {
  layer_id: string;
  name: string;
  type: LayerType;
  z_index: number;
  bbox: BBox;
  visible?: boolean;
  shape?: "rect" | "ellipse"; // shapes only; rect when absent
  icon?: string; // icon layers: a key into lib/icons.ts
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
  typeface?: "inter" | "bebas" | "playfair" | "grotesk";
  composition?: "anchor" | "centered" | "split";
  date_badge?: string | null;
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

/** A client's fixed identity: the director treats it as binding across a campaign. */
export interface BrandKit {
  name: string;
  palette: string[]; // #RRGGBB
  typeface?: "inter" | "bebas" | "playfair" | "grotesk";
}

/** poster: plan + layout + render. image: one photograph. logo: one mark. */
export type JobKind = "poster" | "image" | "logo";

/** The /generate list endpoint's row shape - no plan/result, matching the backend's
 * JobSummary (those fields can be large and the list view never reads them). */
export interface JobSummary {
  job_id: string;
  status: JobStatus;
  prompt: string;
  /** A short name written by the backend when the job landed. Null on jobs made
   * before titles existed and on anything unfinished, so always fall back to prompt. */
  title?: string | null;
  aesthetic_version: string;
  kind: JobKind;
  created_at: string;
  updated_at: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  prompt: string;
  title?: string | null;
  aesthetic_version: string;
  kind: JobKind;
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

/** One turn in a chat thread. `action` and `job_id` are set on assistant turns that
 * did work; `landed` is filled in by the server once that job reaches a terminal
 * state - the reply itself is written before the render runs and only ever states an
 * intent, so it is the one field that describes a result. */
export interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  text: string;
  action: "revise" | "edit_copy" | "new_direction" | null;
  job_id: string | null;
  landed: string | null;
  created_at: string;
}

export interface ChatThread {
  thread_id: string;
  active_job_id: string | null;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

/** A quick-action chip. Its intent is known from the button, so the server carries it
 * out without a model call - the chips stay instant and cannot be misrouted. */
export type QuickAction = "swap_photo" | "recompose";
