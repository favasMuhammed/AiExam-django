import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Avg, F, Q
from .models import *
from .forms import *
from .models import Exam, StudentAnswer
from .forms import ExamForm, ClassStudentForm
from common.utils import generate_ai_question, generate_ai_answer
from sentence_transformers import SentenceTransformer, util
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.mail import send_mail
from datetime import datetime, timedelta
from users.models import *
from institute.models import *
from student.models import *
from manager.models import *
from common.utils import auto_grade_answer

import csv
from io import StringIO
from django.core.paginator import Paginator

logger = logging.getLogger(__name__)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count
from teacher.models import Exam, StudentAnswer  # Assuming these are your models
from institute.models import Institution, Class, TeacherProfile, StudentProfile
from .forms import ClassStudentForm  # Assuming this exists
from users.models import User 
from student.models import MalpracticeLog



@login_required(login_url='users:login')
def dashboard(request):
    if not request.user.is_teacher:
        messages.error(request, "Access denied.")
        return redirect('users:login')
    
    # Ensure TeacherProfile exists before anything else
    teacher_profile = getattr(request.user, 'teacher_profile', None)
    if not teacher_profile:
        institution = Institution.objects.filter(manager__is_manager=True).first()
        if not institution:
            messages.error(request, "No institution available. Contact an admin.")
            return redirect('users:login')
        teacher_profile, created = TeacherProfile.objects.get_or_create(
            user=request.user,
            defaults={'institution': institution}
        )
    institution = teacher_profile.institution
    
    exams = Exam.objects.filter(created_by=request.user).select_related('subject')
    total_exams = exams.count()
    total_students = StudentAnswer.objects.filter(question__exam__created_by=request.user).values('student').distinct().count()
    active_exams = exams.filter(is_approved=True, is_active=True).count()
    pending_grading = StudentAnswer.objects.filter(question__exam__created_by=request.user, score__isnull=True).count()
    recent_exams = exams.order_by('-created_at')[:5]
    
    classes = teacher_profile.classes.all() 
    subjects = teacher_profile.subjects.all()
    recent_exams_with_topics = [
        {'exam': exam, 'topics': [t.strip() for t in exam.topics.split(',')] if exam.topics else []}
        for exam in recent_exams
    ]
    
    exam_statistics = []
    for exam in exams:
        stats = StudentAnswer.objects.filter(question__exam=exam).values('student').annotate(
            total_score=Sum('score', default=0),
            questions_answered=Count('question')
        )
        total_students = stats.count()
        if total_students:
            avg_score = sum(s['total_score'] for s in stats) / total_students
            completion_rate = (sum(s['questions_answered'] for s in stats) / (total_students * exam.num_questions)) * 100
            exam_statistics.append({
                'exam': exam,
                'total_students': total_students,
                'average_score': avg_score,
                'completion_rate': completion_rate,
                'highest_score': max((s['total_score'] for s in stats), default=0),
                'lowest_score': min((s['total_score'] for s in stats), default=0),
            })
    
    if request.method == 'POST' and 'assign_students' in request.POST:
        form = ClassStudentForm(request.POST, user=request.user)
        if form.is_valid():
            class_obj = form.cleaned_data['class_obj']
            students = form.cleaned_data['students']
            try:
                with transaction.atomic():
                    for student in students:
                        student_profile, created = StudentProfile.objects.get_or_create(
                            user=student,
                            defaults={'institution': class_obj.institution}
                        )
                        student_profile.classes.add(class_obj)
                    messages.success(request, f"Assigned {len(students)} students to {class_obj.name}.")
                    return redirect('teacher:dashboard')
            except Exception as e:
                messages.error(request, f"Error assigning students: {str(e)}")
    else:
        form = ClassStudentForm(user=request.user)
    
    context = {
        'exams': exams,
        'total_exams': total_exams,
        'total_students': total_students,
        'active_exams': active_exams,
        'pending_grading': pending_grading,
        'recent_exams': recent_exams_with_topics,
        'exam_statistics': exam_statistics,
        'classes': classes,
        'subjects': subjects,
        'form': form,
    }
    return render(request, 'testapp/teacher_dashboard.html', context)


