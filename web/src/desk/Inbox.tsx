import { useId, useMemo, useState } from "react";
import type { Account } from "../workspace/accounts";
import { CASH_CATEGORY } from "../workspace/classification/categories";
import {
  isUncategorized,
  reviewReason,
  similarUncategorized,
  directionOf,
  type Classification,
  type DecisionRecord,
  type MerchantChoice,
  type ReviewReason,
} from "../workspace/classification/decisions";
import { merchantLabel } from "../workspace/classification/merchant";
import type { Transaction } from "../workspace/import/statements";
import { describeError } from "../workspace/session";
import { ClassificationFields, classificationOf, describeClassification, type ClassificationDraft } from "./Classification";
import { formatDate, formatMoney } from "./format";

export interface InboxProps {
  accounts: Account[];
  transactions: Transaction[];
  decisions: ReadonlyMap<string, DecisionRecord>;
  merchantChoices: MerchantChoice[];
  onClassify: (transactionId: string, classification: Classification, options?: { remember?: boolean }) => Promise<{ merchantChoice?: MerchantChoice }>;
  onApplyToSimilar: (merchantChoiceId: string) => Promise<number>;
  onUndo: (transactionId: string) => Promise<void>;
}

/** What the operator last did in the inbox, kept so it can be undone or extended. */
interface LastAction {
  transaction: Transaction;
  classification: Classification;
  merchantChoice?: MerchantChoice;
  appliedToSimilar?: number;
}

function explain(reason: ReviewReason): string {
  switch (reason.kind) {
    case "cash-withdrawal":
      return "The description looks like a cash withdrawal. Confirm it to count it as spending under Other, or choose a category yourself.";
    case "remembered-later":
      return `You remembered ${describeClassification(reason.choice.classification)} for ${reason.choice.merchant.name} after this was imported, so it was not applied automatically.`;
    case "money-in":
      return "Money arrived. Say whether it is income, a refund, an own-account transfer or a contribution.";
    case "unfamiliar-merchant":
      return `No remembered choice for ${reason.merchant.name} yet.`;
    case "no-merchant":
      return "No merchant could be read from the description, so it cannot be remembered.";
  }
}

/**
 * The Uncategorized section of the review inbox. Every item has its own
 * selector, remember choice and assign action; assigning one item touches no
 * other item's selection.
 */
