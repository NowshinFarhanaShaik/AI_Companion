import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const authHeader = (call: unknown[]) => new Headers((call[1] as RequestInit).headers).get("Authorization");

describe("api client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("asc_access", "old-access");
    localStorage.setItem("asc_refresh", "refresh-1");
  });

  it("refreshes once on a 401 and retries with the new token", async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(json(200, { access: "new-access" }))
      .mockResolvedValueOnce(json(200, { items: [], count: 0 }));

    await expect(api.get("/spaces")).resolves.toEqual({ items: [], count: 0 });
    expect(authHeader(fetchMock.mock.calls[0])).toBe("Bearer old-access");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/auth/token/refresh");
    expect(authHeader(fetchMock.mock.calls[2])).toBe("Bearer new-access");
    expect(localStorage.getItem("asc_access")).toBe("new-access");
  });

  it("signs out when the refresh is rejected", async () => {
    const onLogout = vi.fn();
    window.addEventListener("asc:logout", onLogout);
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(json(401, { detail: "Refresh token invalid" }));

    await expect(api.get("/spaces")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem("asc_access")).toBeNull();
    expect(onLogout).toHaveBeenCalledOnce();
    window.removeEventListener("asc:logout", onLogout);
  });

  it("does not refresh again when the retried request is still unauthorized", async () => {
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "Token expired" }))
      .mockResolvedValueOnce(json(200, { access: "new-access" }))
      .mockResolvedValueOnce(json(401, { detail: "Still not allowed" }));

    await expect(api.get("/spaces")).rejects.toMatchObject({ status: 401, message: "Still not allowed" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("carries the server's message and code", async () => {
    fetchMock.mockResolvedValueOnce(json(429, { detail: "Too many requests.", code: "rate_limited" }));

    await expect(api.post("/conversations/c1/messages", { text: "hi" })).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
      message: "Too many requests.",
    });
  });

  it("turns network failures and bare server errors into readable messages", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(api.get("/spaces")).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/reach the server/) });

    fetchMock.mockResolvedValueOnce(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(api.get("/spaces")).rejects.toMatchObject({ status: 502, message: expect.stringMatching(/try again/) });
  });
});
