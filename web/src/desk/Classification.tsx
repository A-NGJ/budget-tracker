import { useId } from "react";
import {
  CATEGORIES,
  NON_SPENDING_TYPES,
  SPENDING_TYPES,
  TYPE_NAMES,
  categoryName,
  isSpendingType,
  type CategoryId,
  type TransactionType,
  CASH_CATEGORY,
} from "../workspace/classification/categories";
import { normalizeClassification, type Classification, type DecisionRecord } from "../workspace/classification/decisions";

/** An unfinished choice in a form: either part may still be empty. */
export interface ClassificationDraft {
  type: TransactionType | "";
  category: CategoryId | "";
}

export function draftOf(classification: Classification | null | undefined, fallbackType: TransactionType | "" = ""): ClassificationDraft {
  if (!classification) return { type: fallbackType, category: "" };
  return { type: classification.type, category: "category" in classification ? classification.category : "" };
}

export function classificationOf(draft: ClassificationDraft): Classification | null {
  return draft.type ? normalizeClassification(draft) : null;
}

/** "Groceries" for spending, the type name otherwise. */
export function describeClassification(classification: Classification): string {
  if (classification.type === "purchase") return categoryName(classification.category);
  if ("category" in classification) return `${TYPE_NAMES[classification.type]} · ${categoryName(classification.category)}`;
  return TYPE_NAMES[classification.type];
}

/**
 * Type and category controls. Only spending types take a category; a cash
 * withdrawal is always Other; income, transfers and contributions take none.
 */
export function ClassificationFields({ draft, onChange, describedBy }: { draft: ClassificationDraft; onChange: (draft: ClassificationDraft) => void; describedBy?: string }) {
  const typeId = useId();
  const categoryId = useId();
  const spending = draft.type !== "" && isSpendingType(draft.type);
  const cash = draft.type === "cash-withdrawal";
  return (
    <div className="dk-classification-fields">
      <div className="dk-field">
        <label htmlFor={typeId}>Type</label>
        <select
          id={typeId}
          value={draft.type}
          aria-describedby={describedBy}
          onChange={(event) => {
            const type = event.target.value as TransactionType | "";
            const category = type === "cash-withdrawal" ? CASH_CATEGORY : type && isSpendingType(type) ? (draft.type === "cash-withdrawal" ? "" : draft.category) : "";
            onChange({ type, category });
          }}
        >
          <option value="" disabled>
            Choose type
          </option>
          <optgroup label="Spending">
            {SPENDING_TYPES.map((type) => (
              <option key={type} value={type}>
                {TYPE_NAMES[type]}
              </option>
            ))}
          </optgroup>
          <optgroup label="Not spending">
            {NON_SPENDING_TYPES.map((type) => (
              <option key={type} value={type}>
                {TYPE_NAMES[type]}
              </option>
            ))}
          </optgroup>
        </select>
      </div>
      <div className="dk-field">
        <label htmlFor={categoryId}>Category</label>
        <select
          id={categoryId}
          value={spending ? draft.category : ""}
          disabled={!spending || cash}
          aria-describedby={describedBy}
          onChange={(event) => onChange({ ...draft, category: event.target.value as CategoryId | "" })}
        >
          <option value="" disabled>
            {draft.type === "" || spending ? "Choose category" : "None · not spending"}
          </option>
          {CATEGORIES.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/** Type and category as shown in the ledger. Uncategorized is shown as unresolved, never as Other. */
export function DecisionCells({ record }: { record: DecisionRecord | undefined }) {
  const decision = record?.current ?? null;
  if (!decision) {
    return (
      <>
        <td>
          <span className="dk-muted">Unresolved</span>
        </td>
        <td>
          <span className="dk-tag dk-tag-warning">Uncategorized</span>
        </td>
      </>
    );
  }
  const { classification } = decision;
  return (
    <>
      <td>
        {TYPE_NAMES[classification.type]}
        {decision.source === "remembered" && <small>Remembered choice</small>}
      </td>
      <td>{"category" in classification ? <span className="dk-tag">{categoryName(classification.category)}</span> : <span className="dk-muted">Not spending</span>}</td>
    </>
  );
}
