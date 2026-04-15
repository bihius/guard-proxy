const DEFAULT_THEME_STORAGE_KEY = "guard-proxy-theme";

export const THEME_STORAGE_META_SELECTOR =
  'meta[name="guard-proxy-theme-storage-key"]';

export const THEMES = ["emerald", "frost"] as const;

export type Theme = (typeof THEMES)[number];

export function getThemeStorageKey() {
  return (
    document
      .querySelector(THEME_STORAGE_META_SELECTOR)
      ?.getAttribute("content")
      ?.trim() || DEFAULT_THEME_STORAGE_KEY
  );
}
