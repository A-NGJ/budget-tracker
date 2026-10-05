import { useId, useMemo, useState } from "react";
import type { Account } from "../workspace/accounts";
import { CATEGORIES, TRANSACTION_TYPES, TYPE_NAMES, type CategoryId, type TransactionType } from "../workspace/classification/categories";
import { canUndo, type Classification, type DecisionRecord } from "../workspace/classification/decisions";
import { merchantLabel } from "../workspace/classification/merchant";
import type { StatementImport, Transaction } from "../workspace/import/statements";
import { describeError } from "../workspace/session";
import { ClassificationFields, DecisionCells, classificationOf, describeClassification, draftOf, type ClassificationDraft } from "./Classification";
import { formatBytes, formatDate, formatMoney, formatPeriod } from "./format";
import { Modal } from "./Modal";

type KindFilter = "" | "uncategorized" | `category:${CategoryId}` | `type:${TransactionType}`;

interface LedgerProps {
  accounts: Account[];
  statements: StatementImport[];
  transactions: Transaction[];
  decisions: ReadonlyMap<string, DecisionRecord>;
  onClassify: (transactionId: string, classification: Classification, options?: { remember?: boolean }) => Promise<unknown>;
  onUndo: (transactionId: string) => Promise<void>;
  onDownload: (statement: StatementImport) => void;
  onDelete: (statement: StatementImport) => void;
  onNotice: (message: string) => void;
}

function matchesKind(filter: KindFilter, record: DecisionRecord | undefined): boolean {
  if (!filter) return true;
  const classification = record?.current?.classification;
  if (filter === "uncategorized") return !classification;
  if (!classification) return false;
  if (filter.startsWith("type:")) return classification.type === filter.slice(5);
  return "category" in classification && classification.category === filter.slice(9);
}

