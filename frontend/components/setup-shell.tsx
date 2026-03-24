"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { LLMSettingsPublic, PackRecord, SetupBootstrapView } from "../lib/api-contract";
import { startGameSession } from "../lib/api";
import { AppSidebar } from "./app-sidebar";

type SetupShellProps = {
  setupView: SetupBootstrapView;
  packs: PackRecord[];
  llmSettings: LLMSettingsPublic;
};

export function SetupShell({ setupView, packs, llmSettings }: SetupShellProps) {
  const router = useRouter();
  const [selectedSlot, setSelectedSlot] = useState(setupView.selected_slot);
  const [customSlot, setCustomSlot] = useState("");
  const [language, setLanguage] = useState(setupView.language);
  const [isStarting, setIsStarting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const effectiveSlot = customSlot.trim() || selectedSlot;
  const selectedPackIds = useMemo(() => {
    const enabled = packs.filter((pack) => pack.enabled).map((pack) => pack.pack_id);
    return enabled.length > 0 ? enabled : setupView.selected_pack_ids;
  }, [packs, setupView.selected_pack_ids]);

  const preflightSteps = [
    {
      title: "01 // Pick Identity",
      tone: "accent-green",
      body: "Choose slot and language.",
    },
    {
      title: "02 // Review Config",
      tone: "accent-blue",
      body: "Confirm packs and runtime.",
    },
    {
      title: "03 // Launch",
      tone: "accent-gold",
      body: "Validate and start.",
    },
  ];

  const launchPreviewLines = [
    "POST /game/start",
    `save_slot: ${effectiveSlot || "slot_001"}`,
    `pack_ids: [${selectedPackIds.join(", ")}]`,
    `language: ${language}`,
  ];

  async function handleStartSession() {
    const saveSlot = effectiveSlot.trim();
    if (!saveSlot || isStarting) {
      return;
    }

    setIsStarting(true);
    setErrorMessage(null);

    try {
      await startGameSession({
        save_slot: saveSlot,
        pack_ids: selectedPackIds,
        language,
      });
      router.push("/");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to start the session.");
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar
          activePath="/setup"
          sections={[
            { label: "Backend", value: "online" },
            { label: "Storage", value: "local" },
            { label: "Runtime", value: setupView.ui_mode },
          ]}
        />

        <section className="light-main">
          <header className="light-topbar preflight-topbar">
            <div className="preflight-copy">
              <div className="mono-label accent-green">Session Preflight</div>
              <h1 className="preflight-title">
                Review the chosen slot, world profile, and runtime before you launch.
              </h1>
              <p className="light-copy">
                Setup summarizes the current configuration. Edit details in Sessions, Pack Manager,
                or Settings.
              </p>
            </div>

            <div className="header-actions">
              <Link className="btn-secondary dark-button" href="/">
                Open Play
              </Link>
              <button className="btn-secondary light-button" onClick={() => router.refresh()} type="button">
                Sync API
              </button>
            </div>
          </header>

          <section className="boot-strip">
            {preflightSteps.map((step) => (
              <article className="boot-step-card" key={step.title}>
                <div className={`mono-label ${step.tone}`}>{step.title}</div>
                <div className="boot-step-copy">{step.body}</div>
              </article>
            ))}
          </section>

          <section className="setup-grid">
            <div className="setup-col">
              <article className="surface-card">
                <div className="mono-label accent-green">Session Identity</div>
                <div className="field-stack">
                  {setupView.available_slots.map((slot) => (
                    <label className="radio-row" key={slot}>
                      <input
                        checked={!customSlot.trim() && selectedSlot === slot}
                        name="save-slot"
                        onChange={() => setSelectedSlot(slot)}
                        type="radio"
                      />
                      <span>{slot}</span>
                    </label>
                  ))}

                  <label className="field-label" htmlFor="custom-slot">
                    Create new slot
                  </label>
                  <input
                    className="text-input"
                    id="custom-slot"
                    onChange={(event) => setCustomSlot(event.target.value)}
                    placeholder="slot_003"
                    value={customSlot}
                  />
                </div>
              </article>

              <article className="surface-card">
                <div className="mono-label accent-green">Launch Rules</div>
                <div className="field-stack">
                  <label className="field-label" htmlFor="language-select">
                    Language
                  </label>
                  <select
                    className="text-input"
                    id="language-select"
                    onChange={(event) => setLanguage(event.target.value)}
                    value={language}
                  >
                    <option value="zh">zh</option>
                    <option value="en">en</option>
                  </select>
                  <div className="panel-note">Language: {language}. Uses selected runtime profile.</div>
                </div>
              </article>
            </div>

            <div className="setup-col">
              <article className="surface-card">
                <div className="mono-label accent-blue">World Modules Summary</div>
                <div className="summary-stack">
                  <div className="light-copy">
                    Enabled packs: {selectedPackIds.length > 0 ? selectedPackIds.join(", ") : "none"}
                  </div>
                  <div className="light-copy">
                    Expansion packs: {packs.some((pack) => pack.source !== "builtin") ? "present" : "none"}
                  </div>
                  <div className="light-copy">Pack source mix: builtin + local</div>
                  <div className="light-inline-note">
                    Summary only. Edit details in Pack Manager.
                  </div>
                  <Link className="light-action-button load" href="/packs">
                    Open Pack Manager
                  </Link>
                </div>
              </article>
            </div>

            <div className="setup-col">
              <article className="surface-card">
                <div className="mono-label accent-purple">Runtime Profile</div>
                <div className="summary-stack">
                  <div className="light-copy">provider: {llmSettings.provider}</div>
                  <div className="light-copy">
                    chat model: {llmSettings.model_name || "not configured"}
                  </div>
                  <div className="light-copy">
                    embedding: {llmSettings.embedding_model || "not configured"}
                  </div>
                  <div className="light-copy">mock llm: {llmSettings.use_mock_llm ? "on" : "off"}</div>
                  <div className="light-inline-note">Summary only. Edit details in Settings.</div>
                  <Link className="light-action-button settings-link" href="/settings">
                    Open Settings
                  </Link>
                </div>
              </article>

              <article className="surface-card">
                <div className="mono-label accent-gold">Launch Preview</div>
                <div className="panel-body light-panel-body">{launchPreviewLines.join("\n")}</div>
              </article>

              <article className="surface-card">
                <div className="mono-label accent-green">Launch Checklist</div>
                <div className="summary-stack">
                  <div className="light-copy">Backend reachable</div>
                  <div className="light-copy">Storage backend detected</div>
                  <div className="light-copy">Pack summary available</div>
                  <div className="light-copy">Runtime summary available</div>
                  {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
                  <button className="light-action-button new" disabled={isStarting} onClick={handleStartSession} type="button">
                    {isStarting ? "Starting..." : "Start Session"}
                  </button>
                </div>
              </article>
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
