import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchFacilities } from "../../api/facilities";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import type { Facility, FacilityGroup } from "../../types/facility";
import { GROUP_LABELS } from "../../utils/format";
import { FacilityCard } from "./FacilityCard";

type Filter = "ALL" | FacilityGroup;
const FILTERS: Filter[] = ["ALL", "LHC", "AUDITORIUM", "SPORTS"];

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; facilities: Facility[] };

export function FacilityCatalogue() {
  const { user } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [filter, setFilter] = useState<Filter>("ALL");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchFacilities(controller.signal)
      .then((data) => setState({ kind: "ready", facilities: data.items }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "Unexpected error while loading facilities.";
        setState({ kind: "error", message });
      });
    return () => controller.abort();
  }, [reloadKey]);

  const retry = useCallback(() => setReloadKey((k) => k + 1), []);

  const visible = useMemo(() => {
    if (state.kind !== "ready") return [];
    return filter === "ALL" ? state.facilities : state.facilities.filter((f) => f.group === filter);
  }, [state, filter]);

  return (
    <section className="page" aria-labelledby="catalogue-heading">
      <div className="page__intro">
        <h1 id="catalogue-heading">Facility catalogue</h1>
        <p>
          Lecture halls, the auditorium and sports grounds available for events. Charges shown are the booking
          tariff per slot before GST, cleaning, security deposit and electricity, which are added when a request is
          costed.
        </p>
      </div>

      <div className="filters" role="group" aria-label="Filter by facility group">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            className={`filter${filter === f ? " filter--active" : ""}`}
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
          >
            {f === "ALL" ? "All facilities" : GROUP_LABELS[f]}
          </button>
        ))}
      </div>

      {state.kind === "loading" && <LoadingState label="Loading facilities…" />}
      {state.kind === "error" && (
        <ErrorState title="Couldn't load facilities" message={state.message} onRetry={retry} />
      )}
      {state.kind === "ready" && visible.length === 0 && (
        <EmptyState message="No facilities are available in this group right now." />
      )}
      {state.kind === "ready" && visible.length > 0 && (
        <>
          <p className="result-count" aria-live="polite">
            Showing {visible.length} of {state.facilities.length} facilities
          </p>
          <div className="grid">
            {visible.map((facility) => (
              <FacilityCard key={facility.id} facility={facility} highlight={user?.rate_category} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
