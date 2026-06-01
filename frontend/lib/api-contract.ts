export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type WorldFacts = {
  attrs: Record<string, Record<string, string>>;
  edges: Array<{
    subject_id: string;
    relation: string;
    object_id: string;
    ts?: number;
    confidence?: number;
    source?: string;
  }>;
};

export type StateView = {
  turn_id: number | null;
  recent_messages: ChatMessage[];
  chat_history: ChatMessage[];
  narration: string;
  world_facts: WorldFacts;
  allowed_actions: string[];
  retrieved_cards: string[];
  validated_ops: Array<Record<string, unknown>>;
  errors: string[];
  custom_ui_panels: Array<Record<string, unknown>>;
  ui_template_id: string;
  ui_variable_values: Record<string, unknown>;
  ui_panel_visibility: Record<string, boolean>;
  save_slot: string | null;
  ui_generation_status: string;
  ui_update_status: string;
  ui_update_mode: string;
  ui_auto_update_every: number;
  // Backend-facing display fields. The frontend still normalizes fallbacks
  // when the API is unavailable.
  enabled_packs: string[];
  location_label: string;
  storage_backend_label: string;
};

export type PackRecord = {
  pack_id: string;
  name: string;
  version: string;
  author: string;
  description: string;
  cards_root: string;
  enabled: boolean;
  source: string;
};

export type LLMSettingsPublic = {
  provider: string;
  model_name: string;
  embedding_model: string;
  base_url: string;
  api_key_set: boolean;
  use_mock_llm: boolean;
  force_fake_embeddings: boolean;
};

export type LLMSettingsUpdateRequest = {
  provider: string;
  model_name: string;
  embedding_model: string;
  base_url: string;
  api_key: string;
  use_mock_llm: boolean;
  force_fake_embeddings: boolean;
};

export type LLMPlanRecord = {
  plan_id: string;
  name: string;
  description: string;
  provider: string;
  model_name: string;
  embedding_model: string;
  base_url: string;
  input_tokens_per_coin: number;
  output_tokens_per_coin: number;
  display_order: number;
};

export type LLMPlanSelection = {
  selected_plan_id: string;
  name?: string;
  description?: string;
  input_tokens_per_coin?: number;
  output_tokens_per_coin?: number;
};

export type SettingsOverview = {
  plans: LLMPlanRecord[];
  selected_plan_id: string;
  coin_balance: number;
  redeem_tiers: Record<string, number>;
};

export type LLMPlanSelectRequest = {
  plan_id: string;
};

export type CoinRedeemRequest = {
  redeem_key: string;
};

export type CoinRedeemResponse = {
  coins_added: number;
  balance_after: number;
};

export type CoinBalanceResponse = {
  coin_balance: number;
};

export type CoinConsumptionRecord = {
  ledger_id: number;
  created_at: string;
  delta_coin: number;
  balance_after: number;
  scene: string;
  plan_id: string;
  input_tokens: number;
  output_tokens: number;
  input_coin_cost: number;
  output_coin_cost: number;
};

export type SetupBootstrapView = {
  selected_slot: string;
  available_slots: string[];
  language: string;
  ui_mode: string;
  ui_auto_update_every: number;
  selected_pack_ids: string[];
};

export type SessionSummary = {
  slot_id: string;
  language: string;
  enabled_packs: string[];
  location_label: string;
  turn_count: number;
  updated_label: string;
  ui_generation_status: string;
};

export type SessionManagerView = {
  selected_slot: string;
  backend_status: string;
  storage_backend: string;
  last_sync_label: string;
  sessions: SessionSummary[];
};

export type OkResponse = {
  ok: boolean;
};

export type AuthUser = {
  id: string;
  email: string;
  username: string;
};

export type LoginRequest = {
  email_or_username: string;
  password: string;
};

export type RegisterRequest = {
  email: string;
  username: string;
  password: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export type StartGameRequest = {
  save_slot: string;
  pack_ids?: string[];
  language?: string;
  ui_template_id?: string;
};

export type LoadGameRequest = {
  save_slot: string;
  language?: string;
};

export type DuplicateSessionRequest = {
  target_slot?: string;
};

export type PackEnabledRequest = {
  enabled: boolean;
};

export type PackExportResponse = {
  ok: boolean;
  pack_id: string;
  export_path: string;
};

export type StepRequest = {
  input_text: string;
};

export type GameActionResponse = {
  result: Record<string, unknown>;
  state_view: Partial<StateView>;
};

export type GameStepStreamEvent =
  | { type: "narration_delta"; delta: string }
  | { type: "done"; response: GameActionResponse }
  | { type: "error"; detail: string };

export type DesignerCardSummary = {
  path: string;
  folder_path: string;
  card_id: string;
  card_type: string;
  category: string;
  title: string;
};

export type DesignerCardPayload = {
  path: string;
  folder_path: string;
  pack_id: string;
  card_type: string;
  card_id: string;
  frontmatter: Record<string, unknown>;
  body: string;
};

export type CanvasWorkspaceState = {
  canvas_nodes: Array<Record<string, unknown>>;
  canvas_edges: Array<Record<string, unknown>>;
  canvas_offset: { x: number; y: number };
  canvas_scale: number;
  selected_node_id: string | null;
  selected_edge_id: string | null;
  connect_source_id: string | null;
  entry_events: string[];
};

export type SaveCanvasWorkspaceRequest = CanvasWorkspaceState;

export type CreateDesignerPackRequest = {
  pack_id: string;
  name: string;
  version: string;
  author: string;
  description: string;
};

export type SaveDesignerCardRequest = {
  card_type: string;
  card_id: string;
  folder_path?: string;
  frontmatter_text: string;
  body: string;
  original_path?: string;
};

export type ValidateDesignerCardRequest = {
  frontmatter_text: string;
  body: string;
};

export type DesignerAgentSession = {
  session_id: string;
  selected_pack_id: string;
  mode: string;
  state: Record<string, unknown>;
  updated_at?: string | null;
};

export type DesignerAgentMessageResponse = {
  session_id: string;
  assistant: string;
  tool_logs: string[];
  selected_pack_id: string;
  state: Record<string, unknown>;
};

export type UiTemplateRecord = {
  template_id: string;
  pack_id: string;
  name: string;
  template: Record<string, unknown>;
  variable_template: Record<string, unknown>;
  sessions_in_use: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CreateUiTemplateRequest = {
  name: string;
  template?: Record<string, unknown>;
  variable_template?: Record<string, unknown>;
};
