import hashlib
import hmac
import secrets
import time
from datetime import datetime

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Anomaly, Badge, ControlPoint, Passage, ParentStudent, Route, ExceptionDay, Student, Summary


def role(user, *roles):
    return hasattr(user, 'profile') and user.profile.role in roles


class LoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        user = authenticate(request, username=request.data.get('login',''), password=request.data.get('password',''))
        if not user:
            return Response({'detail':'Identifiants invalides'}, status=401)
        login(request, user)
        return Response({'ok':True,'role':user.profile.role,'name':user.get_full_name() or user.username})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'ok':True})


class MeView(APIView):
    def get(self, request):
        return Response({'name':request.user.get_full_name() or request.user.username,'role':request.user.profile.role})


class ControlPointsView(APIView):
    def get(self, request):
        if not role(request.user,'agent','responsable'):
            return Response({'detail':'Accès refusé'}, status=403)
        return Response(list(ControlPoint.objects.values('id','label','type')))


class BadgeTokenView(APIView):
    def post(self, request, student_id):
        if not role(request.user,'responsable','agent'):
            return Response({'detail':'Accès refusé'}, status=403)
        badge = Badge.objects.filter(student_id=student_id,state='actif').first()
        if not badge:
            return Response({'detail':'Badge actif introuvable'}, status=404)
        nonce = secrets.token_urlsafe(16)
        expires = int(time.time()) + 30
        payload = f'{badge.serial}.{expires}.{nonce}'.encode()
        sig = hmac.new(badge.signing_secret.encode(), payload, hashlib.sha256).hexdigest()[:16]
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
                event = item.get('local_event_id','')
                if Passage.objects.filter(local_event_id=event).exists():
                    duplicates += 1; duplicate_events.append(event); continue
                try:
                    serial,expires_s,nonce,sig=item['badge_token'].split('.')
                    badge=Badge.objects.filter(serial=serial,state='actif').first()
                    if not badge:
                        rejected.append({'event':event,'reason':'badge_invalide'}); continue
                    payload=f'{serial}.{expires_s}.{nonce}'.encode()
                    expected=hmac.new(badge.signing_secret.encode(),payload,hashlib.sha256).hexdigest()[:16]
                    if int(expires_s)<int(time.time()) or not hmac.compare_digest(expected,sig):
                        rejected.append({'event':event,'reason':'badge_expire_ou_invalide'}); continue
                    if Passage.objects.filter(nonce=nonce).exists():
                        rejected.append({'event':event,'reason':'badge_deja_utilise'}); continue
                    local=datetime.fromisoformat(item['local_time'].replace('Z','+00:00'))
                    if abs((timezone.now()-local).total_seconds())>3600:
                        rejected.append({'event':event,'reason':'heure_locale_invalide'}); continue
                    point=ControlPoint.objects.filter(id=item['point_id']).first()
                    if not point:
                        rejected.append({'event':event,'reason':'point_inconnu'}); continue
                except (KeyError,ValueError,AttributeError):
                    rejected.append({'event':event,'reason':'format_invalide'}); continue
                Passage.objects.create(badge=badge,point=point,local_time=local,device_id=item['device_id'],local_event_id=event,nonce=nonce)
                accepted += 1; accepted_events.append(event)
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
        class_name=request.data.get('class_name','6eA')
        date=request.data.get('date',timezone.localdate().isoformat())
        existing=Summary.objects.filter(class_name=class_name,date=date).first()
        if existing:
            return Response({'text':existing.text,'origin':existing.origin,'counts':existing.counts_json})
        students=list(Student.objects.filter(class_name=class_name))
        present=sum(1 for student in students if Passage.objects.filter(badge__student=student,server_time__date=date).exists())
        counts={'eleves':len(students),'present':present,'retards':0,'sorties_hors_plage':0}
        text=f"{counts['eleves']} élèves, {counts['present']} présents, {counts['retards']} retards au portail, {counts['sorties_hors_plage']} sorties hors plage."
        summary=Summary.objects.create(class_name=class_name,date=date,counts_json=counts,text=text,origin='gabarit')
        return Response({'text':summary.text,'origin':summary.origin,'counts':summary.counts_json})


class DetectAnomaliesView(APIView):
    def post(self, request):
        if not role(request.user,'responsable'):
            return Response({'detail':'Accès refusé'},status=403)
        today=timezone.localdate(); now=timezone.localtime().time(); count=0
        for route in Route.objects.select_related('student','point'):
            if route.end_time > now:
                continue
            if ExceptionDay.objects.filter(student=route.student,date=today).exists():
                continue
            if Passage.objects.filter(badge__student=route.student,point=route.point,server_time__date=today).exists():
                continue
            if not Anomaly.objects.filter(student=route.student,type='absence_attendue',date=today).exists():
                Anomaly.objects.create(student=route.student,type='absence_attendue',date=today); count+=1
        return Response({'created':count})
