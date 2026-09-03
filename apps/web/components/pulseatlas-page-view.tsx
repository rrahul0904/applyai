"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { trackPulseAtlasPage } from "@/lib/pulseatlas";

export function PulseAtlasPageView() {
  const pathname = usePathname();
  useEffect(() => { if (pathname) void trackPulseAtlasPage(pathname); }, [pathname]);
  return null;
}
