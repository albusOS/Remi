"use client";

import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";

export default function AskPage() {
  return (
    <Suspense>
      <Workspace initialTab="remi" />
    </Suspense>
  );
}
