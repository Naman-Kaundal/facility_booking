const STEPS = ["Event details", "Facilities & dates", "Review & submit"];

/** Booking form progress. Step 3 (review & submit) arrives in Week 3. */
export function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  return (
    <ol className="steps" aria-label="Booking steps">
      {STEPS.map((label, index) => {
        const step = index + 1;
        const state = step < current ? "done" : step === current ? "current" : "todo";
        return (
          <li key={label} className={`steps__item steps__item--${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="steps__number" aria-hidden="true">
              {step}
            </span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}
