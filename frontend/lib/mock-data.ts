import type {
  LLMSettingsPublic,
  PackRecord,
  SessionManagerView,
  SetupBootstrapView,
  StateView,
} from "./api-contract";

export function createMockStateView(): StateView {
  return {
    turn_id: 18,
    recent_messages: [
      {
        role: "user",
        content: "Ask the bartender about the sealed room upstairs.",
      },
      {
        role: "assistant",
        content:
          "Mira lowers her voice. She says the upstairs room was locked after a guest vanished, but the old brass key still changes hands in whispers.",
      },
    ],
    chat_history: [
      {
        role: "user",
        content: "Look around the tavern and note who avoids eye contact.",
      },
      {
        role: "assistant",
        content:
          "Most patrons keep talking, but the barkeep glances at the stairwell every time the floor creaks above.",
      },
    ],
    narration:
      "Mira lowers her voice. She says the upstairs room was locked after a guest vanished, but the old brass key still changes hands in whispers.",
    world_facts: {
      attrs: {
        player: { location: "tavern", objective: "learn about the key" },
        mira: { trust: "uncertain", mood: "guarded" },
      },
      edges: [
        { subject_id: "player", relation: "at", object_id: "tavern" },
        { subject_id: "mira", relation: "knows", object_id: "sealed_room" },
      ],
    },
    allowed_actions: ["investigate", "ask", "observe", "use_item"],
    retrieved_cards: ["tavern", "bartender", "sealed_room"],
    validated_ops: [],
    errors: [],
    custom_ui_panels: [],
    ui_template_id: "",
    ui_variable_values: {},
    ui_panel_visibility: {},
    save_slot: "slot_001",
    ui_generation_status: "ready",
    ui_update_status: "idle",
    ui_update_mode: "manual",
    ui_auto_update_every: 1,
    enabled_packs: ["starter_kingdom"],
    location_label: "Tavern District",
    storage_backend_label: "local",
  };
}

export function createMockPacks(): PackRecord[] {
  return [
    {
      pack_id: "starter_kingdom",
      name: "Starter Kingdom",
      version: "0.1.0",
      author: "TextRPG",
      description: "Base kingdom narrative pack.",
      cards_root: "cards",
      enabled: true,
      source: "builtin",
    },
    {
      pack_id: "smugglers_wharf",
      name: "Smuggler's Wharf",
      version: "0.1.0",
      author: "TextRPG",
      description: "Dockside intrigue and rumor chains.",
      cards_root: "cards",
      enabled: false,
      source: "local",
    },
  ];
}

export function createMockLLMSettings(): LLMSettingsPublic {
  return {
    provider: "custom",
    model_name: "gpt-4o-mini",
    embedding_model: "text-embedding-3-small",
    base_url: "https://api.openai.com/v1",
    api_key_set: false,
    use_mock_llm: false,
    force_fake_embeddings: false,
  };
}

export function createMockSetupBootstrapView(): SetupBootstrapView {
  return {
    selected_slot: "slot_001",
    available_slots: ["slot_001", "slot_002"],
    language: "zh",
    ui_mode: "manual",
    ui_auto_update_every: 1,
    selected_pack_ids: ["starter_kingdom"],
  };
}

export function createMockSessionManagerView(): SessionManagerView {
  return {
    selected_slot: "slot_001",
    backend_status: "online",
    storage_backend: "local",
    last_sync_label: "just now",
    sessions: [
      {
        slot_id: "slot_001",
        language: "zh",
        enabled_packs: ["starter", "tavern"],
        location_label: "旅店大厅",
        turn_count: 3,
        updated_label: "2026-03-24 14:32",
      },
      {
        slot_id: "slot_002",
        language: "zh",
        enabled_packs: ["starter"],
        location_label: "城门外小路",
        turn_count: 12,
        updated_label: "yesterday",
      },
      {
        slot_id: "slot_003",
        language: "zh",
        enabled_packs: ["starter", "academy"],
        location_label: "角色创建中",
        turn_count: 0,
        updated_label: "4 days ago",
      },
    ],
  };
}
