import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CandidateShell } from "./candidate-shell";

const state = vi.hoisted(() => ({ pathname: "/portfolio", push: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => state.pathname,
  useRouter: () => ({ push: state.push }),
}));
vi.mock("@clerk/nextjs", () => ({ UserButton: () => <button>Clerk account</button> }));
vi.mock("@/app/auth/actions", () => ({ signOutAction: vi.fn() }));
vi.mock("@/app/dev-login/actions", () => ({ devSignOut: vi.fn() }));

function renderShell() {
  return render(<CandidateShell session={{ kind: "supabase", authenticated: true, email: "candidate@example.com" }}><p>Candidate content</p></CandidateShell>);
}

describe("CandidateShell navigation", () => {
  beforeEach(() => { state.pathname = "/portfolio"; state.push.mockReset(); });

  it("marks only Portfolio active on the portfolio route", () => {
    renderShell();
    const desktop = screen.getByRole("navigation", { name: "Candidate workspace" });
    const active = desktop.querySelectorAll('[aria-current="page"]');
    expect(active).toHaveLength(1);
    expect(active[0].textContent).toBe("Portfolio");
    expect(within(desktop).getByRole("link", { name: "Career Coach" }).hasAttribute("aria-current")).toBe(false);
  });

  it("keeps four primary mobile links and exposes secondary destinations and sign-out through More", () => {
    renderShell();
    const mobile = screen.getByRole("navigation", { name: "Primary mobile navigation" });
    expect(within(mobile).getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual(["/dashboard", "/jobs", "/applications", "/interview-prep"]);
    const more = within(mobile).getByRole("button", { name: "More navigation" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(more);
    expect(more.getAttribute("aria-expanded")).toBe("true");
    const panel = screen.getByRole("navigation", { name: "More mobile navigation" });
    for (const name of ["Job Radar", "Career Coach", "Portfolio", "Referrals", "Profile", "Settings and privacy"]) {
      expect(within(panel).getByRole("link", { name })).toBeTruthy();
    }
    expect(within(panel).getByRole("button", { name: "Sign out" })).toBeTruthy();
    expect(document.activeElement).toBe(within(panel).getAllByRole("link")[0]);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("navigation", { name: "More mobile navigation" })).toBeNull();
    expect(document.activeElement).toBe(more);
  });

  it("closes More after selecting a destination", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "More navigation" }));
    const panel = screen.getByRole("navigation", { name: "More mobile navigation" });
    const profileLink = within(panel).getByRole("link", { name: "Profile" });
    profileLink.addEventListener("click", (event) => event.preventDefault());
    fireEvent.click(profileLink);
    expect(screen.queryByRole("navigation", { name: "More mobile navigation" })).toBeNull();
  });

  it("makes the advertised search shortcut work with Mac and Windows/Linux modifiers", () => {
    renderShell();
    const macEvent = new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(macEvent);
    expect(macEvent.defaultPrevented).toBe(true);
    fireEvent.keyDown(document, { key: "K", ctrlKey: true });
    expect(state.push.mock.calls).toEqual([["/jobs"], ["/jobs"]]);
    fireEvent.keyDown(document, { key: "k" });
    expect(state.push).toHaveBeenCalledTimes(2);
  });

  it("retains the grouped Career Coach highlight for resume routes", () => {
    state.pathname = "/resume/studio";
    renderShell();
    const desktop = screen.getByRole("navigation", { name: "Candidate workspace" });
    expect(within(desktop).getByRole("link", { name: "Career Coach" }).getAttribute("aria-current")).toBe("page");
    expect(desktop.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  });
});
