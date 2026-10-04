import { useId, useState, type FormEvent, type ReactNode } from "react";
import { MIN_PASSPHRASE_LENGTH, WrongCredentialError, validatePassphrase } from "../workspace/crypto/vault";
import { describeError, type LockReason, type Operator } from "../workspace/session";
import { Brand } from "./Brand";
import { Icon } from "./Icon";

function GateFrame({ title, eyebrow, children, footer }: { title: string; eyebrow: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="dk-gate">
      <main className="dk-gate-card" aria-labelledby="dk-gate-title">
        <Brand />
        <span className="dk-eyebrow">{eyebrow}</span>
        <h1 id="dk-gate-title">{title}</h1>
        {children}
        {footer && <div className="dk-gate-footer">{footer}</div>}
      </main>
    </div>
  );
}

function SignedInAs({ operator, onSignOut }: { operator: Operator; onSignOut: () => void }) {
  return (
    <>
      <span>Signed in as {operator.email ?? operator.displayName ?? "your Google account"}</span>
      <button type="button" className="dk-text-button" onClick={onSignOut}>
        Sign out
      </button>
    </>
  );
}

export function StatusScreen({ message }: { message: string }) {
  return (
    <div className="dk-gate">
      <p className="dk-gate-status" role="status" aria-live="polite">
        {message}
      </p>
    </div>
  );
}

export function ConfigurationMissing({ missing }: { missing: string[] }) {
  return (
    <GateFrame eyebrow="SETUP REQUIRED" title="Storage is not configured">
      <p>This build has no Firebase project settings. Set these variables and rebuild:</p>
      <ul className="dk-code-list">
        {missing.map((name) => (
          <li key={name}>
            <code>{name}</code>
          </li>
        ))}
      </ul>
      <p>For local development, run <code>npm run dev:emulators</code> from <code>web/</code>.</p>
    </GateFrame>
  );
}

export function SignInScreen({ onSignIn, error, usingEmulators }: { onSignIn: () => Promise<void>; error?: string; usingEmulators: boolean }) {
  const [busy, setBusy] = useState(false);
  return (
    <GateFrame eyebrow="PRIVATE WORKSPACE" title="Sign in to your budget">
      <p>Google sign-in gives access to your encrypted workspace. A separate passphrase unlocks it in this browser.</p>
      {error && (
        <p className="dk-form-error" role="alert">
          {error}
        </p>
      )}
      <button
        type="button"
        className="dk-button dk-primary dk-wide"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await onSignIn();
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Waiting for Google…" : "Sign in with Google"}
      </button>
      {usingEmulators && <p className="dk-hint">Development mode: sign-in and storage use local Firebase emulators.</p>}
    </GateFrame>
  );
}

function PassphraseField({ label, value, onChange, autoComplete, error, describedBy, autoFocus }: { label: string; value: string; onChange: (value: string) => void; autoComplete: string; error?: string; describedBy?: string; autoFocus?: boolean }) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <label className="dk-field" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        type="password"
        value={value}
        autoComplete={autoComplete}
        spellCheck={false}
        autoFocus={autoFocus}
        aria-invalid={error ? true : undefined}
        aria-describedby={[describedBy, error ? errorId : undefined].filter(Boolean).join(" ") || undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error && (
        <span className="dk-field-error" id={errorId}>
          {error}
        </span>
      )}
    </label>
  );
}

export function OnboardingScreen({ operator, onCreate, onSignOut }: { operator: Operator; onCreate: (passphrase: string) => Promise<void>; onSignOut: () => void }) {
  const hintId = useId();
  const [passphrase, setPassphrase] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<{ passphrase?: string; confirmation?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validatePassphrase(passphrase);
    const mismatch = passphrase !== confirmation ? "The passphrases do not match." : undefined;
    if (problem || mismatch) {
      setErrors({ passphrase: problem ?? undefined, confirmation: problem ? undefined : mismatch });
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      await onCreate(passphrase);
    } catch (error) {
      setErrors({ form: describeError(error) });
      setBusy(false);
    }
  };

  return (
    <GateFrame eyebrow="FIRST USE" title="Protect your workspace" footer={<SignedInAs operator={operator} onSignOut={onSignOut} />}>
      <p>Choose an unlock passphrase. Your financial data is encrypted in this browser with a key only this passphrase can open; Google never receives it.</p>
      <form className="dk-form" onSubmit={submit} noValidate>
        <PassphraseField label="Unlock passphrase" value={passphrase} onChange={setPassphrase} autoComplete="new-password" error={errors.passphrase} describedBy={hintId} autoFocus />
        <p className="dk-hint" id={hintId}>
          At least {MIN_PASSPHRASE_LENGTH} characters. A few unrelated words work well. Store it in your password manager.
        </p>
        <PassphraseField label="Repeat passphrase" value={confirmation} onChange={setConfirmation} autoComplete="new-password" error={errors.confirmation} />
        <div className="dk-callout" role="note">
          <Icon name="lock" />
          <p>
            An offline recovery key is not available yet. Until it is, losing this passphrase means re-entering your accounts and re-importing statements.
          </p>
        </div>
        {errors.form && (
          <p className="dk-form-error" role="alert">
            {errors.form}
          </p>
        )}
        <button type="submit" className="dk-button dk-primary dk-wide" disabled={busy}>
          {busy ? "Creating encrypted workspace…" : "Create encrypted workspace"}
        </button>
      </form>
    </GateFrame>
  );
}

export function UnlockScreen({ operator, reason, onUnlock, onSignOut }: { operator: Operator; reason?: LockReason; onUnlock: (passphrase: string) => Promise<void>; onSignOut: () => void }) {
  const [passphrase, setPassphrase] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!passphrase) {
      setError("Enter your unlock passphrase.");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      await onUnlock(passphrase);
    } catch (caught) {
      setError(caught instanceof WrongCredentialError ? caught.message : describeError(caught));
      setBusy(false);
    }
  };

  const notice = reason === "idle" ? "Locked after 15 minutes without activity." : reason === "manual" ? "Workspace locked." : undefined;
  return (
    <GateFrame eyebrow="ENCRYPTED WORKSPACE" title="Unlock your workspace" footer={<SignedInAs operator={operator} onSignOut={onSignOut} />}>
      {notice && (
        <p className="dk-notice" role="status">
          {notice}
        </p>
      )}
      <p>Enter your unlock passphrase. Decryption happens only in this browser.</p>
      <form className="dk-form" onSubmit={submit} noValidate>
        <PassphraseField label="Unlock passphrase" value={passphrase} onChange={setPassphrase} autoComplete="current-password" error={error} autoFocus />
        <button type="submit" className="dk-button dk-primary dk-wide" disabled={busy}>
          {busy ? "Unlocking…" : "Unlock"}
        </button>
      </form>
    </GateFrame>
  );
}

export function FailedScreen({ operator, message, onRetry, onSignOut }: { operator: Operator; message: string; onRetry: () => void; onSignOut: () => void }) {
  return (
    <GateFrame eyebrow="WORKSPACE UNAVAILABLE" title="Could not open your workspace" footer={<SignedInAs operator={operator} onSignOut={onSignOut} />}>
      <p className="dk-form-error" role="alert">
        {message}
      </p>
      <button type="button" className="dk-button dk-primary dk-wide" onClick={onRetry}>
        Try again
      </button>
    </GateFrame>
  );
}
