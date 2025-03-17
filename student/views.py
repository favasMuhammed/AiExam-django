from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Avg, Sum, Count, F
from teacher.models import Exam, Question, ExamAttempt, StudentAnswer
from institute.models import Subject
from common.utils import auto_grade_answer
from users.models import User
import logging

logger = logging.getLogger(__name__)
@login_required(login_url='users:login')
def dashboard(request):
    if not request.user.is_student:
        messages.error(request, "Access denied. Only students can access this page.")
        return redirect('users:login')

    try:
        student_classes = request.user.student_profile.classes.all()
    except AttributeError:
        student_classes = []
        messages.warning(request, "Student profile not set up. Contact your administrator.")

    completed_exam_ids = ExamAttempt.objects.filter(
        student=request.user, completed=True
    ).values_list('exam_id', flat=True)

    available_exams = Exam.objects.filter(
        is_approved=True,
        is_active=True,
        classes__in=student_classes
    ).exclude(id__in=completed_exam_ids).select_related('subject').prefetch_related('classes').distinct()

    completed_exams_qs = Exam.objects.filter(
        attempts__student=request.user,
        attempts__completed=True,
        is_published=True  # Only show published results
    ).values(
        'id',
        'title',
        'subject__name'
    ).annotate(
        total_score=Sum('questions__answers__score', filter=F('questions__answers__student')==request.user),
        total_possible=Sum('questions__marks'),
        total_questions=Count('questions', distinct=True),
    ).order_by('-id')

    completed_exams_list = [
        {
            'id': exam['id'],
            'title': exam['title'],
            'total_score': exam['total_score'] or 0,
            'total_possible': exam['total_possible'],
            'percentage': (exam['total_score'] / exam['total_possible'] * 100) if exam['total_possible'] > 0 else 0
        } for exam in completed_exams_qs
    ]

    total_completed = len(completed_exams_list)
    total_score_sum = sum(exam['total_score'] for exam in completed_exams_list)
    total_possible_sum = sum(exam['total_possible'] for exam in completed_exams_list)
    average_score = (total_score_sum / total_possible_sum * 100) if total_possible_sum > 0 else 0
    upcoming_exams = available_exams.filter(
        date__gte=timezone.now().date()
    ).order_by('date', 'start_time')[:5]

    try:
        subjects = request.user.student_profile.subjects.all()
    except AttributeError:
        subjects = Subject.objects.filter(
            exam__questions__answers__student=request.user
        ).distinct()

    subject_data = {'labels': [], 'scores': []}
    for subject in subjects:
        subject_answers = StudentAnswer.objects.filter(
            student=request.user,
            question__exam__subject=subject,
            question__exam__is_published=True  # Only published exams
        ).select_related('question')
        if subject_answers.exists():
            subject_score = subject_answers.aggregate(total_score=Sum('score'))['total_score'] or 0
            subject_possible = subject_answers.aggregate(total_possible=Sum('question__marks'))['total_possible'] or 0
            if subject_possible > 0:
                subject_data['labels'].append(subject.name)
                subject_data['scores'].append(subject_score / subject_possible * 100)

    context = {
        'available_exams': available_exams,
        'completed_exams': completed_exams_list,
        'total_completed': total_completed,
        'average_score': average_score,
        'upcoming_exams': upcoming_exams,
        'subject_data': subject_data,
        'user': request.user,
    }
    return render(request, 'testapp/student_dashboard.html', context)

