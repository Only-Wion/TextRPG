"use client";

import { useMemo, useState } from "react";

import {
  createPackUiTemplate,
  deletePackUiTemplate,
  exportPack,
  listPackUiTemplates,
  removePack,
  setPackEnabled,
} from "../lib/api";
import type { AuthUser, PackRecord, UiTemplateRecord } from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type PacksShellProps = {
  packs: PackRecord[];
  currentUser: AuthUser;
};

export function PacksShell({ packs, currentUser }: PacksShellProps) {
  const [runtimePacks, setRuntimePacks] = useState(packs);
  const [busyPackId, setBusyPackId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [templatePackId, setTemplatePackId] = useState<string>(packs[0]?.pack_id ?? "");
  const [templates, setTemplates] = useState<UiTemplateRecord[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [isTemplateBusy, setIsTemplateBusy] = useState(false);

  const exportCandidate = useMemo(
    () => runtimePacks.find((pack) => pack.enabled) ?? runtimePacks[0] ?? null,
    [runtimePacks],
  );

  async function handleToggle(packId: string, enabled: boolean) {
    setBusyPackId(packId);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await setPackEnabled(packId, enabled);
      setRuntimePacks((current) =>
        current.map((pack) => (pack.pack_id === packId ? { ...pack, enabled } : pack)),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to update the pack.");
    } finally {
      setBusyPackId(null);
    }
  }

  async function handleRemove(packId: string) {
    setBusyPackId(packId);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await removePack(packId);
      setRuntimePacks((current) => current.filter((pack) => pack.pack_id !== packId));
      setSuccessMessage(`Removed pack: ${packId}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to remove the pack.");
    } finally {
      setBusyPackId(null);
    }
  }

  async function handleExport(packId: string) {
    setBusyPackId(packId);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const response = await exportPack(packId);
      setSuccessMessage(`Exported ${response.pack_id} to ${response.export_path}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to export the pack.");
    } finally {
      setBusyPackId(null);
    }
  }

  async function handleLoadTemplates(packId: string) {
    setIsTemplateBusy(true);
    setErrorMessage(null);
    try {
      const records = await listPackUiTemplates(packId);
      setTemplates(records);
      setTemplatePackId(packId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load UI templates.");
    } finally {
      setIsTemplateBusy(false);
    }
  }

  async function handleCreateTemplate() {
    if (!templatePackId || !templateName.trim()) {
      setErrorMessage("Choose a pack and input template name.");
      return;
    }
    setIsTemplateBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createPackUiTemplate(templatePackId, {
        name: templateName.trim(),
        template: { panels: [] },
        variable_template: { variables: [] },
      });
      setTemplateName("");
      await handleLoadTemplates(templatePackId);
      setSuccessMessage("UI template created.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create UI template.");
    } finally {
      setIsTemplateBusy(false);
    }
  }

  async function handleDeleteTemplate(templateId: string) {
    if (!templatePackId) {
      return;
    }
    const record = templates.find((item) => item.template_id === templateId);
    if (record && (record.sessions_in_use ?? 0) > 0) {
      setErrorMessage(`Template is used by ${record.sessions_in_use} active session(s) and cannot be deleted.`);
      return;
    }
    setIsTemplateBusy(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deletePackUiTemplate(templatePackId, templateId);
      await handleLoadTemplates(templatePackId);
      setSuccessMessage("UI template removed.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete UI template.");
    } finally {
      setIsTemplateBusy(false);
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar activePath="/packs" currentUser={currentUser} />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Pack Manager</h1>
          </header>

          <div className="light-stack">
            <section className="light-card">
              <h2 className="light-card-title">Installed Packs</h2>
              <div className="pack-table">
                <div className="pack-table-head">
                  <span>Name (ID)</span>
                  <span>Version / Author</span>
                  <span>Enabled</span>
                  <span>Action</span>
                </div>

                {runtimePacks.map((pack) => (
                  <div className="pack-row" key={pack.pack_id}>
                    <div>
                      <div className="pack-title">{pack.name}</div>
                      <div className="pack-subtle">{pack.pack_id}</div>
                    </div>
                    <div className="pack-subtle">
                      {pack.version} / {pack.author}
                    </div>
                    <label className="toggle-row">
                      <input
                        checked={pack.enabled}
                        disabled={busyPackId === pack.pack_id}
                        onChange={(event) => handleToggle(pack.pack_id, event.target.checked)}
                        type="checkbox"
                      />
                      <span>{pack.enabled ? "Enabled" : "Disabled"}</span>
                    </label>
                    <button
                      className="table-action-button"
                      disabled={busyPackId === pack.pack_id || pack.source === "builtin"}
                      onClick={() => handleRemove(pack.pack_id)}
                      type="button"
                    >
                      {busyPackId === pack.pack_id ? "Working..." : "Remove"}
                    </button>
                  </div>
                ))}
              </div>
              {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
              {successMessage ? <div className="light-success-banner">{successMessage}</div> : null}
              <div className="light-inline-note">
                Enable/disable updates your account's default pack set. Builtin packs are protected from removal.
              </div>
            </section>

            <section className="light-card light-form-card">
              <h2 className="light-card-title">Install from URL</h2>
              <div className="inline-form">
                <input className="light-input" placeholder="https://example.com/pack.zip" readOnly />
                <button className="light-action-button load disabled" disabled type="button">
                  Download & Install
                </button>
              </div>
            </section>

            <section className="light-card light-form-card">
              <h2 className="light-card-title">Install from ZIP</h2>
              <div className="dropzone-placeholder">Upload pack ZIP</div>
            </section>

            <section className="light-card light-form-card">
              <h2 className="light-card-title">Export Pack</h2>
              <div className="inline-form">
                <input
                  className="light-input"
                  readOnly
                  value={exportCandidate?.pack_id ?? "No pack selected"}
                />
                <button
                  className="light-action-button new"
                  disabled={!exportCandidate || !!busyPackId}
                  onClick={() => exportCandidate && handleExport(exportCandidate.pack_id)}
                  type="button"
                >
                  {busyPackId === exportCandidate?.pack_id ? "Exporting..." : "Export"}
                </button>
              </div>
              <div className="light-inline-note">
                Export writes a ZIP into the local runtime exports directory and returns the path.
              </div>
            </section>

            <section className="light-card light-form-card">
              <h2 className="light-card-title">UI Templates</h2>
              <div className="inline-form">
                <select
                  className="light-input"
                  onChange={(event) => setTemplatePackId(event.target.value)}
                  value={templatePackId}
                >
                  {runtimePacks.map((pack) => (
                    <option key={pack.pack_id} value={pack.pack_id}>
                      {pack.name} ({pack.pack_id})
                    </option>
                  ))}
                </select>
                <button
                  className="light-action-button load"
                  disabled={!templatePackId || isTemplateBusy}
                  onClick={() => void handleLoadTemplates(templatePackId)}
                  type="button"
                >
                  {isTemplateBusy ? "Loading..." : "Load"}
                </button>
              </div>
              <div className="inline-form">
                <input
                  className="light-input"
                  onChange={(event) => setTemplateName(event.target.value)}
                  placeholder="Template name"
                  value={templateName}
                />
                <button className="light-action-button new" disabled={isTemplateBusy} onClick={() => void handleCreateTemplate()} type="button">
                  Create Blank
                </button>
              </div>
              <div className="slot-list">
                {templates.map((template) => (
                  <div className="slot-row" key={template.template_id}>
                    <div className="slot-row-title">{template.name}</div>
                    <div className="slot-row-subtle">
                      {template.template_id} · in use: {template.sessions_in_use ?? 0}
                    </div>
                    <button
                      className="table-action-button"
                      disabled={isTemplateBusy || (template.sessions_in_use ?? 0) > 0}
                      onClick={() => void handleDeleteTemplate(template.template_id)}
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
              <div className="light-inline-note">
                Delete is blocked if the template is bound to active sessions.
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
