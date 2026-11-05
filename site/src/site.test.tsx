import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { conversation } from "./content";
import { detectPlatform, installerFor, pickDownload, resetReleaseCache } from "./useRelease";

function setReducedMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

beforeEach(() => {
  resetReleaseCache();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  vi.stubGlobal("IntersectionObserver", undefined);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("the hero conversation", () => {
  it("shows the finished exchange straight away when motion is reduced", () => {
    setReducedMotion(true);
    render(<App />);
    const stage = screen.getByRole("figure", { name: /sample conversation/i });
    expect(stage).toHaveAttribute("data-phase", "speaking");
    expect(stage).toHaveTextContent("¡Claro! Puedo charlar contigo");
    expect(screen.queryByRole("button", { name: "Play again" })).not.toBeInTheDocument();
  });

  it("plays through listening, thinking, a cut-off reply and the Spanish answer", async () => {
    setReducedMotion(false);
    vi.useFakeTimers();
    render(<App />);
    const stage = screen.getByRole("figure", { name: /sample conversation/i });
    const reply = () => stage.querySelector(".reply")!;
    const seen = new Set<string>();
    let cutSeen = false;
    const total = conversation.reduce((ms, beat) => ms + ("pause" in beat ? beat.pause : 3000), 0);
    for (let elapsed = 0; elapsed < total; elapsed += 100) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      seen.add(stage.getAttribute("data-phase")!);
      cutSeen ||= reply().classList.contains("cut") && reply().textContent!.endsWith("…");
    }
    expect([...seen]).toEqual(expect.arrayContaining(["listening", "thinking", "speaking"]));
    expect(cutSeen).toBe(true);
    expect(reply()).toHaveTextContent("buscar cosas por ti.");
    expect(screen.getByRole("button", { name: "Play again" })).toBeInTheDocument();
  });
});

describe("install", () => {
  beforeEach(() => setReducedMotion(true));

  it("switches tabs by click and with the arrow keys", () => {
    render(<App />);
    const robot = screen.getByRole("tab", { name: "On Reachy Mini" });
    const desktop = screen.getByRole("tab", { name: "Windows and macOS" });
    expect(robot).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("pip install");

    fireEvent.click(desktop);
    expect(desktop).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("code-signed");

    fireEvent.keyDown(desktop, { key: "ArrowRight" });
    const source = screen.getByRole("tab", { name: "From source" });
    expect(source).toHaveAttribute("aria-selected", "true");
    expect(source).toHaveFocus();
    fireEvent.keyDown(source, { key: "ArrowRight" });
    expect(robot).toHaveAttribute("aria-selected", "true");
  });

  it("copies a command and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<App />);
    const copy = screen.getByRole("button", { name: /Copy: pip install/ });
    await act(async () => {
      fireEvent.click(copy);
    });
    expect(writeText).toHaveBeenCalledWith("pip install git+https://github.com/curious-pm/Everything-Agent");
    expect(copy).toHaveTextContent("Copied");
  });
});

describe("download button", () => {
  const release = {
    tag_name: "v0.1.0",
    assets: [
      { name: "Everything Agent_0.1.0_x64-setup.exe", browser_download_url: "https://example.com/a.exe" },
      { name: "Everything Agent_0.1.0_aarch64.dmg", browser_download_url: "https://example.com/a.dmg" },
    ],
  };

  it("names the visitor's system", () => {
    expect(detectPlatform("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")).toBe("windows");
    expect(detectPlatform("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)")).toBe("mac");
    expect(detectPlatform("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")).toBe("other");
    expect(detectPlatform("Mozilla/5.0 (X11; Linux x86_64)")).toBe("other");
  });

  it("links the right installer once a release is published, the desktop tab before", () => {
    expect(pickDownload("windows", release)).toEqual({
      label: "Download for Windows", href: "https://example.com/a.exe", version: "v0.1.0",
    });
    expect(pickDownload("mac", release).href).toBe("https://example.com/a.dmg");
    expect(pickDownload("mac", null).href).toBe("#desktop");
    expect(pickDownload("other", release).label).toBe("Download for Windows or macOS");
  });

  it("describes each installer, and says when a Mac build is Apple silicon only", () => {
    const sized = { ...release, assets: release.assets.map((a) => ({ ...a, size: 249_400_000 })) };
    expect(installerFor("windows", sized).detail).toBe("v0.1.0, .exe, 249 MB");
    expect(installerFor("mac", sized).label).toBe("Download for macOS (Apple silicon)");
    expect(installerFor("windows", null)).toMatchObject({ direct: false, href: expect.stringMatching(/\/releases$/) });
  });

  it("downloads straight from the desktop tab when a release is out", async () => {
    setReducedMotion(true);
    resetReleaseCache();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(release) }));
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: "Windows and macOS" }));
    const pane = within(screen.getByRole("tabpanel"));
    const windows = await pane.findByRole("link", { name: /^Download for Windows/ });
    expect(windows).toHaveAttribute("href", "https://example.com/a.exe");
    expect(pane.getByRole("link", { name: /Download for macOS \(Apple silicon\)/ })).toHaveAttribute("href", "https://example.com/a.dmg");
    expect(screen.queryByText(/isn't published yet/)).not.toBeInTheDocument();
  });

  it("explains the fallback while no release is published", async () => {
    setReducedMotion(true);
    resetReleaseCache();
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: "Windows and macOS" }));
    expect(await screen.findByText(/isn't published yet/)).toBeInTheDocument();
    for (const link of within(screen.getByRole("tabpanel")).getAllByRole("link", { name: /^Download for (Windows|macOS)/ })) {
      expect(link.getAttribute("href")).toMatch(/\/releases$/);
    }
  });

  it("opens the desktop tab from the page address", () => {
    setReducedMotion(true);
    window.location.hash = "#desktop";
    Element.prototype.scrollIntoView = vi.fn();
    render(<App />);
    expect(screen.getByRole("tab", { name: "Windows and macOS" })).toHaveAttribute("aria-selected", "true");
    window.location.hash = "";
  });
});
