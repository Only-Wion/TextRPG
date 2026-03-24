-- PostgreSQL schema draft for the future TextRPG persistence backend.
-- This file is documentation-oriented at the current stage. It is not executed yet.

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
