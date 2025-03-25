import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Avg, F, Q
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
import requests
from sentence_transformers import SentenceTransformer, util
from django.conf import settings

from .models import Exam, Question, StudentAnswer, ExamAttempt
from .forms import ExamForm, QuestionForm, StudentAnswerForm, GradeAnswerForm

# Initialize AI tools
grader_model = SentenceTransformer('all-MiniLM-L6-v2')
logger = logging.getLogger(__name__)

class CustomLoginView(LoginView):
    template_name = 'testapp/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('testapp:dashboard')

    def form_invalid(self, form):
        messages.error(self.request, 'Invalid email or password.')
        return super().form_invalid(form)

def login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user:
            auth_login(request, user)
            return redirect('testapp:dashboard')
        messages.error(request, 'Invalid email or password.')
    return render(request, 'testapp/login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('testapp:login')

@login_required
def dashboard(request):
    if request.user.is_student:
        # Available Exams
        available_exams = Exam.objects.filter(
            is_approved=True, 
            is_active=True
        ).exclude(
            id__in=StudentAnswer.objects.filter(
                student=request.user
            ).values_list('question__exam', flat=True)
        )

        # Completed Exams with Aggregated Stats
        completed_exams_stats = StudentAnswer.objects.filter(
            student=request.user,
            question__exam__isnull=False  # Ensure exam exists
        ).values('question__exam', 'question__exam__title').annotate(
            total_score=Sum('score'),
            total_questions=Count('question'),
            average_score=Avg('score') * 100.0 / F('question__marks')  # Percentage based on max marks
        ).filter(
            question__exam__isnull=False  # Additional filter to avoid null exams
        ).order_by('question__exam')

        # Total Completed Exams
        total_completed = completed_exams_stats.count()

        # Average Score Across All Completed Exams
        avg_score = StudentAnswer.objects.filter(
            student=request.user
        ).aggregate(
            avg_score=Avg('score') * 100.0 / Avg('question__marks')
        )['avg_score'] or 0

        # Upcoming Exams
        upcoming_exams = available_exams.filter(
            date__gte=timezone.now().date()
        ).order_by('date', 'start_time')[:5]

        context = {
            'available_exams': available_exams,
            'completed_exams': completed_exams_stats,  # Dictionary with exam_id and stats
            'total_completed': total_completed,
            'average_score': avg_score,
            'upcoming_exams': upcoming_exams,
        }
        logger.debug(f"Student dashboard context: {context}")
        return render(request, 'testapp/student_dashboard.html', context)
    elif request.user.is_teacher:
        exams = Exam.objects.filter(created_by=request.user)
        pending_count = StudentAnswer.objects.filter(
            question__exam__created_by=request.user, score__isnull=True
        ).count()
        context = {'exams': exams, 'pending_count': pending_count}
        return render(request, 'testapp/teacher_dashboard.html', context)
    raise PermissionDenied("Invalid user type.")

@login_required
def create_exam(request):
    if not request.user.is_teacher:
        messages.error(request, "Only teachers can create exams.")
        return redirect('testapp:dashboard')
    
    form = ExamForm(request.POST or None)
    if request.method == 'POST':
        logger.debug(f"POST data: {request.POST}")
        if form.is_valid():
            try:
                with transaction.atomic():
                    exam = form.save(commit=False)
                    exam.created_by = request.user
                    exam.save()
                    logger.info(f"Exam created: {exam.id} - {exam.title}")
                    messages.success(request, "Exam created successfully!")
                    return redirect('testapp:generate_questions', exam_id=exam.id)
            except Exception as e:
                logger.error(f"Error saving exam: {str(e)}")
                messages.error(request, f"Failed to create exam: {str(e)}")
        else:
            logger.debug(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the form errors below.")
    
    return render(request, 'testapp/create_exam.html', {'form': form})


def generate_ai_question(topic, difficulty, number):
    """Generate a question using Google Gemini API."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Generate a {difficulty}-level exam question numbered {number} about {topic}."
            }]
        }],
        "key": settings.GEMINI_API_KEY
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

def generate_ai_answer(topic, difficulty):
    """Generate a correct answer using Google Gemini API."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Provide a detailed, correct answer for a {difficulty}-level exam question about {topic}."
            }]
        }],
        "key": settings.GEMINI_API_KEY
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

