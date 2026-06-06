import { Check, X as XIcon } from "./icons";

export type StepState = "done" | "current" | "error" | "upcoming";

/** 4-step 마법사 스텝퍼 (시안 대량 등록). errorStep 지정 시 해당 단계 빨강. */
export function Stepper({
  steps,
  current,
  errorStep,
}: {
  steps: string[];
  current: number;
  errorStep?: number;
}) {
  const stateOf = (i: number): StepState => {
    if (errorStep === i) return "error";
    if (i < current) return "done";
    if (i === current) return "current";
    return "upcoming";
  };

  return (
    <div className="flex items-start">
      {steps.map((label, i) => {
        const st = stateOf(i);
        const last = i === steps.length - 1;
        return (
          <div key={label} className={`flex items-start ${last ? "" : "flex-1"}`}>
            <div className="flex flex-col items-center">
              <Circle state={st} index={i} />
              <span
                className={`mt-2.5 whitespace-nowrap text-sm font-semibold ${
                  st === "error"
                    ? "text-[var(--color-danger)]"
                    : st === "upcoming"
                      ? "text-muted-foreground"
                      : "text-foreground"
                }`}
              >
                {label}
              </span>
            </div>
            {!last && (
              <div className="mt-4 h-0.5 flex-1">
                <div
                  className={`h-full w-full rounded-full ${
                    i < current ? "bg-ink" : "bg-divider"
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Circle({ state, index }: { state: StepState; index: number }) {
  const cls: Record<StepState, string> = {
    done: "bg-ink text-white",
    current: "bg-ink text-white",
    error: "bg-[var(--color-danger)] text-white",
    upcoming: "bg-surface-muted text-muted-foreground",
  };
  return (
    <span className={`flex size-9 items-center justify-center rounded-full text-sm font-bold ${cls[state]}`}>
      {state === "done" ? (
        <Check width={16} height={16} />
      ) : state === "error" ? (
        <XIcon width={16} height={16} />
      ) : (
        index + 1
      )}
    </span>
  );
}
