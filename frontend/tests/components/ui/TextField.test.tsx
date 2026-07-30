import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TextField } from "../../../src/components/ui/TextField";

describe("TextField", () => {
  it("associates its visible label with the input", async () => {
    render(<TextField label="Username" defaultValue="" />);
    const input = screen.getByLabelText("Username");
    expect(input.tagName).toBe("INPUT");
    await userEvent.type(input, "admin");
    expect(input).toHaveValue("admin");
  });

  it("links a validation message to its field via aria-describedby", () => {
    render(<TextField label="Password" error="Password is required" />);
    const input = screen.getByLabelText("Password");
    const message = screen.getByText("Password is required");

    expect(input).toHaveAttribute("aria-invalid", "true");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(message).toHaveAttribute("id", describedBy);
  });

  it("has no aria-invalid or description when valid", () => {
    render(<TextField label="Username" />);
    const input = screen.getByLabelText("Username");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
  });
});
