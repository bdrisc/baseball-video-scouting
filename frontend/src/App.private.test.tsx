import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn().mockResolvedValue(undefined) }));

vi.mock("./pages/ScoutingWorkspace", () => ({
  default: () => <div>Private scouting data rendered</div>,
}));
vi.mock("./services/privateAuth", () => ({
  PRIVATE_MODE: true,
  privateAuthConfigurationError: null,
  initializePrivateSession: vi.fn().mockResolvedValue(null),
  signOutPrivateSession: vi.fn(),
  privateUserManager: {
    events: {
      addUserUnloaded: vi.fn(), removeUserUnloaded: vi.fn(),
      addAccessTokenExpired: vi.fn(), removeAccessTokenExpired: vi.fn(),
    },
    signinRedirect: signIn,
  },
}));

import App from "./App";

beforeEach(() => {
  signIn.mockClear();
});

it("keeps the scouting workspace unmounted before private sign-in", async () => {
  render(<App />);
  await screen.findByRole("button", { name: /Sign in with Cognito/i });
  expect(screen.queryByText("Private scouting data rendered")).not.toBeInTheDocument();
});
