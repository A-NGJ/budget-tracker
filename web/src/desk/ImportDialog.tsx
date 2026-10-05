import { useId, useRef, useState, type FormEvent } from "react";
import { INITIAL_BANKS, COMMON_CURRENCIES, newAccount, validateDraft, type Account, type AccountDraft, type AccountErrors } from "../workspace/accounts";
import { UnreadableStatementError } from "../workspace/import/csv";
import { InvalidRowsError, UnsupportedStatementError, detectProfiles, parseStatement, type ParsedStatement } from "../workspace/import/parse";
import { STATEMENT_PROFILES } from "../workspace/import/profiles";
import { accountForIdentifiers, accountIdentityProblem, type ImportItem, type StatementImport } from "../workspace/import/statements";
import { describeError } from "../workspace/session";
import { formatBytes, formatDate, formatMoney, formatPeriod } from "./format";
import { Icon } from "./Icon";
import { Modal } from "./Modal";

const PREVIEW_ROWS = 8;
const NEW_ACCOUNT = "__new__";

/** One opened file. Its bytes and parsed records exist only in this dialog's memory. */
type OpenedFile =
  | { key: string; name: string; status: "ready"; type: string; bytes: Uint8Array; parsed: ParsedStatement; accountId: string }
  | { key: string; name: string; status: "rejected"; reason: string; details?: string[] };

async function openFile(file: File): Promise<OpenedFile> {
  const key = crypto.randomUUID();
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.byteLength === 0) throw new UnreadableStatementError("The file is empty.");
    const [profile] = detectProfiles(bytes);
    if (!profile) {
      throw new UnsupportedStatementError(`This file is not in a supported statement format. Supported: ${STATEMENT_PROFILES.map((item) => item.name).join(", ")}.`);
    }
    const parsed = parseStatement(bytes, profile);
    return { key, name: file.name, status: "ready", type: file.type, bytes, parsed, accountId: "" };
  } catch (error) {
    if (error instanceof InvalidRowsError) {
      return { key, name: file.name, status: "rejected", reason: `${error.problems.length === 1 ? "1 row" : `${error.problems.length} rows`} could not be read, so nothing from this file will be imported.`, details: error.problems };
    }
    if (error instanceof UnsupportedStatementError || error instanceof UnreadableStatementError) return { key, name: file.name, status: "rejected", reason: error.message };
    return { key, name: file.name, status: "rejected", reason: "The file could not be read." };
  }
}

interface ImportDialogProps {
  accounts: Account[];
  onClose: () => void;
  onConfirm: (items: ImportItem[]) => Promise<StatementImport[]>;
}

/**
 * Choose → preview → confirm. Files are read and parsed in this browser;
 * nothing is stored until the operator confirms, and cancelling discards
 * every opened file.
 */
