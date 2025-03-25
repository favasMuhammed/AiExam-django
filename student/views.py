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
from institute.models import Class
import random  # Added import

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import MalpracticeLog
import json


MIN_SUBMISSION_THRESHOLD = 0

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
    """Handle the student taking an exam, including time tracking and question sequencing based on order."""
    if not hasattr(request.user, 'is_student') or not request.user.is_student:
        messages.error(request, "Access denied. Only students can take exams.")
        return redirect('student:dashboard')

    exam = get_object_or_404(Exam.objects.select_related('subject').prefetch_related('classes'), 
                            id=exam_id, is_approved=True)
    
    if not exam.is_available():
        messages.error(request, "This exam is not currently available.")
        return redirect('student:dashboard')

    student_classes = set(Class.objects.filter(studentprofile__user=request.user).values_list('id', flat=True))
    exam_class_ids = set(exam.classes.values_list('id', flat=True))
    if not student_classes & exam_class_ids:
        messages.error(request, "You are not enrolled in a class assigned to this exam.")
        return redirect('student:dashboard')

    attempt, created = ExamAttempt.objects.get_or_create(
        student=request.user,
        exam=exam,
        defaults={
            'start_time': timezone.now(),
            'ip_address': request.META.get('REMOTE_ADDR', 'Unknown'),
        }
    )

    total_seconds = exam.duration * 60
    elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
    remaining_seconds = max(0, total_seconds - elapsed_seconds)

    answers = StudentAnswer.objects.filter(
        student=request.user,
        question__exam=exam
    ).select_related('question')
    answer_dict = {answer.question_id: answer.answer_text for answer in answers}
    total_questions = exam.questions.count()

    if attempt.completed or remaining_seconds <= 0 or len(answer_dict) >= total_questions:
        attempt.completed = True
        attempt.end_time = timezone.now()
        attempt.ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
        attempt.save(update_fields=['completed', 'end_time', 'ip_address'])
        messages.info(request, "Exam time expired or already completed.")
        logger.info(f"Exam {exam_id} completed for {request.user.email} - IP: {attempt.ip_address}")
        return redirect('student:dashboard')

    # Use order field for sequencing instead of randomization
    questions = list(exam.questions.order_by('order').all())

    progress_percentage = (len(answer_dict) / total_questions * 100) if total_questions > 0 else 0

    context = {
        'exam': exam,
        'attempt': attempt,
        'questions': questions,
        'answer_dict': answer_dict,
        'time_in_seconds': int(remaining_seconds),
        'progress_percentage': progress_percentage,
        'attempt_uuid': str(attempt.attempt_uuid),
    }
    return render(request, 'testapp/take_exam.html', context)



