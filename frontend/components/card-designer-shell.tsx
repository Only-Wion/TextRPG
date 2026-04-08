"use client";

import { useEffect, useMemo, useState } from "react";

import {
  createDesignerAgentSession,
  createDesignerPack,
  deleteDesignerCard,
  getDesignerCards,
  getDesignerCardTemplate,
  getDesignerCardTypes,
  loadDesignerCard,
  saveDesignerCard,
  sendDesignerAgentMessage,
  validateDesignerCard,
} from "../lib/api";
import type {
  AuthUser,
  DesignerAgentSession,
  DesignerCardSummary,
  PackRecord,
} from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type CardDesignerShellProps = {
  packs: PackRecord[];
  currentUser: AuthUser;
};

type DesignerMode = "edit" | "create-pack";

type CreatePackDraft = {
  pack_id: string;
  name: string;
  version: string;
  author: string;
  description: string;
};

function stringifyFrontmatter(payload: Record<string, unknown>): string {
  return JSON.stringify(payload, null, 2);
}

function createEmptyPackDraft(): CreatePackDraft {
  return {
    pack_id: "",
    name: "",
    version: "0.1.0",
    author: "",
    description: "",
  };
}

type PendingCardPreview = {
  title: string;
  card_type: string;
  card_id: string;
  tags: string[];
  body: string;
};

type PendingBatchSavePreview = {
  pack_id: string;
  cards: PendingCardPreview[];
};

function parsePendingBatchSavePreview(content: string): PendingBatchSavePreview | null {
  const marker = "以下动作将修改数据，请确认后执行：";
  if (!content.includes(marker)) {
    return null;
  }

  const line = content
    .split("\n")
    .map((item) => item.trim())
    .find((item) => item.startsWith("- batch_save_cards:"));
  if (!line) {
    return null;
  }

  const jsonText = line.slice("- batch_save_cards:".length).trim();
  if (!jsonText) {
    return null;
  }

  try {
    const payload = JSON.parse(jsonText) as {
      pack_id?: unknown;
      cards?: Array<{
        card_type?: unknown;
        card_id?: unknown;
        frontmatter?: { title?: unknown; name?: unknown; tags?: unknown };
        body?: unknown;
      }>;
    };
    const rawCards = Array.isArray(payload.cards) ? payload.cards : [];
    const cards: PendingCardPreview[] = rawCards.map((card) => {
      const frontmatter = card.frontmatter ?? {};
      const title = String(frontmatter.title ?? frontmatter.name ?? card.card_id ?? "untitled").trim() || "untitled";
      const rawTags = frontmatter.tags;
      const tags = Array.isArray(rawTags) ? rawTags.map((tag) => String(tag)) : [];
      return {
        title,
        card_type: String(card.card_type ?? "card"),
        card_id: String(card.card_id ?? "unknown"),
        tags,
        body: String(card.body ?? ""),
      };
    });

    return {
      pack_id: String(payload.pack_id ?? ""),
      cards,
    };
  } catch {
    return null;
  }
}

function directoryOfCardPath(path: string): string {
  const normalized = String(path || "").replace(/\\+/g, "/").replace(/^\/+|\/+$/g, "");
  if (!normalized) {
    return "";
  }
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 1) {
    return "";
  }
  parts.pop();
  return parts.join("/");
}

function folderPathFromCurrentDirectory(currentDirectory: string): string {
  const normalized = String(currentDirectory || "")
    .replace(/\\+/g, "/")
    .replace(/^\/+|\/+$/g, "");
  if (!normalized) {
    return "";
  }
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 1) {
    return "";
  }
  return parts.slice(1).join("/");
}

