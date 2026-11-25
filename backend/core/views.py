import hashlib
import hmac
import secrets
import time
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Anomaly, Badge, ControlPoint, Passage, ParentStudent, Route, ExceptionDay, Student, Summary, OutgoingMessage, Establishment
from .services import create_anomaly
from .summary_ai import generate_summary_text


def role(user, *roles):
    return hasattr(user, 'profile') and user.profile.role in roles


class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = str(request.data.get('login', '')).strip()[:150]
        password = str(request.data.get('password', ''))
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        key_digest = hashlib.sha256(f'{client_ip}:{username.casefold()}'.encode()).hexdigest()
        attempt_key = f'passage:login:fail:{key_digest}'
        if cache.get(attempt_key, 0) >= settings.LOGIN_FAILURE_LIMIT:
            return Response({'detail':'Identifiants invalides'}, status=429)

        user = authenticate(request, username=username, password=password)
        if not user or not hasattr(user, 'profile'):
            try:
                cache.incr(attempt_key)
            except ValueError:
                cache.add(attempt_key, 1, timeout=settings.LOGIN_FAILURE_WINDOW_SECONDS)
            return Response({'detail':'Identifiants invalides'}, status=401)
        cache.delete(attempt_key)
        login(request, user)
        request.session.set_expiry(3600)
        return Response({'ok':True,'role':user.profile.role,'name':user.get_full_name() or user.username})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'ok':True})


class MeView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        if not request.user.is_authenticated or not hasattr(request.user, 'profile'):
            return Response({'authenticated':False})
        return Response({'name':request.user.get_full_name() or request.user.username,'role':request.user.profile.role})


