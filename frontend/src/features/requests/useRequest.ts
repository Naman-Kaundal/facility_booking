import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { getRequest } from "../../api/requests";
import type { BookingRequest } from "../../types/request";

/** Loads one request; `setRequest` lets pages apply the updated request returned by edits. */
export function useRequest(id: number) {
  const [request, setRequest] = useState<BookingRequest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setError(null);
    getRequest(id)
      .then(setRequest)
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  useEffect(reload, [reload]);

  return { request, setRequest, error, reload };
}
