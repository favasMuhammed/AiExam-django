from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('class/<int:class_id>/manage-students/', views.manage_class_students, name='manage_class_students'),
    path('exam/create/', views.create_exam, name='create_exam'),
    path('exam/<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('exam/<int:exam_id>/generate/', views.generate_questions, name='generate_questions'),
    path('exam/<int:exam_id>/review/', views.review_exam, name='review_exam'),
    path('exam/<int:exam_id>/results/', views.exam_results, name='exam_results'),
    path('exam/<int:exam_id>/review_questions/', views.review_questions, name='review_questions'),
    path('exam/<int:exam_id>/student/<int:student_id>/review/', views.review_student_answers, name='review_student_answers'),
    path('save_answer/', views.save_answer, name='save_answer'),
]