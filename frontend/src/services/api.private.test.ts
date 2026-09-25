import { afterEach, expect, it, vi } from "vitest";

vi.mock("./privateAuth", () => ({
  PRIVATE_MODE: true,
  getPrivateAccessToken: vi.fn().mockResolvedValue("private-access-token"),
}));

import { getSeasons } from "./api";
import { getPrivateAccessToken } from "./privateAuth";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(getPrivateAccessToken).mockReset();
  vi.mocked(getPrivateAccessToken).mockResolvedValue("private-access-token");
});

it("attaches the private access token to API requests", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);

  await getSeasons();

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringMatching(/\/seasons$/),
    expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer private-access-token" }),
    }),
  );
});

it("does not call the API when the private session has expired", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(getPrivateAccessToken).mockRejectedValueOnce(new Error("Private session expired."));

  await expect(getSeasons()).rejects.toThrow("Private session expired.");
  expect(fetchMock).not.toHaveBeenCalled();
});
