import secrets

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Anomaly, Badge, ControlPoint, Establishment, OutgoingMessage, ParentStudent, Profile, Student
from .notifications import dispatch_message


class PassageAPITests(TestCase):
	def setUp(self):
		cache.clear()
		self.client = APIClient()
		self.establishment = Establishment.objects.create(name='École Afric')
		self.agent = self.create_user('agent', 'agent')
		self.manager = self.create_user('responsable', 'responsable')
		self.parent = self.create_user('parent1', 'parent')
		self.other_parent = self.create_user('parent2', 'parent')
		self.student = Student.objects.create(name='Élève A', class_name='6eA', establishment=self.establishment)
		self.other_student = Student.objects.create(name='Élève B', class_name='6eA', establishment=self.establishment)
		self.badge = Badge.objects.create(student=self.student, serial=secrets.token_urlsafe(18), signing_secret=secrets.token_hex(32))
		self.point = ControlPoint.objects.create(establishment=self.establishment, label='Portail entrée', type='portail')
		ParentStudent.objects.create(parent=self.parent, student=self.student)
		ParentStudent.objects.create(parent=self.other_parent, student=self.other_student)

	@staticmethod
	def create_user(username, role):
		user = User.objects.create_user(username=username, password='Test1234')
		Profile.objects.create(user=user, role=role)
		return user

	def authenticate_as(self, user):
		self.client.force_authenticate(user=user)

	def test_all_seed_roles_can_authenticate(self):
		for username, expected_role in [('agent', 'agent'), ('responsable', 'responsable'), ('parent1', 'parent'), ('parent2', 'parent')]:
			client = APIClient()
			response = client.post('/api/login/', {'login': username, 'password': 'Test1234'}, format='json')
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response.data['role'], expected_role)

	def test_me_endpoint_returns_anonymous_state_without_forbidden_response(self):
		response = self.client.get('/api/me/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data, {'authenticated': False})

	def test_login_errors_are_uniform_and_rate_limited(self):
		invalid_password = self.client.post('/api/login/', {'login': 'agent', 'password': 'incorrect'}, format='json')
		absent_user = self.client.post('/api/login/', {'login': 'absent', 'password': 'incorrect'}, format='json')
		self.assertEqual(invalid_password.status_code, 401)
		self.assertEqual(invalid_password.data, absent_user.data)
		for _ in range(4):
			self.client.post('/api/login/', {'login': 'agent', 'password': 'incorrect'}, format='json')
		limited = self.client.post('/api/login/', {'login': 'agent', 'password': 'Test1234'}, format='json')
		self.assertEqual(limited.status_code, 429)

	def test_agent_cannot_read_private_or_analytics_endpoints(self):
		self.authenticate_as(self.agent)
		for path in ['/api/students/', '/api/badges/', '/api/anomalies/', '/api/messages/']:
			self.assertEqual(self.client.get(path).status_code, 403, path)
		self.assertEqual(self.client.post('/api/summaries/', {}, format='json').status_code, 403)
		self.assertEqual(self.client.get('/api/passages/').status_code, 403)
		self.assertEqual(self.client.get('/api/parent/children/').status_code, 403)

	def test_parent_can_only_read_linked_students(self):
		self.authenticate_as(self.parent)
		own = self.client.get(f'/api/students/{self.student.id}/')
		other = self.client.get(f'/api/students/{self.other_student.id}/')
		self.assertEqual(own.status_code, 200)
		self.assertEqual(other.status_code, 403)

	def test_badge_reissue_revokes_old_and_keeps_history(self):
		self.authenticate_as(self.manager)
		old_token = self.client.post(f'/api/badges/{self.student.id}/token/').data['token']
		response = self.client.post(f'/api/badges/{self.badge.id}/action/', {'action': 'reissue'}, format='json')
		self.assertEqual(response.status_code, 201)
		self.badge.refresh_from_db()
		self.assertEqual(self.badge.state, 'révoqué')
		self.assertEqual(self.badge.replaced_by_id, response.data['id'])
		self.assertEqual(Badge.objects.filter(student=self.student, state='actif').count(), 1)
		self.authenticate_as(self.agent)
		revoked_scan = self.client.post('/api/sync/', {'items':[{
			'point_id':self.point.id,
			'local_time':timezone.now().isoformat(),
			'device_id':'test-device',
			'badge_token':old_token,
			'local_event_id':'revoked-badge-event-001',
		}]}, format='json')
		self.assertEqual(revoked_scan.data['rejected'][0]['reason'], 'badge_invalide')

	def test_database_rejects_two_active_badges_for_one_student(self):
		with self.assertRaises(IntegrityError), transaction.atomic():
			Badge.objects.create(student=self.student, serial='second-active', signing_secret=secrets.token_hex(32))

	def test_signed_badge_sync_is_idempotent_and_replay_protected(self):
		self.authenticate_as(self.manager)
		token_response = self.client.post(f'/api/badges/{self.student.id}/token/')
		self.assertEqual(token_response.status_code, 200)
		item = {
			'point_id': self.point.id,
			'local_time': timezone.now().isoformat(),
			'device_id': 'test-device',
			'badge_token': token_response.data['token'],
			'local_event_id': 'event-000000000001',
		}
		self.authenticate_as(self.agent)
		first = self.client.post('/api/sync/', {'items': [item]}, format='json')
		same_event = self.client.post('/api/sync/', {'items': [item]}, format='json')
		self.assertEqual(first.data['accepted'], 1)
		self.assertEqual(same_event.data['duplicates'], 1)
		different_event = dict(item, local_event_id='event-000000000002')
		replay = self.client.post('/api/sync/', {'items': [different_event]}, format='json')
		self.assertEqual(replay.data['rejected'][0]['reason'], 'badge_deja_utilise')

	def test_sync_rejects_malformed_events_without_breaking_valid_items(self):
		self.authenticate_as(self.manager)
		token = self.client.post(f'/api/badges/{self.student.id}/token/').data['token']
		self.authenticate_as(self.agent)
		valid_item = {
			'point_id': self.point.id,
			'local_time': timezone.localtime().replace(tzinfo=None).isoformat(),
			'device_id': 'test-device',
			'badge_token': token,
			'local_event_id': 'event-valid-000001',
		}
		malformed = dict(valid_item, local_event_id='')
		response = self.client.post('/api/sync/', {'items': [malformed, valid_item]}, format='json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data['accepted'], 1)
		self.assertEqual(response.data['rejected'][0]['reason'], 'identifiant_evenement_invalide')

	@override_settings(MESSAGE_DAILY_LIMIT=1)
	def test_notifications_are_queued_deduplicated_and_capped(self):
		self.authenticate_as(self.manager)
		anomaly = Anomaly.objects.create(student=self.student, type='double_scan', date=timezone.localdate())
		first = self.client.post(f'/api/anomalies/{anomaly.id}/notify/', {}, format='json')
		second = self.client.post(f'/api/anomalies/{anomaly.id}/notify/', {}, format='json')
		self.assertEqual(first.data['queued'], 1)
		self.assertEqual(second.data['duplicates'], 1)
		message = OutgoingMessage.objects.get(parent=self.parent, anomaly=anomaly)
		self.assertEqual(message.state, 'pending')
		self.assertIsNone(message.sent_at)
		another = Anomaly.objects.create(student=self.student, type='hors_fenetre', date=timezone.localdate())
		capped = self.client.post(f'/api/anomalies/{another.id}/notify/', {}, format='json')
		self.assertEqual(capped.data['suppressed'], 1)
		self.assertEqual(OutgoingMessage.objects.get(parent=self.parent, anomaly=another).state, 'suppressed')

	def test_notification_provider_failures_are_recorded_and_retriable(self):
		self.parent.email = 'parent@example.test'
		self.parent.save(update_fields=['email'])
		anomaly = Anomaly.objects.create(student=self.student, type='double_scan', date=timezone.localdate())
		message = OutgoingMessage.objects.create(parent=self.parent, anomaly=anomaly, text='Info', state='pending')

		class FailingProvider:
			def send(self, recipient, text):
				raise RuntimeError('Fournisseur indisponible')

		with self.assertRaisesRegex(RuntimeError, 'Fournisseur indisponible'):
			dispatch_message(message.id, FailingProvider())
		message.refresh_from_db()
		self.assertEqual(message.state, 'failed')
		self.assertEqual(message.attempt_count, 1)
		self.assertIn('Fournisseur indisponible', message.last_error)
		self.assertIsNone(message.sent_at)

		class SuccessfulProvider:
			def send(self, recipient, text):
				return None

		dispatch_message(message.id, SuccessfulProvider())
		message.refresh_from_db()
		self.assertEqual(message.state, 'sent')
		self.assertEqual(message.attempt_count, 2)
		self.assertIsNotNone(message.sent_at)
