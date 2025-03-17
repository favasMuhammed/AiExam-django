from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from institute.models import Institution
from users.models import User

@login_required
def dashboard(request):
    if not request.user.is_manager:
        messages.error(request, "Access denied.")
        return redirect('users:login')
    institutions = Institution.objects.filter(manager=request.user)
    context = {
        'institutions': institutions,
        'total_institutions': institutions.count(),
    }
    return render(request, 'manager/dashboard.html', context)

@login_required
def add_institution(request):
    if not request.user.is_manager:
        messages.error(request, "Access denied.")
        return redirect('manager:dashboard')
    if request.method == 'POST':
        name = request.POST.get('name')
        institution = Institution.objects.create(name=name, manager=request.user)
        messages.success(request, f"Institution '{name}' added successfully!")
        return redirect('manager:dashboard')
    return render(request, 'manager/add_institution.html')