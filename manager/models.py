from django.db import models
from common.models import TimeStampedModel
from users.models import User

class ManagerProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='manager_profile')
    # Additional fields can be added if needed (e.g., contact info)