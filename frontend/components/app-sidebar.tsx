"use client";

import Link from "next/link";

type AppSidebarProps = {
  activePath: "/sessions" | "/" | "/packs" | "/settings" | "/setup";
  title?: string;
  sections?: Array<{ label: string; value: string }>;
};

const navItems = [
  { href: "/sessions" as const, label: "Sessions" },
  { href: "/" as const, label: "Play" },
  { href: "/packs" as const, label: "Pack Manager" },
  { href: "/settings" as const, label: "Settings" },
  { href: "/setup" as const, label: "Setup" },
];

export function AppSidebar({
  activePath,
  title = "TextRPG UI",
  sections = [],
}: AppSidebarProps) {
  return (
    <aside className="light-sidebar">
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
    </aside>
  );
}
