import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','passage_backend.settings')
import django
django.setup()
from django.contrib.auth.models import User
from core.models import *

Student.objects.all().delete(); Establishment.objects.all().delete(); User.objects.exclude(is_superuser=True).delete()
est=Establishment.objects.create(name='École Afric')
accounts=[('responsable','Responsable','responsable'),('agent','Agent','agent'),('parent1','Parent A','parent'),('parent2','Parent B','parent')]
for username,name,role in accounts:
    u=User.objects.create_user(username=username,email=f'{username}@passage.local',password='Test1234',first_name=name)
    Profile.objects.create(user=u,role=role)
responsable=User.objects.get(username='responsable')
parent1=User.objects.get(username='parent1'); parent2=User.objects.get(username='parent2')
import secrets
students=[]
for i in range(1,6):
    s=Student.objects.create(name=f'Élève {i}',class_name='6eA',establishment=est)
    students.append(s)
    Badge.objects.create(student=s,serial=secrets.token_urlsafe(18),signing_secret=secrets.token_hex(32))
ParentStudent.objects.create(parent=parent1,student=students[0]); ParentStudent.objects.create(parent=parent1,student=students[1]); ParentStudent.objects.create(parent=parent2,student=students[2])
entry=ControlPoint.objects.create(establishment=est,label='Portail entrée',type='portail'); exit_point=ControlPoint.objects.create(establishment=est,label='Portail sortie',type='portail')
for s in students:
    Route.objects.create(student=s,point=entry,sequence=1,start_time='07:00',end_time='07:45',days='LMMJV')
    Route.objects.create(student=s,point=exit_point,sequence=2,start_time='15:30',end_time='16:15',days='LMMJV')
print('Seed Django prêt. Comptes: responsable, agent, parent1, parent2 — mot de passe Test1234')
