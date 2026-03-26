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
