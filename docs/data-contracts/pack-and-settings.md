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

## PackEnabledRequest

```json
{
  "enabled": true
}
```

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
