import { UserManager, WebStorageStateStore } from "oidc-client-ts";

export const PRIVATE_MODE = import.meta.env.VITE_AUTH_MODE === "private";

const issuer = import.meta.env.VITE_COGNITO_ISSUER?.replace(/\/$/, "");
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
const authDomain = import.meta.env.VITE_COGNITO_AUTH_DOMAIN?.replace(/\/$/, "");
const expectedScope = "baseball-video-scouting/access";

export const privateAuthConfigurationError = PRIVATE_MODE && (
  !import.meta.env.VITE_API_BASE_URL ||
  !issuer || !issuer.startsWith("https://cognito-idp.") ||
  !authDomain || !/^https:\/\/[a-z0-9-]+\.auth\.[a-z0-9-]+\.amazoncognito\.com$/.test(authDomain) ||
  !clientId ||
  window.location.hostname !== "localhost" && window.location.protocol !== "https:"
)
  ? "Private sign-in needs a private API URL, Cognito issuer, auth domain, client ID, and HTTPS (or localhost)."
  : null;

export const privateUserManager = PRIVATE_MODE && !privateAuthConfigurationError
  ? new UserManager({
      authority: issuer!,
      client_id: clientId!,
      redirect_uri: `${window.location.origin}/`,
      response_type: "code",
      scope: `openid ${expectedScope}`,
      loadUserInfo: false,
      automaticSilentRenew: true,
      monitorSession: false,
      // Browser-session storage, never localStorage: closing the tab removes the tokens.
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    })
  : null;

let callbackPromise: ReturnType<UserManager["signinRedirectCallback"]> | null = null;

export async function initializePrivateSession() {
  if (!privateUserManager) return null;
  const query = new URLSearchParams(window.location.search);
  if (query.has("code") || (query.has("error") && query.has("state"))) {
    callbackPromise ??= privateUserManager.signinRedirectCallback();
    try {
      const user = await callbackPromise;
      return !user.expired && user.scopes.includes(expectedScope) ? user : null;
    } finally {
      const safeUrl = new URL(window.location.href);
      for (const key of ["code", "state", "error", "error_description", "session_state"]) {
        safeUrl.searchParams.delete(key);
      }
      window.history.replaceState({}, "", safeUrl);
      callbackPromise = null;
    }
  }
  const user = await privateUserManager.getUser();
  return user && !user.expired && user.scopes.includes(expectedScope) ? user : null;
}

export async function getPrivateAccessToken(): Promise<string> {
  if (!privateUserManager) throw new Error("Private sign-in is not configured.");
  const user = await privateUserManager.getUser();
  if (!user || user.expired || !user.scopes.includes(expectedScope)) {
    throw new Error("Private session expired. Sign in again.");
  }
  return user.access_token;
}

export async function signOutPrivateSession(): Promise<void> {
  if (!privateUserManager || !authDomain || !clientId) return;
  await privateUserManager.removeUser();
  const logout = new URL(`${authDomain}/logout`);
  logout.searchParams.set("client_id", clientId);
  logout.searchParams.set("logout_uri", `${window.location.origin}/`);
  window.location.assign(logout.toString());
}
