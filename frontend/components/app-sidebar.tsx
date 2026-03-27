"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { AuthUser } from "../lib/api-contract";
import { logout } from "../lib/api";
import { clearClientAccessToken } from "../lib/auth";

type SidebarStatusSection = { label: string; value: string };
type SidebarInspectorSection = {
  id: string;
  title: string;
  defaultOpen?: boolean;
  lines: string[];
};

type AppSidebarProps = {
  activePath: "/sessions" | "/" | "/packs" | "/settings" | "/card-designer";
  title?: string;
  sections?: SidebarStatusSection[];
  inspectorSections?: SidebarInspectorSection[];
  currentUser?: AuthUser | null;
};

const navItems = [
  { href: "/sessions" as const, label: "Sessions" },
  { href: "/" as const, label: "Play" },
  { href: "/packs" as const, label: "Pack Manager" },
  { href: "/card-designer" as const, label: "Card Designer" },
  { href: "/settings" as const, label: "Settings" },
];

export function AppSidebar({
  activePath,
  title = "TextRPG UI",
  sections = [],
  inspectorSections = [],
  currentUser = null,
}: AppSidebarProps) {
  const router = useRouter();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(
    Object.fromEntries(inspectorSections.map((section) => [section.id, section.defaultOpen ?? true])),
  );

  function toggleInspectorSection(sectionId: string) {
    setOpenSections((current) => ({
      ...current,
      [sectionId]: !current[sectionId],
    }));
  }

  async function handleLogout() {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      // Clearing the local token keeps the user unblocked even if revoke fails.
    } finally {
      clearClientAccessToken();
      router.push("/login");
      router.refresh();
      setIsLoggingOut(false);
    }
  }

  return (
    <aside className={`light-sidebar ${isCollapsed ? "is-collapsed" : ""}`}>
      <div className="light-sidebar-scroll">
        {isCollapsed ? null : (
          <>
            <div>
              <div className="light-brand-title">{title}</div>
              <div className="light-muted small-copy">Pages</div>
            </div>

            <nav className="light-sidebar-nav">
              {navItems.map((item) => (
                <Link
                  className={`light-sidebar-link ${item.href === activePath ? "active" : ""}`}
                  href={item.href}
                  key={item.href}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            {currentUser ? (
              <div className="sidebar-section-stack">
                <div className="light-section-title">Account</div>
                <div className="light-copy">{currentUser.username}</div>
                <div className="light-muted small-copy sidebar-account-email">{currentUser.email}</div>
                <button
                  className="light-action-button archive sidebar-logout-button"
                  disabled={isLoggingOut}
                  onClick={handleLogout}
                  type="button"
                >
                  {isLoggingOut ? "Signing out..." : "Sign Out"}
                </button>
              </div>
            ) : null}

            {sections.length > 0 ? (
              <div className="sidebar-section-stack">
                <div className="light-section-title">Session Health</div>
                {sections.map((section) => (
                  <div className="light-status-row" key={section.label}>
                    <span>{section.label}</span>
                    <span>{section.value}</span>
                  </div>
                ))}
              </div>
            ) : null}

            {inspectorSections.length > 0 ? (
              <div className="sidebar-section-stack">
                <div className="light-section-title">Inspector</div>
                {inspectorSections.map((section) => {
                  const isOpen = openSections[section.id] ?? section.defaultOpen ?? true;
                  return (
                    <div className="sidebar-inspector-card" key={section.id}>
                      <button
                        className="sidebar-inspector-toggle"
                        onClick={() => toggleInspectorSection(section.id)}
                        type="button"
                      >
                        <span>{section.title}</span>
                        <span className="sidebar-inspector-arrow">{isOpen ? "^" : "v"}</span>
                      </button>
                      {isOpen ? (
                        <div className="sidebar-inspector-body">
                          {section.lines.map((line, index) => (
                            <div className="sidebar-inspector-line" key={`${section.id}-${index}`}>
                              {line}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </>
        )}
      </div>

      <button
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="sidebar-collapse-handle"
        onClick={() => setIsCollapsed((current) => !current)}
        type="button"
      >
        <span className={`sidebar-collapse-arrow ${isCollapsed ? "active" : "muted"}`}>{"<"}</span>
        <span className={`sidebar-collapse-arrow ${isCollapsed ? "muted" : "active"}`}>{">"}</span>
      </button>
    </aside>
  );
}
