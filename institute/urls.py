from django.urls import path
from . import views

app_name = 'institute'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add_teacher/', views.add_teacher, name='add_teacher'),
    path('add_class/', views.add_class, name='add_class'),
    path('add_subject/', views.add_subject, name='add_subject'),
]