import type { ReactElement } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "../auth/RequireAuth";
import { RequireRole } from "../auth/RequireRole";
import { AppHeader } from "../components/AppHeader";
import { ApiStatus } from "../components/ApiStatus";
import { CategoryPage } from "../features/auth/CategoryPage";
import { LoginPage } from "../features/auth/LoginPage";
import { FacilityCatalogue } from "../features/facilities/FacilityCatalogue";
import { HomePage } from "../features/home/HomePage";
import { EditEventPage } from "../features/requests/EditEventPage";
import { FacilityLinesPage } from "../features/requests/FacilityLinesPage";
import { MyRequestsPage } from "../features/requests/MyRequestsPage";
import { NewRequestPage } from "../features/requests/NewRequestPage";
import { RequestDetailPage } from "../features/requests/RequestDetailPage";
import { ReviewSubmitPage } from "../features/requests/ReviewSubmitPage";
import { DeskQueuePage } from "../features/staff/DeskQueuePage";
import { StaffRequestPage } from "../features/staff/StaffRequestPage";

function NotFound() {
  return (
    <section className="page">
      <h1>Page not found</h1>
      <p>
        <Link to="/home">Go to the home page</Link>
      </p>
    </section>
  );
}

const authed = (page: ReactElement) => <RequireAuth>{page}</RequireAuth>;

export function App() {
  return (
    <div className="layout">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <AppHeader />
      <main id="main" className="layout__main">
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/facilities" element={<FacilityCatalogue />} />
          <Route
            path="/profile/category"
            element={
              <RequireAuth allowMissingCategory>
                <CategoryPage />
              </RequireAuth>
            }
          />
          <Route path="/home" element={authed(<HomePage />)} />
          <Route path="/requests" element={authed(<MyRequestsPage />)} />
          <Route path="/requests/new" element={authed(<NewRequestPage />)} />
          <Route path="/requests/:id" element={authed(<RequestDetailPage />)} />
          <Route path="/requests/:id/edit" element={authed(<EditEventPage />)} />
          <Route path="/requests/:id/facilities" element={authed(<FacilityLinesPage />)} />
          <Route path="/requests/:id/review" element={authed(<ReviewSubmitPage />)} />
          <Route
            path="/desk/facilities"
            element={
              <RequireRole roles={["FACILITY"]}>
                <DeskQueuePage desk="FACILITY" />
              </RequireRole>
            }
          />
          <Route
            path="/desk/academic"
            element={
              <RequireRole roles={["ACADEMIC"]}>
                <DeskQueuePage desk="ACADEMIC" />
              </RequireRole>
            }
          />
          <Route
            path="/desk/sports"
            element={
              <RequireRole roles={["SPORTS"]}>
                <DeskQueuePage desk="SPORTS" />
              </RequireRole>
            }
          />
          <Route
            path="/desk/requests/:id"
            element={
              <RequireRole roles={["FACILITY", "ACADEMIC", "SPORTS", "ADMIN"]}>
                <StaffRequestPage />
              </RequireRole>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="app-footer">
        <span>Facilities Section, IIT Ropar</span>
        <ApiStatus />
      </footer>
    </div>
  );
}