class ControlPointsView(APIView):
    def get(self, request):
        if not role(request.user,'agent','responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        return Response(list(ControlPoint.objects.values('id','label','type')))


class BadgeTokenView(APIView):
    def post(self, request, student_id):
        if not role(request.user,'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        badge = Badge.objects.filter(student_id=student_id,state='actif').first()
        if not badge:
            return Response({'detail':'Badge actif introuvable'}, status=404)
        nonce = secrets.token_urlsafe(16)
        expires = int(time.time()) + settings.BADGE_TOKEN_TTL_SECONDS
        payload = f'{badge.serial}.{expires}.{nonce}'.encode()
        sig = hmac.new(badge.signing_secret.encode(), payload, hashlib.sha256).hexdigest()
        return Response({'token':payload.decode()+'.'+sig,'expires_at':expires})


class SyncView(APIView):
    def post(self, request):
        if not role(request.user,'agent','responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        items = request.data.get('items',[])
        if not isinstance(items,list) or not 1 <= len(items) <= 100:
            return Response({'detail':'Liste invalide'}, status=400)
        accepted = duplicates = 0
        accepted_events=[]; duplicate_events=[]; rejected=[]
        with transaction.atomic():
            for item in items:
                if not isinstance(item, dict):
                    rejected.append({'event':None,'reason':'format_invalide'})
                    continue
                event = item.get('local_event_id','')
                if not isinstance(event, str) or not event.strip() or len(event) > 100:
                    rejected.append({'event':None,'reason':'identifiant_evenement_invalide'})
                    continue
                if Passage.objects.filter(local_event_id=event).exists():
                    duplicates += 1; duplicate_events.append(event); continue
                try:
                    token = item['badge_token']
                    device_id = item['device_id']
                    if not isinstance(token, str) or len(token) > 300 or not isinstance(device_id, str) or not device_id.strip() or len(device_id) > 100:
                        raise ValueError('Champs de synchronisation invalides')
                    serial,expires_s,nonce,sig=token.split('.')
                    badge=Badge.objects.filter(serial=serial,state='actif').first()
                    if not badge:
                        rejected.append({'event':event,'reason':'badge_invalide'}); continue
                    payload=f'{serial}.{expires_s}.{nonce}'.encode()
                    expected=hmac.new(badge.signing_secret.encode(),payload,hashlib.sha256).hexdigest()
                    if int(expires_s)<int(time.time()) or not hmac.compare_digest(expected,sig):
                        rejected.append({'event':event,'reason':'badge_expire_ou_invalide'}); continue
                    if Passage.objects.filter(nonce=nonce).exists():
                        rejected.append({'event':event,'reason':'badge_deja_utilise'}); continue
                    local_value=item['local_time']
                    if not isinstance(local_value, str) or len(local_value) > 40:
                        raise ValueError('Heure locale invalide')
                    local=datetime.fromisoformat(local_value.replace('Z','+00:00'))
                    if timezone.is_naive(local):
                        local=timezone.make_aware(local, timezone.get_current_timezone())
                    point_id=item['point_id']
                    if not isinstance(point_id, int) or point_id < 1:
                        raise ValueError('Point de contrôle invalide')
                    point=ControlPoint.objects.filter(id=point_id).first()
                    if not point:
                        rejected.append({'event':event,'reason':'point_inconnu'}); continue
                except (KeyError,ValueError,AttributeError):
                    rejected.append({'event':event,'reason':'format_invalide'}); continue
                try:
                    with transaction.atomic():
                        passage = Passage.objects.create(
                            badge=badge,
                            point=point,
                            local_time=local,
                            device_id=device_id,
                            local_event_id=event,
                            nonce=nonce,
                        )
                except IntegrityError:
                    if Passage.objects.filter(local_event_id=event).exists():
                        duplicates += 1; duplicate_events.append(event)
                    else:
                        rejected.append({'event':event,'reason':'badge_deja_utilise'})
                    continue
                accepted += 1; accepted_events.append(event)
                server_now = timezone.localtime()
                day = server_now.date()
                weekday = ('L', 'M', 'M', 'J', 'V', 'S', 'D')[server_now.weekday()]
                student = badge.student
                day_routes = list(
                    Route.objects.filter(student=student)
                    .filter(days__contains=weekday)
                    .select_related('point')
                )
                matching_routes = [route for route in day_routes if route.point_id == point.id]
                if not matching_routes:
                    create_anomaly(student, 'point_inattendu', day, passage)
                elif not any(route.start_time <= server_now.time() <= route.end_time for route in matching_routes):
                    create_anomaly(student, 'hors_fenetre', day, passage)
                recent_duplicate = Passage.objects.filter(
                    badge=badge,
                    server_time__gte=server_now - timedelta(seconds=60),
                ).exclude(pk=passage.pk).exists()
                if recent_duplicate:
                    create_anomaly(student, 'double_scan', day, passage)
                if abs((timezone.now() - local).total_seconds()) > 3600:
                    create_anomaly(student, 'horloge_appareil', day, passage)
        return Response({'accepted':accepted,'duplicates':duplicates,'rejected':rejected,'accepted_events':accepted_events,'duplicate_events':duplicate_events})


class StudentDetailView(APIView):
    def get(self, request, student_id):
        if role(request.user,'parent'):
            if not ParentStudent.objects.filter(parent=request.user,student_id=student_id).exists():
                return Response({'detail':'Accès refusé'},status=403)
        elif not role(request.user,'responsable'):
            return Response({'detail':'Accès refusé'},status=403)
        student=Student.objects.filter(id=student_id).first()
        if not student:
            return Response({'detail':'Élève introuvable'},status=404)
        return Response({'id':student.id,'name':student.name,'class_name':student.class_name,'establishment':student.establishment.name,'state':student.state})

    def patch(self, request, student_id):
        if not role(request.user, 'responsable'):
            return Response({'detail': 'Accès refusé'}, status=403)
        student = Student.objects.filter(pk=student_id).first()
        if not student:
            return Response({'detail': 'Élève introuvable'}, status=404)
        name = request.data.get('name', student.name)
        class_name = request.data.get('class_name', student.class_name)
        state = request.data.get('state', student.state)
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 120:
            return Response({'detail': 'Nom invalide'}, status=400)
        if not isinstance(class_name, str) or not 1 <= len(class_name.strip()) <= 30:
            return Response({'detail': 'Classe invalide'}, status=400)
        if state not in ('actif', 'inactif'):
            return Response({'detail': 'État invalide'}, status=400)
        student.name = name.strip()
        student.class_name = class_name.strip()
        student.state = state
        student.save(update_fields=['name', 'class_name', 'state'])
        return Response({'id': student.id, 'name': student.name, 'class_name': student.class_name, 'state': student.state})


class PassagesView(APIView):
    def get(self, request):
        qs=Passage.objects.select_related('badge__student','point')
        if role(request.user,'parent'):
            ids=ParentStudent.objects.filter(parent=request.user).values_list('student_id',flat=True)
            qs=qs.filter(badge__student_id__in=ids)
        elif not role(request.user,'responsable'):
            return Response({'detail':'Accès interdit'},status=403)
        data=[{'id':p.id,'student':p.badge.student.name,'point':p.point.label,'local_time':p.local_time.isoformat(),'server_time':p.server_time.isoformat(),'device_id':p.device_id,'state':p.state} for p in qs.order_by('-server_time')]
        return Response(data)


class SummaryView(APIView):
    def post(self, request):
        if not role(request.user,'responsable'):
            return Response({'detail':'Accès refusé'},status=403)
        class_name = str(request.data.get('class_name', '')).strip()
        if not class_name or len(class_name) > 30:
            return Response({'detail': 'Classe invalide'}, status=400)
        try:
            summary_date = date.fromisoformat(str(request.data.get('date', timezone.localdate().isoformat())))
        except ValueError:
            return Response({'detail': 'Date invalide'}, status=400)

        students = list(Student.objects.filter(class_name=class_name))
        student_ids = [student.id for student in students]
        summary_weekday = ('L', 'M', 'M', 'J', 'V', 'S', 'D')[summary_date.weekday()]
        passages = list(
            Passage.objects.filter(
                badge__student_id__in=student_ids,
                server_time__date=summary_date,
            ).select_related('badge__student', 'point')
        )
        routes_by_student = {}
        for route in Route.objects.filter(
            student_id__in=student_ids,
            days__contains=summary_weekday,
        ).select_related('point').order_by('sequence'):
            routes_by_student.setdefault(route.student_id, []).append(route)

        passages_by_student = {}
        for passage in passages:
            passages_by_student.setdefault(passage.badge.student_id, []).append(passage)

        present = 0
        late_students = set()
        late_exits = set()
        for student in students:
            student_passages = passages_by_student.get(student.id, [])
            routes = routes_by_student.get(student.id, [])
            if student_passages:
                present += 1
            if not routes:
                continue
            entry_route = routes[0]
            exit_route = routes[-1]
            for passage in student_passages:
                server_local_time = timezone.localtime(passage.server_time).time()
                if passage.point_id == entry_route.point_id and server_local_time > entry_route.end_time:
                    late_students.add(student.id)
                if passage.point_id == exit_route.point_id and not (
                    exit_route.start_time <= server_local_time <= exit_route.end_time
                ):
                    late_exits.add(passage.id)

        counts = {
            'eleves': len(students),
            'present': present,
            'retards': len(late_students),
            'sorties_hors_plage': len(late_exits),
        }
        existing = Summary.objects.filter(class_name=class_name, date=summary_date).first()
        if existing and existing.counts_json == counts:
            return Response({'text': existing.text, 'origin': existing.origin, 'counts': existing.counts_json})
        text, origin = generate_summary_text(counts)
        summary, _ = Summary.objects.update_or_create(
            class_name=class_name,
            date=summary_date,
            defaults={'counts_json': counts, 'text': text, 'origin': origin},
        )
        return Response({'text':summary.text,'origin':summary.origin,'counts':summary.counts_json})


class DetectAnomaliesView(APIView):
    def post(self, request):
        if not role(request.user,'responsable'):
            return Response({'detail':'Accès refusé'},status=403)
        today = timezone.localdate()
        now = timezone.localtime().time()
        weekday = ('L', 'M', 'M', 'J', 'V', 'S', 'D')[today.weekday()]
        count = 0
        for route in Route.objects.select_related('student','point'):
            if weekday not in route.days or route.end_time > now:
                continue
            if ExceptionDay.objects.filter(student=route.student,date=today).exists():
                continue
            if Passage.objects.filter(badge__student=route.student,point=route.point,server_time__date=today).exists():
                continue
            _, created = create_anomaly(route.student, 'absence_attendue', today)
            count += int(created)
        return Response({'created':count})


class CsrfView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class StudentsView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        data=[]
        for s in Student.objects.select_related('establishment'):
            badge=Badge.objects.filter(student=s, state='actif').first()
            data.append({'id':s.id,'name':s.name,'class_name':s.class_name,'establishment':s.establishment.name,'state':s.state,'badge_state':badge.state if badge else 'aucun'})
        return Response(data)
    def post(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        name=str(request.data.get('name','')).strip()
        class_name=str(request.data.get('class_name','')).strip()
        if len(name)<2 or len(class_name)<1:
            return Response({'detail':'Nom ou classe invalide'}, status=400)
        establishment=Establishment.objects.first()
        if not establishment:
            establishment=Establishment.objects.create(name='École Afric')
        student=Student.objects.create(name=name,class_name=class_name,establishment=establishment)
        serial=secrets.token_urlsafe(18)
        Badge.objects.create(student=student,serial=serial,signing_secret=secrets.token_hex(32))
        return Response({'id':student.id,'name':student.name,'badge_state':'actif'}, status=201)


class ParentLinksView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail': 'Accès refusé'}, status=403)
        parents = User.objects.filter(profile__role='parent').order_by('username')
        links = ParentStudent.objects.select_related('parent', 'student').order_by('student__name')
        return Response({
            'parents': [{'id': parent.id, 'username': parent.username} for parent in parents],
            'links': [{
                'id': link.id,
                'parent_id': link.parent_id,
                'parent': link.parent.username,
                'student_id': link.student_id,
                'student': link.student.name,
            } for link in links],
        })

    def post(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail': 'Accès refusé'}, status=403)
        try:
            parent = User.objects.get(pk=int(request.data['parent_id']), profile__role='parent')
            student = Student.objects.get(pk=int(request.data['student_id']))
        except (User.DoesNotExist, Student.DoesNotExist, KeyError, TypeError, ValueError):
            return Response({'detail': 'Compte parent ou élève introuvable'}, status=400)
        link, created = ParentStudent.objects.get_or_create(parent=parent, student=student)
        return Response({
            'id': link.id,
            'parent': parent.username,
            'student': student.name,
            'created': created,
        }, status=201 if created else 200)

    def delete(self, request, link_id):
        if not role(request.user, 'responsable'):
            return Response({'detail': 'Accès refusé'}, status=403)
        link = ParentStudent.objects.filter(pk=link_id).first()
        if not link:
            return Response({'detail': 'Rattachement introuvable'}, status=404)
        link.delete()
        return Response(status=204)


class BadgesView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        return Response([{'id':b.id,'student_id':b.student_id,'student':b.student.name,'state':b.state,'issued_at':b.issued_at.isoformat(),'replaced_by':b.replaced_by_id} for b in Badge.objects.select_related('student').order_by('-issued_at')])


class ControlPointsManageView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        return Response([{'id':p.id,'label':p.label,'type':p.type,'establishment':p.establishment.name} for p in ControlPoint.objects.select_related('establishment')])
    def post(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        label=str(request.data.get('label','')).strip()
        type_name=str(request.data.get('type','portail')).strip()
        if len(label)<2:
            return Response({'detail':'Libellé invalide'}, status=400)
        establishment=Establishment.objects.first()
        point=ControlPoint.objects.create(establishment=establishment,label=label,type=type_name)
        return Response({'id':point.id,'label':point.label,'type':point.type}, status=201)
    def patch(self, request, point_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        point = ControlPoint.objects.filter(pk=point_id).first()
        if not point:
            return Response({'detail':'Point introuvable'}, status=404)
        label = request.data.get('label', point.label)
        type_name = request.data.get('type', point.type)
        if not isinstance(label, str) or not 2 <= len(label.strip()) <= 100:
            return Response({'detail':'Libellé invalide'}, status=400)
        if type_name not in ('portail', 'autobus'):
            return Response({'detail':'Type invalide'}, status=400)
        point.label = label.strip()
        point.type = type_name
        point.save(update_fields=['label', 'type'])
        return Response({'id':point.id,'label':point.label,'type':point.type})
    def delete(self, request, point_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        point = ControlPoint.objects.filter(pk=point_id).first()
        if not point:
            return Response({'detail':'Point introuvable'}, status=404)
        if Route.objects.filter(point=point).exists() or Passage.objects.filter(point=point).exists():
            return Response({'detail':'Ce point est utilisé par un itinéraire ou un passage'}, status=409)
        point.delete()
        return Response(status=204)


class RoutesView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        data=[{'id':r.id,'student_id':r.student_id,'student':r.student.name,'point':r.point.label,'sequence':r.sequence,'start_time':r.start_time.strftime('%H:%M'),'end_time':r.end_time.strftime('%H:%M'),'days':r.days} for r in Route.objects.select_related('student','point').order_by('student_id','sequence')]
        return Response(data)


class AnomaliesView(APIView):
    def get(self, request):
        if role(request.user, 'responsable'):
            qs=Anomaly.objects.select_related('student','passage')
        elif role(request.user, 'parent'):
            ids=ParentStudent.objects.filter(parent=request.user).values_list('student_id',flat=True)
            qs=Anomaly.objects.select_related('student','passage').filter(student_id__in=ids)
        else:
            return Response({'detail':'Accès interdit'}, status=403)
        return Response([{'id':a.id,'student':a.student.name,'type':a.type,'date':a.date.isoformat(),'state':a.state,'passage_id':a.passage_id} for a in qs.order_by('-date','-id')])
    def post(self, request, anomaly_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        anomaly=Anomaly.objects.filter(id=anomaly_id).first()
        if not anomaly:
            return Response({'detail':'Anomalie introuvable'}, status=404)
        state = request.data.get('state', 'traitée')
        if state not in ('nouvelle', 'en_cours', 'traitée', 'ignorée'):
            return Response({'detail':'État invalide'}, status=400)
        anomaly.state=state
        anomaly.save(update_fields=['state'])
        return Response({'id':anomaly.id,'state':anomaly.state})


class MessagesView(APIView):
    def get(self, request):
        if role(request.user, 'responsable'):
            qs=OutgoingMessage.objects.select_related('parent','anomaly__student')
        elif role(request.user, 'parent'):
            qs=OutgoingMessage.objects.select_related('parent','anomaly__student').filter(parent=request.user)
        else:
            return Response({'detail':'Accès interdit'}, status=403)
        return Response([{'id':m.id,'parent':m.parent.username,'student':m.anomaly.student.name,'text':m.text,'state':m.state,'reason':m.reason,'created_at':m.created_at.isoformat()} for m in qs.order_by('-created_at')])


class ParentChildrenView(APIView):
    def get(self, request):
        if not role(request.user, 'parent'):
            return Response({'detail':'Accès réservé aux parents'}, status=403)
        links=ParentStudent.objects.filter(parent=request.user).select_related('student','student__establishment')
        data=[]
        for link in links:
            student=link.student
            passages=Passage.objects.filter(badge__student=student).select_related('point').order_by('-server_time')[:10]
            anomalies=Anomaly.objects.filter(student=student).order_by('-date','-id')[:10]
            data.append({'id':student.id,'name':student.name,'class_name':student.class_name,'establishment':student.establishment.name,'passages':[{'point':p.point.label,'server_time':p.server_time.isoformat(),'state':p.state} for p in passages],'anomalies':[{'id':a.id,'type':a.type,'date':a.date.isoformat(),'state':a.state} for a in anomalies]})
        return Response(data)


class SyncStatusView(APIView):
    def get(self, request):
        if not role(request.user, 'agent','responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        passages=Passage.objects.select_related('point').all()
        if role(request.user, 'agent'):
            device_id=str(request.query_params.get('device_id',''))[:100]
            if not device_id:
                return Response({'server_passages':None,'recent':[]})
            passages=passages.filter(device_id=device_id)
        recent=passages.order_by('-server_time')[:20]
        return Response({'server_passages':passages.count() if role(request.user,'responsable') else None,'recent':[{'id':p.id,'point':p.point.label,'server_time':p.server_time.isoformat(),'state':p.state} for p in recent]})
    

class BadgeActionView(APIView):
    def post(self, request, badge_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        action = str(request.data.get('action','')).strip()
        states = {'revoke':'révoqué', 'suspend':'suspendu', 'lose':'perdu'}
        if action not in (*states.keys(), 'activate', 'reissue'):
            return Response({'detail':'Action invalide'}, status=400)
        with transaction.atomic():
            badge = Badge.objects.select_for_update().select_related('student').filter(id=badge_id).first()
            if not badge:
                return Response({'detail':'Badge introuvable'}, status=404)
            if action == 'reissue':
                if badge.state != 'actif':
                    return Response({'detail':'Seul le badge actif peut être réémis'}, status=409)
                badge.state = 'révoqué'
                badge.save(update_fields=['state'])
                new_badge = Badge.objects.create(
                    student=badge.student,
                    serial=secrets.token_urlsafe(18),
                    signing_secret=secrets.token_hex(32),
                    state='actif',
                )
                badge.replaced_by = new_badge
                badge.save(update_fields=['state', 'replaced_by'])
                return Response({'id':new_badge.id,'state':new_badge.state,'student':new_badge.student.name,'replaces':badge.id}, status=201)
            if action == 'activate' and Badge.objects.filter(student=badge.student, state='actif').exclude(pk=badge.pk).exists():
                return Response({'detail':'Un badge actif existe déjà pour cet élève'}, status=409)
            badge.state = 'actif' if action == 'activate' else states[action]
            badge.save(update_fields=['state'])
            return Response({'id':badge.id,'state':badge.state,'student':badge.student.name})


class RouteManageView(APIView):
    def post(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        try:
            student = Student.objects.get(id=request.data['student_id'])
            point = ControlPoint.objects.get(id=request.data['point_id'])
            sequence = int(request.data.get('sequence', 1))
            start_time = datetime.strptime(request.data.get('start_time', '07:00'), '%H:%M').time()
            end_time = datetime.strptime(request.data.get('end_time', '07:45'), '%H:%M').time()
            days = str(request.data.get('days', 'LMMJV')).strip().upper()
        except (Student.DoesNotExist, ControlPoint.DoesNotExist, KeyError, TypeError, ValueError):
            return Response({'detail':'Élève ou point introuvable'}, status=400)
        if sequence < 1 or start_time >= end_time or not days or any(day not in 'LMMJVSD' for day in days):
            return Response({'detail':'Fenêtre, ordre ou jours invalides'}, status=400)
        route = Route.objects.create(
            student=student,
            point=point,
            sequence=sequence,
            start_time=start_time,
            end_time=end_time,
            days=days
        )
        return Response({'id':route.id,'student':student.name,'point':point.label}, status=201)
    def delete(self, request, route_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        route = Route.objects.filter(pk=route_id).first()
        if not route:
            return Response({'detail':'Itinéraire introuvable'}, status=404)
        route.delete()
        return Response(status=204)


class ExceptionManageView(APIView):
    def get(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        return Response([{
            'id': item.id,
            'student_id': item.student_id,
            'student': item.student.name,
            'date': item.date.isoformat(),
            'kind': item.kind,
        } for item in ExceptionDay.objects.select_related('student').order_by('-date')])

    def post(self, request):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        try:
            student = Student.objects.get(id=request.data['student_id'])
            date = timezone.datetime.strptime(request.data['date'], '%Y-%m-%d').date()
        except (Student.DoesNotExist, KeyError, ValueError):
            return Response({'detail':'Élève ou date invalide'}, status=400)
        exception = ExceptionDay.objects.create(
            student=student,
            date=date,
            kind=str(request.data.get('kind','absence_justifiée')),
            approved_by=request.user
        )
        return Response({'id':exception.id,'kind':exception.kind,'date':exception.date.isoformat()}, status=201)


class NotifyAnomalyView(APIView):
    def post(self, request, anomaly_id):
        if not role(request.user, 'responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        anomaly = Anomaly.objects.select_related('student').filter(id=anomaly_id).first()
        if not anomaly:
            return Response({'detail':'Anomalie introuvable'}, status=404)
        limit = max(0, settings.MESSAGE_DAILY_LIMIT)
        today = timezone.localdate()
        created = 0
        blocked = 0
        duplicates = 0
        for link in ParentStudent.objects.filter(student=anomaly.student).select_related('parent'):
            with transaction.atomic():
                User.objects.select_for_update().filter(pk=link.parent_id).first()
                prior = OutgoingMessage.objects.filter(parent=link.parent, anomaly=anomaly).first()
                if prior:
                    duplicates += 1
                    continue
                queued_today = OutgoingMessage.objects.filter(
                    parent=link.parent,
                    created_at__date=today,
                    state__in=['pending', 'sending', 'sent'],
                ).count()
                text = f"Information scolaire : une anomalie {anomaly.type} a été enregistrée pour votre enfant."
                if queued_today >= limit:
                    OutgoingMessage.objects.create(parent=link.parent, anomaly=anomaly, text=text, state='suppressed', reason='plafond journalier')
                    blocked += 1
                else:
                    OutgoingMessage.objects.create(parent=link.parent, anomaly=anomaly, text=text, state='pending', reason='En attente du fournisseur de notification')
                    created += 1
        return Response({'queued':created,'suppressed':blocked,'duplicates':duplicates,'anomaly':anomaly_id}, status=202)