/** Search, filter and edit every imported transaction. All matching runs on the unlocked history in this browser. */
export function Ledger({ accounts, statements, transactions, decisions, onClassify, onUndo, onDownload, onDelete, onNotice }: LedgerProps) {
  const ids = { search: useId(), account: useId(), kind: useId() };
  const accountName = useMemo(() => new Map(accounts.map((account) => [account.id, `${account.name} · ${account.bank}`])), [accounts]);
  const [query, setQuery] = useState("");
  const [accountId, setAccountId] = useState("");
  const [kind, setKind] = useState<KindFilter>("");
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [undoing, setUndoing] = useState<string | null>(null);

  const needle = query.trim().toLocaleLowerCase("da");
  const shown = transactions.filter((transaction) => {
    if (accountId && transaction.accountId !== accountId) return false;
    if (!matchesKind(kind, decisions.get(transaction.id))) return false;
    if (!needle) return true;
    const haystack = [transaction.bank.description, merchantLabel(transaction.bank.description)?.name ?? "", accountName.get(transaction.accountId) ?? "", transaction.bank.amount]
      .join(" ")
      .toLocaleLowerCase("da");
    return haystack.includes(needle);
  });
  const filtered = Boolean(needle || accountId || kind);
  const count = transactions.length;

  return (
    <>
      <div className="dk-page-title">
        <div>
          <h1>Every movement, in context</h1>
          <p>
            {count} {count === 1 ? "transaction" : "transactions"} from {statements.length} imported {statements.length === 1 ? "statement" : "statements"}
          </p>
        </div>
      </div>
      <section className="dk-panel dk-table-panel" aria-labelledby="dk-ledger-heading">
        <div className="dk-section-heading">
          <h2 id="dk-ledger-heading">Transactions</h2>
          <span>Income, transfers and contributions are types, not spending categories</span>
        </div>
        <form className="dk-filters" role="search" aria-label="Filter transactions" onSubmit={(event) => event.preventDefault()}>
          <div className="dk-field">
            <label htmlFor={ids.search}>Search</label>
            <input id={ids.search} type="search" value={query} placeholder="Description, merchant or amount" onChange={(event) => setQuery(event.target.value)} />
          </div>
          <div className="dk-field">
            <label htmlFor={ids.account}>Account</label>
            <select id={ids.account} value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">All accounts</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name} · {account.bank}
                </option>
              ))}
            </select>
          </div>
          <div className="dk-field">
            <label htmlFor={ids.kind}>Category or type</label>
            <select id={ids.kind} value={kind} onChange={(event) => setKind(event.target.value as KindFilter)}>
              <option value="">All</option>
              <option value="uncategorized">Uncategorized</option>
              <optgroup label="Spending categories">
                {CATEGORIES.map((category) => (
                  <option key={category.id} value={`category:${category.id}`}>
                    {category.name}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Types">
                {TRANSACTION_TYPES.map((type) => (
                  <option key={type} value={`type:${type}`}>
                    {TYPE_NAMES[type]}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
          {filtered && (
            <button
              type="button"
              className="dk-text-button"
              onClick={() => {
                setQuery("");
                setAccountId("");
                setKind("");
              }}
            >
              Clear filters
            </button>
          )}
        </form>
        <p className="dk-filter-summary" aria-live="polite">
          {filtered ? `${shown.length} of ${count} ${count === 1 ? "transaction" : "transactions"} match` : `Showing all ${count}`}
        </p>
        <div className="dk-table-scroll">
          <table className="dk-table" aria-labelledby="dk-ledger-heading">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Description</th>
                <th scope="col">Account</th>
                <th scope="col">Type</th>
                <th scope="col">Category</th>
                <th scope="col" className="dk-number">
                  Amount
                </th>
                <th scope="col">
                  <span className="dk-visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((transaction) => {
                const record = decisions.get(transaction.id);
                return (
                  <tr key={transaction.id}>
                    <td>{formatDate(transaction.bank.date)}</td>
                    <td>{transaction.bank.description}</td>
                    <td>{accountName.get(transaction.accountId) ?? "Unknown account"}</td>
                    <DecisionCells record={record} />
                    <td className="dk-number">{formatMoney(transaction.bank.amount, transaction.bank.currency)}</td>
                    <td>
                      <div className="dk-row-actions">
                      <button type="button" className="dk-text-button" aria-label={`Edit ${transaction.bank.description}`} onClick={() => setEditing(transaction)}>
                        Edit
                      </button>
                      {canUndo(record) && (
                        <button
                          type="button"
                          className="dk-text-button"
                          aria-label={`Undo edit of ${transaction.bank.description}`}
                          disabled={undoing === transaction.id}
                          onClick={async () => {
                            setUndoing(transaction.id);
                            try {
                              await onUndo(transaction.id);
                              onNotice(`Undid the last edit of ${transaction.bank.description}.`);
                            } catch (error) {
                              onNotice(`Could not undo: ${describeError(error)}`);
                            } finally {
                              setUndoing(null);
                            }
                          }}
                        >
                          Undo
                        </button>
                      )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {shown.length === 0 && <p className="dk-empty dk-table-empty">No transactions match these filters.</p>}
        </div>
      </section>
      <section className="dk-panel dk-statements" aria-labelledby="dk-statements-heading">
        <div className="dk-section-heading">
          <h2 id="dk-statements-heading">Imported statements</h2>
          <span>Originals are kept encrypted until you delete them</span>
        </div>
        <ul className="dk-statement-list" aria-labelledby="dk-statements-heading">
          {statements.map((statement) => (
            <li key={statement.id}>
              <span className="dk-account-name">
                <strong>{statement.original.fileName}</strong>
                <small>
                  {accountName.get(statement.accountId) ?? "Unknown account"} · {statement.recordCount} {statement.recordCount === 1 ? "transaction" : "transactions"} ·{" "}
                  {formatPeriod(statement.period)}
                </small>
              </span>
              {statement.original.deletedAt ? (
                <span className="dk-tag">Original deleted</span>
              ) : (
                <>
                  <span className="dk-muted dk-statement-size">{formatBytes(statement.original.byteLength)}</span>
                  <button type="button" className="dk-text-button" onClick={() => onDownload(statement)} aria-label={`Download original ${statement.original.fileName}`}>
                    Download original
                  </button>
                  <button type="button" className="dk-text-button dk-danger-text" onClick={() => onDelete(statement)} aria-label={`Delete original ${statement.original.fileName}`}>
                    Delete original
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </section>
      {editing && (
        <EditDialog
          transaction={editing}
          account={accountName.get(editing.accountId) ?? "Unknown account"}
          record={decisions.get(editing.id)}
          onClose={() => setEditing(null)}
          onSave={async (classification, remember) => {
            await onClassify(editing.id, classification, { remember });
            setEditing(null);
            onNotice(`Saved ${describeClassification(classification)} for ${editing.bank.description} · encrypted before upload.`);
          }}
        />
      )}
    </>
  );
}

function EditDialog({
  transaction,
  account,
  record,
  onClose,
  onSave,
}: {
  transaction: Transaction;
  account: string;
  record: DecisionRecord | undefined;
  onClose: () => void;
  onSave: (classification: Classification, remember: boolean) => Promise<void>;
}) {
  const rememberId = useId();
  const current = record?.current ?? null;
  const [draft, setDraft] = useState<ClassificationDraft>(draftOf(current?.classification));
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const merchant = merchantLabel(transaction.bank.description);
  const classification = classificationOf(draft);
  const { bank, provenance } = transaction;

  return (
    <Modal eyebrow="CATEGORY AND TYPE" title="Edit transaction" onClose={() => !busy && onClose()}>
      <section aria-label="Original bank record" className="dk-original-record">
        <h3>Original bank record</h3>
        <p className="dk-hint-inline">Kept exactly as imported. Your decision is stored separately.</p>
        <dl className="dk-settings-list">
          <dt>Description</dt>
          <dd>{bank.description || "No description"}</dd>
          <dt>Date</dt>
          <dd>{formatDate(bank.date)}</dd>
          <dt>Amount</dt>
          <dd>{formatMoney(bank.amount, bank.currency)}</dd>
          <dt>Account</dt>
          <dd>{account}</dd>
          {(bank.details.bankCategory || bank.details.bankSubcategory) && (
            <>
              <dt>Bank's own label</dt>
              <dd>{[bank.details.bankCategory?.trim(), bank.details.bankSubcategory?.trim()].filter(Boolean).join(" · ")}</dd>
            </>
          )}
          <dt>Statement entry</dt>
          <dd>Row {provenance.row}, line {provenance.line}</dd>
        </dl>
      </section>
      <p className="dk-muted">
        Currently: <strong>{current ? describeClassification(current.classification) : "Uncategorized"}</strong>
        {current?.source === "remembered" && " · applied from a remembered choice"}
      </p>
      <form
        className="dk-form"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!classification) return;
          setBusy(true);
          setError(undefined);
          try {
            await onSave(classification, remember && merchant !== null);
          } catch (failure) {
            setError(describeError(failure));
            setBusy(false);
          }
        }}
      >
        <ClassificationFields draft={draft} onChange={setDraft} />
        {merchant && (
          <label className="dk-check" htmlFor={rememberId}>
            <input id={rememberId} type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
            <span>Remember for {merchant.name} on later imports</span>
          </label>
        )}
        {error && (
          <p className="dk-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dk-dialog-actions">
          <button type="button" className="dk-button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="dk-button dk-primary" disabled={busy || !classification}>
            {busy ? "Encrypting and saving…" : "Save"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
