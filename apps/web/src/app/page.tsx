"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Spinner } from "@/components/icons";

/** 루트 진입 — 세션 있으면 백오피스(/products), 없으면 /login 으로. */
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      router.replace(data.session ? "/products" : "/login");
    });
  }, [router]);

  return (
    <div className="grid min-h-screen place-items-center bg-canvas text-muted-foreground">
      <Spinner width={28} height={28} />
    </div>
  );
}
