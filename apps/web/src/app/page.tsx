"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { getMe } from "@/lib/products";
import { Spinner } from "@/components/icons";

/** 루트 진입 — 세션 없으면 /login, 있으면 역할별 홈(관리자→/customers, 그 외→/products). */
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      if (!data.session) {
        router.replace("/login");
        return;
      }
      try {
        const me = await getMe();
        router.replace(me.role === "admin" ? "/customers" : "/products");
      } catch {
        router.replace("/products");
      }
    });
  }, [router]);

  return (
    <div className="grid min-h-screen place-items-center bg-canvas text-muted-foreground">
      <Spinner width={28} height={28} />
    </div>
  );
}
