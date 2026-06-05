"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { AuthShell } from "@/components/AuthShell";
import { Button, Checkbox, FileRow, Modal, SegTabs, TextField } from "@/components/ui";
import { ArrowRight, Check } from "@/components/icons";

type MemberType = "retailer" | "wholesaler" | "agency";

const MEMBER_OPTIONS: { value: MemberType; label: string }[] = [
  { value: "retailer", label: "Retailer (소매)" },
  { value: "wholesaler", label: "Wholesaler (도매)" },
  { value: "agency", label: "Agency (에이전시)" },
];

const COPY: Record<MemberType, { title: string; subtitle: string; terms: string }> = {
  retailer: {
    title: "회원가입",
    subtitle: "이지머스에 오신 것을 환영합니다. 비즈니스 계정을 생성하세요.",
    terms: "",
  },
  wholesaler: {
    title: "계정 생성",
    subtitle: "도매 파트너로서 비즈니스를 확장하세요.",
    terms: "이용약관 및 개인정보 처리방침에 동의합니다. 또한 도매 파트너 약관의 모든 내용을 확인하였습니다.",
  },
  agency: {
    title: "계정 생성",
    subtitle: "에이전시 파트너로서 비즈니스를 확장하세요.",
    terms: "이용약관 및 개인정보 처리방침에 동의합니다. 또한 에이전시 파트너 약관의 모든 내용을 확인하였습니다.",
  },
};

export default function RegisterPage() {
  const [type, setType] = useState<MemberType>("retailer");
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [bizCert, setBizCert] = useState<File | null>(null);
  const [idDoc, setIdDoc] = useState<File | null>(null);
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const needsDocs = type !== "retailer";
  const copy = COPY[type];

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) return setError("비밀번호는 8자 이상이어야 합니다.");
    if (password !== confirm) return setError("비밀번호가 일치하지 않습니다.");
    if (needsDocs && !agree) return setError("파트너 약관에 동의해주세요.");

    setLoading(true);
    try {
      const role = type === "retailer" ? "retail_seller" : type;
      const payload: Record<string, unknown> = {
        email,
        password,
        role,
        full_name: fullName,
        company_name: companyName,
      };
      if (role === "retail_seller") payload.seller_type = "independent"; // 자가가입 소매 = 라이브셀러

      await api("/auth/register", { method: "POST", body: JSON.stringify(payload) });

      // 도매/에이전시 서류: 가입 직후 로그인하여 인증 상태로 업로드 → 다시 로그아웃(아직 pending)
      if (needsDocs && (bizCert || idDoc)) {
        const { error: signInErr } = await supabase.auth.signInWithPassword({ email, password });
        if (!signInErr) {
          const fd = new FormData();
          if (bizCert) fd.append("business_cert", bizCert);
          if (idDoc) fd.append("id_doc", idDoc);
          try {
            await api("/auth/register/documents", { method: "POST", body: fd, auth: true });
          } catch {
            /* 서류 업로드 실패해도 가입은 유지(승인 단계에서 보완) */
          }
          await supabase.auth.signOut();
        }
      }
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "가입에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <AuthShell>
        <div className="flex size-12 items-center justify-center rounded-full bg-[var(--color-success-bg)] text-[var(--color-success-fg)]">
          <Check />
        </div>
        <h1 className="mt-5 text-3xl font-extrabold tracking-tight text-foreground">가입 신청 완료</h1>
        <p className="mt-3 text-muted-foreground">
          계정이 생성되었습니다. <strong className="text-foreground">관리자 승인</strong> 후 로그인할 수 있습니다.
          {needsDocs && " 제출하신 사업자 서류를 검토합니다."}
        </p>
        <Link href="/login" className="mt-8 inline-block">
          <Button>로그인 화면으로</Button>
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div className="mb-6">
        <SegTabs options={MEMBER_OPTIONS} value={type} onChange={setType} />
      </div>

      <h1 className="text-3xl font-extrabold tracking-tight text-foreground">{copy.title}</h1>
      <p className="mt-2 text-muted-foreground">{copy.subtitle}</p>

      <form onSubmit={onSubmit} className="mt-7 space-y-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="성명"
            name="full_name"
            required
            placeholder="홍길동"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <TextField
            label="회사명"
            name="company_name"
            placeholder="주식회사 이지머스"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
          />
        </div>

        <TextField
          label="이메일"
          type="email"
          name="email"
          autoComplete="email"
          required
          placeholder="name@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="비밀번호"
            type="password"
            name="password"
            autoComplete="new-password"
            required
            placeholder="8자 이상"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <TextField
            label="비밀번호 확인"
            type="password"
            name="confirm"
            autoComplete="new-password"
            required
            placeholder="••••••••"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>

        {needsDocs && (
          <div className="space-y-3 pt-1">
            <p className="text-sm font-semibold text-[var(--color-text-secondary)]">
              비즈니스 인증 <span className="font-normal text-muted-foreground">(선택 · 승인 전 제출 권장)</span>
            </p>
            <FileRow
              title="사업자등록증"
              hint="JPG, PNG, PDF (MAX 5MB)"
              file={bizCert}
              onPick={setBizCert}
            />
            <FileRow
              title="신분증"
              hint="주민등록증 또는 운전면허증 · 주민번호 마스킹 권장"
              file={idDoc}
              onPick={setIdDoc}
              variant="secondary"
            />
            <Checkbox
              checked={agree}
              onChange={(e) => setAgree(e.target.checked)}
              label={<span className="text-muted-foreground">{copy.terms}</span>}
            />
          </div>
        )}

        <Button type="submit" loading={loading} className="w-full">
          계정 생성{needsDocs && <ArrowRight width={16} height={16} />}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        이미 계정이 있으신가요?{" "}
        <Link href="/login" className="font-semibold text-ink hover:underline">
          로그인
        </Link>
      </p>

      <Modal
        open={!!error}
        onClose={() => setError(null)}
        title="가입을 완료할 수 없습니다"
        description={error ?? undefined}
      />
    </AuthShell>
  );
}
