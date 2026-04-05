-- PostgreSQL schema for TextRPG persistence backend.
-- This schema is executed by game.infrastructure.postgres.db.ensure_schema at runtime.
-- For production, migrate to versioned SQL migrations and controlled rollout.

create table if not exists users (
    id text primary key,
    email text not null unique,
    username text not null unique,
    password_salt text not null,
    password_hash text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists auth_tokens (
    token_hash text primary key,
    user_id text not null references users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists user_sessions (
    user_id text not null references users(id) on delete cascade,
    save_slot text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, save_slot)
);

create table if not exists user_llm_settings (
    user_id text primary key references users(id) on delete cascade,
    provider text not null,
    model_name text not null,
    embedding_model text not null,
    base_url text not null,
    api_key_encrypted text not null,
    use_mock_llm boolean not null default false,
    force_fake_embeddings boolean not null default false,
    updated_at timestamptz not null default now()
);

create table if not exists user_pack_states (
    user_id text not null references users(id) on delete cascade,
    pack_id text not null,
    enabled boolean not null default true,
    updated_at timestamptz not null default now(),
    primary key (user_id, pack_id)
);

create table if not exists user_pack_catalog (
    internal_pack_id text primary key,
    user_id text not null references users(id) on delete cascade,
    private_pack_id text not null,
    public_pack_id text unique,
    name text not null,
    author text not null,
    description text not null,
    cards_root text not null,
    source text not null,
    visibility text not null default 'private',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, private_pack_id)
);

create table if not exists user_pack_versions (
    internal_pack_id text not null references user_pack_catalog(internal_pack_id) on delete cascade,
    version text not null,
    storage_backend text not null,
    storage_path text not null,
    cards_root text not null,
    manifest_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (internal_pack_id, version)
);

create table if not exists public_pack_index (
    public_pack_id text primary key,
    internal_pack_id text not null references user_pack_catalog(internal_pack_id) on delete cascade,
    owner_user_id text not null references users(id) on delete cascade,
    version text not null,
    status text not null default 'draft',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists user_session_metadata (
    user_id text not null references users(id) on delete cascade,
    save_slot text not null,
    language text not null,
    enabled_packs_json jsonb not null default '[]'::jsonb,
    location_label text not null,
    turn_count integer not null default 0,
    updated_label text not null,
    ui_generation_status text not null default 'ready',
    primary key (user_id, save_slot)
);

create table if not exists user_chat_history (
    user_id text not null references users(id) on delete cascade,
    save_slot text not null,
    history_json jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (user_id, save_slot)
);

create table if not exists user_card_designer_sessions (
    session_id text primary key,
    user_id text not null references users(id) on delete cascade,
    selected_pack_id text not null default '',
    mode text not null default 'edit',
    state_json jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists user_pack_ui_templates (
    template_id text not null,
    user_id text not null references users(id) on delete cascade,
    pack_id text not null,
    name text not null,
    template_json jsonb not null default '{}'::jsonb,
    variable_template_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, pack_id, template_id)
);

create table if not exists user_session_ui_bindings (
    user_id text not null references users(id) on delete cascade,
    save_slot text not null,
    pack_id text not null,
    template_id text not null,
    variables_json jsonb not null default '{}'::jsonb,
    visibility_json jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    primary key (user_id, save_slot)
);

create table if not exists game_sessions (
    session_key text primary key,
    save_slot text not null unique,
    language text not null default 'zh',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists world_attrs (
    session_key text not null references game_sessions(session_key) on delete cascade,
    entity_id text not null,
    key text not null,
    value text not null,
    source text not null,
    ts bigint not null,
    primary key (session_key, entity_id, key)
);

create table if not exists kg_edges (
    session_key text not null references game_sessions(session_key) on delete cascade,
    sub text not null,
    rel text not null,
    obj text not null,
    ts bigint not null,
    confidence double precision not null,
    source text not null
);

create index if not exists idx_kg_edges_session_sub_rel
    on kg_edges(session_key, sub, rel);

create table if not exists chat_messages (
    session_key text not null references game_sessions(session_key) on delete cascade,
    message_index bigint not null,
    role text not null,
    content text not null,
    created_at timestamptz not null default now(),
    primary key (session_key, message_index)
);

create table if not exists ui_panel_defs (
    session_key text not null references game_sessions(session_key) on delete cascade,
    panel_id text not null,
    payload jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (session_key, panel_id)
);

create table if not exists memory_entries (
    session_key text not null references game_sessions(session_key) on delete cascade,
    memory_id bigserial primary key,
    text text not null,
    tags text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- Future pgvector extension candidate:
-- alter table memory_entries add column embedding vector(1536);
