from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import *
from .forms import *
from users.models import User
from django.core.mail import send_mail

@login_required
def dashboard(request):
    if not request.user.is_institute:
        messages.error(request, "Access denied.")
        return redirect('users:login')
    institution = Institution.objects.filter(manager__email=request.user.email).first()
    if not institution:
        messages.error(request, "No institution assigned.")
        return redirect('users:login')
    teachers = TeacherProfile.objects.filter(institution=institution)
    classes = Class.objects.filter(institution=institution)
    subjects = Subject.objects.filter(institution=institution)
    context = {
        'institution': institution,
        'teachers': teachers,
        'classes': classes,
        'subjects': subjects,
    }
    return render(request, 'institute/dashboard.html', context)


@login_required
def add_teacher(request):
    if not request.user.is_institute:
        messages.error(request, "Access denied. Only institute users can add teachers.")
        return redirect('institute:dashboard')

    institution = Institution.objects.filter(manager=request.user).first()
    if not institution:
        messages.error(request, "No institution assigned. Please register an institution first.")
        return redirect('institute:dashboard')

    if request.method == 'POST':
        form = TeacherProfileForm(request.POST, institution=institution)
        if form.is_valid():
            email = form.cleaned_data['email']
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'is_teacher': True}
            )
            if created:
                user.set_unusable_password()
                user.save()
                signup_url = request.build_absolute_uri(reverse('users:register'))
                try:
                    send_mail(
                        'Teacher Account Invitation',
                        f'You’ve been invited to join {institution.name} as a teacher.\n'
                        f'Please sign up to set your password: {signup_url}\n'
                        f'Email: {email}',
                        'admin@gmail.com',
                        [email],
                        fail_silently=False,
                    )
                    messages.success(request, f"Teacher {email} invited successfully! They’ll need to sign up.")
                except Exception as e:
                    messages.warning(request, f"Teacher added, but email failed: {str(e)}")
            else:
                messages.warning(request, f"Teacher {email} already exists. Profile updated.")

            try:
                teacher_profile = TeacherProfile.objects.get(user=user)
                if teacher_profile.institution != institution:
                    teacher_profile.institution = institution
                    messages.info(request, f"Teacher {email} reassigned to {institution.name}.")
                teacher_profile.classes.set(form.cleaned_data['classes'])
                teacher_profile.subjects.set(form.cleaned_data['subjects'])
                teacher_profile.save()
            except TeacherProfile.DoesNotExist:
                teacher_profile = TeacherProfile.objects.create(user=user, institution=institution)
                teacher_profile.classes.set(form.cleaned_data['classes'])
                teacher_profile.subjects.set(form.cleaned_data['subjects'])
                teacher_profile.save()

            return redirect('institute:dashboard')
    else:
        form = TeacherProfileForm(institution=institution)

    return render(request, 'institute/add_teacher.html', {
        'form': form,
        'institution': institution,
    })

@login_required
def add_class(request):
    if not request.user.is_institute:
        messages.error(request, "Access denied.")
        return redirect('institute:dashboard')
    
    institution = Institution.objects.filter(manager__email=request.user.email).first()
    if not institution:
        messages.error(request, "No institution assigned.")
        return redirect('institute:dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        teacher_ids = request.POST.getlist('teachers')  # Get list of selected teacher IDs
        
        # Create the class
        class_obj = Class.objects.create(name=name, institution=institution)
        
        # Assign selected teachers to the class
        if teacher_ids:
            teachers = User.objects.filter(id__in=teacher_ids, is_teacher=True)
            class_obj.teachers.add(*teachers)
        
        messages.success(request, f"Class '{name}' added successfully!")
        return redirect('institute:dashboard')
    
    # Get all teachers in the institution for the form
    teachers = User.objects.filter(
        is_teacher=True,
        teacher_profiles__institution=institution
    ).distinct()
    
    return render(request, 'institute/add_class.html', {
        'institution': institution,
        'teachers': teachers
    })

@login_required
def add_subject(request):
    if not request.user.is_institute:
        messages.error(request, "Access denied.")
        return redirect('institute:dashboard')
    institution = Institution.objects.filter(manager__email=request.user.email).first()
    if request.method == 'POST':
        name = request.POST.get('name')
        Subject.objects.create(name=name, institution=institution)
        messages.success(request, f"Subject '{name}' added successfully!")
        return redirect('institute:dashboard')
    return render(request, 'institute/add_subject.html', {'institution': institution})