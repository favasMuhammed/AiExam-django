

from django import forms
from .models import User

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Create a password'}))
    role = forms.ChoiceField(choices=[
        ('manager', 'Manager'),
        ('institute', 'Institution'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ], widget=forms.Select(attrs={'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}))
    institution_name = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'placeholder': 'Institution Name'}))

    class Meta:
        model = User
        fields = ['email', 'password', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'Enter your email', 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'phone': forms.TextInput(attrs={'placeholder': 'Enter your phone number', 'class': 'mt-1 block w-full px-4 py-3 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        institution_name = cleaned_data.get('institution_name')
        if role == 'institute' and not institution_name:
            raise forms.ValidationError("Institution name is required for the Institute role.")
        return cleaned_data