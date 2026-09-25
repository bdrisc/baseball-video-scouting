import { useEffect, useState } from "react";

import ScoutingWorkspace from "./pages/ScoutingWorkspace";
import {
  initializePrivateSession,
  PRIVATE_MODE,
  privateAuthConfigurationError,
  privateUserManager,
  signOutPrivateSession,
} from "./services/privateAuth";

export default function App() {
  const [signedIn, setSignedIn] = useState(false);
  const [loading, setLoading] = useState(PRIVATE_MODE);
  const [error, setError] = useState<string | null>(privateAuthConfigurationError);

  useEffect(() => {
    const manager = privateUserManager;
    if (!manager) return;
    let mounted = true;
    const resetSession = () => {
      if (mounted) setSignedIn(false);
    };
    manager.events.addUserUnloaded(resetSession);
    manager.events.addAccessTokenExpired(resetSession);

    void initializePrivateSession().then(
      (user) => {
        if (mounted) setSignedIn(Boolean(user));
      },
      () => {
        if (mounted) setError("Sign-in failed. Please try again.");
      },
    ).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => {
      mounted = false;
      manager.events.removeUserUnloaded(resetSession);
      manager.events.removeAccessTokenExpired(resetSession);
    };
  }, []);

  if (!PRIVATE_MODE) return <ScoutingWorkspace />;
  if (loading) return <main className="private-signin" role="status">Checking private session…</main>;
  if (!signedIn) {
    return (
      <main className="private-signin">
        <p className="eyebrow">Private season-wide workspace</p>
        <h1>Sign in to review your scouting data</h1>
        {error ? <p role="alert">{error}</p> : null}
        <button
          className="primary-button"
          type="button"
          disabled={!privateUserManager}
          onClick={() => {
            void privateUserManager?.signinRedirect().catch(() => {
              setError("Could not start sign-in. Please try again.");
            });
          }}
        >
          Sign in with Cognito
        </button>
      </main>
    );
  }

  return (
    <>
      <div className="private-session-bar">
        <span>Private workspace</span>
        {error ? <span role="alert">{error}</span> : null}
        <button
          className="text-button"
          type="button"
          onClick={() => {
            void signOutPrivateSession().catch(() => {
              setError("Could not sign out. Please try again.");
            });
          }}
        >
          Sign out
        </button>
      </div>
      <ScoutingWorkspace />
    </>
  );
}