@login_required
def review_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_teacher or exam.created_by != request.user:
        messages.error(request, "Access denied.")
        return redirect('testapp:dashboard')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                total_marks = 0
                for question in exam.questions.all():
                    question_text = request.POST.get(f'question_{question.id}')
                    correct_answer = request.POST.get(f'answer_{question.id}')
                    explanation = request.POST.get(f'explanation_{question.id}', '')
                    marks = int(request.POST.get(f'marks_{question.id}', 0))
                    
                    question.question_text = question_text
                    question.correct_answer = correct_answer
                    question.explanation = explanation
                    question.marks = marks
                    total_marks += marks
                    question.save()
                
                if total_marks != exam.total_marks:
                    messages.warning(request, f"Total marks ({total_marks}) must match exam total ({exam.total_marks}).")
                    return redirect('testapp:review_exam', exam_id=exam.id)
                
                action = request.POST.get('action')
                if action == 'approve':
                    exam.is_approved = True
                    exam.save()
                    messages.success(request, "Exam approved successfully!")
                    return redirect('testapp:dashboard')
                messages.success(request, "Questions updated successfully!")
                return redirect('testapp:review_exam', exam_id=exam.id)
        except Exception as e:
            messages.error(request, f"Error updating exam: {e}")
    
    context = {
        'exam': exam,
        'total_marks': exam.questions.aggregate(total=Sum('marks'))['total'] or 0,
    }
    return render(request, 'testapp/review_exam.html', context)

@login_required
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_teacher or exam.created_by != request.user:
        messages.error(request, "Access denied.")
        return redirect('testapp:dashboard')
    
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam updated successfully!")
            return redirect('testapp:dashboard')
    else:
        form = ExamForm(instance=exam)
    return render(request, 'testapp/create_exam.html', {'form': form, 'exam': exam, 'is_edit': True})

@login_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_teacher or exam.created_by != request.user:
        messages.error(request, "Access denied.")
        return redirect('testapp:dashboard')
    
    if request.method == 'POST':
        exam.delete()
        messages.success(request, "Exam deleted successfully!")
        return redirect('testapp:dashboard')
    return render(request, 'testapp/delete_exam.html', {'exam': exam})

@login_required
def take_exam(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Only students can take exams.")
        return redirect('testapp:dashboard')
    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)
    
    if not exam.is_available():
        messages.error(request, "Exam not available.")
        return redirect('testapp:dashboard')
    
    attempt, created = ExamAttempt.objects.get_or_create(
        student=request.user, exam=exam, defaults={'start_time': timezone.now()}
    )
    elapsed = (timezone.now() - attempt.start_time).total_seconds()
    remaining = max(0, exam.duration * 60 - elapsed)
    
    if remaining <= 0:
        messages.error(request, "Time expired.")
        return redirect('testapp:exam_results', exam_id=exam.id)
    
    if StudentAnswer.objects.filter(student=request.user, question__exam=exam).count() >= exam.num_questions:
        messages.info(request, "Exam already completed.")
        return redirect('testapp:exam_results', exam_id=exam.id)
    
    return render(request, 'testapp/take_exam.html', {'exam': exam, 'time_in_seconds': remaining})

@login_required
def submit_exam(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Only students can submit exams.")
        return redirect('testapp:dashboard')
    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)
    
    if request.method != 'POST':
        return redirect('testapp:take_exam', exam_id=exam_id)
    
    try:
        with transaction.atomic():
            attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam)
            if not exam.is_available() or (timezone.now() - attempt.start_time).total_seconds() > exam.duration * 60:
                messages.error(request, "Exam time expired.")
                return redirect('testapp:dashboard')
            
            answers_submitted = 0
            for question in exam.questions.all():
                answer_text = request.POST.get(f'question_{question.id}', '').strip()
                if answer_text:
                    answer, created = StudentAnswer.objects.update_or_create(
                        student=request.user, question=question, defaults={'answer_text': answer_text}
                    )
                    answer.score = auto_grade_answer(answer_text, question.correct_answer, question.marks)
                    answer.graded_by = None  # AI-graded
                    answer.graded_at = timezone.now()
                    answer.save()
                    answers_submitted += 1
            messages.success(request, f"Submitted and auto-graded {answers_submitted}/{exam.num_questions} answers.")
            return redirect('testapp:exam_results', exam_id=exam.id)
    except ExamAttempt.DoesNotExist:
        messages.error(request, "Start the exam first.")
    except Exception as e:
        messages.error(request, f"Error submitting: {e}")
    return redirect('testapp:take_exam', exam_id=exam_id)

