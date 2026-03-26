"use client";

import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { login, register } from "../lib/api";
import { persistClientAccessToken } from "../lib/auth";

type AuthShellProps = {
  mode: "login" | "register";
};

export function AuthShell({ mode }: AuthShellProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response =
        mode === "login"
          ? await login({ email_or_username: email.trim(), password })
          : await register({ email: email.trim(), username: username.trim(), password });
      persistClientAccessToken(response.access_token);
      router.push("/sessions");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="light-app-shell auth-page-shell">
      <section className="auth-card">
        <div className="auth-heading">
          <div className="light-brand-title">TextRPG</div>
          <div className="light-copy">
            {mode === "login"
              ? "Sign in to load your sessions and continue your current story."
              : "Create an account to keep your sessions isolated and stored per user."}
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="settings-field">
            <label className="settings-label" htmlFor="auth-email">
              {mode === "login" ? "Email or Username" : "Email"}
            </label>
            <input
              className="light-input"
              id="auth-email"
              onChange={(event) => setEmail(event.target.value)}
              value={email}
            />
          </div>

          {mode === "register" ? (
            <div className="settings-field">
              <label className="settings-label" htmlFor="auth-username">
                Username
              </label>
              <input
                className="light-input"
                id="auth-username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
            </div>
          ) : null}

          <div className="settings-field">
            <label className="settings-label" htmlFor="auth-password">
              Password
            </label>
            <input
              className="light-input"
              id="auth-password"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </div>

          {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}

          <button className="light-action-button new auth-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Working..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="light-inline-note">
          {mode === "login" ? (
            <>
              Need an account? <Link href="/register">Create one</Link>.
            </>
          ) : (
            <>
              Already have an account? <Link href="/login">Sign in</Link>.
            </>
          )}
        </div>
      </section>
    </main>
  );
}