@csrf_exempt
@require_POST
@login_required(login_url='users:login')
def log_malpractice(request):
    try:
        data = json.loads(request.body)
        exam_id = data.get('exam_id')
        attempt_uuid = data.get('attempt_uuid')
        malpractice_type = data.get('type')

        exam = Exam.objects.get(id=exam_id)
        attempt = ExamAttempt.objects.get(attempt_uuid=attempt_uuid, student=request.user, exam=exam)

        MalpracticeLog.objects.create(
            attempt=attempt,
            exam=exam,
            student=request.user,
            type=malpractice_type,
            details=f"IP: {request.META.get('REMOTE_ADDR', 'Unknown')}"
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    


@login_required(login_url='users:login')
def submit_exam(request, exam_id):
    if not request.user.is_student:
        messages.error(request, "Access denied. Only students can submit exams.")
        return redirect('student:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, is_approved=True)
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam)

    if request.method != 'POST':
        messages.error(request, "Invalid submission method.")
        return redirect('student:take_exam', exam_id=exam.id)

    try:
        with transaction.atomic():
            # Validate attempt UUID
            submitted_uuid = request.POST.get('attempt_uuid')
            if str(attempt.attempt_uuid) != submitted_uuid:
                logger.error(f"UUID mismatch for exam {exam_id} by {request.user.email}: Expected {attempt.attempt_uuid}, Got {submitted_uuid}")
                messages.error(request, "Invalid exam attempt. Submission rejected.")
                return redirect('student:take_exam', exam_id=exam.id)

            # Calculate time elapsed and remaining
            elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
            total_duration = exam.duration * 60

            # Check availability and time limits
            if not exam.is_available() or elapsed_seconds > total_duration:
                attempt.completed = True
                attempt.end_time = timezone.now()
                attempt.ip_address = request.META.get('REMOTE_ADDR', attempt.ip_address)
                attempt.save()
                messages.error(request, "Exam time has expired or is no longer available.")
                logger.info(f"Exam {exam_id} expired for {request.user.email}, UUID: {attempt.attempt_uuid}")
                return redirect('student:dashboard')

            # Prevent resubmission
            if attempt.completed:
                messages.info(request, "Exam already submitted.")
                return redirect('student:dashboard')

            # Detect rapid submission
            rapid_threshold = total_duration * MIN_SUBMISSION_THRESHOLD
            if elapsed_seconds < rapid_threshold:
                logger.warning(
                    f"Rapid submission detected for {request.user.email} on exam {exam_id}, "
                    f"UUID: {attempt.attempt_uuid}, Time: {elapsed_seconds:.1f}s"
                )

            # Process answers
            answers_submitted = 0
            total_questions = exam.questions.count()
            is_time_expired = request.POST.get('time_expired', 'false').lower() == 'true'

            for question in exam.questions.all():
                answer_text = request.POST.get(f'question_{question.id}', '').strip()
                answer, created = StudentAnswer.objects.update_or_create(
                    student=request.user,
                    question=question,
                    exam=exam,  # Explicitly include exam in the lookup
                    defaults={
                        'answer_text': answer_text,
                        'submitted_at': timezone.now(),
                    }
                )
                if answer_text:
                    answers_submitted += 1
                logger.debug(f"Question {question.id} ({question.question_type}): Saved answer '{answer_text[:50]}...' (Created: {created})")

            # Finalize attempt
            attempt.completed = True
            attempt.end_time = timezone.now()
            attempt.ip_address = request.META.get('REMOTE_ADDR', attempt.ip_address)
            attempt.save()

            # Customize success message based on submission type
            submission_type = "automatically due to time expiry" if is_time_expired else "manually"
            completion_msg = (
                f"Exam submitted {submission_type} successfully! "
                f"You answered {answers_submitted} out of {total_questions} questions."
            )
            messages.success(request, completion_msg)
            logger.info(
                f"Exam {exam_id} submitted by {request.user.email}, UUID: {attempt.attempt_uuid}: "
                f"{answers_submitted}/{total_questions} answered, Type: {submission_type}, IP: {attempt.ip_address}"
            )
            return redirect('student:dashboard')

    except Exception as e:
        logger.error(f"Error submitting exam {exam_id} for {request.user.email}, UUID: {attempt.attempt_uuid}: {str(e)}")
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

    # Get the student's answers
    answers = StudentAnswer.objects.filter(
        question__exam=exam,
        student=request.user
    ).select_related('question')

    # Calculate the student's score
    total_score = sum(a.score or 0 for a in answers)
    total_possible = sum(a.question.marks for a in answers)
    percentage = (total_score / total_possible * 100) if total_possible > 0 else 0

    # Get all completed attempts for this exam
    attempts = ExamAttempt.objects.filter(exam=exam, completed=True)
    total_students = attempts.count()

    # Count answers pending grading
    pending_grading = StudentAnswer.objects.filter(
        question__exam=exam,
        score__isnull=True
    ).count()

    # Calculate average score across all students
    scores = StudentAnswer.objects.filter(
        question__exam=exam
    ).aggregate(
        avg_score=Avg('score'),
        total_marks=Sum('question__marks')
    )
    average_score = (
        (scores['avg_score'] / scores['total_marks'] * 100)
        if scores['avg_score'] and scores['total_marks']
        else 0
    )

    # Calculate enrolled students (students in the exam's classes)
    enrolled_students = User.objects.filter(
        is_student=True,
        student_profile__classes__in=exam.classes.all()
    ).distinct().count() or 1  # Avoid division by zero

    # Calculate completion rate
    completion_rate = (total_students / enrolled_students) * 100 if enrolled_students else 0

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
        defaults={
            'start_time': timezone.now(),
            'ip_address': request.META.get('REMOTE_ADDR'),
        }
    )

    elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
    remaining_seconds = max(0, exam.duration * 60 - elapsed_seconds)
    status = 'completed' if attempt.completed else 'in_progress' if remaining_seconds > 0 else 'expired'

    return JsonResponse({
        'status': status,
        'remaining_time': int(remaining_seconds),
        'is_available': exam.is_available(),
        'attempt_uuid': str(attempt.attempt_uuid),
    })


@login_required(login_url='users:login')
def save_answer(request):
    if not request.user.is_student or request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

    question_id = request.POST.get('question_id')
    answer_text = request.POST.get('answer_text', '').strip()
    question = get_object_or_404(Question, id=question_id)
    exam = question.exam
    attempt = get_object_or_404(ExamAttempt, student=request.user, exam=exam, completed=False)

    elapsed_seconds = (timezone.now() - attempt.start_time).total_seconds()
    if elapsed_seconds > exam.duration * 60 or not exam.is_available():
        attempt.completed = True
        attempt.end_time = timezone.now()
        attempt.ip_address = request.META.get('REMOTE_ADDR')
        attempt.save()
        return JsonResponse({'success': False, 'error': 'Time expired or exam unavailable'})

    answer, created = StudentAnswer.objects.update_or_create(
        student=request.user,
        question=question,
        defaults={'answer_text': answer_text}
    )
    logger.info(f"Answer saved for question {question_id} by {request.user.email}, UUID: {attempt.attempt_uuid} (Created: {created})")
    return JsonResponse({'success': True})