"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { AuthGuard } from "@/components/AuthGuard";
import { Button } from "@/components/ui";

export default function Home() {
  return (
    <AuthGuard>
      <HomeInner />
    </AuthGuard>
  );
}

function HomeInner() {
  const router = useRouter();
  const [email, setEmail] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setEmail(data.session?.user.email ?? ""));
  }, []);

  async function logout() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-6">
      <div className="w-full max-w-md text-center">
        <div className="font-serif text-3xl italic text-foreground">ezmerce</div>
        <h1 className="mt-6 text-2xl font-extrabold text-foreground">로그인되었습니다</h1>
        {email && <p className="mt-2 text-muted-foreground">{email}</p>}
        <p className="mt-1 text-sm text-muted-foreground">
          대시보드는 준비 중입니다. 관리자 승인 후 카탈로그·상품 관리가 제공됩니다.
        </p>
        <div className="mt-8">
          <Button variant="secondary" onClick={logout}>
            로그아웃
          </Button>
        </div>
      </div>
    </main>
  );
}
