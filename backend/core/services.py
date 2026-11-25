from django.conf import settings
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Anomaly, OutgoingMessage, ParentStudent


def create_anomaly(student, anomaly_type, day, passage=None):
    filters = {
        'student': student,
        'type': anomaly_type,
        'date': day,
        'passage': passage,
    }
    anomaly = Anomaly.objects.filter(**filters).first()
    if anomaly:
        return anomaly, False

    anomaly = Anomaly.objects.create(**filters)
    queue_anomaly_notifications(anomaly)
    return anomaly, True


def queue_anomaly_notifications(anomaly):
    limit = max(0, settings.MESSAGE_DAILY_LIMIT)
    today = timezone.localdate()
    for link in ParentStudent.objects.filter(student=anomaly.student).select_related('parent'):
        with transaction.atomic():
            prior = OutgoingMessage.objects.filter(parent=link.parent, anomaly=anomaly).first()
            if prior:
                continue
            User.objects.select_for_update().filter(pk=link.parent_id).first()
            sent_or_queued = OutgoingMessage.objects.filter(
                parent=link.parent,
                created_at__date=today,
                state__in=['pending', 'sending', 'sent'],
            ).count()
            state = 'suppressed' if sent_or_queued >= limit else 'pending'
            reason = 'plafond journalier' if state == 'suppressed' else 'En attente du fournisseur'
            try:
                with transaction.atomic():
                    OutgoingMessage.objects.create(
                        parent=link.parent,
                        anomaly=anomaly,
                        text=(
                            'Information scolaire : un événement nécessitant votre attention '
                            'a été enregistré pour votre enfant.'
                        ),
                        state=state,
                        reason=reason,
                    )
            except IntegrityError:
                # Another request may have queued the same parent/anomaly concurrently.
                continue
