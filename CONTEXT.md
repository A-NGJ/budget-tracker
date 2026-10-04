# Budget tracking

Personal spending analysis based on bank statements, with comparisons across periods and identification of recurring costs.

## Language

**Bank statement**:
A bank-exported record of transactions for a period.

**Statement profile**:
A reusable description of how a bank's statement format represents transaction information. It identifies a format, not a particular account.
_Avoid_: Bank schema, bank mapping

**Account**:
A distinct bank account or currency balance whose transactions are tracked separately, even when several accounts belong to the same bank.

**Transaction**:
A recorded movement of money into or out of an account.

**Spending**:
Money used for purchases, bills, fees, or cash withdrawals, reduced by refunds received in the reporting period. Own-account transfers and savings or investment contributions are excluded.

**Own-account transfer**:
A movement of money between accounts belonging to the operator, with no income or spending created by the movement itself.

**Refund**:
Money returned for a previous purchase, reducing spending in that purchase's category in the period the money is received.

**Contribution**:
Money allocated to savings or investments, reported separately from everyday spending and counted once even when both sides of the movement are recorded. Returning money from savings is not income.

**Category**:
A broad, flat grouping of spending by purpose. Transaction type and recurring status are separate from category.

**Recurring cost**:
An ongoing payment commitment, such as rent, a subscription, a variable utility bill, or an annual renewal. Repeated discretionary purchases are not recurring costs.

**Reporting currency**:
The currency used to compare and total transactions while preserving their original amounts and currencies. The reporting currency is DKK.

**Uncategorized transaction**:
A transaction whose spending category has not been resolved. It is distinct from a transaction deliberately assigned to Other.

**Review inbox**:
The place where the operator resolves uncategorized transactions, ambiguous transfer matches, and suggested recurring costs.

**Merchant label**:
A normalized name identifying a business paid by a transaction, excluding payment references and personal messages.

**Import provenance**:
The record of which bank statement and statement entry a transaction came from.

**Recurring-cost suggestion**:
A possible ongoing payment commitment inferred from transaction history, awaiting the operator's confirmation.

**Statement coverage**:
The accounts and date periods represented by imported statements, indicating the scope of a report rather than guaranteeing that every transaction is present.

**Workspace**:
The operator's encrypted collection of financial records, owned by one Google account and readable only after it is unlocked in the browser.

**Unlock passphrase**:
The secret, separate from Google sign-in, that decrypts the workspace on each fresh application load.
_Avoid_: Password, master password

**Locked**:
The state in which the workspace's readable records and decryption key have been discarded from the browser, while the operator stays signed in.
