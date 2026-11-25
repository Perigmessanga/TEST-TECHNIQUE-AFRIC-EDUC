"""
URL configuration for passage_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from core.views import (
    AnomaliesView,
    BadgeActionView,
    BadgeTokenView,
    BadgesView,
    ControlPointsManageView,
    ControlPointsView,
    CsrfView,
    DetectAnomaliesView,
    ExceptionManageView,
    LoginView,
    LogoutView,
    MeView,
    MessagesView,
    NotifyAnomalyView,
    ParentChildrenView,
    PassagesView,
    ParentLinksView,
    RouteManageView,
    RoutesView,
    StudentsView,
    StudentDetailView,
    SummaryView,
    SyncStatusView,
    SyncView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/csrf/', CsrfView.as_view()),
    path('api/login/', LoginView.as_view()),
    path('api/logout/', LogoutView.as_view()),
    path('api/me/', MeView.as_view()),
    path('api/control-points/', ControlPointsView.as_view()),
    path('api/control-points/manage/', ControlPointsManageView.as_view()),
    path('api/control-points/manage/<int:point_id>/', ControlPointsManageView.as_view()),
    path('api/badges/', BadgesView.as_view()),
    path('api/badges/<int:badge_id>/action/', BadgeActionView.as_view()),
    path('api/badges/<int:student_id>/token/', BadgeTokenView.as_view()),
    path('api/sync/', SyncView.as_view()),
    path('api/sync/status/', SyncStatusView.as_view()),
    path('api/students/', StudentsView.as_view()),
    path('api/students/<int:student_id>/', StudentDetailView.as_view()),
    path('api/parent-links/', ParentLinksView.as_view()),
    path('api/parent-links/<int:link_id>/', ParentLinksView.as_view()),
    path('api/routes/', RoutesView.as_view()),
    path('api/routes/manage/', RouteManageView.as_view()),
    path('api/routes/manage/<int:route_id>/', RouteManageView.as_view()),
    path('api/exceptions/', ExceptionManageView.as_view()),
    path('api/passages/', PassagesView.as_view()),
    path('api/anomalies/', AnomaliesView.as_view()),
    path('api/anomalies/detect/', DetectAnomaliesView.as_view()),
    path('api/anomalies/<int:anomaly_id>/state/', AnomaliesView.as_view()),
    path('api/anomalies/<int:anomaly_id>/notify/', NotifyAnomalyView.as_view()),
    path('api/messages/', MessagesView.as_view()),
    path('api/parent/children/', ParentChildrenView.as_view()),
    path('api/summaries/', SummaryView.as_view()),
]