export function CardDesignerShell({ packs, currentUser }: CardDesignerShellProps) {
  const [runtimePacks, setRuntimePacks] = useState(packs);
  const [mode, setMode] = useState<DesignerMode>(packs.length > 0 ? "edit" : "create-pack");
  const [selectedPackId, setSelectedPackId] = useState(packs[0]?.pack_id ?? "");
  const [cardTypes, setCardTypes] = useState<string[]>([]);
  const [cards, setCards] = useState<DesignerCardSummary[]>([]);
  const [currentDirectory, setCurrentDirectory] = useState("");
  const [keyword, setKeyword] = useState("");
  const [editingCardPath, setEditingCardPath] = useState("");
  const [editingCardType, setEditingCardType] = useState("card");
  const [customCardType, setCustomCardType] = useState("");
  const [editingCardId, setEditingCardId] = useState("");
  const [editingFolderPath, setEditingFolderPath] = useState("");
  const [frontmatterText, setFrontmatterText] = useState("{}");
  const [bodyText, setBodyText] = useState("");
  const [createPackDraft, setCreatePackDraft] = useState<CreatePackDraft>(createEmptyPackDraft());
  const [agentSession, setAgentSession] = useState<DesignerAgentSession | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [toolLogs, setToolLogs] = useState<string[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [isCardsLoading, setIsCardsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const currentCardType = customCardType.trim() || editingCardType;
  const agentHistory = useMemo(() => {
    const history = agentSession?.state?.history;
    return Array.isArray(history) ? history : [];
  }, [agentSession]);

  const normalizedCurrentDirectory = useMemo(
    () => currentDirectory.trim().replace(/\\+/g, "/").replace(/^\/+|\/+$/g, ""),
    [currentDirectory],
  );

  const currentDirectoryPrefix = normalizedCurrentDirectory ? `${normalizedCurrentDirectory}/` : "";

  const visibleFolders = useMemo(() => {
    const folders = new Set<string>();
    for (const card of cards) {
      const relative = currentDirectoryPrefix
        ? card.path.startsWith(currentDirectoryPrefix)
          ? card.path.slice(currentDirectoryPrefix.length)
          : ""
        : card.path;
      if (!relative) {
        continue;
      }
      const parts = relative.split("/").filter(Boolean);
      if (parts.length > 1) {
        folders.add(parts[0]);
      }
    }
    return Array.from(folders).sort((a, b) => a.localeCompare(b));
  }, [cards, currentDirectoryPrefix]);

  const visibleCards = useMemo(() => {
    return cards
      .filter((card) => {
        const relative = currentDirectoryPrefix
          ? card.path.startsWith(currentDirectoryPrefix)
            ? card.path.slice(currentDirectoryPrefix.length)
            : ""
          : card.path;
        if (!relative) {
          return false;
        }
        return !relative.includes("/");
      })
      .sort((a, b) => a.card_id.localeCompare(b.card_id));
  }, [cards, currentDirectoryPrefix]);

  const breadcrumbItems = useMemo(() => {
    const parts = normalizedCurrentDirectory ? normalizedCurrentDirectory.split("/").filter(Boolean) : [];
    const crumbs: Array<{ label: string; path: string }> = [{ label: "root", path: "" }];
    let current = "";
    for (const part of parts) {
      current = current ? `${current}/${part}` : part;
      crumbs.push({ label: part, path: current });
    }
    return crumbs;
  }, [normalizedCurrentDirectory]);

  const agentTargetPackId = useMemo(() => {
    const sessionPackId = String(agentSession?.selected_pack_id ?? "").trim();
    if (sessionPackId) {
      return sessionPackId;
    }
    const statePackId = String((agentSession?.state as { selected_pack_id?: unknown } | undefined)?.selected_pack_id ?? "").trim();
    if (statePackId) {
      return statePackId;
    }
    return selectedPackId;
  }, [agentSession, selectedPackId]);

  const agentTargetPackName = useMemo(() => {
    if (!agentTargetPackId) {
      return "Unknown";
    }
    const record = runtimePacks.find((pack) => pack.pack_id === agentTargetPackId);
    return record?.name ?? "Unknown";
  }, [agentTargetPackId, runtimePacks]);

  useEffect(() => {
    if (runtimePacks.length === 0) {
      setMode("create-pack");
    }
  }, [runtimePacks.length]);

  useEffect(() => {
    if (!selectedPackId || mode !== "edit") {
      return;
    }

    let cancelled = false;
    async function loadDesignerData() {
      setIsCardsLoading(true);
      try {
        const [nextTypes, nextCards] = await Promise.all([
          getDesignerCardTypes(selectedPackId),
          getDesignerCards(selectedPackId),
        ]);
        if (cancelled) {
          return;
        }
        setCardTypes(nextTypes.length > 0 ? nextTypes : ["card"]);
        setCards(nextCards);
        setCurrentDirectory("");
        if (!editingCardPath && nextTypes.length > 0) {
          setEditingCardType(nextTypes[0]);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load designer data.");
        }
      } finally {
        if (!cancelled) {
          setIsCardsLoading(false);
        }
      }
    }

    void loadDesignerData();
    return () => {
      cancelled = true;
    };
  }, [selectedPackId, mode]);

  useEffect(() => {
    if (mode !== "edit" || agentSession) {
      return;
    }

    let cancelled = false;
    async function bootstrapAgentSession() {
      try {
        const nextSession = await createDesignerAgentSession(selectedPackId || undefined);
        if (!cancelled) {
          setAgentSession(nextSession);
          setToolLogs([]);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to create designer session.");
        }
      }
    }

    void bootstrapAgentSession();
    return () => {
      cancelled = true;
    };
  }, [selectedPackId, mode, agentSession]);

  async function refreshCards(packId: string, nextKeyword?: string) {
    if (!packId) {
      return;
    }
    setIsCardsLoading(true);
    try {
      const updated = await getDesignerCards(packId, {
        keyword: nextKeyword?.trim() ? nextKeyword.trim() : undefined,
      });
      setCards(updated);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to refresh cards.");
    } finally {
      setIsCardsLoading(false);
    }
  }

  function resetEditor(useCurrentDirectoryFolder: boolean = false) {
    setEditingCardPath("");
    setEditingCardId("");
    setEditingFolderPath(
      useCurrentDirectoryFolder
        ? folderPathFromCurrentDirectory(normalizedCurrentDirectory)
        : "",
    );
    setCustomCardType("");
    setFrontmatterText("{}");
    setBodyText("");
    setEditingCardType(cardTypes[0] ?? "card");
  }

  async function handleLoadCard(path: string) {
    if (!selectedPackId) {
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const payload = await loadDesignerCard(selectedPackId, path);
      setEditingCardPath(payload.path);
      setEditingCardType(payload.card_type);
      setCustomCardType("");
      setEditingCardId(payload.card_id);
      setEditingFolderPath(payload.folder_path || "");
      setCurrentDirectory(directoryOfCardPath(payload.path));
      setFrontmatterText(stringifyFrontmatter(payload.frontmatter));
      setBodyText(payload.body);
      setSuccessMessage(`Loaded ${payload.path}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load the card.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleGenerateTemplate() {
    if (!selectedPackId) {
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const payload = await getDesignerCardTemplate(selectedPackId, currentCardType || "card");
      setFrontmatterText(stringifyFrontmatter(payload));
      setSuccessMessage(`Generated template for ${currentCardType || "card"}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to generate the template.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSaveCard() {
    if (!selectedPackId || !editingCardId.trim()) {
      setErrorMessage("Pack and card id are required.");
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    const submittedFrontmatterText = frontmatterText;
    const submittedBodyText = bodyText;
    try {
      const payload = await saveDesignerCard(selectedPackId, {
        card_type: currentCardType || "card",
        card_id: editingCardId.trim(),
        folder_path: editingFolderPath.trim() || undefined,
        frontmatter_text: submittedFrontmatterText,
        body: submittedBodyText,
        original_path: editingCardPath || undefined,
      });
      setEditingCardPath(payload.path);
      setEditingCardType(payload.card_type);
      setEditingCardId(payload.card_id);
      setEditingFolderPath(payload.folder_path || "");
      setCurrentDirectory(directoryOfCardPath(payload.path));
      await refreshCards(selectedPackId, keyword);
      setSuccessMessage(`Saved ${payload.path}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save the card.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleValidateCard() {
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await validateDesignerCard({ frontmatter_text: frontmatterText, body: bodyText });
      setSuccessMessage("Card content is valid.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Card validation failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDeleteCard() {
    if (!selectedPackId || !editingCardPath) {
      setErrorMessage("Load a card before deleting it.");
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteDesignerCard(selectedPackId, editingCardPath);
      resetEditor();
      await refreshCards(selectedPackId, keyword);
      setSuccessMessage("Card deleted.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete the card.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCreatePack() {
    if (!createPackDraft.pack_id.trim() || !createPackDraft.name.trim() || !createPackDraft.author.trim()) {
      setErrorMessage("pack_id, name, and author are required.");
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createDesignerPack(createPackDraft);
      const nextPack: PackRecord = {
        ...createPackDraft,
        cards_root: "cards",
        enabled: false,
        source: "local",
      };
      setRuntimePacks((current) => [nextPack, ...current.filter((pack) => pack.pack_id !== nextPack.pack_id)]);
      setSelectedPackId(createPackDraft.pack_id);
      setAgentSession(null);
      setToolLogs([]);
      setMode("edit");
      setCreatePackDraft(createEmptyPackDraft());
      setSuccessMessage(`Created pack ${nextPack.pack_id}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create pack.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSendAgentMessage() {
    if (!agentInput.trim() || !agentSession) {
      return;
    }
    setIsBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const response = await sendDesignerAgentMessage(agentSession.session_id, agentInput.trim());
      setAgentSession((current) =>
        current
          ? {
              ...current,
              selected_pack_id: response.selected_pack_id,
              state: response.state,
            }
          : null,
      );
      setToolLogs(response.tool_logs);
      if (response.selected_pack_id && response.selected_pack_id !== selectedPackId) {
        setSelectedPackId(response.selected_pack_id);
      } else if (selectedPackId) {
        await refreshCards(selectedPackId, keyword);
      }
      setAgentInput("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to send the designer prompt.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar activePath="/card-designer" currentUser={currentUser} />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Card Designer</h1>
          </header>

          <div className="designer-grid">
            <section className="light-card designer-panel designer-editor-panel">
              <div className="designer-panel-header">
                <h2 className="light-card-title">{mode === "edit" ? "Create / Edit Card" : "New Pack Manifest"}</h2>
                <div className="designer-mode-switch">
                  <button
                    className={`light-action-button ${mode === "edit" ? "load" : "disabled"}`}
                    onClick={() => setMode("edit")}
                    type="button"
                  >
                    Edit Pack
                  </button>
                  <button
                    className={`light-action-button ${mode === "create-pack" ? "new" : "archive"}`}
                    onClick={() => setMode("create-pack")}
                    type="button"
                  >
                    Create Pack
                  </button>
                </div>
              </div>

              {mode === "edit" ? (
                <div className="designer-editor-scroll">
                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-pack-id">
                      Pack
                    </label>
                    <select
                      className="light-input"
                      id="designer-pack-id"
                      onChange={(event) => {
                        setSelectedPackId(event.target.value);
                        setKeyword("");
                        setCurrentDirectory("");
                        setAgentSession(null);
                        setToolLogs([]);
                        resetEditor();
                      }}
                      value={selectedPackId}
                    >
                      {runtimePacks.map((pack) => (
                        <option key={pack.pack_id} value={pack.pack_id}>
                          {pack.name} ({pack.pack_id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-card-type">
                      Type
                    </label>
                    <select
                      className="light-input"
                      id="designer-card-type"
                      onChange={(event) => setEditingCardType(event.target.value)}
                      value={editingCardType}
                    >
                      {cardTypes.map((cardType) => (
                        <option key={cardType} value={cardType}>
                          {cardType}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-custom-card-type">
                      Custom Type
                    </label>
                    <input
                      className="light-input"
                      id="designer-custom-card-type"
                      onChange={(event) => setCustomCardType(event.target.value)}
                      placeholder="e.g. faction, clue, chapter"
                      value={customCardType}
                    />
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-card-id">
                      Card ID
                    </label>
                    <input
                      className="light-input"
                      id="designer-card-id"
                      onChange={(event) => setEditingCardId(event.target.value)}
                      placeholder="card id"
                      value={editingCardId}
                    />
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-folder-path">
                      Folder Path (optional)
                    </label>
                    <input
                      className="light-input"
                      id="designer-folder-path"
                      onChange={(event) => setEditingFolderPath(event.target.value)}
                      placeholder="e.g. main_story/chapter_01"
                      value={editingFolderPath}
                    />
                  </div>

                  <div className="designer-inline-actions">
                    <button className="light-action-button load" onClick={handleGenerateTemplate} type="button">
                      Generate Template
                    </button>
                    <button className="light-action-button archive" onClick={() => resetEditor(true)} type="button">
                      New Card
                    </button>
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-frontmatter">
                      Frontmatter (YAML / JSON)
                    </label>
                    <textarea
                      className="designer-textarea designer-frontmatter"
                      id="designer-frontmatter"
                      onChange={(event) => setFrontmatterText(event.target.value)}
                      value={frontmatterText}
                    />
                  </div>

                  <div className="settings-field">
                    <label className="settings-label" htmlFor="designer-body">
                      Body (Markdown)
                    </label>
                    <textarea
                      className="designer-textarea designer-body"
                      id="designer-body"
                      onChange={(event) => setBodyText(event.target.value)}
                      value={bodyText}
                    />
                  </div>

                  <div className="designer-inline-actions designer-footer-actions">
                    <button className="light-action-button new" disabled={isBusy} onClick={handleSaveCard} type="button">
                      Save
                    </button>
                    <button className="light-action-button load" disabled={isBusy} onClick={handleValidateCard} type="button">
                      Validate
                    </button>
                    <button
                      className="light-action-button archive"
                      disabled={isBusy || !editingCardPath}
                      onClick={handleDeleteCard}
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ) : (
                <div className="designer-editor-scroll">
                  {(["pack_id", "name", "version", "author", "description"] as const).map((field) => (
                    <div className="settings-field" key={field}>
                      <label className="settings-label" htmlFor={`create-pack-${field}`}>
                        {field}
                      </label>
                      {field === "description" ? (
                        <textarea
                          className="designer-textarea designer-frontmatter"
                          id={`create-pack-${field}`}
                          onChange={(event) =>
                            setCreatePackDraft((current) => ({
                              ...current,
                              [field]: event.target.value,
                            }))
                          }
                          value={createPackDraft[field]}
                        />
                      ) : (
                        <input
                          className="light-input"
                          id={`create-pack-${field}`}
                          onChange={(event) =>
                            setCreatePackDraft((current) => ({
                              ...current,
                              [field]: event.target.value,
                            }))
                          }
                          value={createPackDraft[field]}
                        />
                      )}
                    </div>
                  ))}

                  <button className="light-action-button new designer-create-pack-button" onClick={handleCreatePack} type="button">
                    Save Pack
                  </button>
                </div>
              )}
            </section>

            <section className="light-card designer-panel designer-library-panel">
              <h2 className="light-card-title">{mode === "edit" ? "Existing Cards" : "Planned Card Mix"}</h2>
              {mode === "edit" ? (
                <>
                  <div className="designer-filter-row">
                    <input
                      className="light-input"
                      onChange={(event) => {
                        const nextKeyword = event.target.value;
                        setKeyword(nextKeyword);
                        void refreshCards(selectedPackId, nextKeyword);
                      }}
                      placeholder="Search cards"
                      value={keyword}
                    />
                    <button
                      className="light-action-button load"
                      disabled={isCardsLoading || !selectedPackId}
                      onClick={() => void refreshCards(selectedPackId, keyword)}
                      type="button"
                    >
                      {isCardsLoading ? "Loading..." : "Reload"}
                    </button>
                    <button
                      className="light-action-button archive"
                      disabled={isCardsLoading || (!keyword && !currentDirectory)}
                      onClick={() => {
                        setKeyword("");
                        setCurrentDirectory("");
                        void refreshCards(selectedPackId, "");
                      }}
                      type="button"
                    >
                      Reset View
                    </button>
                  </div>

                  <div className="designer-filter-row">
                    <button
                      className="light-action-button archive"
                      disabled={!normalizedCurrentDirectory}
                      onClick={() => {
                        const parts = normalizedCurrentDirectory.split("/").filter(Boolean);
                        parts.pop();
                        setCurrentDirectory(parts.join("/"));
                      }}
                      type="button"
                    >
                      Up
                    </button>
                    <div className="light-inline-note" style={{ flex: 1 }}>
                      {breadcrumbItems.map((crumb, index) => (
                        <span key={crumb.path || "root"}>
                          {index > 0 ? " / " : ""}
                          <button
                            className="light-action-button load"
                            onClick={() => setCurrentDirectory(crumb.path)}
                            style={{ padding: "2px 8px", minHeight: "auto" }}
                            type="button"
                          >
                            {crumb.label}
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="light-inline-note">
                    {isCardsLoading
                      ? "Loading existing cards..."
                      : `Showing ${visibleFolders.length} folder${visibleFolders.length === 1 ? "" : "s"} and ${visibleCards.length} card${visibleCards.length === 1 ? "" : "s"} in ${normalizedCurrentDirectory || "root"}.`}
                  </div>

                  <div className="designer-card-list">
                    {visibleFolders.map((folder) => {
                      const nextPath = normalizedCurrentDirectory ? `${normalizedCurrentDirectory}/${folder}` : folder;
                      return (
                        <button
                          className="designer-card-row"
                          key={`folder:${nextPath}`}
                          onClick={() => setCurrentDirectory(nextPath)}
                          type="button"
                        >
                          <div className="designer-card-title">[Folder] {folder}</div>
                          <div className="designer-card-meta">{nextPath}</div>
                        </button>
                      );
                    })}

                    {visibleCards.map((card) => (
                      <button
                        className={`designer-card-row ${card.path === editingCardPath ? "active" : ""}`}
                        key={card.path}
                        onClick={() => void handleLoadCard(card.path)}
                        type="button"
                      >
                        <div className="designer-card-title">{card.title}</div>
                        <div className="designer-card-meta">
                          {card.category} / {card.card_type}
                        </div>
                        <div className="designer-card-path">{card.path}</div>
                      </button>
                    ))}
                    {visibleFolders.length === 0 && visibleCards.length === 0 ? (
                      <div className="light-inline-note">No folders or cards in current directory.</div>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="designer-plan-stack">
                  <div className="light-copy">Pack ID: {createPackDraft.pack_id || "pending"}</div>
                  <div className="light-copy">Name: {createPackDraft.name || "pending"}</div>
                  <div className="light-copy">Version: {createPackDraft.version || "0.1.0"}</div>
                  <div className="light-inline-note">
                    This area will later host a richer structural preview. For the MVP it reflects the current pack draft summary.
                  </div>
                </div>
              )}
            </section>

            <section className="light-card designer-panel designer-agent-panel">
              <div className="designer-panel-header">
                <h2 className="light-card-title">Pack Builder Agent</h2>
                <div className="designer-agent-target" title="Agent current write target">
                  <div className="designer-agent-target-label">Write Target</div>
                  <div className="designer-agent-target-value">{agentTargetPackId || "(none)"}</div>
                  <div className="designer-agent-target-name">{agentTargetPackName}</div>
                </div>
              </div>
              <div className="designer-agent-history">
                {agentHistory.length === 0 ? (
                  <div className="light-inline-note">No designer chat yet. Describe the pack or card changes you want.</div>
                ) : (
                  agentHistory.map((entry, index) => {
                    const role = typeof entry === "object" && entry && "role" in entry ? String((entry as { role?: unknown }).role ?? "assistant") : "assistant";
                    const content =
                      typeof entry === "object" && entry && "content" in entry
                        ? String((entry as { content?: unknown }).content ?? "")
                        : "";
                    return (
                      <div className={`designer-chat-row ${role === "user" ? "user" : "assistant"}`} key={`${role}-${index}`}>
                        <div className="designer-chat-role">{role.toUpperCase()}</div>
                        <div className="designer-chat-content">
                          {(() => {
                            const preview = role === "assistant" ? parsePendingBatchSavePreview(content) : null;
                            if (!preview) {
                              return content;
                            }
                            return (
                              <div className="designer-pending-plan">
                                <div className="designer-pending-plan-head">
                                  待确认写入：pack_id={preview.pack_id || "(unknown)"}，共 {preview.cards.length} 张卡
                                </div>
                                <div className="designer-pending-plan-list">
                                  {preview.cards.map((card) => (
                                    <details className="designer-pending-item" key={`${card.card_type}-${card.card_id}`}>
                                      <summary className="designer-pending-summary">
                                        {card.title} ({card.card_type})
                                      </summary>
                                      <div className="designer-pending-body">
                                        <div>card_id: {card.card_id}</div>
                                        {card.tags.length > 0 ? <div>tags: {card.tags.join(", ")}</div> : null}
                                        <div className="designer-pending-text">{card.body || "(empty body)"}</div>
                                      </div>
                                    </details>
                                  ))}
                                </div>
                                <div className="light-inline-note">回复“确认执行”后才会真正写入。</div>
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="designer-agent-input">
                  Designer Prompt
                </label>
                <textarea
                  className="designer-textarea designer-agent-input"
                  id="designer-agent-input"
                  onChange={(event) => setAgentInput(event.target.value)}
                  placeholder="Describe the pack, cards, or edits you want the agent to perform."
                  value={agentInput}
                />
              </div>

              <button
                className="light-action-button new"
                disabled={isBusy || !agentSession || !agentInput.trim()}
                onClick={handleSendAgentMessage}
                type="button"
              >
                {isBusy ? "Working..." : "Send to Agent"}
              </button>

              {!agentSession ? (
                <div className="light-inline-note">Agent session is initializing. If it does not recover, switch packs or refresh the page.</div>
              ) : null}

              {toolLogs.length > 0 ? (
                <div className="designer-tool-log">
                  <div className="light-section-title">Last Tool Activity</div>
                  {toolLogs.map((line) => (
                    <div className="designer-tool-line" key={line}>
                      {line}
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
          </div>

          {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
          {successMessage ? <div className="light-success-banner">{successMessage}</div> : null}
        </section>
      </div>
    </main>
  );
}
