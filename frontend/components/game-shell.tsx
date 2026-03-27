"use client";

import type { FormEvent, MutableRefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { AuthUser, StateView } from "../lib/api-contract";
import { normalizeStateViewFromAction, stepGameSession } from "../lib/api";
import { AppSidebar } from "./app-sidebar";

type GameShellProps = {
  state: StateView;
  currentUser: AuthUser;
};

export function GameShell({ state, currentUser }: GameShellProps) {
  const router = useRouter();
  const [runtimeState, setRuntimeState] = useState(state);
  const [commandInput, setCommandInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [controlsExpanded, setControlsExpanded] = useState(true);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const animationRef = useRef<number | null>(null);

  const baseChatFeed =
    runtimeState.recent_messages.length > 0 ? runtimeState.recent_messages : runtimeState.chat_history;
  const chatFeed = [
    ...baseChatFeed,
    ...(pendingUserMessage ? [{ role: "user" as const, content: pendingUserMessage }] : []),
    ...(streamingAssistantText ? [{ role: "assistant" as const, content: streamingAssistantText }] : []),
  ];

  const enabledPacks =
    runtimeState.enabled_packs.length > 0 ? runtimeState.enabled_packs.join(", ") : "none";

  useEffect(() => {
    if (!feedRef.current) {
      return;
    }

    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [chatFeed]);

  useEffect(() => {
    return () => {
      if (animationRef.current !== null) {
        window.clearTimeout(animationRef.current);
      }
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = commandInput.trim();
    if (!trimmed || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      setPendingUserMessage(trimmed);
      setStreamingAssistantText("");

      const response = await stepGameSession({ input_text: trimmed });
      const nextState = normalizeStateViewFromAction(response.state_view);
      const fullNarration = nextState.narration || "";

      await animateNarration(fullNarration, setStreamingAssistantText, animationRef);
      setRuntimeState(nextState);
      setPendingUserMessage(null);
      setStreamingAssistantText("");
      setCommandInput("");
    } catch (error) {
      setPendingUserMessage(null);
      setStreamingAssistantText("");
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
          currentUser={currentUser}
          sections={[
            { label: "Slot", value: runtimeState.save_slot ?? "slot_001" },
            { label: "Backend", value: "fastapi" },
            { label: "Storage", value: runtimeState.storage_backend_label },
          ]}
          inspectorSections={[
            {
              id: "world-facts",
              title: "World Facts",
              defaultOpen: true,
              lines: [
                `Location: ${runtimeState.location_label}`,
                "Weather: cloudy",
                "Quest: ??????",
                "Trust: cautious",
              ],
            },
            {
              id: "ui-agent",
              title: "UI Agent",
              defaultOpen: true,
              lines: [
                `Mode: ${runtimeState.ui_update_mode}`,
                `Generate: ${runtimeState.ui_generation_status}`,
                `Update: ${runtimeState.ui_update_status}`,
              ],
            },
            {
              id: "debug-info",
              title: "Debug Info",
              defaultOpen: false,
              lines: [
                `session_id: ${runtimeState.save_slot ?? "slot_001"}`,
                `llm: ${runtimeState.ui_generation_status === "ready" ? "mock" : "custom"}`,
                `turn_ms: ${runtimeState.turn_id ?? 0}`,
                `retrieved_cards: ${runtimeState.retrieved_cards.length}`,
              ],
            },
          ]}
        />

        <section className="light-main play-main compact-play-main">
          <section className={`play-control-drawer ${controlsExpanded ? "expanded" : "collapsed"}`}>
            {controlsExpanded ? (
              <section className="play-control-bar compact-control-bar">
                <div className="control-meta">Save Slot</div>
                <div className="control-meta">Enabled Packs</div>
                <div className="control-meta">Language</div>

                <div className="control-field">{runtimeState.save_slot ?? "slot_001"}</div>
                <div className="control-field">{enabledPacks}</div>
                <div className="control-field">zh</div>

                <button
                  className="light-action-button load"
                  onClick={() => router.push("/sessions?mode=create")}
                  type="button"
                >
                  Start
                </button>
                <button className="light-action-button new" onClick={() => router.push("/sessions")} type="button">
                  Load
                </button>
              </section>
            ) : null}

            <button
              aria-label={controlsExpanded ? "Collapse play controls" : "Expand play controls"}
              className="play-control-handle"
              onClick={() => setControlsExpanded((current) => !current)}
              type="button"
            >
              <span className={`play-control-arrow ${controlsExpanded ? "muted" : "active"}`}>^</span>
              <span className={`play-control-arrow ${controlsExpanded ? "active" : "muted"}`}>v</span>
            </button>
          </section>

          <div className="play-grid single-column-play-grid">
            <section className="light-card play-transcript-card transcript-only-card">
              <div className="play-feed" ref={feedRef}>
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
          </div>

          <div className="play-footer compact-play-footer">
            {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}

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
          </div>
        </section>
      </div>
    </main>
  );
}

function animateNarration(
  narration: string,
  setStreamingAssistantText: (value: string) => void,
  animationRef: MutableRefObject<number | null>,
): Promise<void> {
  if (!narration) {
    setStreamingAssistantText("");
    return Promise.resolve();
  }

  const stepSize = narration.length > 280 ? 12 : 6;
  const frameDelay = narration.length > 280 ? 24 : 32;

  return new Promise((resolve) => {
    let cursor = 0;

    const tick = () => {
      cursor = Math.min(cursor + stepSize, narration.length);
      setStreamingAssistantText(narration.slice(0, cursor));

      if (cursor >= narration.length) {
        animationRef.current = null;
        resolve();
        return;
      }

      animationRef.current = window.setTimeout(tick, frameDelay);
    };

    tick();
  });
}
