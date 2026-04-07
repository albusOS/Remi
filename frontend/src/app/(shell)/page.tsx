"use client";

import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";

export default function Home() {
  return (
    <Suspense>
      <Workspace />
    </Suspense>
  );
}
