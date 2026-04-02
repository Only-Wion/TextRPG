# Pack and Settings Data Contracts

## PackRecord

Canonical pack payload returned by the application service and HTTP API:

```json
{
  "pack_id": "starter_kingdom",
  "name": "Starter Kingdom",
  "version": "0.1.0",
  "author": "team",
  "description": "starter pack",
  "cards_root": "cards",
  "enabled": true,
  "source": "local"
}
```

Identity notes:
- `pack_id` in current APIs is the user's private pack id.
- Private pack ids are unique only inside one `user_id` namespace.
- Future marketplace publication uses a separate global `public_pack_id`.

## UserPackCatalog Entity (Repository-Level)

Internal persisted entity for user-owned packs:

```json
{
  "internal_pack_id": "uuid",
  "user_id": "uuid",
  "private_pack_id": "starter_kingdom",
  "public_pack_id": null,
  "name": "Starter Kingdom",
  "author": "team",
  "description": "starter pack",
  "cards_root": "cards",
  "source": "local",
  "visibility": "private",
  "version": "0.1.0"
}
```

## UserPackVersion Entity (Repository-Level)

Per-version metadata for a user-owned pack:

```json
{
  "version": "0.1.0",
  "storage_backend": "oss",
  "storage_path": "<user_id>/starter_kingdom/0.1.0/cards",
  "cards_root": "cards",
  "manifest": {
    "pack_id": "starter_kingdom",
    "name": "Starter Kingdom",
    "version": "0.1.0"
  }
}
```

## PackEnabledRequest

```json
{
  "enabled": true
}
```

## PackExportResponse

```json
{
  "ok": true,
  "pack_id": "starter_kingdom",
  "export_path": "E:/TextRPG/data/exports/starter_kingdom-0.1.0.zip"
}
```

Field notes:
- `export_path` is a local filesystem path for the generated ZIP.
- In the current phase this is intended for local development and operator visibility, not browser download streaming.
- `cards_root` is kept in `PackRecord` for runtime compatibility, but Card Designer create-pack requests no longer require user input for it.
- Pack IDs are currently treated as private IDs inside one user namespace.
- Planned marketplace public IDs (`public_pack_id`) are reserved for future publication flows and remain unimplemented.
- Pack content storage is being abstracted; current default backend is local filesystem, and OSS migration settings are read from `TEXTRPG_PACK_STORAGE_BACKEND`, `TEXTRPG_OSS_ENDPOINT`, `TEXTRPG_OSS_BUCKET`, `TEXTRPG_OSS_ACCESS_KEY_ID`, `TEXTRPG_OSS_ACCESS_KEY_SECRET`, `TEXTRPG_OSS_PREFIX`, and `TEXTRPG_OSS_REGION`.
- The OSS backend keeps a local cache mirror for the existing Path-based card editing flow, so the server still needs writable disk for the cache directory.
- User-scoped pack namespace root is `data/user_packs/<user_id>/`.

## Pack Enable State

Behavior:
- `PackRecord.enabled` is now scoped to the authenticated user
- `PackEnabledRequest` updates that user's default enabled-pack set
- existing save slots keep their own persisted enabled-pack list until they are loaded or restarted

## LLMSettingsPublic

Public runtime settings projection:

```json
{
  "provider": "custom",
  "model_name": "gpt-4o-mini",
  "embedding_model": "text-embedding-3-small",
  "base_url": "",
  "api_key_set": false,
  "use_mock_llm": true,
  "force_fake_embeddings": false
}
```

## LLMSettingsUpdateRequest

```json
{
  "provider": "custom",
  "model_name": "gpt-4o-mini",
  "embedding_model": "text-embedding-3-small",
  "base_url": "",
  "api_key": "",
  "use_mock_llm": true,
  "force_fake_embeddings": false
}
```

## CardTemplate

Canonical new-card template shape:

```json
{
  "id": "new_id",
  "type": "character",
  "tags": [],
  "initial_relations": [],
  "hooks": []
}
```
