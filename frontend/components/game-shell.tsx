"use client";

import type { FormEvent, MouseEvent as ReactMouseEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { AuthUser, StateView } from "../lib/api-contract";
import {
  getGameStateView,
  normalizeStateViewFromAction,
  setUiAutoUpdate,
  setUiPanelVisibility,
  setUiUpdateMode,
  stepGameSessionStream,
  triggerUiGeneration,
  triggerUiUpdate,
} from "../lib/api";
import { AppSidebar } from "./app-sidebar";

type GameShellProps = {
  state: StateView;
  currentUser: AuthUser;
};

type PanelRect = {
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
};

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function getInitialPanelRect(panel: Record<string, unknown>, index: number, zIndex: number): PanelRect {
  const layout = (panel.layout ?? {}) as Record<string, unknown>;
  const width = toFiniteNumber(layout.width) ?? 320;
  const height = toFiniteNumber(layout.height) ?? 520;
  const x = toFiniteNumber(layout.x) ?? (40 + (index % 3) * 36);
  const y = toFiniteNumber(layout.y) ?? (120 + index * 24);
  return {
    x,
    y,
    width,
    height,
    zIndex,
  };
}

export function GameShell({ state, currentUser }: GameShellProps) {
  const router = useRouter();
  const [runtimeState, setRuntimeState] = useState(state);
  const [commandInput, setCommandInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [controlsExpanded, setControlsExpanded] = useState(true);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [uiEveryInput, setUiEveryInput] = useState(String(state.ui_auto_update_every || 1));
  const [uiBusy, setUiBusy] = useState(false);
  const [panelRects, setPanelRects] = useState<Record<string, PanelRect>>({});
  const feedRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const panelRefs = useRef<Record<string, HTMLElement | null>>({});
  const dragRef = useRef<{ panelId: string; offsetX: number; offsetY: number } | null>(null);
  const zRef = useRef(10);

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
    const nextIds = new Set<string>();
    setPanelRects((current) => {
      const next: Record<string, PanelRect> = {};
      let changed = false;
      runtimeState.custom_ui_panels.forEach((panel, index) => {
        const panelId = String(panel.panel_id ?? `panel-${index}`);
        nextIds.add(panelId);
        const existing = current[panelId];
        if (existing) {
          next[panelId] = existing;
          return;
        }
        zRef.current += 1;
        next[panelId] = getInitialPanelRect(panel as Record<string, unknown>, index, zRef.current);
        changed = true;
      });
      Object.keys(current).forEach((panelId) => {
        if (nextIds.has(panelId)) {
          return;
        }
        changed = true;
      });
      return changed ? next : current;
    });
  }, [runtimeState.custom_ui_panels]);

  useEffect(() => {
    function onMouseMove(event: globalThis.MouseEvent) {
      if (!dragRef.current) {
        return;
      }
      const overlayEl = overlayRef.current;
      if (!overlayEl) {
        return;
      }
      const overlayBounds = overlayEl.getBoundingClientRect();
      const { panelId, offsetX, offsetY } = dragRef.current;
      setPanelRects((current) => {
        const rect = current[panelId];
        if (!rect) {
          return current;
        }
        const rawX = event.clientX - offsetX - overlayBounds.left;
        const rawY = event.clientY - offsetY - overlayBounds.top;
        const maxX = Math.max(0, overlayBounds.width - rect.width);
        const maxY = Math.max(0, overlayBounds.height - rect.height);
        const nextX = Math.max(0, Math.min(rawX, maxX));
        const nextY = Math.max(0, Math.min(rawY, maxY));
        return {
          ...current,
          [panelId]: {
            ...rect,
            x: nextX,
            y: nextY,
          },
        };
      });
    }

    function onMouseUp() {
      dragRef.current = null;
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  function bringPanelToFront(panelId: string) {
    zRef.current += 1;
    setPanelRects((current) => {
      const rect = current[panelId];
      if (!rect || rect.zIndex === zRef.current) {
        return current;
      }
      return {
        ...current,
        [panelId]: {
          ...rect,
          zIndex: zRef.current,
        },
      };
    });
  }

  function handlePanelDragStart(event: ReactMouseEvent<HTMLDivElement>, panelId: string) {
    const panelEl = panelRefs.current[panelId];
    if (!panelEl) {
      return;
    }
    const bounds = panelEl.getBoundingClientRect();
    dragRef.current = {
      panelId,
      offsetX: event.clientX - bounds.left,
      offsetY: event.clientY - bounds.top,
    };
    bringPanelToFront(panelId);
    event.preventDefault();
  }

  function handlePanelPointerDown(panelId: string) {
    bringPanelToFront(panelId);
  }

  function syncPanelSize(panelId: string) {
    const panelEl = panelRefs.current[panelId];
    if (!panelEl) {
      return;
    }
    const nextWidth = panelEl.offsetWidth;
    const nextHeight = panelEl.offsetHeight;
    setPanelRects((current) => {
      const rect = current[panelId];
      if (!rect) {
        return current;
      }
      if (rect.width === nextWidth && rect.height === nextHeight) {
        return current;
      }
      return {
        ...current,
        [panelId]: {
          ...rect,
          width: nextWidth,
          height: nextHeight,
        },
      };
    });
  }

  async function refreshState() {
    const nextState = await getGameStateView();
    setRuntimeState(nextState);
    setUiEveryInput(String(nextState.ui_auto_update_every || 1));
  }

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

      let streamedNarration = "";
      const response = await stepGameSessionStream({ input_text: trimmed }, (delta) => {
        streamedNarration += delta;
        setStreamingAssistantText(streamedNarration);
      });
      const nextState = normalizeStateViewFromAction(response.state_view);
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

  async function handleSetUiMode(mode: "manual" | "auto") {
    if (uiBusy) {
      return;
    }
    setUiBusy(true);
    setErrorMessage(null);
    try {
      await setUiUpdateMode(mode);
      await refreshState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to set UI mode.");
    } finally {
      setUiBusy(false);
    }
  }

  async function handleSetUiEvery() {
    if (uiBusy) {
      return;
    }
    const parsed = Number.parseInt(uiEveryInput, 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setErrorMessage("UI auto update turns must be a positive integer.");
      return;
    }
    setUiBusy(true);
    setErrorMessage(null);
    try {
      await setUiAutoUpdate(parsed);
      await refreshState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to set auto update interval.");
    } finally {
      setUiBusy(false);
    }
  }

  async function handleTriggerUiUpdate() {
    if (uiBusy) {
      return;
    }
    setUiBusy(true);
    setErrorMessage(null);
    try {
      await triggerUiUpdate();
      await refreshState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to update UI panels.");
    } finally {
      setUiBusy(false);
    }
  }

  async function handleTriggerUiGenerate() {
    if (uiBusy) {
      return;
    }
    setUiBusy(true);
    setErrorMessage(null);
    try {
      await triggerUiGeneration(true);
      await refreshState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to regenerate UI panels.");
    } finally {
      setUiBusy(false);
    }
  }

  async function handleTogglePanel(panelId: string, visible: boolean) {
    if (uiBusy) {
      return;
    }
    setUiBusy(true);
    setErrorMessage(null);
    try {
      await setUiPanelVisibility(panelId, visible);
      await refreshState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to update panel visibility.");
    } finally {
      setUiBusy(false);
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
          extraContent={
            <>
              <div className="light-section-title">UI Agent Controls</div>
              <div className="inline-form">
                <button
                  className="light-action-button load"
                  disabled={uiBusy || runtimeState.ui_update_mode === "manual"}
                  onClick={() => void handleSetUiMode("manual")}
                  type="button"
                >
                  Manual
                </button>
                <button
                  className="light-action-button new"
                  disabled={uiBusy || runtimeState.ui_update_mode === "auto"}
                  onClick={() => void handleSetUiMode("auto")}
                  type="button"
                >
                  Auto
                </button>
              </div>
              <div className="inline-form">
                <input
                  className="light-input"
                  onChange={(event) => setUiEveryInput(event.target.value)}
                  value={uiEveryInput}
                />
                <button className="light-action-button new" disabled={uiBusy} onClick={() => void handleSetUiEvery()} type="button">
                  Set N turns
                </button>
              </div>
              <div className="inline-form">
                <button className="light-action-button load" disabled={uiBusy} onClick={() => void handleTriggerUiUpdate()} type="button">
                  Update UI
                </button>
                <button className="light-action-button duplicate" disabled={uiBusy} onClick={() => void handleTriggerUiGenerate()} type="button">
                  Rebuild UI
                </button>
              </div>
              <div className="light-inline-note">Template: {runtimeState.ui_template_id || "(runtime default)"}</div>
              <div className="light-section-title">UI Panels</div>
              {runtimeState.custom_ui_panels.length === 0 ? (
                <div className="light-inline-note">No UI panel generated yet.</div>
              ) : (
                runtimeState.custom_ui_panels.map((panel, index) => {
                  const panelId = String(panel.panel_id ?? `panel-${index}`);
                  const title = String(panel.title ?? panelId);
                  const visible = Boolean(panel.visible ?? true);
                  return (
                    <label className="toggle-row" key={panelId}>
                      <input
                        checked={visible}
                        disabled={uiBusy}
                        onChange={(event) => void handleTogglePanel(panelId, event.target.checked)}
                        type="checkbox"
                      />
                      <span>{title}</span>
                    </label>
                  );
                })
              )}
            </>
          }
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

          <div className="play-panel-overlay" ref={overlayRef}>
            {runtimeState.custom_ui_panels
              .filter((panel) => Boolean(panel.visible ?? true))
              .map((panel, index) => {
                const panelId = String(panel.panel_id ?? `panel-${index}`);
                const title = String(panel.title ?? panelId);
                const html = typeof panel.html === "string" ? panel.html : "";
                const sections = Array.isArray(panel.sections) ? panel.sections : [];
                const rect = panelRects[panelId] ?? getInitialPanelRect(panel as Record<string, unknown>, index, 1);
                return (
                  <article
                    className="play-floating-panel"
                    key={panelId}
                    onMouseDown={() => handlePanelPointerDown(panelId)}
                    onMouseUp={() => syncPanelSize(panelId)}
                    ref={(element) => {
                      panelRefs.current[panelId] = element;
                    }}
                    style={{
                      left: `${rect.x}px`,
                      top: `${rect.y}px`,
                      width: `${rect.width}px`,
                      height: `${rect.height}px`,
                      zIndex: rect.zIndex,
                    }}
                  >
                    <div className="play-floating-title" onMouseDown={(event) => handlePanelDragStart(event, panelId)}>
                      <span>{title}</span>
                      <span className="play-floating-hint">drag | resize</span>
                    </div>
                    {html ? (
                      <div className="play-floating-html" dangerouslySetInnerHTML={{ __html: html }} />
                    ) : (
                      sections.map((section, sIndex) => {
                        const sectionTitle = String((section as Record<string, unknown>).title ?? `Section ${sIndex + 1}`);
                        const entries = Array.isArray((section as Record<string, unknown>).entries)
                          ? ((section as Record<string, unknown>).entries as Array<Record<string, unknown>>)
                          : [];
                        return (
                          <div className="play-floating-section" key={`${panelId}-${sIndex}`}>
                            <div className="play-floating-section-title">{sectionTitle}</div>
                            {entries.map((entry, eIndex) => (
                              <div className="play-floating-entry" key={`${panelId}-${sIndex}-${eIndex}`}>
                                <span>{String(entry.key ?? "-")}</span>
                                <span>{String(entry.value ?? "")}</span>
                              </div>
                            ))}
                          </div>
                        );
                      })
                    )}
                  </article>
                );
              })}
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
