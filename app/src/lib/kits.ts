/** Brand kits.
 *
 * The backend has no kits endpoint yet - /generate accepts a BrandKit inline on
 * each request. These three are the studio's current kits, kept here so the create
 * deck and the kits screen read from one place; move them behind an endpoint when
 * one exists and this module becomes the fetch. */

import type { BrandKit } from "./types";

export interface Kit extends BrandKit {
  id: string;
  /** Display string for the pairing, e.g. "grotesk / inter". */
  fonts: string;
}

export const KITS: Kit[] = [
  {
    id: "tide",
    name: "tide & salt",
    palette: ["#0E3A3A", "#F2E8D8", "#D96A3B", "#1C1C1F"],
    typeface: "grotesk",
    fonts: "grotesk / inter",
  },
  {
    id: "kin",
    name: "kin streetwear",
    palette: ["#111114", "#F2F2EF", "#FF6B4A", "#3A5AFF"],
    typeface: "bebas",
    fonts: "bebas / inter",
  },
  {
    id: "summit",
    name: "summit conf",
    palette: ["#0E1B2A", "#3E7BFA", "#F2F2EF", "#FFC53D"],
    typeface: "grotesk",
    fonts: "grotesk / inter",
  },
];

export function findKit(id: string): Kit | undefined {
  return KITS.find((k) => k.id === id);
}