export function ImportDialog({ accounts, onClose, onConfirm }: ImportDialogProps) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<OpenedFile[]>([]);
  const [pending, setPending] = useState<Account[]>([]);
  const [creatingFor, setCreatingFor] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const choices = [...accounts, ...pending];
  const ready = files.filter((file): file is Extract<OpenedFile, { status: "ready" }> => file.status === "ready");
  const problemFor = (file: Extract<OpenedFile, { status: "ready" }>): string | null => {
    const account = choices.find((item) => item.id === file.accountId);
    if (!account) return null;
    const currencies = [...new Set(file.parsed.records.map((item) => item.record.currency))];
    if (currencies.some((currency) => currency !== account.currency)) {
      return `${account.name} holds ${account.currency}, but this statement is in ${currencies.join(", ")}.`;
    }
    return accountIdentityProblem(choices, account, file.parsed.accountIdentifiers);
  };
  const canConfirm = ready.length > 0 && ready.every((file) => file.accountId && !problemFor(file)) && !saving && !creatingFor;

  const addFiles = async (list: FileList | null) => {
    if (!list?.length) return;
    setReading(true);
    setError(undefined);
    const opened = await Promise.all(Array.from(list, openFile));
    setFiles((current) => [
      ...current,
      ...opened.map((file) => {
        if (file.status !== "ready") return file;
        // Only an identifier the export itself states can propose an account.
        const known = accountForIdentifiers(choices, file.parsed.accountIdentifiers);
        return known ? { ...file, accountId: known.id } : file;
      }),
    ]);
    setReading(false);
    if (input.current) input.current.value = "";
  };

  const setAccount = (key: string, accountId: string) =>
    setFiles((current) => current.map((file) => (file.key === key && file.status === "ready" ? { ...file, accountId } : file)));

  const confirm = async () => {
    setSaving(true);
    setError(undefined);
    try {
      const items: ImportItem[] = ready.map((file) => ({
        parsed: file.parsed,
        file: { name: file.name, type: file.type, bytes: file.bytes },
        account: choices.find((item) => item.id === file.accountId) as Account,
      }));
      await onConfirm(items);
    } catch (failure) {
      setError(describeError(failure));
      setSaving(false);
    }
  };

  const close = () => {
    if (!saving) onClose();
  };
  const rejected = files.length - ready.length;

  return (
    <Modal eyebrow="IMPORT STATEMENTS" title={files.length ? "Check before importing" : "Import bank statements"} onClose={close} wide={files.length > 0}>
      <div className="dk-dropzone">
        <span className="dk-upload-symbol" aria-hidden="true">
          <Icon name="upload" />
        </span>
        <p>Files are read and parsed in this browser. Nothing is saved until you confirm, and everything is encrypted before upload.</p>
        <p className="dk-muted">Supported: {STATEMENT_PROFILES.map((item) => item.name).join(", ")}</p>
        <input
          ref={input}
          id={inputId}
          className="dk-visually-hidden"
          type="file"
          multiple
          accept=".csv,text/csv"
          data-autofocus
          disabled={saving}
          onChange={(event) => void addFiles(event.target.files)}
        />
        {/* The input stays in the tab order; its label is the visible control. */}
        <label htmlFor={inputId} className="dk-button dk-file-button">
          <Icon name="plus" />
          {files.length ? "Add more files" : "Choose statement files"}
        </label>
      </div>
      {reading && (
        <p className="dk-muted" role="status">
          Reading files…
        </p>
      )}
      {files.map((file) =>
        file.status === "ready" ? (
          <ReadyFile
            key={file.key}
            file={file}
            choices={choices}
            problem={problemFor(file)}
            creating={creatingFor === file.key}
            disabled={saving}
            onChoose={(accountId) => {
              if (accountId === NEW_ACCOUNT) setCreatingFor(file.key);
              else {
                setCreatingFor(null);
                setAccount(file.key, accountId);
              }
            }}
            onCreate={(account) => {
              setPending((current) => [...current, account]);
              setAccount(file.key, account.id);
              setCreatingFor(null);
            }}
            onCancelCreate={() => setCreatingFor(null)}
            onRemove={() => setFiles((current) => current.filter((item) => item.key !== file.key))}
          />
        ) : (
          <section key={file.key} className="dk-import-file dk-import-rejected" aria-label={file.name}>
            <div className="dk-import-file-heading">
              <h3>{file.name}</h3>
              <span className="dk-tag dk-tag-danger">Not imported</span>
              <button type="button" className="dk-text-button" disabled={saving} onClick={() => setFiles((current) => current.filter((item) => item.key !== file.key))}>
                Remove
              </button>
            </div>
            <p role="alert">{file.reason}</p>
            {file.details && (
              <ul className="dk-problem-list">
                {file.details.slice(0, 5).map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
                {file.details.length > 5 && <li>…and {file.details.length - 5} more</li>}
              </ul>
            )}
          </section>
        ),
      )}
      {error && (
        <p className="dk-form-error" role="alert">
          {error}
        </p>
      )}
      <div className="dk-dialog-actions">
        {rejected > 0 && ready.length > 0 && <span className="dk-muted dk-actions-note">Files marked "Not imported" are left out.</span>}
        <button type="button" className="dk-button" onClick={close} disabled={saving}>
          Cancel
        </button>
        <button type="button" className="dk-button dk-primary" onClick={() => void confirm()} disabled={!canConfirm}>
          {saving ? "Encrypting and saving…" : `Import ${ready.length === 1 ? "statement" : `${ready.length || ""} statements`.trim()}`}
        </button>
      </div>
    </Modal>
  );
}

