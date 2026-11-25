from django.conf import settings
from django.db import models

class Establishment(models.Model):
    name = models.CharField(max_length=120)

class Student(models.Model):
    name = models.CharField(max_length=120)
    class_name = models.CharField(max_length=30)
    establishment = models.ForeignKey(Establishment, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, default='actif')

class ParentStudent(models.Model):
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='linked_children')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents')
    class Meta:
        unique_together = ('parent', 'student')

class Badge(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='badges')
    active_student = models.OneToOneField(Student, null=True, blank=True, on_delete=models.PROTECT, related_name='active_badge')
    serial = models.CharField(max_length=80, unique=True)
    signing_secret = models.CharField(max_length=64)
    state = models.CharField(max_length=20, choices=[('actif', 'Actif'), ('suspendu', 'Suspendu'), ('perdu', 'Perdu'), ('révoqué', 'Révoqué')], default='actif')
    issued_at = models.DateTimeField(auto_now_add=True)
    replaced_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replaces')

    def save(self, *args, **kwargs):
        self.active_student_id = self.student_id if self.state == 'actif' else None
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'active_student'}
        super().save(*args, **kwargs)

class ControlPoint(models.Model):
    establishment = models.ForeignKey(Establishment, on_delete=models.PROTECT)
    label = models.CharField(max_length=100)
    type = models.CharField(max_length=30)

class Route(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    point = models.ForeignKey(ControlPoint, on_delete=models.PROTECT)
    sequence = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    days = models.CharField(max_length=20)

class ExceptionDay(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    kind = models.CharField(max_length=30)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

class Passage(models.Model):
    badge = models.ForeignKey(Badge, on_delete=models.PROTECT)
    point = models.ForeignKey(ControlPoint, on_delete=models.PROTECT)
    local_time = models.DateTimeField()
    server_time = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=100)
    local_event_id = models.CharField(max_length=100, unique=True)
    nonce = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=30, default='synchronise')

class Anomaly(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    type = models.CharField(max_length=40)
    date = models.DateField()
    passage = models.ForeignKey(Passage, null=True, blank=True, on_delete=models.SET_NULL)
    state = models.CharField(max_length=20, default='nouvelle')

class OutgoingMessage(models.Model):
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anomaly = models.ForeignKey(Anomaly, on_delete=models.CASCADE)
    text = models.TextField()
    state = models.CharField(max_length=20, choices=[('pending', 'En attente'), ('sending', 'En cours'), ('sent', 'Envoyé'), ('failed', 'Échec'), ('suppressed', 'Plafonné')], default='pending')
    reason = models.CharField(max_length=200, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['parent', 'anomaly'], name='one_notification_per_parent_anomaly'),
        ]

class Summary(models.Model):
    class_name = models.CharField(max_length=30)
    date = models.DateField()
    counts_json = models.JSONField()
    text = models.TextField()
    origin = models.CharField(max_length=20)

class AICall(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    model = models.CharField(max_length=100)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    status = models.CharField(max_length=20)

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=[('agent','Agent'),('responsable','Responsable'),('parent','Parent')])
