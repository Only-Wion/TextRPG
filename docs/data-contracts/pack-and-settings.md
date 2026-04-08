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
  "storage_path": "<oss_prefix>/users/<user_id>/packs/starter_kingdom/0.1.0/cards",
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
- Pack content storage is OSS-only; required settings are `TEXTRPG_PACK_STORAGE_BACKEND=oss`, `TEXTRPG_OSS_ENDPOINT`, `TEXTRPG_OSS_BUCKET`, `TEXTRPG_OSS_ACCESS_KEY_ID`, `TEXTRPG_OSS_ACCESS_KEY_SECRET`, `TEXTRPG_OSS_PREFIX`, and `TEXTRPG_OSS_REGION`.
- OSS card operations are now served directly from object storage; no persistent local pack-file cache is required.
- Registry metadata remains under `data/user_packs/<user_id>/pack_registry.json`; pack markdown content is stored under OSS keys only.
- OSS user-scoped namespace root is `<oss_prefix>/users/<user_id>/packs/`.

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