def auto_grade_answer(student_answer, correct_answer, max_marks):
    """Automatically grade an answer using cosine similarity."""
    student_embedding = grader_model.encode(student_answer, convert_to_tensor=True)
    correct_embedding = grader_model.encode(correct_answer, convert_to_tensor=True)
    similarity = util.cos_sim(student_embedding, correct_embedding).item()
    return int(similarity * max_marks)

@login_required
def exam_results(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.user.is_teacher and exam.created_by != request.user:
        messages.error(request, "Access denied.")
        return redirect('testapp:dashboard')
    
    if request.user.is_teacher and request.method == 'POST':
        try:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('score_'):
                        answer_id = int(key.split('_')[1])
                        answer = get_object_or_404(StudentAnswer, id=answer_id)
                        form = GradeAnswerForm(request.POST, instance=answer)
                        if form.is_valid():
                            answer = form.save(commit=False)
                            answer.graded_by = request.user
                            answer.graded_at = timezone.now()
                            answer.save()
                messages.success(request, "Grades updated manually!")
        except Exception as e:
            messages.error(request, f"Error grading: {e}")
    
    answers = StudentAnswer.objects.filter(
        question__exam=exam, student=request.user if request.user.is_student else None
    ).select_related('question') if request.user.is_student else StudentAnswer.objects.filter(question__exam=exam)
    
    total_score = sum(a.score or 0 for a in answers)
    total_possible = sum(a.question.marks for a in answers)
    
    return render(request, 'testapp/exam_results.html', {
        'exam': exam,
        'answers': answers,
        'total_score': total_score,
        'total_possible': total_possible,
        'user': request.user,
    })

@login_required
@require_POST
def save_answer(request):
    if not request.user.is_student:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        question_id = request.POST.get('question_id')
        answer_text = request.POST.get('answer_text')
        question = get_object_or_404(Question, id=question_id)
        StudentAnswer.objects.update_or_create(
            student=request.user, question=question, defaults={'answer_text': answer_text}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
def update_grade(request):
    if not request.user.is_teacher:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        answer_id = request.POST.get('answer_id')
        score = request.POST.get('score')
        feedback = request.POST.get('feedback', '')
        answer = get_object_or_404(StudentAnswer, id=answer_id)
        if answer.question.exam.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        if score:
            answer.score = int(score)
        answer.feedback = feedback
        answer.graded_by = request.user
        answer.graded_at = timezone.now()
        answer.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def exam_status(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not (request.user.is_student or (request.user.is_teacher and exam.created_by == request.user)):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        now = timezone.now()
        exam_dt = timezone.make_aware(datetime.combine(exam.date, exam.start_time))
        end_dt = exam_dt + timedelta(minutes=exam.duration)
        status = 'upcoming' if now < exam_dt else 'in_progress' if now <= end_dt else 'completed'
        remaining = max(0, (exam_dt if status == 'upcoming' else end_dt) - now).total_seconds()
        return JsonResponse({
            'status': status,
            'remaining_time': int(remaining),
            'is_available': exam.is_available()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def pending_grading(request):
    if not request.user.is_teacher:
        messages.error(request, "Access denied.")
        return redirect('testapp:dashboard')
    pending_answers = StudentAnswer.objects.filter(
        question__exam__created_by=request.user, score__isnull=True
    ).select_related('student', 'question', 'question__exam')
    return render(request, 'testapp/pending_grading.html', {
        'pending_answers': pending_answers,
        'total_pending': pending_answers.count()
    })