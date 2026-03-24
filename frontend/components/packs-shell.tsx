"use client";

import { useMemo, useState } from "react";

import { setPackEnabled } from "../lib/api";
import type { PackRecord } from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type PacksShellProps = {
  packs: PackRecord[];
};

export function PacksShell({ packs }: PacksShellProps) {
  const [runtimePacks, setRuntimePacks] = useState(packs);
  const [busyPackId, setBusyPackId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const exportCandidate = useMemo(
    () => runtimePacks.find((pack) => pack.enabled) ?? runtimePacks[0] ?? null,
    [runtimePacks],
  );

  async function handleToggle(packId: string, enabled: boolean) {
    setBusyPackId(packId);
    setErrorMessage(null);

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

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar activePath="/packs" />

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
                    <button className="table-action-button" disabled type="button">
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
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
                <button className="light-action-button new disabled" disabled type="button">
                  Export
                </button>
              </div>
              <div className="light-inline-note">
                Install and export actions remain UI placeholders until file upload and download
                endpoints are added.
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
