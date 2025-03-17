from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('exam/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('exam/<int:exam_id>/submit/', views.submit_exam, name='submit_exam'),
    path('exam/<int:exam_id>/results/', views.exam_results, name='exam_results'),
    path('exam/<int:exam_id>/status/', views.exam_status, name='exam_status'),
    path('save-answer/', views.save_answer, name='save_answer'),
]