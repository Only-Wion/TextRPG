import type {
  AuthUser,
  AuthTokenResponse,
  GameActionResponse,
  CreateDesignerPackRequest,
  DesignerAgentMessageResponse,
  DesignerAgentSession,
  DesignerCardPayload,
  DesignerCardSummary,
  DuplicateSessionRequest,
  LLMSettingsPublic,
  LoginRequest,
  LLMSettingsUpdateRequest,
  LoadGameRequest,
  OkResponse,
  PackExportResponse,
  PackEnabledRequest,
  PackRecord,
  RegisterRequest,
  SessionManagerView,
  SetupBootstrapView,
  SaveDesignerCardRequest,
  StartGameRequest,
  StateView,
  StepRequest,
  ValidateDesignerCardRequest,
} from "./api-contract";
import { getClientAccessToken } from "./auth";
import {
  createMockLLMSettings,
  createMockPacks,
  createMockSessionManagerView,
  createMockSetupBootstrapView,
  createMockStateView,
} from "./mock-data";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

async function safeJsonFetch<T>(path: string): Promise<T | null> {
  try {
    const headers = await buildHeaders({ Accept: "application/json" });
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      headers,
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function jsonRequest<TResponse, TBody>(path: string, method: string, body: TBody): Promise<TResponse> {
  const headers = await buildHeaders({
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Keep the fallback message when the response body is not JSON.
    }

    throw new Error(message);
  }

  return (await response.json()) as TResponse;
}

function normalizeStateView(payload: Partial<StateView> | null): StateView {
  const fallback = createMockStateView();

  if (!payload) {
    return fallback;
  }

  return {
    ...fallback,
    ...payload,
    world_facts: {
      attrs: payload.world_facts?.attrs ?? fallback.world_facts.attrs,
      edges: payload.world_facts?.edges ?? fallback.world_facts.edges,
    },
    recent_messages: payload.recent_messages ?? fallback.recent_messages,
    chat_history: payload.chat_history ?? fallback.chat_history,
    allowed_actions: payload.allowed_actions ?? fallback.allowed_actions,
    retrieved_cards: payload.retrieved_cards ?? fallback.retrieved_cards,
    validated_ops: payload.validated_ops ?? fallback.validated_ops,
    errors: payload.errors ?? fallback.errors,
    custom_ui_panels: payload.custom_ui_panels ?? fallback.custom_ui_panels,
    enabled_packs: payload.enabled_packs ?? fallback.enabled_packs,
    location_label: payload.location_label ?? fallback.location_label,
    storage_backend_label: payload.storage_backend_label ?? fallback.storage_backend_label,
  };
}

function normalizePacks(payload: PackRecord[] | null): PackRecord[] {
  return payload && payload.length > 0 ? payload : createMockPacks();
}

function normalizeLLMSettings(payload: Partial<LLMSettingsPublic> | null): LLMSettingsPublic {
  return {
    ...createMockLLMSettings(),
    ...(payload ?? {}),
  };
}

async function buildHeaders(baseHeaders: Record<string, string>): Promise<Record<string, string>> {
  let token: string | null = null;

  if (typeof window === "undefined") {
    const { getServerAccessToken } = await import("./auth");
    token = await getServerAccessToken();
  } else {
    token = getClientAccessToken();
  }

  return token
    ? {
        ...baseHeaders,
        Authorization: `Bearer ${token}`,
      }
    : baseHeaders;
}

export async function getGameStateView(): Promise<StateView> {
  const payload = await safeJsonFetch<Partial<StateView>>("/game/state");
  return normalizeStateView(payload);
}

export async function getPacks(): Promise<PackRecord[]> {
  const payload = await safeJsonFetch<PackRecord[]>("/packs");
  return normalizePacks(payload);
}

export async function getLLMSettings(): Promise<LLMSettingsPublic> {
  const payload = await safeJsonFetch<Partial<LLMSettingsPublic>>("/settings/llm");
  return normalizeLLMSettings(payload);
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  return safeJsonFetch<AuthUser>("/auth/me");
}

export async function getSetupBootstrapView(): Promise<SetupBootstrapView> {
  const [stateView, packs] = await Promise.all([getGameStateView(), getPacks()]);

  const selectedPackIds = packs.filter((pack) => pack.enabled).map((pack) => pack.pack_id);
  const fallback = createMockSetupBootstrapView();

  return {
    ...fallback,
    selected_slot: stateView.save_slot ?? fallback.selected_slot,
    available_slots: fallback.available_slots,
    language: "zh",
    ui_mode: stateView.ui_update_mode,
    ui_auto_update_every: stateView.ui_auto_update_every,
    selected_pack_ids: selectedPackIds.length > 0 ? selectedPackIds : fallback.selected_pack_ids,
  };
}

export async function getSessionManagerView(): Promise<SessionManagerView> {
  const payload = await safeJsonFetch<SessionManagerView>("/game/sessions");
  const fallback = createMockSessionManagerView();
  if (!payload || payload.sessions.length === 0) {
    return fallback;
  }
  return {
    ...fallback,
    ...payload,
  };
}

export async function startGameSession(payload: StartGameRequest): Promise<OkResponse> {
  return jsonRequest<OkResponse, StartGameRequest>("/game/start", "POST", payload);
}

export async function login(payload: LoginRequest): Promise<AuthTokenResponse> {
  return jsonRequest<AuthTokenResponse, LoginRequest>("/auth/login", "POST", payload);
}

export async function register(payload: RegisterRequest): Promise<AuthTokenResponse> {
  return jsonRequest<AuthTokenResponse, RegisterRequest>("/auth/register", "POST", payload);
}

export async function logout(): Promise<OkResponse> {
  return jsonRequest<OkResponse, Record<string, never>>("/auth/logout", "POST", {});
}

export async function loadGameSession(payload: LoadGameRequest): Promise<OkResponse> {
  return jsonRequest<OkResponse, LoadGameRequest>("/game/load", "POST", payload);
}

export async function duplicateGameSession(
  slotId: string,
  payload: DuplicateSessionRequest = {},
): Promise<SessionManagerView> {
  return jsonRequest<SessionManagerView, DuplicateSessionRequest>(
    `/game/sessions/${slotId}/duplicate`,
    "POST",
    payload,
  );
}

export async function archiveGameSession(slotId: string): Promise<SessionManagerView> {
  return jsonRequest<SessionManagerView, Record<string, never>>(
    `/game/sessions/${slotId}/archive`,
    "POST",
    {},
  );
}

export async function stepGameSession(payload: StepRequest): Promise<GameActionResponse> {
  return jsonRequest<GameActionResponse, StepRequest>("/game/step", "POST", payload);
}

export async function setPackEnabled(packId: string, enabled: boolean): Promise<OkResponse> {
  return jsonRequest<OkResponse, PackEnabledRequest>(`/packs/${packId}/enabled`, "PATCH", { enabled });
}

export async function removePack(packId: string): Promise<OkResponse> {
  return jsonRequest<OkResponse, Record<string, never>>(`/packs/${packId}`, "DELETE", {});
}

export async function exportPack(packId: string): Promise<PackExportResponse> {
  return jsonRequest<PackExportResponse, Record<string, never>>(`/packs/${packId}/export`, "POST", {});
}

export async function updateLLMSettings(payload: LLMSettingsUpdateRequest): Promise<LLMSettingsPublic> {
  return jsonRequest<LLMSettingsPublic, LLMSettingsUpdateRequest>("/settings/llm", "PUT", payload);
}

export async function getDesignerPacks(): Promise<PackRecord[]> {
  return safeJsonFetch<PackRecord[]>("/card-designer/packs").then((payload) => normalizePacks(payload));
}

export async function createDesignerPack(payload: CreateDesignerPackRequest): Promise<CreateDesignerPackRequest> {
  return jsonRequest<CreateDesignerPackRequest, CreateDesignerPackRequest>("/card-designer/packs", "POST", payload);
}

export async function getDesignerCardTypes(packId: string): Promise<string[]> {
  return (await safeJsonFetch<string[]>(`/card-designer/packs/${packId}/card-types`)) ?? [];
}

export async function getDesignerCards(
  packId: string,
  params?: { category?: string; keyword?: string },
): Promise<DesignerCardSummary[]> {
  const search = new URLSearchParams();
  if (params?.category) {
    search.set("category", params.category);
  }
  if (params?.keyword) {
    search.set("keyword", params.keyword);
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return (await safeJsonFetch<DesignerCardSummary[]>(`/card-designer/packs/${packId}/cards${suffix}`)) ?? [];
}

export async function loadDesignerCard(packId: string, cardPath: string): Promise<DesignerCardPayload> {
  const payload = await safeJsonFetch<DesignerCardPayload>(
    `/card-designer/packs/${packId}/cards/${encodeURI(cardPath)}`,
  );
  if (!payload) {
    throw new Error("Failed to load card.");
  }
  return payload;
}

export async function getDesignerCardTemplate(
  packId: string,
  cardType: string,
): Promise<Record<string, unknown>> {
  return jsonRequest<Record<string, unknown>, { card_type: string }>(
    `/card-designer/packs/${packId}/cards/template`,
    "POST",
    { card_type: cardType },
  );
}

export async function saveDesignerCard(
  packId: string,
  payload: SaveDesignerCardRequest,
): Promise<DesignerCardPayload> {
  return jsonRequest<DesignerCardPayload, SaveDesignerCardRequest>(
    `/card-designer/packs/${packId}/cards`,
    "POST",
    payload,
  );
}

export async function validateDesignerCard(payload: ValidateDesignerCardRequest): Promise<OkResponse> {
  return jsonRequest<OkResponse, ValidateDesignerCardRequest>("/card-designer/cards/validate", "POST", payload);
}

export async function deleteDesignerCard(packId: string, cardPath: string): Promise<OkResponse> {
  return jsonRequest<OkResponse, Record<string, never>>(
    `/card-designer/packs/${packId}/cards/${encodeURI(cardPath)}`,
    "DELETE",
    {},
  );
}

export async function createDesignerAgentSession(packId?: string): Promise<DesignerAgentSession> {
  return jsonRequest<DesignerAgentSession, { pack_id?: string }>(
    "/card-designer/agent/sessions",
    "POST",
    packId ? { pack_id: packId } : {},
  );
}

export async function getDesignerAgentSession(sessionId: string): Promise<DesignerAgentSession> {
  const payload = await safeJsonFetch<DesignerAgentSession>(`/card-designer/agent/sessions/${sessionId}`);
  if (!payload) {
    throw new Error("Failed to load designer session.");
  }
  return payload;
}

export async function sendDesignerAgentMessage(
  sessionId: string,
  message: string,
): Promise<DesignerAgentMessageResponse> {
  return jsonRequest<DesignerAgentMessageResponse, { message: string }>(
    `/card-designer/agent/sessions/${sessionId}/messages`,
    "POST",
    { message },
  );
}

export function normalizeStateViewFromAction(payload: Partial<StateView>): StateView {
  return normalizeStateView(payload);
}
