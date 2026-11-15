from src.appointment_export import Appointment, notification_text


def test_cancelled_appointment_uses_non_clinical_notification():
    appointment = Appointment("apt-1", "2026-10-24T09:00:00Z", "cancelled", "North Clinic")

    assert notification_text(appointment) == (
        "Your appointment was cancelled. Please contact the clinic for next steps."
    )
    assert "diagnosis" not in notification_text(appointment).lower()
