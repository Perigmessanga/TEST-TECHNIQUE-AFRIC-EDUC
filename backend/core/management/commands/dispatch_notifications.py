from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import OutgoingMessage
from core.notifications import DjangoEmailProvider, dispatch_message


class Command(BaseCommand):
    help = 'Envoie les notifications en attente par SMTP si l’envoi est explicitement activé.'

    def add_arguments(self, parser):
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **options):
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            raise CommandError('Configurez EMAIL_HOST et DEFAULT_FROM_EMAIL avant l’envoi.')
        provider = DjangoEmailProvider()
        sent = failed = 0
        states = ['pending', 'failed'] if options['retry_failed'] else ['pending']
        messages = OutgoingMessage.objects.filter(state__in=states).order_by('created_at')
        for message in messages:
            try:
                dispatch_message(message.pk, provider)
                sent += 1
            except Exception as error:
                failed += 1
                self.stderr.write(f'Message {message.pk}: {error}')
        self.stdout.write(self.style.SUCCESS(f'{sent} envoyé(s), {failed} échec(s).'))
