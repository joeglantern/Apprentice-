/** Theme + responsive context for the Umbra shell.
 *
 * The design ships two palettes (space black, graphite) and one accent that is
 * reserved for primary actions and progress. Everything reads its colours from
 * here rather than hardcoding hex, so swapping the accent stays a one-line change
 * (tokens.ts documents the sanctioned alternatives). */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useWindowDimensions } from "react-native";

import { breakpoints, grid, themes, type Palette, type ThemeName } from "@/lib/tokens";

interface ThemeValue {
  name: ThemeName;
  c: Palette;
  /** >=1024: left rail, hover states, keyboard shortcuts. */
  isDesktop: boolean;
  /** <768. Between the two is tablet, which uses the phone chrome at desktop density. */
  isPhone: boolean;
  isTablet: boolean;
  width: number;
  /** Masonry column count for explore, per the handoff's responsive rules. */
  exploreColumns: number;
}

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({
  name = "space",
  children,
}: {
  name?: ThemeName;
  children: ReactNode;
}) {
  const { width } = useWindowDimensions();

  const value = useMemo<ThemeValue>(() => {
    const isDesktop = width >= breakpoints.desktop;
    const isTablet = width >= breakpoints.tablet && width < breakpoints.desktop;
    return {
      name,
      c: themes[name],
      isDesktop,
      isTablet,
      isPhone: width < breakpoints.tablet,
      width,
      exploreColumns: !isDesktop
        ? grid.phone
        : width >= 1700
          ? grid.wide
          : width >= 1250
            ? grid.desktop
            : grid.smallDesktop,
    };
  }, [name, width]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
