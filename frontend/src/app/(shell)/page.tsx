"use client";

import { Suspense } from "react";
import { AskView } from "@/components/ask/AskView";

export default function Home() {
  return (
    <Suspense>
      <AskView />
    </Suspense>
  );
}
