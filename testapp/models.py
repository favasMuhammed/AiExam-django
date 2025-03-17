from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime, time, timedelta

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Exam(TimeStampedModel):
    DIFFICULTY_CHOICES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)
    date = models.DateField()
    start_time = models.TimeField(default=time(9, 0))
    duration = models.IntegerField(help_text="Minutes", validators=[MinValueValidator(1), MaxValueValidator(480)])
    class_name = models.CharField(max_length=50)
    topics = models.TextField()
    syllabus = models.TextField()
    content = models.TextField()
    num_questions = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    total_marks = models.IntegerField(validators=[MinValueValidator(1)])
    instructions = models.TextField()
    difficulty_level = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_exams')
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [models.Index(fields=['date', 'start_time']), models.Index(fields=['created_by'])]

    def __str__(self):
        return f"{self.title} - {self.subject}"

    def is_available(self):
        now = timezone.now()
        exam_dt = timezone.make_aware(datetime.combine(self.date, self.start_time))
        end_dt = exam_dt + timedelta(minutes=self.duration)
        return exam_dt <= now <= end_dt

class Question(TimeStampedModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    correct_answer = models.TextField()
    marks = models.IntegerField(validators=[MinValueValidator(1)])
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Q{self.id} - {self.exam.title}"

class StudentAnswer(TimeStampedModel):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    answer_text = models.TextField()
    score = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_answers')
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ['student', 'question']
        ordering = ['question']

    def __str__(self):
        return f"Answer by {self.student.email} for {self.question}"

    def save(self, *args, **kwargs):
        if self.score is not None and self.score > self.question.marks:
            raise ValueError(f"Score cannot exceed {self.question.marks}")
        if self.score is not None and not self.graded_at:
            self.graded_at = timezone.now()
        super().save(*args, **kwargs)

class ExamAttempt(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'exam']

    def __str__(self):
        return f"{self.student.email} - {self.exam.title}"