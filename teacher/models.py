from django.db import models
from common.models import TimeStampedModel
from institute.models import Institution, Class, Subject
from users.models import User
from django.utils import timezone
from datetime import datetime, timedelta

class ExamTemplate(TimeStampedModel):
    name = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topics = models.TextField()
    num_questions = models.IntegerField()
    total_marks = models.IntegerField()
    difficulty_level = models.CharField(max_length=10, choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Exam(TimeStampedModel):
    DIFFICULTY_CHOICES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classes = models.ManyToManyField(Class)
    date = models.DateField()
    start_time = models.TimeField()
    duration = models.IntegerField(help_text="Minutes")
    topics = models.TextField()
    num_questions = models.IntegerField()
    total_marks = models.IntegerField()
    instructions = models.TextField(blank=True)
    difficulty_level = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exams_created')
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    template = models.ForeignKey(ExamTemplate, on_delete=models.SET_NULL, null=True, blank=True)

    def is_available(self):
        now = timezone.now()
        exam_dt = timezone.make_aware(datetime.combine(self.date, self.start_time))
        end_dt = exam_dt + timedelta(minutes=self.duration)
        return exam_dt <= now <= end_dt

class Question(TimeStampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    correct_answer = models.TextField()
    marks = models.IntegerField()
    explanation = models.TextField(blank=True)

class StudentAnswer(TimeStampedModel):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    score = models.IntegerField(null=True, blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_answers')
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    ai_score = models.IntegerField(null=True, blank=True)
    ai_feedback = models.TextField(blank=True)

class ExamAttempt(TimeStampedModel):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

