import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "../../../src/components/ui/Button";

describe("Button", () => {
  it("renders its label and activates on click", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Sign in</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("cannot be activated while disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Sign in
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Sign in" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("exposes a busy state and blocks activation while loading", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Signing in…
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Signing in…" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
