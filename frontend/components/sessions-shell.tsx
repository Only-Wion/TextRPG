"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  archiveGameSession,
  duplicateGameSession,
  getSessionManagerView,
  listPackUiTemplates,
  loadGameSession,
  startGameSession,
} from "../lib/api";
import type {
  AuthUser,
  PackRecord,
  SessionManagerView,
  SessionSummary,
  UiTemplateRecord,
} from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type SessionsShellProps = {
  view: SessionManagerView;
  availablePacks: PackRecord[];
  currentUser: AuthUser;
};

type CreateDraft = {
  saveSlot: string;
  language: string;
  packIds: string[];
};

export function SessionsShell({ view, availablePacks, currentUser }: SessionsShellProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [runtimeView, setRuntimeView] = useState(view);
  const [selectedSlot, setSelectedSlot] = useState(view.selected_slot);
  const [panelMode, setPanelMode] = useState<"list" | "create">(
    searchParams.get("mode") === "create" ? "create" : "list",
  );
  const [createDraft, setCreateDraft] = useState<CreateDraft>(() => buildInitialDraft(view, availablePacks));
  const [isLoading, setIsLoading] = useState(false);
  const [isDuplicating, setIsDuplicating] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uiTemplates, setUiTemplates] = useState<UiTemplateRecord[]>([]);
  const [selectedUiTemplateId, setSelectedUiTemplateId] = useState("");
  const selectedSummary =
    runtimeView.sessions.find((session) => session.slot_id === selectedSlot) ?? runtimeView.sessions[0];

  const draftSummaryLines = useMemo(
    () => [
      `slot: ${createDraft.saveSlot || "pending"}`,
      `language: ${createDraft.language}`,
      `packs: ${createDraft.packIds.length > 0 ? createDraft.packIds.join(", ") : "none"}`,
      "status: unsaved draft",
    ],
    [createDraft.language, createDraft.packIds, createDraft.saveSlot],
  );

  function resetCreateDraft(seedSlot?: string) {
    setCreateDraft(buildInitialDraft(runtimeView, availablePacks, seedSlot ?? selectedSummary?.slot_id));
  }

  function openCreatePanel() {
    resetCreateDraft();
    setErrorMessage(null);
    setPanelMode("create");
  }

  function closeCreatePanel() {
    setErrorMessage(null);
    setPanelMode("list");
  }

  const primaryPackId = createDraft.packIds[0] ?? "";
