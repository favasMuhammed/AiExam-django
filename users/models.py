from django.db import models
from django.contrib.auth.models import AbstractUser

from .manager import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(max_length=255, unique=True, 
                              error_messages={'unique': "Email already used"})
    is_manager = models.BooleanField('Is manager', default=False)
    is_institute = models.BooleanField('Is institute', default=False)  # Added
    is_student = models.BooleanField('Is student', default=False)
    is_teacher = models.BooleanField('Is teacher', default=False)
    is_parent = models.BooleanField('Is parent', default=False)
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        db_table = 'user_user'
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ["-id"]

    def __str__(self):
        return self.email
    


class OTP(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.IntegerField()
    created_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_otp'
        verbose_name = 'otp'
        verbose_name_plural = 'otps'
        ordering = ["-id"]

    def __str__(self):

        return f'{self.user.email}--{self.otp}'