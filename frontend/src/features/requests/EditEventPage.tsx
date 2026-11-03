import { useNavigate, useParams } from "react-router-dom";
import { updateEvent } from "../../api/requests";
import { StepIndicator } from "../../components/StepIndicator";
import { ErrorState, LoadingState } from "../../components/States";
import { EventDetailsForm } from "./EventDetailsForm";
import { useRequest } from "./useRequest";

export function EditEventPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { request, error, reload } = useRequest(id);

  if (error) return <ErrorState title="Couldn't load the request" message={error} onRetry={reload} />;
  if (!request) return <LoadingState label="Loading request…" />;
  if (!request.editable)
    return <ErrorState title="Can't edit this request" message="Only draft requests can be edited." />;

  const { contact_email, ...event } = request.event;
  return (
    <section className="page page--form" aria-labelledby="edit-event-heading">
      <StepIndicator current={1} />
      <h1 id="edit-event-heading">Edit event details</h1>
      <EventDetailsForm
        initial={event}
        contactEmail={contact_email}
        submitLabel="Save changes"
        onCancel={() => navigate(`/requests/${id}`)}
        onSubmit={async (values) => {
          await updateEvent(id, values);
          navigate(`/requests/${id}`);
        }}
      />
    </section>
  );
}
