# Google managed hosting with EU storage

Use Firebase Hosting, Google sign-in through Firebase Authentication, Firestore for encrypted financial history and statements, and a small Cloud Run relay for Jev. Choose EU locations for stored history and the relay where configurable; this choice does not imply that Jev processing or static application delivery stays within the EU.

The operator accepts a billing-enabled project to use Cloud Run while targeting free allowances or approximately €5/month. Run no always-on relay instances, restrict classification requests, and configure a €5 budget alert; this is an operating target, not a hard spending cap. Managed services avoid depending on an always-on home computer while retaining the browser-only decryption boundary in ADR-0001.
