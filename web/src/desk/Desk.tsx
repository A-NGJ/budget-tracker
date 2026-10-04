import { useEffect, useId, useState, type FormEvent, type ReactNode } from "react";
import { COMMON_CURRENCIES, INITIAL_BANKS, validateDraft, type Account, type AccountDraft, type AccountErrors } from "../workspace/accounts";
import { FORMAT_VERSION } from "../workspace/crypto/vault";
import { INACTIVITY_LOCK_MS } from "../workspace/inactivity";
import { describeError, type Operator } from "../workspace/session";
import { Brand } from "./Brand";
import { Icon, type IconName } from "./Icon";
import { Modal } from "./Modal";

export type View = "overview" | "transactions" | "inbox" | "recurring";
const views: View[] = ["overview", "transactions", "inbox", "recurring"];
const labels: Record<View, string> = { overview: "Overview", transactions: "Transactions", inbox: "Inbox", recurring: "Recurring" };

function viewFromHash(): View {
  const value = window.location.hash.replace(/^#\/?/, "");
  return views.includes(value as View) ? (value as View) : "overview";
}

interface DeskProps {
  operator: Operator;
  accounts: Account[];
  usingEmulators: boolean;
  onAddAccount: (draft: AccountDraft) => Promise<Account>;
  onLock: () => void;
  onSignOut: () => void;
}

type Dialog = "import" | "settings" | "add-account" | null;

export function Desk({ operator, accounts, usingEmulators, onAddAccount, onLock, onSignOut }: DeskProps) {
  const [view, setView] = useState<View>(viewFromHash);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (next: View) => {
    if (next !== view) window.location.hash = `/${next}`;
    setView(next);
  };

  const initial = (operator.displayName ?? operator.email ?? "?").slice(0, 1).toUpperCase();

  return (
    <div className="dk-desk">
      <a className="dk-skip-link" href="#dk-main">
        Skip to content
      </a>
      <aside className="dk-sidebar">
        <Brand />
        <div className="dk-workspace">
          <span className="dk-avatar" aria-hidden="true">
            {initial}
          </span>
          <div>
            Personal workspace
            <small>{operator.email ?? "Private spending analysis"}</small>
          </div>
        </div>
        <nav aria-label="Main navigation" className="dk-navigation">
          {views.map((item) => (
            <button type="button" key={item} aria-current={view === item ? "page" : undefined} onClick={() => go(item)}>
              <Icon name={item} />
              <span>{labels[item]}</span>
            </button>
          ))}
        </nav>
        <div className="dk-sidebar-bottom">
          <span className="dk-secure">
            <Icon name="lock" /> Unlocked in this browser
          </span>
          <button type="button" className="dk-text-button" onClick={onLock}>
            <Icon name="lock" />
            Lock workspace
          </button>
          <button type="button" className="dk-text-button" onClick={() => setDialog("settings")}>
            <Icon name="settings" />
            Settings
          </button>
        </div>
      </aside>
      <div className="dk-desk-main">
        <header className="dk-topbar">
          <div className="dk-breadcrumb">
            Workspace <span aria-hidden="true">/</span> {labels[view]}
          </div>
          <div className="dk-toolbar">
            <button type="button" className="dk-button dk-primary" onClick={() => setDialog("import")}>
              <Icon name="plus" />
              Import statements
            </button>
          </div>
        </header>
        <main className="dk-page" id="dk-main" tabIndex={-1}>
          {view === "overview" && <Overview accounts={accounts} onAddAccount={() => setDialog("add-account")} onImport={() => setDialog("import")} />}
          {view === "transactions" && (
            <EmptyPage title="Every movement, in context" subtitle="Transactions from imported statements will appear here." icon="transactions" heading="No transactions yet" onImport={() => setDialog("import")}>
              Import a bank statement to see its transactions. Transfers and contributions will stay visible without inflating spending.
            </EmptyPage>
          )}
          {view === "inbox" && (
            <EmptyPage title="Review inbox" subtitle="Uncategorized transactions, transfer matches and recurring-cost suggestions." icon="inbox" heading="Nothing to review">
              Decisions appear here once imported transactions need a category, a transfer confirmation or a recurring-cost decision.
            </EmptyPage>
          )}
          {view === "recurring" && (
            <EmptyPage title="Know what's coming" subtitle="Confirmed commitments, not every purchase that happens more than once." icon="recurring" heading="No recurring costs yet">
              Recurring costs you confirm will appear here with their cadence, expected amount and next payment date.
            </EmptyPage>
          )}
        </main>
      </div>
      {notice && (
        <div className="dk-toast" role="status">
          {notice}
          <button type="button" aria-label="Dismiss message" onClick={() => setNotice("")}>
            <Icon name="close" />
          </button>
        </div>
      )}
      {dialog === "import" && <ImportUnavailable onClose={() => setDialog(null)} />}
      {dialog === "settings" && (
        <SettingsDialog
          operator={operator}
          usingEmulators={usingEmulators}
          onClose={() => setDialog(null)}
          onLock={onLock}
          onSignOut={onSignOut}
        />
      )}
      {dialog === "add-account" && (
        <AddAccountDialog
          accounts={accounts}
          onClose={() => setDialog(null)}
          onSubmit={async (draft) => {
            const account = await onAddAccount(draft);
            setDialog(null);
            setNotice(`Saved ${account.name} · encrypted before upload.`);
          }}
        />
      )}
    </div>
  );
}

function PageTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="dk-page-title">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

function EmptyMetric({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="dk-metric">
      <span>{label}</span>
      <strong aria-label="No data">—</strong>
      <p>{detail}</p>
    </div>
  );
}

function Overview({ accounts, onAddAccount, onImport }: { accounts: Account[]; onAddAccount: () => void; onImport: () => void }) {
  const count = accounts.length;
  return (
    <>
      <PageTitle title="Your month, at a glance" subtitle={`${count} ${count === 1 ? "account" : "accounts"} · Reporting currency DKK`} />
      <div className="dk-metrics">
        <EmptyMetric label="Total spending" detail="Available after your first statement import" />
        <EmptyMetric label="Recurring · next 30 days" detail="Available after you confirm recurring costs" />
        <EmptyMetric label="Income minus spending" detail="Available after your first statement import" />
      </div>
      <div className="dk-dashboard-grid">
        <section className="dk-panel" aria-labelledby="dk-accounts-heading">
          <div className="dk-section-heading">
            <h2 id="dk-accounts-heading">Accounts</h2>
            <button type="button" className="dk-button" onClick={onAddAccount}>
              <Icon name="plus" />
              Add account
            </button>
          </div>
          {count === 0 ? (
            <div className="dk-empty">
              <p>
                <strong>No accounts yet.</strong> Add each bank account or currency balance you track separately, such as a Revolut EUR balance.
              </p>
            </div>
          ) : (
            <ul className="dk-account-list" aria-label="Accounts">
              {accounts.map((account) => (
                <li key={account.id}>
                  <span className="dk-merchant-icon" aria-hidden="true">
                    {account.bank.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="dk-account-name">
                    <strong>{account.name}</strong>
                    <small>{account.bank}</small>
                  </span>
                  <span className="dk-tag">{account.currency}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <div className="dk-dashboard-right">
          <section className="dk-panel" aria-labelledby="dk-categories-heading">
            <div className="dk-section-heading">
              <h2 id="dk-categories-heading">Spending by category</h2>
              <span>Net of refunds</span>
            </div>
            <div className="dk-empty">
              <p>No spending recorded yet.</p>
              <button type="button" className="dk-text-button" onClick={onImport}>
                Import statements <Icon name="arrow" />
              </button>
            </div>
          </section>
          <section className="dk-panel" aria-labelledby="dk-upcoming-heading">
            <div className="dk-section-heading">
              <h2 id="dk-upcoming-heading">Coming up</h2>
            </div>
            <div className="dk-empty">
              <p>No confirmed recurring costs.</p>
            </div>
          </section>
        </div>
      </div>
      <p className="dk-coverage">
        <span className="dk-status-dot" aria-hidden="true" /> Statement coverage: no statements imported
      </p>
    </>
  );
}

function EmptyPage({ title, subtitle, icon, heading, children, onImport }: { title: string; subtitle: string; icon: IconName; heading: string; children: ReactNode; onImport?: () => void }) {
  return (
    <>
      <PageTitle title={title} subtitle={subtitle} />
      <section className="dk-panel dk-empty-page" aria-labelledby="dk-empty-heading">
        <span className="dk-empty-icon" aria-hidden="true">
          <Icon name={icon} />
        </span>
        <h2 id="dk-empty-heading">{heading}</h2>
        <p>{children}</p>
        {onImport && (
          <button type="button" className="dk-button" onClick={onImport}>
            <Icon name="plus" />
            Import statements
          </button>
        )}
      </section>
    </>
  );
}

function ImportUnavailable({ onClose }: { onClose: () => void }) {
  return (
    <Modal eyebrow="IMPORT STATEMENTS" title="Statement import is coming next" onClose={onClose}>
      <div className="dk-dropzone">
        <span className="dk-upload-symbol" aria-hidden="true">
          <Icon name="upload" />
        </span>
        <p>
          Importing Danske Bank, mBank and Revolut statements is not available in this version. When it arrives, files are parsed and encrypted in this browser
          before anything is stored.
        </p>
      </div>
      <div className="dk-dialog-actions">
        <button type="button" className="dk-button dk-primary" onClick={onClose} data-autofocus>
          Close
        </button>
      </div>
    </Modal>
  );
}

function SettingsDialog({ operator, usingEmulators, onClose, onLock, onSignOut }: { operator: Operator; usingEmulators: boolean; onClose: () => void; onLock: () => void; onSignOut: () => void }) {
  return (
    <Modal title="Workspace settings" onClose={onClose}>
      <dl className="dk-settings-list">
        <dt>Google account</dt>
        <dd>{operator.email ?? operator.displayName ?? operator.uid}</dd>
        <dt>Reporting currency</dt>
        <dd>DKK</dd>
        <dt>Encryption</dt>
        <dd>AES-256-GCM in this browser · format version {FORMAT_VERSION}</dd>
        <dt>Inactivity lock</dt>
        <dd>After {INACTIVITY_LOCK_MS / 60000} minutes without activity</dd>
        <dt>Recovery key and passphrase change</dt>
        <dd>Not available yet</dd>
        {usingEmulators && (
          <>
            <dt>Storage</dt>
            <dd>Local Firebase emulators (development)</dd>
          </>
        )}
      </dl>
      <div className="dk-dialog-actions">
        <button type="button" className="dk-button" onClick={onLock}>
          <Icon name="lock" />
          Lock now
        </button>
        <button type="button" className="dk-button" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </Modal>
  );
}

function AddAccountDialog({ accounts, onClose, onSubmit }: { accounts: Account[]; onClose: () => void; onSubmit: (draft: AccountDraft) => Promise<void> }) {
  const ids = { name: useId(), bank: useId(), currency: useId(), banks: useId(), currencies: useId() };
  const [draft, setDraft] = useState<AccountDraft>({ name: "", bank: "", currency: "DKK" });
  const [errors, setErrors] = useState<AccountErrors>({});
  const [formError, setFormError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateDraft(draft, accounts);
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    setFormError(undefined);
    try {
      await onSubmit(draft);
    } catch (error) {
      setFormError(describeError(error));
      setBusy(false);
    }
  };

  const field = (key: keyof AccountDraft, label: string, extra: { list?: string; placeholder?: string; maxLength?: number; focusFirst?: boolean }) => (
    <label className="dk-field" htmlFor={ids[key]}>
      <span>{label}</span>
      <input
        id={ids[key]}
        value={draft[key]}
        autoComplete="off"
        data-autofocus={extra.focusFirst ? "" : undefined}
        aria-invalid={errors[key] ? true : undefined}
        aria-describedby={errors[key] ? `${ids[key]}-error` : undefined}
        onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
        list={extra.list}
        placeholder={extra.placeholder}
        maxLength={extra.maxLength}
      />
      {errors[key] && (
        <span className="dk-field-error" id={`${ids[key]}-error`}>
          {errors[key]}
        </span>
      )}
    </label>
  );

  return (
    <Modal eyebrow="NEW ACCOUNT" title="Add an account" onClose={onClose}>
      <p className="dk-muted">Track each bank account or currency balance separately. Several accounts can belong to one bank.</p>
      <form className="dk-form" onSubmit={submit} noValidate>
        {field("name", "Account name", { placeholder: "Everyday", focusFirst: true, maxLength: 80 })}
        <div className="dk-form-grid">
          {field("bank", "Bank", { list: ids.banks, placeholder: "Danske Bank", maxLength: 80 })}
          {field("currency", "Currency", { list: ids.currencies, placeholder: "DKK", maxLength: 3 })}
        </div>
        <datalist id={ids.banks}>
          {INITIAL_BANKS.map((bank) => (
            <option key={bank} value={bank} />
          ))}
        </datalist>
        <datalist id={ids.currencies}>
          {COMMON_CURRENCIES.map((currency) => (
            <option key={currency} value={currency} />
          ))}
        </datalist>
        {formError && (
          <p className="dk-form-error" role="alert">
            {formError}
          </p>
        )}
        <div className="dk-dialog-actions">
          <button type="button" className="dk-button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="dk-button dk-primary" disabled={busy}>
            {busy ? "Encrypting and saving…" : "Save account"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
