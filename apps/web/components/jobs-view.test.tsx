import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JobsView } from "./jobs-view";

const state = vi.hoisted(() => ({ params: new URLSearchParams(), replace: vi.fn(), search: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/jobs", useRouter: () => ({ replace: state.replace }), useSearchParams: () => state.params }));
vi.mock("@/lib/api/client", () => ({ api: { jobs: { search: state.search } } }));

describe("JobsView ordering", () => {
  it("explains its fixed newest-first ordering without offering an inert sort control", async () => {
    state.search.mockResolvedValue({ items: [], next_cursor: null });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={queryClient}><JobsView /></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: "No roles match yet" })).toBeTruthy();
    expect(screen.getByText("Newest first")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Sort jobs" })).toBeNull();
    expect(screen.getByRole("searchbox", { name: "Search jobs" })).toBeTruthy();
    expect(state.search).toHaveBeenCalledOnce();
    expect(state.search.mock.calls[0][0].get("limit")).toBe("20");
    queryClient.clear();
  });
});
