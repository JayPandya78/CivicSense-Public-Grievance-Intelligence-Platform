import React, { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function AuthBrand() {
  return (
    <a className="brand" href="/" aria-label="CivicSense home">
      <span className="brand-icon" aria-hidden="true">
        <svg viewBox="0 0 36 36" fill="none">
          <path d="M18 4.5 30 11v14L18 31.5 6 25V11L18 4.5Z" fill="currentColor" />
          <path d="m12 18 4 4 8-9" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span>Civic<span className="brand-light">Sense</span></span>
    </a>
  );
}

export default function AuthPage({ mode }) {
  const isRegister = mode === "register";
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/auth/${isRegister ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isRegister
          ? form
          : { email: form.email, password: form.password }),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = result.detail;
        const message = typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((item) => item.msg).join(". ")
            : "Please check your details and try again.";
        throw new Error(message);
      }
      localStorage.setItem("civicsense_token", result.token);
      localStorage.setItem("civicsense_user", JSON.stringify(result.user));
      window.location.assign("/");
    } catch (submitError) {
      setError(submitError instanceof TypeError
        ? "We couldn’t connect to CivicSense. Please try again."
        : submitError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <header className="auth-header">
        <AuthBrand />
        <a className="auth-back-link" href="/">← Back to CivicSense</a>
      </header>
      <div className="auth-layout">
        <section className="auth-story">
          <div className="auth-story-content">
            <span className="auth-story-kicker"><span className="live-dot" /> BETTER STARTS TOGETHER</span>
            <h1>Your neighborhood<br />has <span>a voice.</span></h1>
            <p>Make it easier to follow the issues you care about. Join neighbors building a more thoughtful, responsive community.</p>
            <div className="auth-story-note">
              <span className="auth-note-mark">✳</span>
              <span><strong>Local change is a team effort.</strong><br />You bring the care. We’ll help you be heard.</span>
            </div>
          </div>
          <div className="auth-illustration" aria-hidden="true">
            <div className="auth-sun" />
            <div className="auth-horizon" />
            <div className="auth-home"><span /><i /><b /></div>
            <div className="auth-shrub shrub-one"><i /><i /><b /></div>
            <div className="auth-shrub shrub-two"><i /><i /><b /></div>
            <div className="auth-path" />
            <span className="auth-illustration-label">✳ &nbsp;Small actions add up</span>
          </div>
        </section>

        <section className="auth-card">
          <div className="auth-card-heading">
            <span className="section-kicker">{isRegister ? "A BETTER CITY STARTS WITH YOU" : "WELCOME BACK TO YOUR COMMUNITY"}</span>
            <h2>{isRegister ? "Create your account" : "Good to see you again."}</h2>
            <p>{isRegister
              ? "Join your neighbors and help make your corner of the world a little better."
              : "Sign in to pick up where you left off."}</p>
          </div>
          <form className="auth-form" onSubmit={handleSubmit}>
            {isRegister && (
              <div className="auth-field">
                <label htmlFor="auth-name">Your name</label>
                <input
                  id="auth-name"
                  name="name"
                  type="text"
                  autoComplete="name"
                  placeholder="How should we call you?"
                  value={form.name}
                  onChange={updateField}
                  minLength={2}
                  maxLength={80}
                  required
                />
              </div>
            )}
            <div className="auth-field">
              <label htmlFor="auth-email">Email address</label>
              <input
                id="auth-email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={updateField}
                maxLength={254}
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="auth-password">Password</label>
              <div className="auth-password-wrap">
                <input
                  id="auth-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  placeholder={isRegister ? "At least 8 characters" : "Enter your password"}
                  value={form.password}
                  onChange={updateField}
                  minLength={8}
                  maxLength={128}
                  required
                />
                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((shown) => !shown)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              {isRegister && <span className="auth-field-hint">Use at least 8 characters.</span>}
            </div>
            {error && <p className="form-message error-message" role="alert">{error}</p>}
            <button className="button button-dark auth-submit" type="submit" disabled={submitting}>
              {submitting
                ? (isRegister ? "Creating your account…" : "Signing you in…")
                : (isRegister ? "Create my account" : "Sign in")}
              {!submitting && <span aria-hidden="true">↗</span>}
            </button>
          </form>
          <p className="auth-switch">
            {isRegister ? "Already have an account?" : "New to CivicSense?"}
            {" "}
            <a href={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create an account"}
            </a>
          </p>
          <p className="auth-public-note"><span aria-hidden="true">♢</span> Sign in is required to browse and submit reports.</p>
        </section>
      </div>
      <footer className="auth-footer">
        <span>© 2026 CivicSense</span>
        <span>Made for the places we call home.</span>
      </footer>
    </main>
  );
}
