# Encrypted history with text-only classification

Financial history and original statements are encrypted before cloud storage and decrypted only in the operator's trusted desktop browser. We trust Google to deliver the application code and use Google sign-in for access, with a separate unlock passphrase and offline recovery key; losing both decryption credentials requires re-importing statements rather than provider-assisted recovery.

To use Jev without exposing full transactions, the browser may send a single record's normalized merchant label and bank-provided spending label through an authenticated Google-hosted relay holding the operator's Jev API key. Both the relay and Jev receive that text; amounts, dates, bank names, account identifiers, transaction references, people's names, free-form messages, raw statements, and decryption keys are excluded. If permitted text cannot be confidently extracted, classification stays local for human review. This deliberately trades disclosure of merchant-level purchase information for hosted classification while keeping the full financial history encrypted.

The relay has no financial-history decryption key and does not log request bodies. This decision does not promise zero retention by Jev or protection against malicious replacement of the hosted application code; the operator accepts Google as the application-delivery provider.
