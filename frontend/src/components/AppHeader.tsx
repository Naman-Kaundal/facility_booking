import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { desksFor } from "../features/staff/desks";
import { CATEGORY_SHORT } from "../utils/format";

export function AppHeader() {
  const { status, user, signOut } = useAuth();
  const navigate = useNavigate();
  const me = status === "signedIn" ? user : null;

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <NavLink to={me ? "/home" : "/facilities"} className="app-header__brand">
          <span className="app-header__mark" aria-hidden="true">
            IIT
          </span>
          <span>
            <span className="app-header__title">Facility Booking</span>
            <span className="app-header__subtitle">Indian Institute of Technology Ropar</span>
          </span>
        </NavLink>
        <nav aria-label="Main" className="app-header__nav">
          {me && (
            <>
              <NavLink to="/home" className="app-header__link">
                Home
              </NavLink>
              <NavLink to="/requests" end className="app-header__link">
                My requests
              </NavLink>
              {desksFor(me.roles).map((d) => (
                <NavLink key={d.desk} to={d.path} className="app-header__link">
                  {d.short} desk
                </NavLink>
              ))}
            </>
          )}
          <NavLink to="/facilities" className="app-header__link">
            Facilities
          </NavLink>
          {me ? (
            <span className="app-header__user">
              <span className="app-header__user-name" title={me.email}>
                {me.name}
                {me.rate_category && <span className="app-header__badge">{CATEGORY_SHORT[me.rate_category]}</span>}
              </span>
              <button
                type="button"
                className="app-header__link app-header__signout"
                onClick={() => void signOut().then(() => navigate("/login"))}
              >
                Sign out
              </button>
            </span>
          ) : (
            status !== "loading" && (
              <NavLink to="/login" className="app-header__link">
                Sign in
              </NavLink>
            )
          )}
        </nav>
      </div>
    </header>
  );
}