export function Inbox({ accounts, transactions, decisions, merchantChoices, onClassify, onApplyToSimilar, onUndo }: InboxProps) {
  const accountName = useMemo(() => new Map(accounts.map((account) => [account.id, `${account.name} · ${account.bank}`])), [accounts]);
  const items = useMemo(() => transactions.filter((transaction) => isUncategorized(decisions.get(transaction.id))), [transactions, decisions]);
  // Each item's unsaved selection, by transaction id. Kept here so an item's
  // choice survives other items leaving the list.
  const [drafts, setDrafts] = useState<Record<string, ClassificationDraft>>({});
  const [remember, setRemember] = useState<Record<string, boolean>>({});
  const [last, setLast] = useState<LastAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const similar = last?.merchantChoice && last.appliedToSimilar === undefined ? similarUncategorized(last.merchantChoice, transactions, decisions) : [];
  const count = items.length;

  const assign = async (transaction: Transaction, classification: Classification, rememberIt: boolean) => {
    const result = await onClassify(transaction.id, classification, { remember: rememberIt });
    setLast({ transaction, classification, merchantChoice: result.merchantChoice });
    setError(undefined);
  };

  return (
    <section className="dk-panel dk-inbox" aria-labelledby="dk-uncategorized-heading">
      <div className="dk-section-heading">
        <h2 id="dk-uncategorized-heading">
          Uncategorized <span className="dk-count">{count}</span>
        </h2>
        <span>Uncategorized spending still counts in totals until it is resolved</span>
      </div>
      {last && (
        <div className="dk-notice dk-inbox-notice" aria-live="polite">
          <p>
            {last.appliedToSimilar !== undefined ? (
              <>
                Assigned {describeClassification(last.classification)} to {last.appliedToSimilar} more {last.appliedToSimilar === 1 ? "item" : "items"} from{" "}
                {last.merchantChoice?.merchant.name}.
              </>
            ) : (
              <>
                Assigned {describeClassification(last.classification)} to <strong>{last.transaction.bank.description}</strong>.
                {last.merchantChoice && <> Later imports from {last.merchantChoice.merchant.name} will get it automatically.</>}
              </>
            )}
          </p>
          <div className="dk-inline-buttons">
            {similar.length > 0 && last.merchantChoice && (
              <button
                type="button"
                className="dk-button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const applied = await onApplyToSimilar(last.merchantChoice!.id);
                    setLast({ ...last, appliedToSimilar: applied });
                  } catch (failure) {
                    setError(describeError(failure));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Apply to {similar.length} similar {similar.length === 1 ? "item" : "items"}
              </button>
            )}
            {last.appliedToSimilar === undefined && (
              <button
                type="button"
                className="dk-button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onUndo(last.transaction.id);
                    setLast(null);
                  } catch (failure) {
                    setError(describeError(failure));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Undo
              </button>
            )}
            <button type="button" className="dk-text-button" onClick={() => setLast(null)}>
              Dismiss
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className="dk-form-error" role="alert">
          {error}
        </p>
      )}
      {count === 0 ? (
        <div className="dk-empty">
          <p>
            <strong>Every imported transaction has a category or type.</strong> New ones appear here after an import.
          </p>
        </div>
      ) : (
        <ul className="dk-inbox-list" aria-label="Uncategorized transactions">
          {items.map((transaction) => (
            <InboxItem
              key={transaction.id}
              transaction={transaction}
              account={accountName.get(transaction.accountId) ?? "Unknown account"}
              reason={reviewReason(transaction, merchantChoices)}
              draft={drafts[transaction.id] ?? { type: directionOf(transaction) === "out" ? "purchase" : "", category: "" }}
              onDraft={(draft) => setDrafts((current) => ({ ...current, [transaction.id]: draft }))}
              remember={remember[transaction.id] ?? false}
              onRemember={(value) => setRemember((current) => ({ ...current, [transaction.id]: value }))}
              onAssign={assign}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function InboxItem({
  transaction,
  account,
  reason,
  draft,
  onDraft,
  remember,
  onRemember,
  onAssign,
}: {
  transaction: Transaction;
  account: string;
  reason: ReviewReason;
  draft: ClassificationDraft;
  onDraft: (draft: ClassificationDraft) => void;
  remember: boolean;
  onRemember: (value: boolean) => void;
  onAssign: (transaction: Transaction, classification: Classification, remember: boolean) => Promise<void>;
}) {
  const ids = { heading: useId(), meta: useId(), reason: useId(), remember: useId() };
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const merchant = merchantLabel(transaction.bank.description);
  const classification = classificationOf(draft);
  const { bank } = transaction;

  const run = async (chosen: Classification, rememberIt: boolean) => {
    setBusy(true);
    setError(undefined);
    try {
      await onAssign(transaction, chosen, rememberIt);
    } catch (failure) {
      setError(describeError(failure));
      setBusy(false);
    }
  };

  return (
    <li>
      <article className="dk-inbox-item" aria-labelledby={`${ids.heading} ${ids.meta}`}>
        <div className="dk-inbox-record">
          <h3 id={ids.heading}>{bank.description || "No description"}</h3>
          <p id={ids.meta} className="dk-inbox-meta">
            {formatDate(bank.date)} · {account} · <strong className="dk-number">{formatMoney(bank.amount, bank.currency)}</strong>
          </p>
          <p id={ids.reason} className="dk-inbox-reason">
            {explain(reason)}
          </p>
          {reason.kind === "cash-withdrawal" && (
            <p className="dk-suggestion">
              <span className="dk-tag dk-tag-warning">Suggested · Cash withdrawal</span>
              <button type="button" className="dk-button" disabled={busy} onClick={() => run({ type: "cash-withdrawal", category: CASH_CATEGORY }, false)}>
                Confirm cash withdrawal
              </button>
            </p>
          )}
        </div>
        <div className="dk-inbox-decide">
          <ClassificationFields draft={draft} onChange={onDraft} describedBy={ids.reason} />
          {merchant ? (
            <label className="dk-check" htmlFor={ids.remember}>
              <input id={ids.remember} type="checkbox" checked={remember} onChange={(event) => onRemember(event.target.checked)} />
              <span>Remember for {merchant.name}</span>
            </label>
          ) : (
            <p className="dk-hint-inline">No merchant to remember</p>
          )}
          <button
            type="button"
            className="dk-button dk-primary"
            disabled={busy || !classification}
            onClick={() => classification && run(classification, remember && merchant !== null)}
          >
            {busy ? "Saving…" : classification ? `Assign ${describeClassification(classification)}` : "Assign"}
          </button>
          {error && (
            <p className="dk-form-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </article>
    </li>
  );
}
