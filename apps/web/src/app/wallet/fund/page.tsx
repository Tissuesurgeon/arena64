"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function FundRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/wallet");
  }, [router]);
  return <div className="p-12 opacity-60">Locker room…</div>;
}