"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Button, Dialog } from "./ui";
import { LogOut } from "./icons";

/** 로그아웃 확인 팝업 — 셸의 로그아웃 버튼이 열고, 확인 시 실제 signOut. */
export function LogoutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function doLogout() {
    setLoading(true);
    try {
      await supabase.auth.signOut();
      router.replace("/login");
    } catch {
      setLoading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={loading ? () => {} : onClose}
      size="sm"
      icon={<LogOut width={18} height={18} />}
      title="로그아웃"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            취소
          </Button>
          <Button onClick={doLogout} loading={loading}>
            로그아웃
          </Button>
        </>
      }
    >
      <p className="text-sm leading-relaxed text-muted-foreground">
        로그아웃 하시겠습니까? 다시 이용하려면 로그인이 필요합니다.
      </p>
    </Dialog>
  );
}
