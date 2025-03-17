from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout, authenticate
from django.contrib import messages
from .forms import RegistrationForm
from django.core.mail import send_mail
from .models import *

from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.core.mail import send_mail
from .forms import RegistrationForm
from institute.models import *


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            role = form.cleaned_data['role']

            try:
                user = User.objects.get(email=email)
                if not user.has_usable_password():
                    if (role == 'teacher' and user.is_teacher) or \
                       (role == 'student' and user.is_student):
                        user.set_password(password)
                        user.save()
                        # Ensure TeacherProfile exists for invited teachers
                        if user.is_teacher:
                            institution = Institution.objects.filter(manager__is_manager=True).first()
                            if institution:
                                TeacherProfile.objects.get_or_create(user=user, defaults={'institution': institution})
                            else:
                                messages.warning(request, "No institution available for teacher profile.")
                        auth_login(request, user)
                        messages.success(request, "Password set successfully!")
                        return redirect(f'{role}:dashboard')
                    else:
                        messages.error(request, f"This email is registered as a {user.get_role()} but you selected {role}.")
                        return render(request, 'testapp/register.html', {'form': form})
                else:
                    messages.error(request, "This email is already registered with a password.")
                    return render(request, 'testapp/register.html', {'form': form})
            except User.DoesNotExist:
                user = form.save(commit=False)
                user.set_password(password)
                user.is_manager = (role == 'manager')
                user.is_institute = (role == 'institute')
                user.is_teacher = (role == 'teacher')
                user.is_student = (role == 'student')
                user.save()

                if user.is_teacher:
                    institution = Institution.objects.filter(manager__is_manager=True).first()
                    if institution:
                        TeacherProfile.objects.get_or_create(user=user, defaults={'institution': institution})
                    else:
                        messages.warning(request, "No institution available. Teacher profile not created.")
                elif user.is_institute:
                    institution_name = form.cleaned_data.get('institution_name')
                    if institution_name:
                        Institution.objects.create(name=institution_name, manager=user)

                auth_login(request, user)
                try:
                    send_mail(
                        'Your Account Credentials',
                        f'Email: {user.email}\nPassword: {password}\nLogin at: http://127.0.0.1:8000/',
                        'admin@aiexam.com',
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    messages.warning(request, f"Account created, but email failed: {str(e)}")
                messages.success(request, "Registration successful!")
                return redirect(f'{role}:dashboard')
        messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()
    return render(request, 'testapp/register.html', {'form': form})




def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')  # Get selected role
        user = authenticate(request, email=email, password=password)
        if user:
            # Validate role matches user type
            if (role == 'manager' and user.is_manager) or \
               (role == 'institute' and user.is_institute) or \
               (role == 'teacher' and user.is_teacher) or \
               (role == 'student' and user.is_student):
                auth_login(request, user)
                if user.is_manager:
                    return redirect('manager:dashboard')
                elif user.is_institute:
                    return redirect('institute:dashboard')
                elif user.is_teacher:
                    return redirect('teacher:dashboard')
                elif user.is_student:
                    return redirect('student:dashboard')
            else:
                messages.error(request, f"Account exists but not as {role.capitalize()}.")
        else:
            messages.error(request, 'Invalid email or password.')
    return render(request, 'testapp/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('users:login')