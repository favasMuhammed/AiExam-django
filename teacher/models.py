from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.translation import gettext_lazy as _
from common.models import TimeStampedModel
from institute.models import Institution, Class, Subject
from users.models import User
import uuid
from django.core.exceptions import ValidationError


class ExamTemplate(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topics = models.TextField(help_text=_("Comma-separated list of topics covered"))
    num_questions = models.IntegerField(validators=[MinValueValidator(1)])
    total_marks = models.IntegerField(validators=[MinValueValidator(1)])
    difficulty_level = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_templates')
    is_shared = models.BooleanField(default=False, help_text=_("Allow other teachers to use this template"))

    def __str__(self):
        return f"{self.name} ({self.subject})"

    class Meta:
        verbose_name = "Exam Template"
        verbose_name_plural = "Exam Templates"
        indexes = [models.Index(fields=['subject', 'difficulty_level'])]

    def clean(self):
        if self.num_questions <= 0 or self.total_marks <= 0:
            raise ValidationError(_("Number of questions and total marks must be positive."))

class Exam(TimeStampedModel):
    DIFFICULTY_CHOICES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
    ]

    title = models.CharField(max_length=200, unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    classes = models.ManyToManyField(Class, related_name='exams')
    date = models.DateField()
    start_time = models.TimeField()
    duration = models.IntegerField(
        help_text=_("Duration in minutes"),
        validators=[MinValueValidator(1)]
    )
    topics = models.TextField(help_text=_("Comma-separated list of topics"))
    num_questions = models.IntegerField(validators=[MinValueValidator(1)])
    total_marks = models.IntegerField(validators=[MinValueValidator(1)])
    instructions = models.TextField(blank=True)
    difficulty_level = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exams_created')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        help_text=_("Current status of the exam")
    )
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    template = models.ForeignKey(
        ExamTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams'
    )
    randomize_questions = models.BooleanField(
        default=False,
        help_text=_("Randomize question order for each student")
    )

    def is_available(self):
        now = timezone.now()
        exam_dt = timezone.make_aware(datetime.combine(self.date, self.start_time))
        end_dt = exam_dt + timedelta(minutes=self.duration)
        return exam_dt <= now <= end_dt and self.is_active and self.is_approved

    def total_submissions(self):
        return self.attempts.filter(completed=True).count()

    def average_score(self):
        from django.db.models import Avg
        avg = self.student_answers.aggregate(Avg('score'))['score__avg']
        return round(avg, 2) if avg is not None else 0

    def __str__(self):
        return f"{self.title} ({self.subject})"

    class Meta:
        verbose_name = "Exam"
        verbose_name_plural = "Exams"
        indexes = [
            models.Index(fields=['date', 'start_time']),
            models.Index(fields=['status', 'is_published']),
        ]

    def clean(self):
        # Only perform validation involving related objects if the instance is saved
        if self.pk is not None:
            total_question_marks = self.questions.aggregate(total=models.Sum('marks'))['total'] or 0
            if self.total_marks < total_question_marks:
                raise ValidationError(
                    f"Total marks ({self.total_marks}) cannot be less than the sum of question marks ({total_question_marks})."
                )
        # Add other validations that don't depend on related objects
        if self.total_marks <= 0:
            raise ValidationError("Total marks must be greater than 0.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Question(TimeStampedModel):
    QUESTION_TYPES = [
        ('essay', 'Essay'),
        ('mcq', 'Multiple Choice'),
        ('short_answer', 'Short Answer'),
    ]

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='questions',
        help_text=_("The exam this question is associated with.")
    )
    question_text = models.TextField(help_text=_("The content of the question."))
    correct_answer = models.TextField(help_text=_("The expected correct answer for the question."))
    marks = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text=_("The number of marks allocated to this question.")
    )
    explanation = models.TextField(
        blank=True,
        help_text=_("Optional explanation or hint for the question.")
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text=_("The sequence number of the question in the exam."),
        db_index=True
    )
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default='essay',
        help_text=_("The type of question (e.g., Essay, Multiple Choice, Short Answer).")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this question is currently active in the exam.")
    )

    class Meta:
        verbose_name = _("Question")
        verbose_name_plural = _("Questions")
        ordering = ['order']
        unique_together = ('exam', 'order')

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}... ({self.exam.title})"

    def is_complete(self):
        return bool(self.question_text and self.correct_answer and self.marks > 0)

    def clean(self):
        if self.marks <= 0:
            raise ValidationError({'marks': _("Marks must be greater than 0.")})
        if not self.question_text.strip():
            raise ValidationError({'question_text': _("Question text cannot be empty.")})
        if not self.correct_answer.strip():
            raise ValidationError({'correct_answer': _("Correct answer cannot be empty.")})
        if self.order < 1:
            raise ValidationError({'order': _("Order must be a positive integer.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class StudentAnswer(TimeStampedModel):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exam_answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='student_answers',
        help_text=_("The exam this answer pertains to.")
    )
    answer_text = models.TextField(default="No answer provided", help_text=_("The student's response to the question."))
    score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Teacher-assigned score")
    )
    graded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_answers'
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True, help_text=_("Teacher feedback on the answer"))
    ai_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("AI-assigned score")
    )
    ai_feedback = models.TextField(blank=True, help_text=_("AI-generated feedback"))
    ai_graded_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now, help_text=_("Time the answer was submitted"))

    def __str__(self):
        return f"Answer by {self.student.email} for {self.question}"

    class Meta:
        unique_together = ('student', 'question', 'exam')
        verbose_name = "Student Answer"
        verbose_name_plural = "Student Answers"
        indexes = [models.Index(fields=['exam', 'student'])]

    def clean(self):
        if self.score is not None and self.question and self.score > self.question.marks:
            raise ValidationError({'score': _(f"Score cannot exceed {self.question.marks} marks.")})
        if self.ai_score is not None and self.question and self.ai_score > self.question.marks:
            raise ValidationError({'ai_score': _(f"AI score cannot exceed {self.question.marks} marks.")})
        if self.exam and self.question and self.exam != self.question.exam:
            raise ValidationError({'exam': _("Exam must match the question's exam.")})

    def save(self, *args, **kwargs):
        if not self.exam and self.question:
            self.exam = self.question.exam
        self.full_clean()
        super().save(*args, **kwargs)


    def clean(self):
        if self.score is not None and self.question and self.score > self.question.marks:
            raise ValidationError({'score': _(f"Score cannot exceed {self.question.marks} marks.")})
        if self.ai_score is not None and self.question and self.ai_score > self.question.marks:
            raise ValidationError({'ai_score': _(f"AI score cannot exceed {self.question.marks} marks.")})
        if self.exam and self.question and self.exam != self.question.exam:
            raise ValidationError({'exam': _("Exam must match the question's exam.")})

    def save(self, *args, **kwargs):
        if not self.exam and self.question:
            self.exam = self.question.exam  # Auto-set exam if not provided
        self.full_clean()
        super().save(*args, **kwargs)

class ExamAttempt(TimeStampedModel):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exam_attempts'
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    session_data = models.JSONField(
        default=dict,
        help_text=_("Stores randomized question order or other session-specific data")
    )
    
    attempt_uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=_("Unique identifier for this attempt")
    )

    time_taken = models.DurationField(
        null=True,
        blank=True,
        help_text=_("Time taken to complete the exam")
    )

    def save(self, *args, **kwargs):
        if self.completed and self.end_time and self.start_time:
            self.time_taken = self.end_time - self.start_time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attempt by {self.student.email} for {self.exam.title}"

    class Meta:
        unique_together = ('student', 'exam')
        verbose_name = "Exam Attempt"
        verbose_name_plural = "Exam Attempts"
        indexes = [models.Index(fields=['exam', 'completed'])]