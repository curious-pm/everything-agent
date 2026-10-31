import { create } from "zustand";
import type { IconName } from "./components/Icon";

export type Screen = "home" | "settings";

export const SCREENS: { id: Screen; label: string; icon: IconName }[] = [
  { id: "home", label: "Home", icon: "home" },
  { id: "settings", label: "Settings", icon: "settings" },
];

export const useNav = create<{ screen: Screen; go: (screen: Screen) => void }>((set) => ({
  screen: "home",
  go: (screen) => set({ screen }),
}));
