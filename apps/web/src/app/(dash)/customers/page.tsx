"use client";
/* eslint-disable react-hooks/set-state-in-effect -- 서버 데이터 동기화 목적의 의도된 effect */

import { useCallback, useEffect, useState } from "react";
import { CustomerTable } from "@/components/CustomerTable";
import { type Customer, listCustomers } from "@/lib/products";

/** 도매 고객관리 — 나에게 배정된 소매 거래처만(서버가 격리). 등급·가격노출 관리. */
export default function CustomersPage() {
  const [rows, setRows] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await listCustomers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "불러오기 실패");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-extrabold tracking-tight text-foreground">고객 관리</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        나에게 배정된 거래처(소매 파트너)의 등급과 가격 노출을 관리합니다.
      </p>
      <div className="mt-6">
        <CustomerTable rows={rows} role="wholesaler" loading={loading} error={error} onChanged={load} />
      </div>
    </div>
  );
}
