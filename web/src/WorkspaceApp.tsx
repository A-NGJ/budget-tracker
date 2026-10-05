import { setupFirebase, type FirebaseServices } from "./workspace/firebase";
import { useWorkspaceSession } from "./workspace/session";
import { Desk } from "./desk/Desk";
import { ConfigurationMissing, FailedScreen, OnboardingScreen, SignInScreen, StatusScreen, UnlockScreen } from "./desk/Gate";
import "./desk/desk.css";

// The encrypted workspace app. It talks only to Firebase Auth and Firestore
// and never to the legacy plaintext /api, so readable account data stays in
// this browser.
export function WorkspaceApp() {
  const setup = setupFirebase();
  if (!setup.ok) return <ConfigurationMissing missing={setup.missing} />;
  return <Session services={setup.services} />;
}

function Session({ services }: { services: FirebaseServices }) {
  const session = useWorkspaceSession(services);
  const { phase } = session;
  const signOut = () => void session.signOut();
  switch (phase.kind) {
    case "starting":
      return <StatusScreen message="Checking sign-in…" />;
    case "signed-out":
      return <SignInScreen onSignIn={session.signIn} error={phase.error} usingEmulators={services.usingEmulators} />;
    case "loading-workspace":
      return <StatusScreen message="Opening your encrypted workspace…" />;
    case "onboarding":
      return <OnboardingScreen operator={phase.operator} onCreate={session.createWithPassphrase} onSignOut={signOut} />;
    case "locked":
      return <UnlockScreen key={phase.reason ?? "fresh"} operator={phase.operator} reason={phase.reason} onUnlock={session.unlock} onSignOut={signOut} />;
    case "failed":
      return <FailedScreen operator={phase.operator} message={phase.message} onRetry={session.retry} onSignOut={signOut} />;
    case "unlocked":
      return (
        <Desk
          operator={phase.operator}
          accounts={phase.accounts}
          statements={phase.statements}
          transactions={phase.transactions}
          decisions={phase.decisions}
          merchantChoices={phase.merchantChoices}
          usingEmulators={services.usingEmulators}
          onAddAccount={session.addAccount}
          onImport={session.importStatements}
          onLoadOriginal={session.loadOriginal}
          onDeleteOriginal={session.deleteOriginal}
          onClassify={session.classify}
          onApplyToSimilar={session.applyToSimilar}
          onUndo={session.undo}
          onLock={() => session.lock("manual")}
          onSignOut={signOut}
        />
      );
  }
}
