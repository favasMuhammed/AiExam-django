import logging
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.http import HttpResponseServerError

logger = logging.getLogger(__name__)

def root_view(request):
    try:
        logger.debug(f"User: {request.user}, Authenticated: {request.user.is_authenticated}")
        if not request.user.is_authenticated:
            logger.debug("Redirecting to users:login")
            return redirect('users:login')
        if hasattr(request.user, 'is_manager') and request.user.is_manager:
            logger.debug("Redirecting to manager:dashboard")
            return redirect('manager:dashboard')
        elif hasattr(request.user, 'is_institute') and request.user.is_institute:
            logger.debug("Redirecting to institute:dashboard")
            return redirect('institute:dashboard')
        elif hasattr(request.user, 'is_teacher') and request.user.is_teacher:
            logger.debug("Redirecting to teacher:dashboard")
            return redirect('teacher:dashboard')
        elif hasattr(request.user, 'is_student') and request.user.is_student:
            logger.debug("Redirecting to student:dashboard")
            return redirect('student:dashboard')
        elif hasattr(request.user, 'is_parent') and request.user.is_parent:
            logger.debug("Redirecting to parent dashboard (not implemented)")
            return redirect('users:login')
        logger.warning("No valid role, redirecting to login")
        return redirect('users:login')
    except Exception as e:
        logger.error(f"Error in root_view: {str(e)}", exc_info=True)
        return HttpResponseServerError("Internal Server Error - Check logs")

handler404 = 'project.views.custom_404'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_view, name='root'),
    path('auth/', include('users.urls')),
    path('manager/', include('manager.urls')),
    path('institute/', include('institute.urls')),
    path('teacher/', include('teacher.urls')),
    path('student/', include('student.urls')),
]

if settings.DEBUG:
    urlpatterns += (
        static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) +
        static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    )