@login_required(login_url='users:login')
def manage_class_students(request, class_id=None):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Only teachers can manage classes.")
        return redirect('teacher:dashboard')

    # Get or create a TeacherProfile
    teacher_profiles = request.user.teacher_profiles.all()
    if not teacher_profiles:
        institution = Institution.objects.filter(manager__is_manager=True).first()
        if not institution:
            messages.error(request, "No institution available. Contact an admin.")
            return redirect('teacher:dashboard')
        teacher_profile = TeacherProfile.objects.create(user=request.user, institution=institution)
        logger.info(f"Created TeacherProfile for {request.user.email}")
    else:
        teacher_profile = teacher_profiles[0]

    # Handle class retrieval or creation
    if class_id:
        # Check if the class exists and the teacher is assigned to it
        try:
            class_obj = Class.objects.get(id=class_id)
            if not class_obj.teachers.filter(id=request.user.id).exists():
                messages.error(request, f"You are not assigned to the class with ID {class_id}.")
                return redirect('teacher:dashboard')
        except Class.DoesNotExist:
            messages.error(request, f"Class with ID {class_id} does not exist.")
            return redirect('teacher:dashboard')
    else:
        # Create a new class if class_id is not provided
        class_obj = Class.objects.create(
            name=f"Class by {request.user.email} - {timezone.now().strftime('%Y%m%d')}",
            institution=teacher_profile.institution
        )
        class_obj.teachers.add(request.user)
        messages.success(request, f"Created new class: {class_obj.name}")
        logger.info(f"Created class {class_obj.name} for {request.user.email}")

    # Get students not already in the class and current students in the class
    students = User.objects.filter(is_student=True).exclude(student_profile__classes=class_obj)
    class_students = User.objects.filter(student_profile__classes=class_obj)

    if request.method == 'POST':
        student_ids = request.POST.getlist('students')
        try:
            with transaction.atomic():
                selected_students = User.objects.filter(id__in=student_ids, is_student=True)
                for student in selected_students:
                    student_profile, created = StudentProfile.objects.get_or_create(
                        user=student,
                        defaults={'institution': class_obj.institution}
                    )
                    student_profile.classes.add(class_obj)
                messages.success(request, f"Added {len(selected_students)} students to {class_obj.name}.")
                logger.info(f"Added {len(selected_students)} students to {class_obj.name}")
                return redirect('teacher:manage_class_students', class_id=class_obj.id)
        except Exception as e:
            messages.error(request, f"Error adding students: {str(e)}")
            logger.error(f"Error adding students to {class_obj.name}: {str(e)}")

    context = {
        'class_obj': class_obj,
        'students': students,
        'class_students': class_students,
    }
    return render(request, 'testapp/manage_class_students.html', context)