@login_required(login_url='users:login')
def take_exam(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Access denied. Only students can take exams.")
        return redirect('student:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)
    if not exam.is_available():
        messages.error(request, "This exam is not currently available.")
        return redirect('student:dashboard')

    attempt, created = ExamAttempt.objects.get_or_create(
        student=request.user,
        exam=exam,
        defaults={'start_time': timezone.now()}
    )

    elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
    total_seconds = exam.duration * 60
    remaining_seconds = max(0, total_seconds - elapsed_seconds)

    answers_count = StudentAnswer.objects.filter(student=request.user, question__exam=exam).count()
    if attempt.completed or remaining_seconds <= 0 or answers_count >= exam.num_questions:
        attempt.completed = True
        attempt.save()
        messages.info(request, "Exam time expired or already completed.")
        return redirect('student:dashboard')  # Changed from exam_results

    answer_dict = {
        answer.question.id: answer.answer_text
        for answer in StudentAnswer.objects.filter(student=request.user, question__exam=exam)
    }

    return render(request, 'testapp/take_exam.html', {
        'exam': exam,
        'time_in_seconds': int(remaining_seconds),
        'answer_dict': answer_dict,
    })

@login_required(login_url='users:login')
def submit_exam(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Access denied. Only students can submit exams.")
        return redirect('student:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam)

    if request.method != 'POST':
        return redirect('student:take_exam', exam_id=exam.id)

    try:
        with transaction.atomic():
            elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
            if not exam.is_available() or elapsed_seconds > exam.duration * 60:
                attempt.completed = True
                attempt.end_time = timezone.now()
                attempt.save()
                messages.error(request, "Exam time has expired.")
                return redirect('student:dashboard')

            if attempt.completed:
                messages.info(request, "Exam already submitted.")
                return redirect('student:dashboard')

            answers_submitted = 0
            total_questions = exam.questions.count()
            logger.info(f"Submitting exam {exam_id} for {request.user.email}, total questions: {total_questions}")
            for question in exam.questions.all():
                answer_text = request.POST.get(f'question_{question.id}', '').strip()
                answer, created = StudentAnswer.objects.update_or_create(
                    student=request.user,
                    question=question,
                    defaults={'answer_text': answer_text}
                )
                logger.info(f"Question {question.id}: Saved answer '{answer_text}' (Created: {created})")
                if answer_text:
                    answers_submitted += 1

            attempt.completed = True
            attempt.end_time = timezone.now()
            attempt.save()
            logger.info(f"Exam {exam_id} submitted: {answers_submitted}/{total_questions} answered")
            messages.success(request, f"Exam submitted successfully! You answered {answers_submitted} out of {total_questions} questions.")
            return redirect('student:dashboard')

    except Exception as e:
        logger.error(f"Error submitting exam {exam_id}: {str(e)}")
        messages.error(request, f"Error submitting exam: {str(e)}")
        return redirect('student:take_exam', exam_id=exam.id)
    

@login_required(login_url='users:login')
def exam_results(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Access denied. Only students can view results.")
        return redirect('student:dashboard')

    exam = get_object_or_404(Exam, id=exam_id)
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam, completed=True)

    if not exam.is_published:
        messages.error(request, "Results are not yet published by your teacher.")
        return redirect('student:dashboard')

    # Student-specific data
    answers = StudentAnswer.objects.filter(
        question__exam=exam,
        student=request.user
    ).select_related('question')
    total_score = sum(a.score or 0 for a in answers)
    total_possible = sum(a.question.marks for a in answers)
    percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    # Exam-wide statistics
    attempts = ExamAttempt.objects.filter(exam=exam, completed=True).select_related('student')
    total_students = attempts.count()
    pending_grading = StudentAnswer.objects.filter(question__exam=exam, score__isnull=True).count()
    scores = StudentAnswer.objects.filter(question__exam=exam).aggregate(
        avg_score=Avg('score'),
        total_marks=Sum('question__marks')
    )
    average_score = (scores['avg_score'] / scores['total_marks'] * 100) if scores['avg_score'] is not None and scores['total_marks'] else 0
    completion_rate = (attempts.count() / total_students * 100) if total_students > 0 else 0

    context = {
        'exam': exam,
        'answers': answers,
        'total_score': total_score,
        'total_possible': total_possible,
        'percentage': percentage,
        'total_students': total_students,
        'average_score': average_score,
        'completion_rate': completion_rate,
        'pending_grading': pending_grading,
        'user': request.user,
    }
    return render(request, 'testapp/student_exam_results.html', context)

@login_required(login_url='users:login')
def exam_status(request, exam_id):
    if not request.user.is_student:
        return JsonResponse({'error': 'Access denied'}, status=403)

    exam = get_object_or_404(Exam, id=exam_id)
    attempt, created = ExamAttempt.objects.get_or_create(
        student=request.user,
        exam=exam,
        defaults={'start_time': timezone.now()}
    )

    elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
    remaining_seconds = max(0, exam.duration * 60 - elapsed_seconds)
    status = 'completed' if attempt.completed else 'in_progress' if remaining_seconds > 0 else 'expired'

    return JsonResponse({
        'status': status,
        'remaining_time': int(remaining_seconds),
        'is_available': exam.is_available(),
    })

@login_required(login_url='users:login')
def save_answer(request):
    if not request.user.is_student or request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    
    question_id = request.POST.get('question_id')
    answer_text = request.POST.get('answer_text')
    question = get_object_or_404(Question, id=question_id)
    exam = question.exam
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam, completed=False)
    
    StudentAnswer.objects.update_or_create(
        student=request.user,
        question=question,
        defaults={'answer_text': answer_text}
    )
    return JsonResponse({'success': True})