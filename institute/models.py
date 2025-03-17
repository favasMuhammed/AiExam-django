from django.db import models
from common.models import TimeStampedModel
from users.models import User

class Institution(TimeStampedModel):
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_institutions')

    def __str__(self):
        return self.name

class Class(models.Model):
    name = models.CharField(max_length=100)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    teachers = models.ManyToManyField(User, related_name='class_set', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Subject(TimeStampedModel):
    name = models.CharField(max_length=100)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return self.name

class TeacherProfile(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teacher_profiles')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='teachers', null=True, blank=True)
    classes = models.ManyToManyField(Class, blank=True)
    subjects = models.ManyToManyField(Subject, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.institution.name}"

class StudentProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='students')
    classes = models.ManyToManyField(Class, blank=True)
    subjects = models.ManyToManyField(Subject, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.institution.name}"