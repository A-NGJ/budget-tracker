import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { COMMON_CURRENCIES, INITIAL_BANKS, validateDraft, type Account, type AccountDraft, type AccountErrors } from "../workspace/accounts";
import { FORMAT_VERSION } from "../workspace/crypto/vault";
import { INACTIVITY_LOCK_MS } from "../workspace/inactivity";
import type { Classification, DecisionRecord, MerchantChoice } from "../workspace/classification/decisions";
import { isUncategorized } from "../workspace/classification/decisions";
import type { ImportItem, StatementImport, Transaction } from "../workspace/import/statements";
import { describeError, type Operator } from "../workspace/session";
import { Brand } from "./Brand";
import { ImportDialog } from "./ImportDialog";
import { Inbox } from "./Inbox";
import { Ledger } from "./Ledger";
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
  statements: StatementImport[];
  transactions: Transaction[];
  decisions: ReadonlyMap<string, DecisionRecord>;
  merchantChoices: MerchantChoice[];
  usingEmulators: boolean;
  onAddAccount: (draft: AccountDraft) => Promise<Account>;
  onImport: (items: ImportItem[]) => Promise<StatementImport[]>;
  onLoadOriginal: (statementId: string) => Promise<Uint8Array>;
  onDeleteOriginal: (statementId: string) => Promise<void>;
  onClassify: (transactionId: string, classification: Classification, options?: { remember?: boolean }) => Promise<{ merchantChoice?: MerchantChoice }>;
  onApplyToSimilar: (merchantChoiceId: string) => Promise<number>;
  onUndo: (transactionId: string) => Promise<void>;
  onLock: () => void;
  onSignOut: () => void;
}

type Dialog = "import" | "settings" | "add-account" | { deleteOriginal: StatementImport } | null;

export function Desk({
  operator,
  accounts,
  statements,
  transactions,
  decisions,
  merchantChoices,
  usingEmulators,
  onAddAccount,
  onImport,
  onLoadOriginal,
  onDeleteOriginal,
  onClassify,
  onApplyToSimilar,
  onUndo,
  onLock,
  onSignOut,
}: DeskProps) {
  const [view, setView] = useState<View>(viewFromHash);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState("");
  const mainRef = useRef<HTMLElement>(null);

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
  const inboxCount = transactions.filter((transaction) => isUncategorized(decisions.get(transaction.id))).length;

  return (
    <div className="dk-desk">
      {/* Routing uses the URL hash, so the skip link must not change it: it
          moves focus to the main region and leaves the destination as is. */}
      <a
        className="dk-skip-link"
        href="#dk-main"
        onClick={(event) => {
          event.preventDefault();
          mainRef.current?.focus();
        }}
      >
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
              {item === "inbox" && inboxCount > 0 && (
                <span className="dk-nav-count">
                  {inboxCount}
                  <span className="dk-visually-hidden"> to review</span>
                </span>
              )}
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
        <main className="dk-page" id="dk-main" tabIndex={-1} ref={mainRef}>
          {view === "overview" && (
            <Overview accounts={accounts} statements={statements} onAddAccount={() => setDialog("add-account")} onImport={() => setDialog("import")} />
          )}
          {view === "transactions" &&
            (transactions.length ? (
              <Ledger
                accounts={accounts}
                statements={statements}
                transactions={transactions}
                decisions={decisions}
                onClassify={onClassify}
                onUndo={onUndo}
                onNotice={setNotice}
                onDownload={async (statement) => {
                  try {
                    download(statement.original.fileName, statement.original.mediaType, await onLoadOriginal(statement.id));
                  } catch (error) {
                    setNotice(`Could not open the original: ${describeError(error)}`);
                  }
                }}
                onDelete={(statement) => setDialog({ deleteOriginal: statement })}
              />
            ) : (
              <EmptyPage title="Every movement, in context" subtitle="Transactions from imported statements will appear here." icon="transactions" heading="No transactions yet" onImport={() => setDialog("import")}>
                Import a bank statement to see its transactions. Transfers and contributions will stay visible without inflating spending.
              </EmptyPage>
            ))}
          {view === "inbox" &&
            (transactions.length ? (
              <>
                <PageTitle title="Review inbox" subtitle={`${inboxCount} ${inboxCount === 1 ? "decision" : "decisions"} waiting · each item is assigned on its own`} />
                <Inbox
                  accounts={accounts}
                  transactions={transactions}
                  decisions={decisions}
                  merchantChoices={merchantChoices}
                  onClassify={onClassify}
                  onApplyToSimilar={onApplyToSimilar}
                  onUndo={onUndo}
                />
              </>
            ) : (
              <EmptyPage title="Review inbox" subtitle="Uncategorized transactions, transfer matches and recurring-cost suggestions." icon="inbox" heading="Nothing to review">
                Decisions appear here once imported transactions need a category, a transfer confirmation or a recurring-cost decision.
              </EmptyPage>
            ))}
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
      {dialog === "import" && (
        <ImportDialog
          accounts={accounts}
          onClose={() => setDialog(null)}
          onConfirm={async (items) => {
            const saved = await onImport(items);
            const count = saved.reduce((total, statement) => total + statement.recordCount, 0);
            setDialog(null);
            setNotice(`Imported ${count} ${count === 1 ? "transaction" : "transactions"} from ${saved.length === 1 ? "1 statement" : `${saved.length} statements`} · encrypted before upload.`);
            go("transactions");
            return saved;
          }}
        />
      )}
      {dialog && typeof dialog === "object" && (
        <DeleteOriginalDialog
          statement={dialog.deleteOriginal}
          onClose={() => setDialog(null)}
          onConfirm={async () => {
            await onDeleteOriginal(dialog.deleteOriginal.id);
            setDialog(null);
            setNotice(`Deleted the original ${dialog.deleteOriginal.original.fileName}. Its transactions remain.`);
          }}
        />
      )}
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

function Overview({ accounts, statements, onAddAccount, onImport }: { accounts: Account[]; statements: StatementImport[]; onAddAccount: () => void; onImport: () => void }) {
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
        <span className="dk-status-dot" aria-hidden="true" /> Statement coverage:{" "}
        {statements.length ? `${statements.length} ${statements.length === 1 ? "statement" : "statements"} imported` : "no statements imported"}
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

/** Hand a decrypted original back to the operator as a local file; nothing is uploaded. */
function download(fileName: string, mediaType: string, bytes: Uint8Array) {
  const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: mediaType }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function DeleteOriginalDialog({ statement, onClose, onConfirm }: { statement: StatementImport; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <Modal eyebrow="RETAINED ORIGINAL" title="Delete the original file?" onClose={() => !busy && onClose()}>
      <p className="dk-muted">
        This permanently deletes the stored copy of <strong>{statement.original.fileName}</strong>. Its {statement.recordCount}{" "}
        {statement.recordCount === 1 ? "transaction stays" : "transactions stay"} in your history with their import provenance.
      </p>
      {error && (
        <p className="dk-form-error" role="alert">
          {error}
        </p>
      )}
      <div className="dk-dialog-actions">
        <button type="button" className="dk-button" onClick={onClose} disabled={busy} data-autofocus>
          Keep original
        </button>
        <button
          type="button"
          className="dk-button dk-danger"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError(undefined);
            try {
              await onConfirm();
            } catch (failure) {
              setError(describeError(failure));
              setBusy(false);
            }
          }}
        >
          {busy ? "Deleting…" : "Delete original"}
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
