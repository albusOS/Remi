"use client";

import { use } from "react";
import { ManagerDetailView } from "@/components/managers/ManagerDetailView";

export default function ManagerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ManagerDetailView managerId={decodeURIComponent(id)} />;
}