/*
useEffect
自动加载模板
*/
  useEffect(() => {
    let cancelled = false;
    async function loadTemplates() {
      if (!panelMode || panelMode !== "create" || !primaryPackId) {
        setUiTemplates([]);
        setSelectedUiTemplateId("");
        return;
      }
      setIsLoadingTemplates(true);
      try {
        const records = await listPackUiTemplates(primaryPackId);
        if (!cancelled) {
          setUiTemplates(records);
          setSelectedUiTemplateId((current) => {
            if (current && records.some((item) => item.template_id === current)) {
              return current;
            }
            return "";
          });
        }
      } catch {
        if (!cancelled) {
          setUiTemplates([]);
          setSelectedUiTemplateId("");
        }
      } finally {
        if (!cancelled) {
          setIsLoadingTemplates(false);
        }
      }
    }
    void loadTemplates();
    return () => {
      cancelled = true;
    };
  }, [panelMode, primaryPackId]);

  async function refreshSessionView(preferredSlot?: string) {
    const nextView = await getSessionManagerView();
    setRuntimeView(nextView);
    setSelectedSlot(preferredSlot ?? nextView.selected_slot);
    return nextView;
  }

  async function waitForUiReady(targetSlot: string, timeoutMs = 120000) {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const nextView = await refreshSessionView(targetSlot);
      const nextSummary = nextView.sessions.find((session) => session.slot_id === targetSlot);
      if (!nextSummary || nextSummary.ui_generation_status === "ready") {
        return nextSummary ?? null;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("UI generation is still running. Please try again in a moment.");
  }
/*  
handleLoad
加载存档
*/
  async function handleLoad() {
    if (!selectedSummary || isLoading) {
      return;
    }

    if (selectedSummary.ui_generation_status !== "ready") {
      setErrorMessage("This session is still generating its UI. Please wait until it is ready.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      await loadGameSession({ save_slot: selectedSummary.slot_id, language: selectedSummary.language });
      router.push("/");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load the session.");
    } finally {
      setIsLoading(false);
    }
  }
/*
handleDuplicate
复制存档
*/ 
  async function handleDuplicate() {
    if (!selectedSummary || isDuplicating || panelMode === "create") {
      return;
    }

    setIsDuplicating(true);
    setErrorMessage(null);

    try {
      const nextView = await duplicateGameSession(selectedSummary.slot_id);
      setRuntimeView(nextView);
      setSelectedSlot(nextView.selected_slot);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to duplicate the session.");
    } finally {
      setIsDuplicating(false);
    }
  }
/*
handleArchive
删除存档
*/
  async function handleArchive() {
    if (!selectedSummary || isArchiving || panelMode === "create") {
      return;
    }

    setIsArchiving(true);
    setErrorMessage(null);

    try {
      const nextView = await archiveGameSession(selectedSummary.slot_id);
      setRuntimeView(nextView);
      setSelectedSlot(nextView.selected_slot);
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to archive the session.");
    } finally {
      setIsArchiving(false);
    }
  }
/*
handleSaveCreate
创建存档
*/
  async function handleSaveCreate() {
    if (isSaving) {
      return;
    }

    const trimmedSlot = createDraft.saveSlot.trim();
    if (!trimmedSlot) {
      setErrorMessage("Save slot ID is required.");
      return;
    }

    if (createDraft.packIds.length === 0) {
      setErrorMessage("Select at least one pack before saving the session.");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);

    try {
      await startGameSession({
        save_slot: trimmedSlot,
        language: createDraft.language,
        pack_ids: createDraft.packIds,
        ui_template_id: selectedUiTemplateId || undefined,
      });
      const readySummary = await waitForUiReady(trimmedSlot);
      if (readySummary) {
        await loadGameSession({ save_slot: trimmedSlot, language: readySummary.language });
        router.push("/");
        router.refresh();
      }
      setPanelMode("list");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save the new session.");
    } finally {
      setIsSaving(false);
    }
  }

  function toggleDraftPack(packId: string) {
    setCreateDraft((current) => ({
      ...current,
      packIds: current.packIds.includes(packId)
        ? current.packIds.filter((existingId) => existingId !== packId)
        : [...current.packIds, packId],
    }));
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar
          activePath="/sessions"
          currentUser={currentUser}
          sections={[
            { label: "Backend", value: view.backend_status },
            { label: "Storage", value: runtimeView.storage_backend },
            { label: "Last sync", value: runtimeView.last_sync_label },
          ]}
        />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Sessions</h1>
          </header>

          <div className="manager-grid">
            <section className={`light-card tall-card ${panelMode === "create" ? "session-create-card" : ""}`}>
              {panelMode === "create" ? (
                <div className="session-create-scroll">
                  <button className="session-create-back" onClick={closeCreatePanel} type="button">
                    <span>{"<"}</span>
                    <span>Create Session</span>
                  </button>
                  <p className="light-card-copy">
                    Fill the session profile, save the draft, then return to the session list.
                  </p>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="create-save-slot">
                      Save Slot ID
                    </label>
                    <input
                      className="light-input"
                      id="create-save-slot"
                      onChange={(event) =>
                        setCreateDraft((current) => ({
                          ...current,
                          saveSlot: event.target.value,
                        }))
                      }
                      placeholder="slot_brass_key_001"
                      value={createDraft.saveSlot}
                    />
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="create-language">
                      Language
                    </label>
                    <select
                      className="light-input"
                      id="create-language"
                      onChange={(event) =>
                        setCreateDraft((current) => ({
                          ...current,
                          language: event.target.value,
                        }))
                      }
                      value={createDraft.language}
                    >
                      <option value="zh">zh</option>
                      <option value="en">en</option>
                    </select>
                  </div>

                  <div className="settings-field">
                    <div className="settings-label">Enabled Packs</div>
                    <div className="session-pack-grid">
                      {availablePacks.map((pack) => {
                        const checked = createDraft.packIds.includes(pack.pack_id);
                        return (
                          <label className="session-pack-option" key={pack.pack_id}>
                            <input
                              checked={checked}
                              onChange={() => toggleDraftPack(pack.pack_id)}
                              type="checkbox"
                            />
                            <div className="session-pack-copy">
                              <div className="session-pack-title">{pack.name}</div>
                              <div className="session-pack-meta">
                                {pack.pack_id} · {pack.source} · v{pack.version}
                              </div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                    <div className="light-inline-note">
                      Need a different world module set? Open Pack Manager after returning to the list.
                    </div>
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="create-ui-template">
                      UI Template ({primaryPackId || "no pack"})
                    </label>
                    <select
                      className="light-input"
                      disabled={!primaryPackId || isLoadingTemplates}
                      id="create-ui-template"
                      onChange={(event) => setSelectedUiTemplateId(event.target.value)}
                      value={selectedUiTemplateId}
                    >
                      <option value="">Do not use template</option>
                      {uiTemplates.map((template) => (
                        <option key={template.template_id} value={template.template_id}>
                          {template.name} ({template.template_id})
                        </option>
                      ))}
                    </select>
                    <div className="light-inline-note">
                      {isLoadingTemplates
                        ? "Loading templates..."
                        : primaryPackId
                          ? uiTemplates.length > 0
                            ? `Found ${uiTemplates.length} template(s). Choose one to reuse, or keep \"Do not use template\" for a fresh runtime UI.`
                            : "No existing template for this pack yet. You can start without template and create one later in Pack Manager."
                          : "Select at least one pack to load template options."}
                    </div>
                  </div>

                  <button
                    className="light-action-button new session-create-save"
                    disabled={isSaving}
                    onClick={handleSaveCreate}
                    type="button"
                  >
                    {isSaving ? "Saving..." : "Save Session"}
                  </button>
                </div>
              ) : (
                <>
                  <h2 className="light-card-title">Save Slots</h2>
                  <p className="light-card-copy">
                    Choose a session to continue, duplicate, or archive.
                  </p>

                  <div className="slot-list">
                    {runtimeView.sessions.map((session) => (
                      <button
                        className={`slot-row ${session.slot_id === selectedSlot ? "active" : ""}`}
                        key={session.slot_id}
                        onClick={() => setSelectedSlot(session.slot_id)}
                        type="button"
                      >
                        <div className="slot-row-title">{session.slot_id}</div>
                        <div className="slot-row-meta">
                          {session.location_label} | {session.turn_count} turns | {session.ui_generation_status} | packs: {" "}
                          {session.enabled_packs.join(", ")}
                        </div>
                        <div className="slot-row-subtle">{session.updated_label}</div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </section>

            <div className="manager-rail">
              <section className="light-card">
                <h2 className="light-card-title">{panelMode === "create" ? "Draft Summary" : "Current Selection"}</h2>
                {panelMode === "create" ? (
                  <div className="summary-stack">
                    {draftSummaryLines.map((line) => (
                      <div className="light-copy" key={line}>
                        {line}
                      </div>
                    ))}
                  </div>
                ) : selectedSummary ? (
                  <SessionSummaryBlock session={selectedSummary} />
                ) : (
                  <div className="light-copy">No session selected.</div>
                )}
              </section>

              <section className="light-card">
                <h2 className="light-card-title">Quick Actions</h2>
                <div className="action-grid">
                  <button
                    className="light-action-button load"
                    disabled={Boolean(selectedSummary && selectedSummary.ui_generation_status !== "ready")}
                    onClick={handleLoad}
                    type="button"
                  >
                    {isLoading ? "Loading..." : "Load Session"}
                  </button>
                  <button
                    className="light-action-button new"
                    disabled={panelMode === "create"}
                    onClick={openCreatePanel}
                    type="button"
                  >
                    {panelMode === "create" ? "Creating..." : "New Session"}
                  </button>
                  <button
                    className="light-action-button duplicate"
                    disabled={isDuplicating || isArchiving || panelMode === "create"}
                    onClick={handleDuplicate}
                    type="button"
                  >
                    {isDuplicating ? "Duplicating..." : "Duplicate"}
                  </button>
                  <button
                    className="light-action-button archive"
                    disabled={isDuplicating || isArchiving || panelMode === "create"}
                    onClick={handleArchive}
                    type="button"
                  >
                    {isArchiving ? "Archiving..." : "Archive"}
                  </button>
                </div>
                {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
                <div className="light-inline-note">
                  {panelMode === "create"
                    ? "Save creates the session and returns you to the list. The back arrow closes the draft without saving."
                    : selectedSummary?.ui_generation_status !== "ready"
                      ? "This session is still generating UI. Load is disabled until it becomes ready."
                      : "Duplicate creates a new copy slot. Archive removes the selected slot from the active session inventory."}
                </div>
              </section>

              <section className="light-card">
                <h2 className="light-card-title">Session Notes</h2>
                <p className="light-copy">
                  {panelMode === "create"
                    ? "Create and save a new session here, then return to the session list."
                    : "Manage save slots here before entering Play."}
                </p>
                <p className="light-copy">
                  {panelMode === "create"
                    ? "Return arrow exits the draft view without leaving the Sessions page."
                    : `Next: load ${selectedSummary?.slot_id ?? "a slot"} and continue the current thread.`}
                </p>
              </section>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function SessionSummaryBlock({ session }: { session: SessionSummary }) {
  return (
    <div className="summary-stack">
      <div className="summary-heading">{session.slot_id}</div>
      <div className="light-copy">Language: {session.language}</div>
      <div className="light-copy">Enabled packs: {session.enabled_packs.join(", ")}</div>
      <div className="light-copy">Last location: {session.location_label}</div>
      <div className="light-copy">Last played: {session.updated_label}</div>
      <div className="light-copy">UI status: {session.ui_generation_status}</div>
    </div>
  );
}

function buildInitialDraft(
  view: SessionManagerView,
  availablePacks: PackRecord[],
  preferredSlot?: string,
): CreateDraft {
  const selectedSession = view.sessions.find((session) => session.slot_id === view.selected_slot) ?? view.sessions[0];
  const baseSlot = preferredSlot ?? selectedSession?.slot_id ?? "slot_001";

  return {
    saveSlot: createNextSlotId(baseSlot, view.sessions.map((session) => session.slot_id)),
    language: selectedSession?.language ?? "zh",
    packIds: availablePacks.filter((pack) => pack.enabled).map((pack) => pack.pack_id),
  };
}

function createNextSlotId(baseSlot: string, existingSlots: string[]): string {
  const sanitizedBase = baseSlot.replace(/_copy_\d+$/, "").trim() || "slot_001";

  if (!existingSlots.includes(sanitizedBase)) {
    return sanitizedBase;
  }

  let index = 1;
  let candidate = `${sanitizedBase}_new_${String(index).padStart(2, "0")}`;
  while (existingSlots.includes(candidate)) {
    index += 1;
    candidate = `${sanitizedBase}_new_${String(index).padStart(2, "0")}`;
  }
  return candidate;
}
