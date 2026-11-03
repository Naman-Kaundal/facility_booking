import { useNavigate } from "react-router-dom";
import { createDraft } from "../../api/requests";
import { useAuth } from "../../auth/AuthContext";
import { LoadingState } from "../../components/States";
import { StepIndicator } from "../../components/StepIndicator";
import { EventDetailsForm } from "./EventDetailsForm";

export function NewRequestPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // The form copies the user's name once when it first renders, so wait until we know who is signed in.
  if (!user) return <LoadingState label="Loading…" />;

  return (
    <section className="page page--form" aria-labelledby="new-request-heading">
      <StepIndicator current={1} />
      <h1 id="new-request-heading">New booking request</h1>
      <p className="muted">Tell us about the event. You'll add facilities, dates and slots in the next step.</p>
      <EventDetailsForm
        contactEmail={user.email}
        initial={{ applicant_name: user.name }}
        submitLabel="Save and add facilities"
        onCancel={() => navigate("/home")}
        onSubmit={async (event) => {
          const draft = await createDraft(event);
          navigate(`/requests/${draft.id}/facilities`);
        }}
      />
    </section>
  );
}
