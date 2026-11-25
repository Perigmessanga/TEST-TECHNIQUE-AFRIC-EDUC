from typing import Protocol

from django.db import transaction
from django.utils import timezone

from .models import OutgoingMessage


class NotificationProvider(Protocol):
    def send(self, recipient: str, message: str) -> None:
        """Send the message or raise an exception with a provider error."""


class NotificationProviderUnavailable(Exception):
    pass


class UnconfiguredNotificationProvider:
    def send(self, recipient: str, message: str) -> None:
        raise NotificationProviderUnavailable('Aucun fournisseur de notification configuré')


def dispatch_message(message_id: int, provider: NotificationProvider) -> OutgoingMessage:
    """Dispatch one queued message and persist the real delivery outcome."""
    with transaction.atomic():
        message = OutgoingMessage.objects.select_for_update().select_related('parent').get(pk=message_id)
        if message.state == 'sent':
            return message
        if message.state == 'suppressed':
            raise ValueError('Une notification plafonnée ne peut pas être envoyée')
        if message.state == 'sending':
            raise ValueError('Cette notification est déjà en cours d’envoi')
        message.state = 'sending'
        message.attempt_count += 1
        message.last_error = ''
        message.save(update_fields=['state', 'attempt_count', 'last_error', 'updated_at'])
        recipient = message.parent.email
        text = message.text

    try:
        if not recipient:
            raise ValueError('Le parent ne possède pas d’adresse de notification')
        provider.send(recipient, text)
    except Exception as error:
        message.state = 'failed'
        message.last_error = str(error)[:2000]
        message.reason = 'Échec fournisseur'
        message.save(update_fields=['state', 'last_error', 'reason', 'updated_at'])
        raise

    message.state = 'sent'
    message.sent_at = timezone.now()
    message.last_error = ''
    message.reason = ''
    message.save(update_fields=['state', 'sent_at', 'last_error', 'reason', 'updated_at'])
    return message
