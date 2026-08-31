import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CandidateAuthShell } from "./candidate-auth-shell";

describe("CandidateAuthShell", () => {
  it("presents the returning-candidate experience and safety promises", () => {
    render(
      <CandidateAuthShell mode="sign-in">
        <div>Auth form</div>
      </CandidateAuthShell>,
    );

    expect(screen.getByRole("heading", { name: "Welcome back to your job search." })).toBeTruthy();
    expect(screen.getByText("Auth form")).toBeTruthy();
    expect(screen.getByText("Private by default")).toBeTruthy();
    expect(screen.getByText("Evidence-bound AI")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Create account" })).toHaveAttribute("href", "/sign-up");
  });

  it("presents account creation as the start of a reusable career workspace", () => {
    render(
      <CandidateAuthShell mode="sign-up">
        <div>Create account form</div>
      </CandidateAuthShell>,
    );

    expect(screen.getByRole("heading", { name: "Make every application more intentional." })).toBeTruthy();
    expect(screen.getByText("Create account form")).toBeTruthy();
    expect(screen.getByText("See the recruiter view before you apply")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in");
  });
});
