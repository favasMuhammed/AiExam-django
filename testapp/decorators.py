# from django.shortcuts import redirect
# from django.contrib import messages
# from functools import wraps

# def teacher_required(view_func):
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             messages.error(request, "Please log in first.")
#             return redirect('testapp:login')
#         if not request.user.is_teacher:
#             messages.error(request, "Access denied. Teachers only.")
#             return redirect('testapp:dashboard')
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view

# def student_required(view_func):
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             messages.error(request, "Please log in first.")
#             return redirect('testapp:login')
#         if not request.user.is_student:
#             messages.error(request, "Access denied. Students only.")
#             return redirect('testapp:dashboard')
#         return view_func(request, *args, **kwargs)
#     return _wrapped_view