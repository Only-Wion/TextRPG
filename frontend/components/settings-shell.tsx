"use client";

import { useState } from "react";

import { updateLLMSettings } from "../lib/api";
import type { AuthUser, LLMSettingsPublic, LLMSettingsUpdateRequest } from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type SettingsShellProps = {
  settings: LLMSettingsPublic;
  currentUser: AuthUser;
};

export function SettingsShell({ settings, currentUser }: SettingsShellProps) {
  const [runtimeSettings, setRuntimeSettings] = useState(settings);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSave() {
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const payload: LLMSettingsUpdateRequest = {
        provider: runtimeSettings.provider,
        model_name: runtimeSettings.model_name,
        embedding_model: runtimeSettings.embedding_model,
        base_url: runtimeSettings.base_url,
        api_key: apiKeyInput,
        use_mock_llm: runtimeSettings.use_mock_llm,
        force_fake_embeddings: runtimeSettings.force_fake_embeddings,
      };
      const nextSettings = await updateLLMSettings(payload);
      setRuntimeSettings(nextSettings);
      setApiKeyInput("");
      setSuccessMessage("Settings saved.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save settings.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar activePath="/settings" currentUser={currentUser} />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Settings</h1>
          </header>

          <div className="light-stack">
            <div className="light-caption">
              Settings apply to subsequent chat and pack-builder tasks.
            </div>

            <section className="light-card settings-form-card">
              <div className="settings-field">
                <label className="settings-label" htmlFor="provider">
                  LLM Platform
                </label>
                <input
                  className="light-input"
                  id="provider"
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({ ...current, provider: event.target.value }))
                  }
                  value={runtimeSettings.provider}
                />
              </div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="api-key">
                  API Key
                </label>
                <input
                  className="light-input"
                  id="api-key"
                  onChange={(event) => setApiKeyInput(event.target.value)}
                  placeholder={runtimeSettings.api_key_set ? "api key stored" : "api key not set"}
                  type="password"
                  value={apiKeyInput}
                />
              </div>

              <div className="settings-check">[x] Keep existing key</div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="base-url">
                  Base URL
                </label>
                <input
                  className="light-input"
                  id="base-url"
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({ ...current, base_url: event.target.value }))
                  }
                  value={runtimeSettings.base_url}
                />
              </div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="chat-model">
                  Chat Model
                </label>
                <input
                  className="light-input"
                  id="chat-model"
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({ ...current, model_name: event.target.value }))
                  }
                  value={runtimeSettings.model_name}
                />
              </div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="embedding-model">
                  Embedding Model
                </label>
                <input
                  className="light-input"
                  id="embedding-model"
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({
                      ...current,
                      embedding_model: event.target.value,
                    }))
                  }
                  value={runtimeSettings.embedding_model}
                />
              </div>

              <label className="toggle-row">
                <input
                  checked={runtimeSettings.use_mock_llm}
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({
                      ...current,
                      use_mock_llm: event.target.checked,
                    }))
                  }
                  type="checkbox"
                />
                <span>Use Mock LLM</span>
              </label>

              <label className="toggle-row">
                <input
                  checked={runtimeSettings.force_fake_embeddings}
                  onChange={(event) =>
                    setRuntimeSettings((current) => ({
                      ...current,
                      force_fake_embeddings: event.target.checked,
                    }))
                  }
                  type="checkbox"
                />
                <span>Force Fake Embeddings</span>
              </label>

              <button className="light-action-button new" onClick={handleSave} type="button">
                {isSaving ? "Saving..." : "Save Settings"}
              </button>

              {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
              {successMessage ? <div className="light-success-banner">{successMessage}</div> : null}
            </section>

            <section className="light-card">
              <h2 className="light-card-title">Current Settings</h2>
              <pre className="settings-json">{JSON.stringify(runtimeSettings, null, 2)}</pre>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
