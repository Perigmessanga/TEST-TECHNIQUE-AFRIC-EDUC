from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ExceptionDay, Passage, Route
from core.services import create_anomaly


class Command(BaseCommand):
    help = 'Détecte les passages attendus manquants dont la fenêtre est clôturée.'

    def handle(self, *args, **options):
        now = timezone.localtime()
        weekday = ('L', 'M', 'M', 'J', 'V', 'S', 'D')[now.weekday()]
        created = 0
        routes = Route.objects.filter(days__contains=weekday).select_related('student', 'point')
        for route in routes:
            if route.end_time > now.time():
                continue
            if ExceptionDay.objects.filter(student=route.student, date=now.date()).exists():
                continue
            if Passage.objects.filter(
                badge__student=route.student,
                point=route.point,
                server_time__date=now.date(),
            ).exists():
                continue
            _, was_created = create_anomaly(route.student, 'absence_attendue', now.date())
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'{created} anomalie(s) d’absence créée(s).'))
