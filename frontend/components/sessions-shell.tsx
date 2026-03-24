"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { loadGameSession } from "../lib/api";
import type { SessionManagerView, SessionSummary } from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type SessionsShellProps = {
  view: SessionManagerView;
};

export function SessionsShell({ view }: SessionsShellProps) {
  const router = useRouter();
  const [selectedSlot, setSelectedSlot] = useState(view.selected_slot);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const selectedSummary =
    view.sessions.find((session) => session.slot_id === selectedSlot) ?? view.sessions[0];

  async function handleLoad() {
    if (!selectedSummary || isLoading) {
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

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar
          activePath="/sessions"
          sections={[
            { label: "Backend", value: view.backend_status },
            { label: "Storage", value: view.storage_backend },
            { label: "Last sync", value: view.last_sync_label },
          ]}
        />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Sessions</h1>
          </header>

          <div className="manager-grid">
            <section className="light-card tall-card">
              <h2 className="light-card-title">Save Slots</h2>
              <p className="light-card-copy">
                Choose a session to continue, duplicate, or archive.
              </p>

              <div className="slot-list">
                {view.sessions.map((session) => (
                  <button
                    className={`slot-row ${session.slot_id === selectedSlot ? "active" : ""}`}
                    key={session.slot_id}
                    onClick={() => setSelectedSlot(session.slot_id)}
                    type="button"
                  >
                    <div className="slot-row-title">{session.slot_id}</div>
                    <div className="slot-row-meta">
                      {session.location_label} | {session.turn_count} turns | packs:{" "}
                      {session.enabled_packs.join(", ")}
                    </div>
                    <div className="slot-row-subtle">{session.updated_label}</div>
                  </button>
                ))}
              </div>
            </section>

            <div className="manager-rail">
              <section className="light-card">
                <h2 className="light-card-title">Current Selection</h2>
                {selectedSummary ? (
                  <SessionSummaryBlock session={selectedSummary} />
                ) : (
                  <div className="light-copy">No session selected.</div>
                )}
              </section>

              <section className="light-card">
                <h2 className="light-card-title">Quick Actions</h2>
                <div className="action-grid">
                  <button className="light-action-button load" onClick={handleLoad} type="button">
                    {isLoading ? "Loading..." : "Load Session"}
                  </button>
                  <Link className="light-action-button new" href="/setup">
                    New Session
                  </Link>
                  <button className="light-action-button duplicate disabled" disabled type="button">
                    Duplicate
                  </button>
                  <button className="light-action-button archive disabled" disabled type="button">
                    Archive
                  </button>
                </div>
                {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
                <div className="light-inline-note">
                  Duplicate and archive stay disabled until the backend exposes dedicated session
                  management endpoints.
                </div>
              </section>

              <section className="light-card">
                <h2 className="light-card-title">Session Notes</h2>
                <p className="light-copy">Manage save slots here before entering Play.</p>
                <p className="light-copy">
                  Next: load {selectedSummary?.slot_id ?? "a slot"} and continue the current thread.
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
    </div>
  );
}
