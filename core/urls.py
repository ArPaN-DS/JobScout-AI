from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile_setup, name='profile_setup'),
    path('jobs/', views.job_discovery, name='job_discovery'),
    path('jobs/generate/', views.generate_kit, name='generate_kit'),
    path('jobs/submit/', views.mark_submitted, name='mark_submitted'),
]
