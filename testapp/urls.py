from django.urls import path
from . import views

app_name = 'testapp'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('exam/create/', views.create_exam, name='create_exam'),
    # path('exam/<int:exam_id>/generate/', views.generate_questions, name='generate_questions'),
    path('exam/<int:exam_id>/review/', views.review_exam, name='review_exam'),
    path('exam/<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('exam/<int:exam_id>/delete/', views.delete_exam, name='delete_exam'),
    path('exam/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('exam/<int:exam_id>/submit/', views.submit_exam, name='submit_exam'),
    path('exam/<int:exam_id>/results/', views.exam_results, name='exam_results'),
    path('pending-grading/', views.pending_grading, name='pending_grading'),
    path('api/save-answer/', views.save_answer, name='save_answer'),
    path('api/update-grade/', views.update_grade, name='update_grade'),
    path('api/exam-status/<int:exam_id>/', views.exam_status, name='exam_status'),
    
]