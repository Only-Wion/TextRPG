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
  cards_root: string;
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
    cards_root: "cards",
  };
}

export function CardDesignerShell({ packs, currentUser }: CardDesignerShellProps) {
  const [runtimePacks, setRuntimePacks] = useState(packs);
  const [mode, setMode] = useState<DesignerMode>(packs.length > 0 ? "edit" : "create-pack");
  const [selectedPackId, setSelectedPackId] = useState(packs[0]?.pack_id ?? "");
  const [cardTypes, setCardTypes] = useState<string[]>([]);
  const [cards, setCards] = useState<DesignerCardSummary[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("All");
  const [keyword, setKeyword] = useState("");
  const [editingCardPath, setEditingCardPath] = useState("");
  const [editingCardType, setEditingCardType] = useState("card");
  const [customCardType, setCustomCardType] = useState("");
  const [editingCardId, setEditingCardId] = useState("");
  const [frontmatterText, setFrontmatterText] = useState("{}");
  const [bodyText, setBodyText] = useState("");
  const [createPackDraft, setCreatePackDraft] = useState<CreatePackDraft>(createEmptyPackDraft());
  const [agentSession, setAgentSession] = useState<DesignerAgentSession | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [toolLogs, setToolLogs] = useState<string[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const currentCardType = customCardType.trim() || editingCardType;
  const agentHistory = useMemo(() => {
    const history = agentSession?.state?.history;
    return Array.isArray(history) ? history : [];
  }, [agentSession]);

  const categoryOptions = useMemo(() => {
    const values = Array.from(new Set(cards.map((card) => card.category))).sort();
    return ["All", ...values];
  }, [cards]);

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
        if (!editingCardPath && nextTypes.length > 0) {
          setEditingCardType(nextTypes[0]);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load designer data.");
        }
      }
    }

    void loadDesignerData();
    return () => {
      cancelled = true;
    };
  }, [selectedPackId, mode]);

  useEffect(() => {
    if (!selectedPackId || mode !== "edit" || agentSession) {
      return;
    }

    let cancelled = false;
    async function bootstrapAgentSession() {
      try {
        const nextSession = await createDesignerAgentSession(selectedPackId);
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

  useEffect(() => {
    if (selectedCategory !== "All" && !categoryOptions.includes(selectedCategory)) {
      setSelectedCategory("All");
    }
  }, [categoryOptions, selectedCategory]);

  async function refreshCards(packId: string, nextCategory?: string, nextKeyword?: string) {
    const updated = await getDesignerCards(packId, {
      category: nextCategory && nextCategory !== "All" ? nextCategory : undefined,
      keyword: nextKeyword?.trim() ? nextKeyword.trim() : undefined,
    });
    setCards(updated);
  }

  function resetEditor() {
    setEditingCardPath("");
    setEditingCardId("");
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
    try {
      const payload = await saveDesignerCard(selectedPackId, {
        card_type: currentCardType || "card",
        card_id: editingCardId.trim(),
        frontmatter_text: frontmatterText,
        body: bodyText,
        original_path: editingCardPath || undefined,
      });
      setEditingCardPath(payload.path);
      setFrontmatterText(stringifyFrontmatter(payload.frontmatter));
      await refreshCards(selectedPackId, selectedCategory, keyword);
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
      await refreshCards(selectedPackId, selectedCategory, keyword);
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
        await refreshCards(selectedPackId, selectedCategory, keyword);
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
                        setSelectedCategory("All");
                        setKeyword("");
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

                  <div className="designer-inline-actions">
                    <button className="light-action-button load" onClick={handleGenerateTemplate} type="button">
                      Generate Template
                    </button>
                    <button className="light-action-button archive" onClick={resetEditor} type="button">
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
                  {(["pack_id", "name", "version", "author", "description", "cards_root"] as const).map((field) => (
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
                    <select
                      className="light-input"
                      onChange={async (event) => {
                        const nextCategory = event.target.value;
                        setSelectedCategory(nextCategory);
                        await refreshCards(selectedPackId, nextCategory, keyword);
                      }}
                      value={selectedCategory}
                    >
                      {categoryOptions.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </select>
                    <input
                      className="light-input"
                      onChange={async (event) => {
                        const nextKeyword = event.target.value;
                        setKeyword(nextKeyword);
                        await refreshCards(selectedPackId, selectedCategory, nextKeyword);
                      }}
                      placeholder="Search cards"
                      value={keyword}
                    />
                  </div>

                  <div className="designer-card-list">
                    {cards.map((card) => (
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
                    {cards.length === 0 ? <div className="light-inline-note">No cards matched the current filters.</div> : null}
                  </div>
                </>
              ) : (
                <div className="designer-plan-stack">
                  <div className="light-copy">Pack ID: {createPackDraft.pack_id || "pending"}</div>
                  <div className="light-copy">Name: {createPackDraft.name || "pending"}</div>
                  <div className="light-copy">Version: {createPackDraft.version || "0.1.0"}</div>
                  <div className="light-copy">Cards root: {createPackDraft.cards_root || "cards"}</div>
                  <div className="light-inline-note">
                    This area will later host a richer structural preview. For the MVP it reflects the current pack draft summary.
                  </div>
                </div>
              )}
            </section>

            <section className="light-card designer-panel designer-agent-panel">
              <h2 className="light-card-title">Pack Builder Agent</h2>
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
                        <div className="designer-chat-content">{content}</div>
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
                disabled={isBusy || !agentSession}
                onClick={handleSendAgentMessage}
                type="button"
              >
                {isBusy ? "Working..." : "Send to Agent"}
              </button>

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