@login_required(login_url='users:login')
def create_exam(request):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. You must be a teacher to create exams.")
        return redirect('teacher:dashboard')

    # Get or create a TeacherProfile
    teacher_profiles = request.user.teacher_profiles.all()
    if not teacher_profiles:
        institution = Institution.objects.filter(manager__is_manager=True).first()
        if not institution:
            messages.error(request, "No institution available. An institute or manager must set one up first.")
            return redirect('teacher:dashboard')
        teacher_profile = TeacherProfile.objects.create(user=request.user, institution=institution)
        logger.info(f"Created TeacherProfile for {request.user.email}")
        messages.success(request, "Teacher profile created with default institution.")
    else:
        teacher_profile = teacher_profiles[0]  # Use first profile; adjust if needed

    institution = teacher_profile.institution
    if not institution:
        messages.warning(request, "Your profile lacks an institution. Contact an administrator.")
        return redirect('teacher:dashboard')

    form = ExamForm(request.POST or None, user=request.user)
    classes = teacher_profile.classes.all()

    if request.method == 'POST':
        if form.is_valid():
            try:
                with transaction.atomic():
                    exam = form.save(commit=False)
                    exam.created_by = request.user
                    if form.cleaned_data.get('use_template') and form.cleaned_data.get('template'):
                        template = form.cleaned_data['template']
                        exam.topics = template.topics
                        exam.num_questions = template.num_questions
                        exam.total_marks = template.total_marks
                        exam.difficulty_level = template.difficulty_level
                    exam.save()
                    form.save_m2m()

                    # Validate total_marks against question marks after saving
                    total_question_marks = exam.questions.aggregate(total=models.Sum('marks'))['total'] or 0
                    if exam.total_marks < total_question_marks:
                        # Delete the exam to rollback the transaction
                        exam.delete()
                        form.add_error(
                            'total_marks',
                            f"Total marks ({exam.total_marks}) cannot be less than the sum of question marks ({total_question_marks})."
                        )
                        raise ValueError("Total marks validation failed.")

                    exam_datetime = timezone.make_aware(datetime.combine(exam.date, exam.start_time))
                    if exam_datetime > timezone.now():
                        student_emails = User.objects.filter(
                            is_student=True,
                            student_profile__classes__in=exam.classes.all()
                        ).values_list('email', flat=True).distinct()
                        if student_emails:
                            try:
                                send_mail(
                                    subject=f'Upcoming Exam: {exam.title}',
                                    message=f'The exam "{exam.title}" is scheduled for {exam_datetime.strftime("%Y-%m-%d %H:%M")}. Prepare accordingly!',
                                    from_email='admin@aiexam.com',
                                    recipient_list=list(student_emails),
                                    fail_silently=False,
                                )
                                exam.scheduled_notification = True
                                exam.save()
                                logger.info(f"Sent notification for exam {exam.id} to {len(student_emails)} students")
                            except Exception as e:
                                logger.error(f"Notification failed for exam {exam.id}: {str(e)}")
                                messages.warning(request, f"Exam created, but notification failed: {str(e)}")
                        else:
                            messages.warning(request, "Exam created, but no students found in selected classes.")
                            logger.warning(f"No students found for exam {exam.id}")

                    messages.success(request, "Exam created successfully!")
                    return redirect('teacher:generate_questions', exam_id=exam.id)
            except ValueError as ve:
                # Handle validation errors related to total_marks
                messages.error(request, str(ve))
            except Exception as e:
                messages.error(request, f"Error creating exam: {str(e)}")
                logger.error(f"Error creating exam: {str(e)}")

    return render(request, 'testapp/create_exam.html', {
        'form': form,
        'teacher_profile': teacher_profile,
        'classes': classes,
    })