function ReadyFile({
  file,
  choices,
  problem,
  creating,
  disabled,
  onChoose,
  onCreate,
  onCancelCreate,
  onRemove,
}: {
  file: Extract<OpenedFile, { status: "ready" }>;
  choices: Account[];
  problem: string | null;
  creating: boolean;
  disabled: boolean;
  onChoose: (accountId: string) => void;
  onCreate: (account: Account) => void;
  onCancelCreate: () => void;
  onRemove: () => void;
}) {
  const selectId = useId();
  const { parsed } = file;
  const shown = parsed.records.slice(0, PREVIEW_ROWS);
  return (
    <section className="dk-import-file" aria-label={file.name}>
      <div className="dk-import-file-heading">
        <h3>{file.name}</h3>
        <span className="dk-tag">{parsed.profile.name}</span>
        <button type="button" className="dk-text-button" disabled={disabled} onClick={onRemove}>
          Remove
        </button>
      </div>
      <p className="dk-import-summary">
        {parsed.records.length} {parsed.records.length === 1 ? "transaction" : "transactions"} · {formatPeriod(parsed.period)} · {formatBytes(file.bytes.byteLength)} ·{" "}
        {parsed.encoding === "windows-1252" ? "Windows-1252" : "UTF-8"}
      </p>
      <label className="dk-field" htmlFor={selectId}>
        <span>Account for this file</span>
        <select
          id={selectId}
          value={creating ? NEW_ACCOUNT : file.accountId}
          disabled={disabled}
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? `${selectId}-problem` : undefined}
          onChange={(event) => onChoose(event.target.value)}
        >
          <option value="" disabled>
            Choose an account…
          </option>
          {choices.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} · {account.bank} · {account.currency}
            </option>
          ))}
          <option value={NEW_ACCOUNT}>New account…</option>
        </select>
        {problem && (
          <span className="dk-field-error" id={`${selectId}-problem`}>
            {problem}
          </span>
        )}
        {!parsed.accountIdentifiers.length && !creating && !file.accountId && (
          <span className="dk-hint-inline">This export does not name its account, so choose where the money moved.</span>
        )}
      </label>
      {creating && <NewAccountForm choices={choices} bank={parsed.profile.bank} currency={parsed.records[0]?.record.currency ?? "DKK"} onCreate={onCreate} onCancel={onCancelCreate} />}
      <div className="dk-table-scroll">
        <table className="dk-table">
          <caption className="dk-visually-hidden">Preview of {file.name}</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Description</th>
              <th scope="col" className="dk-number">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ row, record }) => (
              <tr key={row}>
                <td>{formatDate(record.date)}</td>
                <td>{record.description}</td>
                <td className="dk-number">{formatMoney(record.amount, record.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {parsed.records.length > shown.length && <p className="dk-muted dk-table-more">…and {parsed.records.length - shown.length} more</p>}
    </section>
  );
}

/** Creates an account in memory; it is saved only with the confirmed import. */
function NewAccountForm({ choices, bank, currency, onCreate, onCancel }: { choices: Account[]; bank: string; currency: string; onCreate: (account: Account) => void; onCancel: () => void }) {
  const ids = { name: useId(), bank: useId(), currency: useId(), banks: useId(), currencies: useId() };
  const [draft, setDraft] = useState<AccountDraft>({ name: "", bank, currency });
  const [errors, setErrors] = useState<AccountErrors>({});

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateDraft(draft, choices);
    setErrors(found);
    if (!Object.keys(found).length) onCreate(newAccount(draft));
  };

  const field = (key: keyof AccountDraft, label: string, extra: { list?: string; maxLength: number; autoFocus?: boolean }) => (
    <label className="dk-field" htmlFor={ids[key]}>
      <span>{label}</span>
      <input
        id={ids[key]}
        value={draft[key]}
        autoComplete="off"
        autoFocus={extra.autoFocus}
        maxLength={extra.maxLength}
        list={extra.list}
        aria-invalid={errors[key] ? true : undefined}
        aria-describedby={errors[key] ? `${ids[key]}-error` : undefined}
        onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
      />
      {errors[key] && (
        <span className="dk-field-error" id={`${ids[key]}-error`}>
          {errors[key]}
        </span>
      )}
    </label>
  );

  return (
    <form className="dk-form dk-inline-form" onSubmit={submit} noValidate aria-label="New account">
      {field("name", "Account name", { maxLength: 80, autoFocus: true })}
      <div className="dk-form-grid">
        {field("bank", "Bank", { list: ids.banks, maxLength: 80 })}
        {field("currency", "Currency", { list: ids.currencies, maxLength: 3 })}
      </div>
      <datalist id={ids.banks}>
        {INITIAL_BANKS.map((item) => (
          <option key={item} value={item} />
        ))}
      </datalist>
      <datalist id={ids.currencies}>
        {COMMON_CURRENCIES.map((item) => (
          <option key={item} value={item} />
        ))}
      </datalist>
      <p className="dk-hint">The account is saved together with this import.</p>
      <div className="dk-dialog-actions dk-inline-actions">
        <button type="button" className="dk-button" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="dk-button dk-primary">
          Use this account
        </button>
      </div>
    </form>
  );
}
