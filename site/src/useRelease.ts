import { useEffect, useState } from "react";
import { LATEST_RELEASE_API, RELEASES } from "./content";

export type Platform = "windows" | "mac" | "other";

export type ReleaseAsset = { name: string; browser_download_url: string; size?: number };
export type Release = { tag_name: string; assets: ReleaseAsset[] };

export type Installer = {
  platform: Exclude<Platform, "other">;
  label: string;
  href: string;
  detail: string;
  direct: boolean;
};

export type Download = { label: string; href: string; version?: string };

export function detectPlatform(userAgent: string): Platform {
  if (/Windows/i.test(userAgent)) return "windows";
  if (/Macintosh|Mac OS X/i.test(userAgent) && !/iPhone|iPad/i.test(userAgent)) return "mac";
  return "other";
}

const EXTENSION = { windows: ".exe", mac: ".dmg" } as const;
const NAME = { windows: "Windows", mac: "macOS" } as const;

function megabytes(size?: number): string {
  return size ? `${Math.round(size / 1_000_000)} MB` : "";
}

export function installerFor(platform: Exclude<Platform, "other">, release: Release | null): Installer {
  const asset = release?.assets.find((a) => a.name.toLowerCase().endsWith(EXTENSION[platform]));
  if (!release || !asset) {
    return { platform, label: `Download for ${NAME[platform]}`, href: RELEASES, detail: EXTENSION[platform], direct: false };
  }
  const appleSilicon = platform === "mac" && /aarch64|arm64/i.test(asset.name);
  const label = appleSilicon ? "Download for macOS (Apple silicon)" : `Download for ${NAME[platform]}`;
  const detail = [release.tag_name, EXTENSION[platform], megabytes(asset.size)].filter(Boolean).join(", ");
  return { platform, label, href: asset.browser_download_url, detail, direct: true };
}

export function pickDownload(platform: Platform, release: Release | null): Download {
  if (platform === "other") return { label: "Download for Windows or macOS", href: "#desktop" };
  const installer = installerFor(platform, release);
  return installer.direct
    ? { label: installer.label, href: installer.href, version: release?.tag_name }
    : { label: installer.label, href: "#desktop" };
}

let request: Promise<Release | null> | null = null;

export function fetchLatestRelease(): Promise<Release | null> {
  request ??= fetch(LATEST_RELEASE_API, { headers: { Accept: "application/vnd.github+json" } })
    .then((response) => (response.ok ? response.json() : null))
    .then((data: Release | null) => (data && Array.isArray(data.assets) ? data : null))
    .catch(() => null);
  return request;
}

export function resetReleaseCache() {
  request = null;
}

export function useLatestRelease(): Release | null {
  const [release, setRelease] = useState<Release | null>(null);
  useEffect(() => {
    let live = true;
    void fetchLatestRelease().then((data) => {
      if (live) setRelease(data);
    });
    return () => {
      live = false;
    };
  }, []);
  return release;
}

export function useDownload(): Download {
  return pickDownload(detectPlatform(navigator.userAgent), useLatestRelease());
}