@login_required(login_url='users:login')
def edit_exam(request, exam_id):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Only teachers can edit exams.")
        return redirect('teacher:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)

    # Get or create a TeacherProfile
    teacher_profiles = request.user.teacher_profiles.all()
    if not teacher_profiles:
        institution = Institution.objects.filter(manager__is_manager=True).first()
        if not institution:
            messages.error(request, "No institution available. Contact an admin to set one up.")
            return redirect('teacher:dashboard')
        teacher_profile = TeacherProfile.objects.create(user=request.user, institution=institution)
        logger.info(f"Created TeacherProfile for {request.user.email}")
        messages.success(request, "Teacher profile created with default institution.")
    else:
        teacher_profile = teacher_profiles[0]  # Use first profile; adjust if needed

    institution = teacher_profile.institution
    if not institution:
        messages.warning(request, "Your profile lacks an institution. Contact an admin.")
        return redirect('teacher:dashboard')

    subjects = Subject.objects.filter(institution=institution)
    classes = Class.objects.filter(institution=institution)
    form = ExamForm(request.POST or None, instance=exam, user=request.user)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                exam = form.save(commit=False)
                exam.created_by = request.user
                exam.save()
                form.save_m2m()

                if 'reconduct' in request.POST:
                    ExamAttempt.objects.filter(exam=exam).delete()
                    StudentAnswer.objects.filter(question__exam=exam).delete()
                    exam.is_approved = False
                    exam.is_published = False
                    exam.save()
                    messages.success(request, "Exam rescheduled and reset for reconduction.")
                    logger.info(f"Exam {exam.id} reset for reconduction")

                    exam_datetime = timezone.make_aware(datetime.combine(exam.date, exam.start_time))
                    if exam_datetime > timezone.now() and exam.classes.exists():
                        student_emails = User.objects.filter(
                            is_student=True,
                            student_profile__classes__in=exam.classes.all()
                        ).values_list('email', flat=True).distinct()
                        if student_emails:
                            try:
                                send_mail(
                                    subject=f'Rescheduled Exam: {exam.title}',
                                    message=f'The exam "{exam.title}" has been rescheduled to {exam_datetime.strftime("%Y-%m-%d %H:%M")}.',
                                    from_email='admin@aiexam.com',
                                    recipient_list=list(student_emails),
                                    fail_silently=False,
                                )
                                exam.scheduled_notification = True
                                exam.save()
                                messages.success(request, "Students notified via email.")
                                logger.info(f"Sent reschedule notification for exam {exam.id}")
                            except Exception as e:
                                logger.error(f"Failed to send email for exam {exam.id}: {str(e)}")
                                messages.warning(request, f"Exam updated, but email notification failed: {str(e)}")
                else:
                    messages.success(request, "Exam updated successfully!")
                    logger.info(f"Exam {exam.id} updated")

                return redirect('teacher:dashboard')
        except Exception as e:
            logger.error(f"Error updating exam {exam.id}: {str(e)}")
            messages.error(request, f"Error updating exam: {str(e)}")

    if not classes.exists():
        messages.warning(request, "No classes found in your institution. Add classes via 'Manage Students' or contact an admin.")

    return render(request, 'testapp/edit_exam.html', {
        'form': form,
        'exam': exam,
        'subjects': subjects,
        'classes': classes,
    })


@login_required(login_url='users:login')
def generate_questions(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                exam.questions.all().delete()
                marks_per_question = exam.total_marks // exam.num_questions
                remaining_marks = exam.total_marks % exam.num_questions
                topics = [t.strip() for t in exam.topics.split(',') if t.strip()]
                if not topics:
                    raise ValueError("No valid topics provided in exam topics field.")

                for i in range(exam.num_questions):
                    marks = marks_per_question + (1 if i < remaining_marks else 0)
                    topic = topics[i % len(topics)]
                    question_text = generate_ai_question(topic, exam.difficulty_level, i + 1)
                    correct_answer = generate_ai_answer(topic, exam.difficulty_level)
                    Question.objects.create(
                        exam=exam,
                        question_text=question_text,
                        correct_answer=correct_answer,
                        marks=marks,
                        explanation="AI-generated explanation pending review",
                        order=i + 1  # Add order field to maintain sequence
                    )
                messages.success(request, f"{exam.num_questions} questions generated successfully! Please review and approve.")
                logger.info(f"Generated {exam.num_questions} questions for exam {exam_id} by {request.user.email}")
                return redirect('teacher:review_questions', exam_id=exam.id)
        except ValueError as ve:
            logger.error(f"Validation error generating questions for exam {exam_id}: {str(ve)}")
            messages.error(request, f"Validation error: {str(ve)}")
        except Exception as e:
            logger.error(f"Error generating questions for exam {exam_id}: {str(e)}")
            messages.error(request, f"Error generating questions: {str(e)}")
    return render(request, 'testapp/generate_questions.html', {'exam': exam})


@login_required(login_url='users:login')
def review_questions(request, exam_id):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Only teachers can review questions.")
        return redirect('teacher:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    questions = exam.questions.order_by('order').all()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                total_marks = 0
                for question in questions:
                    q_text = request.POST.get(f'question_{question.id}')
                    c_answer = request.POST.get(f'answer_{question.id}')
                    marks = request.POST.get(f'marks_{question.id}')
                    explanation = request.POST.get(f'explanation_{question.id}', '')
                    if q_text and c_answer and marks:
                        question.question_text = q_text
                        question.correct_answer = c_answer
                        question.marks = int(marks)
                        question.explanation = explanation
                        question.save()
                        total_marks += int(marks)
                
                if total_marks != exam.total_marks:
                    messages.warning(request, f"Total marks ({total_marks}) do not match exam total ({exam.total_marks}). Adjust marks accordingly.")
                    return render(request, 'testapp/review_questions.html', {'exam': exam, 'questions': questions})

                action = request.POST.get('action')
                if action == 'approve':
                    exam.is_approved = True
                    exam.save()
                    messages.success(request, "Exam questions approved and exam activated!")
                    return redirect('teacher:dashboard')
                elif action == 'save':
                    messages.success(request, "Questions updated successfully!")
                    return redirect('teacher:review_questions', exam_id=exam.id)

        except Exception as e:
            logger.error(f"Error reviewing questions for exam {exam_id}: {str(e)}")
            messages.error(request, f"Error updating questions: {str(e)}")

    return render(request, 'testapp/review_questions.html', {
        'exam': exam,
        'questions': questions,
    })


@login_required(login_url='users:login')
def review_exam(request, exam_id):
    if not request.user.is_teacher:
        messages.error(request, "Access denied. Only teachers can review exams.")
        return redirect('teacher:dashboard')

    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    attempts = ExamAttempt.objects.filter(exam=exam, completed=True).select_related('student').prefetch_related('exam__student_answers')

    if not attempts:
        messages.info(request, "No student submissions available for review.")
        return redirect('teacher:dashboard')

    # Handle POST actions
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'export_csv':
            return export_review_data(exam, attempts)
        elif action == 'ajax_update':
            return ajax_update_grade(request, exam)
        elif action == 'mark_reviewed':
            # Handle marking malpractices as reviewed
            malpractice_id = request.POST.get('malpractice_id')
            try:
                malpractice = MalpracticeLog.objects.get(id=malpractice_id, exam=exam)
                malpractice.is_reviewed = True
                malpractice.save()
                return JsonResponse({'success': True})
            except MalpracticeLog.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Malpractice log not found'}, status=404)

        try:
            with transaction.atomic():
                for attempt in attempts:
                    answers = StudentAnswer.objects.filter(exam=exam, student=attempt.student)
                    for answer in answers:
                        score_key = f'score_{answer.id}'
                        feedback_key = f'feedback_{answer.id}'
                        score = request.POST.get(score_key)
                        feedback = request.POST.get(feedback_key, '')
                        if score is not None:
                            score = float(score)
                            if score < 0 or score > answer.question.marks:
                                raise ValueError(f"Score {score} for Q{answer.question.order} is out of range (0-{answer.question.marks})")
                            answer.score = score
                            answer.feedback = feedback
                            answer.graded_by = request.user
                            answer.graded_at = timezone.now()
                            answer.save()

                if 'publish' in request.POST:
                    exam.is_published = True
                    exam.status = 'completed'
                    exam.save()
                    messages.success(request, "Exam results published successfully!")
                    return redirect('teacher:dashboard')
                messages.success(request, "Grades updated successfully!")
        except ValueError as e:
            messages.error(request, f"Invalid score: {e}")
        except Exception as e:
            messages.error(request, f"Error updating grades: {e}")
        return redirect('teacher:review_exam', exam_id=exam.id)

    # Filters and Sorting
    malpractice_filter = request.GET.get('malpractice_filter', 'all')
    sort_by = request.GET.get('sort_by', 'student__username')
    page = request.GET.get('page', 1)

    # Fetch all malpractice logs for the exam
    all_malpractices = MalpracticeLog.objects.filter(exam=exam).select_related('student').order_by('timestamp')
    if malpractice_filter != 'all':
        all_malpractices = all_malpractices.filter(type=malpractice_filter)

    # Prepare student data
    student_answers = {}
    for attempt in attempts:
        answers = StudentAnswer.objects.filter(exam=exam, student=attempt.student).select_related('question').order_by('question__order')
        total_marks = attempt.exam.total_marks
        malpractices = MalpracticeLog.objects.filter(exam_id=exam.id, attempt_uuid=attempt.attempt_uuid).order_by('timestamp')
        
        if malpractice_filter != 'all':
            malpractices = malpractices.filter(type=malpractice_filter)
        
        student_answers[attempt.student] = {
            'answers': answers,
            'total_marks': total_marks,
            'malpractices': malpractices,
            'attempt': attempt,
            'total_score': sum(a.score or 0 for a in answers),
            'malpractice_count': malpractices.count(),
        }

    # Sorting
    sorted_students = sorted(student_answers.items(), key=lambda x: getattr(x[0], sort_by.split('__')[1]) if '__' in sort_by else x[1][sort_by])

    # Pagination
    paginator = Paginator(sorted_students, 5)  # 5 students per page
    page_obj = paginator.get_page(page)

    # Exam statistics
    stats = {
        'avg_score': exam.average_score(),
        'submission_count': exam.total_submissions(),
        'malpractice_total': MalpracticeLog.objects.filter(exam_id=exam.id).count(),
    }

    context = {
        'exam': exam,
        'student_answers': dict(page_obj.object_list),
        'all_malpractices': all_malpractices,  # Add all malpractice logs to context
        'malpractice_types': [t[0] for t in MalpracticeLog.MALPRACTICE_TYPES],
        'selected_filter': malpractice_filter,
        'sort_by': sort_by,
        'stats': stats,
        'page_obj': page_obj,
    }
    return render(request, 'testapp/review_exam.html', context)

def ajax_update_grade(request, exam):
    if request.method != 'POST' or not request.user.is_teacher:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=403)
    
    answer_id = request.POST.get('answer_id')
    score = request.POST.get('score')
    feedback = request.POST.get('feedback', '')

    try:
        answer = StudentAnswer.objects.get(id=answer_id, exam=exam)
        score = float(score) if score else None
        if score is not None and (score < 0 or score > answer.question.marks):
            return JsonResponse({'success': False, 'error': f'Score out of range (0-{answer.question.marks})'})
        
        answer.score = score
        answer.feedback = feedback
        answer.graded_by = request.user
        answer.graded_at = timezone.now()
        answer.save()
        return JsonResponse({'success': True, 'total_score': sum(a.score or 0 for a in StudentAnswer.objects.filter(exam=exam, student=answer.student))})
    except StudentAnswer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Answer not found'}, status=404)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid score value'})

