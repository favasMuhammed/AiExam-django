from django.shortcuts import render

def custom_404(request, exception):
    return render(request, 'testapp/404.html', status=404)