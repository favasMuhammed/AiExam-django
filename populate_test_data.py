import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
import django
django.setup()

from users.models import User
from institute.models import Institution, Class, Subject, TeacherProfile
from teacher.models import Exam, Question, StudentAnswer, ExamAttempt
from datetime import date, time
from django.utils import timezone

# Manager
manager = User.objects.create_user(email='manager@example.com', password='1234', is_manager=True)
institution = Institution.objects.create(name="Test Institute", manager=manager)

# Institute Classes and Subjects
class_10a = Class.objects.create(name="10A", institution=institution)
subject_math = Subject.objects.create(name="Math", institution=institution)

# Teacher
teacher = User.objects.create_user(email='teacher@example.com', password='1234', is_teacher=True)
teacher_profile = TeacherProfile.objects.create(user=teacher, institution=institution)
teacher_profile.classes.add(class_10a)
teacher_profile.subjects.add(subject_math)

# Student
student = User.objects.create_user(email='student@example.com', password='1234', is_student=True)

# Exam
exam = Exam.objects.create(
    title="Math Test", subject=subject_math, date=date(2025, 3, 4), start_time=time(9, 0),
    duration=60, topics="Algebra", num_questions=2, total_marks=20, created_by=teacher,
    is_approved=True, instructions="Solve all questions."
)
exam.classes.add(class_10a)

# Questions
q1 = Question.objects.create(exam=exam, question_text="What is 2+2?", correct_answer="4", marks=10)
q2 = Question.objects.create(exam=exam, question_text="Solve x+3=5", correct_answer="x=2", marks=10)

# Student Attempt
attempt = ExamAttempt.objects.create(student=student, exam=exam)
StudentAnswer.objects.create(student=student, question=q1, answer_text="4", score=10, graded_at=timezone.now())
StudentAnswer.objects.create(student=student, question=q2, answer_text="x=3", score=5, graded_at=timezone.now())

print("Test data populated successfully!")