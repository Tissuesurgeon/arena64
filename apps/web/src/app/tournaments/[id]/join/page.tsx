"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/** Join flow lives on tournament detail; keep route for plan completeness. */
export default function JoinRedirect() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/tournaments/${id}`);
  }, [id, router]);
  return <div className="p-12 opacity-60">Opening gate…</div>;
}