def export_review_data(exam, attempts):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="review_{exam.title}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Student', 'Question Order', 'Question Text', 'Answer', 'Correct Answer', 'Score', 'Feedback', 
        'Malpractices', 'Severity', 'Attempt Started', 'Attempt Completed', 'Time Taken'
    ])
    
    for attempt in attempts:
        answers = StudentAnswer.objects.filter(exam=exam, student=attempt.student).select_related('question')
        malpractices = MalpracticeLog.objects.filter(exam_id=exam.id, attempt_uuid=attempt.attempt_uuid)
        malpractice_summary = "; ".join([f"{m.get_type_display()} ({m.severity}): {m.message}" for m in malpractices])
        
        for answer in answers:
            writer.writerow([
                attempt.student.username,
                answer.question.order,
                answer.question.question_text,
                answer.answer_text or 'Not answered',
                answer.question.correct_answer,
                answer.score if answer.score is not None else '',
                answer.feedback,
                malpractice_summary,
                max(m.severity for m in malpractices) if malpractices else 0,
                attempt.start_time,
                attempt.end_time or '',
                str(attempt.time_taken) if attempt.time_taken else ''
            ])
    
    return response


@login_required
def exam_results(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    logger.info(f"Exam {exam_id} fetched: {exam.title}")

    attempts = ExamAttempt.objects.filter(exam=exam, completed=True).select_related('student')
    total_students = attempts.count()
    logger.info(f"Total completed attempts: {total_students}")

    pending_grading = StudentAnswer.objects.filter(question__exam=exam, score__isnull=True).count()
    logger.info(f"Pending grading count: {pending_grading}")

    # Aggregate stats
    completion_rate = (attempts.count() / total_students * 100) if total_students > 0 else 0
    scores = StudentAnswer.objects.filter(question__exam=exam).aggregate(
        avg_score=Avg('score'), total=Sum('question__marks')
    )
    # Handle None cases for both avg_score and total
    if scores['avg_score'] is not None and scores['total']:
        average_score = (scores['avg_score'] / scores['total']) * 100
    else:
        average_score = 0
    logger.info(f"Average score: {average_score}, Completion rate: {completion_rate}")

    students_data = []
    for attempt in attempts:
        student_answers = StudentAnswer.objects.filter(student=attempt.student, question__exam=exam)
        total_score = sum(a.score or 0 for a in student_answers)
        total_possible = sum(a.question.marks for a in student_answers)
        student_data = {
            'student': attempt.student,
            'total_score': total_score,
            'total_possible': total_possible,
            'percentage': (total_score / total_possible * 100) if total_possible > 0 else 0,
            'graded': all(a.score is not None for a in student_answers),
            'time_taken': attempt.time_taken,
        }
        students_data.append(student_data)
        logger.info(f"Student {attempt.student.email}: Score {total_score}/{total_possible}, Graded: {student_data['graded']}")

    if not students_data:
        messages.info(request, "No students have completed this exam yet.")

    context = {
        'exam': exam,
        'students_data': students_data,
        'total_students': total_students,
        'average_score': average_score,
        'completion_rate': completion_rate,
        'pending_grading': pending_grading,
    }
    return render(request, 'testapp/exam_results.html', context)


@login_required(login_url='users:login')
def review_student_answers(request, exam_id, student_id):
    exam = get_object_or_404(Exam, id=exam_id, created_by=request.user)
    student = get_object_or_404(User, id=student_id, is_student=True)
    attempt = get_object_or_404(ExamAttempt, exam=exam, student=student, completed=True)
    answers = StudentAnswer.objects.filter(student=student, question__exam=exam).select_related('question')

    logger.info(f"Fetching answers for exam {exam_id}, student {student.email}: {answers.count()} answers found")

    if request.method == 'POST':
        try:
            with transaction.atomic():
                for answer in answers:
                    score_key = f'score_{answer.id}'
                    feedback_key = f'feedback_{answer.id}'
                    if score_key in request.POST:
                        score = request.POST.get(score_key).strip()
                        feedback = request.POST.get(feedback_key, '').strip()
                        try:
                            answer.score = int(score) if score else None
                            if answer.score is not None and (answer.score < 0 or answer.score > answer.question.marks):
                                raise ValueError(f"Score {answer.score} out of range for question {answer.question.id}")
                        except ValueError as e:
                            messages.error(request, f"Invalid score for Question {answer.question.id}: {str(e)}")
                            return render(request, 'testapp/review_student_answers.html', {
                                'exam': exam,
                                'student': student,
                                'answers': answers,
                            })
                        answer.feedback = feedback
                        answer.graded_by = request.user
                        answer.graded_at = timezone.now()
                        answer.save()
                        logger.info(f"Graded answer {answer.id} for {student.email} with score {answer.score}")

                if 'publish' in request.POST and not exam.is_published:
                    exam.is_published = True
                    exam.save()
                    messages.success(request, "Results published successfully!")
                    logger.info(f"Published results for exam {exam.id}")
                else:
                    messages.success(request, "Grades saved successfully!")
                
                return redirect('teacher:exam_results', exam_id=exam.id)

        except Exception as e:
            logger.error(f"Error processing grades for exam {exam_id}, student {student_id}: {str(e)}")
            messages.error(request, f"Failed to save grades: {str(e)}")

    # Prepare AI suggestions
    answer_data = []
    for answer in answers:
        ai_score = None
        ai_feedback = None
        if answer.score is None and answer.answer_text:
            try:
                ai_score, ai_feedback = auto_grade_answer(
                    answer.answer_text,
                    answer.question.correct_answer,
                    answer.question.marks
                )
            except Exception as e:
                logger.warning(f"AI grading failed for answer {answer.id}: {str(e)}")
                ai_feedback = f"AI grading unavailable: {str(e)}"
        answer_data.append({
            'answer': answer,
            'ai_score': ai_score,
            'ai_feedback': ai_feedback,
        })

    context = {
        'exam': exam,
        'student': student,
        'answers': answer_data,
    }
    return render(request, 'testapp/review_student_answers.html', context)


@login_required
def save_answer(request):
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        answer_text = request.POST.get('answer_text')
        question = get_object_or_404(Question, id=question_id)
        StudentAnswer.objects.update_or_create(
            student=request.user,
            question=question,
            defaults={'answer_text': answer_text}
        )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    