from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from teacher.models import Exam, ExamAttempt
from users.models import User
import uuid
from django.utils import timezone
from django.core.exceptions import ValidationError


class MalpracticeLog(models.Model):
    MALPRACTICE_TYPES = (
        ('tab_switch', 'Tab Switch'),
        ('context_menu', 'Context Menu'),
        ('shortcut', 'Keyboard Shortcut'),
        ('devtools', 'Developer Tools'),
        ('fullscreen_exit', 'Fullscreen Exit'),
        ('save_error', 'Save Error'),
    )
    
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='malpractice_logs',
        help_text=_("The exam during which the malpractice occurred.")
    )
    attempt_uuid = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text=_("Links to ExamAttempt.attempt_uuid")
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='malpractice_logs',
        help_text=_("The student responsible for the malpractice, if identifiable.")
    )
    type = models.CharField(
        max_length=50,
        choices=MALPRACTICE_TYPES,
        help_text=_("The type of malpractice detected.")
    )
    message = models.TextField(
        default="No details provided",
        help_text=_("Description of the malpractice event."),
        blank=True
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text=_("Time the malpractice was logged.")
    )
    severity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text=_("Severity level: 1=Low, 2=Medium, 3=High")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("IP address from which the malpractice was logged, if available.")
    )
    is_reviewed = models.BooleanField(
        default=False,
        help_text=_("Indicates if a teacher has reviewed this malpractice.")
    )

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['exam', 'attempt_uuid']),
            models.Index(fields=['type', 'severity']),
        ]
        verbose_name = "Malpractice Log"
        verbose_name_plural = "Malpractice Logs"

    def __str__(self):
        return f"{self.get_type_display()} - {self.attempt_uuid} at {self.timestamp}"

    def get_linked_attempt(self):
        """Retrieve the associated ExamAttempt, if it exists."""
        return ExamAttempt.objects.filter(attempt_uuid=self.attempt_uuid).first()

    def clean(self):
        """Validate the model fields."""
        if not self.message.strip():
            raise ValidationError({'message': _("Message cannot be empty or whitespace.")})
        if self.severity not in [1, 2, 3]:
            raise ValidationError({'severity': _("Severity must be between 1 and 3.")})

    def save(self, *args, **kwargs):
        """Ensure validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def severity_label(self):
        """Return a human-readable severity label."""
        labels = {1: 'Low', 2: 'Medium', 3: 'High'}
        return labels.get(self.severity, 'Unknown')