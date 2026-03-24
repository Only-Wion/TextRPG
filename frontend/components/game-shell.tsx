"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import type { StateView } from "../lib/api-contract";
import { normalizeStateViewFromAction, stepGameSession } from "../lib/api";
import { AppSidebar } from "./app-sidebar";

type GameShellProps = {
  state: StateView;
};

function linesToBody(lines: string[]): string {
  return lines.filter(Boolean).join("\n");
}

export function GameShell({ state }: GameShellProps) {
  const [runtimeState, setRuntimeState] = useState(state);
  const [commandInput, setCommandInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const chatFeed =
    runtimeState.recent_messages.length > 0 ? runtimeState.recent_messages : runtimeState.chat_history;

  const enabledPacks =
    runtimeState.enabled_packs.length > 0 ? runtimeState.enabled_packs.join(", ") : "none";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = commandInput.trim();
    if (!trimmed || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await stepGameSession({ input_text: trimmed });
      setRuntimeState(normalizeStateViewFromAction(response.state_view));
      setCommandInput("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to send the command.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar
          activePath="/"
          sections={[
            { label: "Slot", value: runtimeState.save_slot ?? "slot_001" },
            { label: "Backend", value: "fastapi" },
            { label: "Storage", value: runtimeState.storage_backend_label },
          ]}
        />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Play</h1>
          </header>

          <section className="play-control-bar">
            <div className="control-meta">Save Slot</div>
            <div className="control-meta">Enabled Packs</div>
            <div className="control-meta">Language</div>

            <div className="control-field">{runtimeState.save_slot ?? "slot_001"}</div>
            <div className="control-field">{enabledPacks}</div>
            <div className="control-field">zh</div>

            <button className="light-action-button load" type="button">
              Start
            </button>
            <button className="light-action-button new" type="button">
              Load
            </button>
            <button className="light-action-button duplicate" type="button">
              Hide Panels
            </button>
          </section>

          <div className="play-grid">
            <section className="light-card play-transcript-card">
              <h2 className="light-card-title">Narrative Transcript</h2>
              <div className="light-copy">Assistant and world narration stream lives here.</div>

              <div className="play-feed">
                {chatFeed.map((message, index) => (
                  <article className="play-feed-item" key={`${message.role}-${index}`}>
                    <div className={`mono-label ${message.role === "user" ? "accent-green" : "accent-blue"}`}>
                      {message.role === "user" ? "User" : "System"}
                    </div>
                    <div className="play-feed-text">{message.content}</div>
                  </article>
                ))}
              </div>
            </section>

            <aside className="manager-rail">
              <section className="light-card">
                <h2 className="light-card-title">World Facts</h2>
                <div className="light-panel-body">
                  {linesToBody([
                    `Location: ${runtimeState.location_label}`,
                    "Weather: cloudy",
                    "Active quest: 问清失窃货箱",
                    "Trust with barkeep: cautious",
                  ])}
                </div>
              </section>

              <section className="light-card">
                <h2 className="light-card-title">UI Agent</h2>
                <div className="light-panel-body">
                  {linesToBody([
                    `Update mode: ${runtimeState.ui_update_mode}`,
                    `Last generate: ${runtimeState.ui_generation_status}`,
                    `Last update: ${runtimeState.ui_update_status}`,
                  ])}
                </div>
              </section>

              <section className="light-card">
                <h2 className="light-card-title">Debug Info</h2>
                <div className="light-panel-body">
                  {linesToBody([
                    `session_id: ${runtimeState.save_slot ?? "slot_001"}`,
                    `llm: ${runtimeState.ui_generation_status === "ready" ? "mock" : "custom"}`,
                    `last_turn_ms: ${runtimeState.turn_id ?? 0}`,
                    `retrieved_cards: ${runtimeState.retrieved_cards.length}`,
                  ])}
                </div>
              </section>
            </aside>
          </div>

          <form className="play-composer" onSubmit={handleSubmit}>
            <input
              className="play-composer-input"
              onChange={(event) => setCommandInput(event.target.value)}
              placeholder="Input your next action, say, or command..."
              value={commandInput}
            />
            <button className="light-action-button new" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Running..." : "Execute"}
            </button>
          </form>

          {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
        </section>
      </div>
    </main>
  );
}
