import random
import datetime
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import JobPost, JobUpdate, SavedJob, PasswordResetOTP, UserProfile, UserNotification, NewsletterSubscriber

def seed_jobs_if_empty():
    if not JobPost.objects.exists():
        JobPost.objects.create(
            title="RRB Assistant Loco Pilot (ALP)",
            department="Ministry of Railways",
            category="Railway",
            state="All India",
            qualification="10th",
            vacancies=18799,
            min_age=18,
            max_age=30,
            last_date=datetime.date.today() + datetime.timedelta(days=2),
            apply_url="https://indianrailways.gov.in"
        )

# Home View
def home_view(request):
    seed_jobs_if_empty()
    jobs = JobPost.objects.all().order_by('-created_at')

    category = request.GET.get('category')
    state = request.GET.get('state')
    qualification = request.GET.get('qualification')
    search_query = request.GET.get('q')

    if category:
        jobs = jobs.filter(category__iexact=category)
    if state:
        jobs = jobs.filter(state__iexact=state)
    if qualification:
        jobs = jobs.filter(qualification__icontains=qualification)
    if search_query:
        jobs = jobs.filter(title__icontains=search_query) | jobs.filter(department__icontains=search_query)

    updates = JobUpdate.objects.all().order_by('-released_date')[:6]
    
    saved_ids = []
    user_notifications = []
    if request.user.is_authenticated:
        saved_ids = list(SavedJob.objects.filter(user=request.user).values_list('job_id', flat=True))
        user_notifications = UserNotification.objects.filter(user=request.user).order_by('-created_at')[:6]

    return render(request, 'home.html', {
        'jobs': jobs,
        'updates': updates,
        'saved_ids': saved_ids,
        'user_notifications': user_notifications,
        'current_category': category,
        'current_state': state,
        'current_qualification': qualification
    })

# Register View
def register_view(request):
    if request.method == 'POST':
        uname = request.POST.get('username')
        email = request.POST.get('email')
        passw = request.POST.get('password')

        if User.objects.filter(username=uname).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            User.objects.create_user(username=uname, email=email, password=passw)
            messages.success(request, 'Account created successfully! Please Sign In.')
            return redirect('login')
    return render(request, 'register.html')

# Login View
def login_view(request):
    if request.method == 'POST':
        uname = request.POST.get('username')
        passw = request.POST.get('password')
        user = authenticate(request, username=uname, password=passw)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

# Logout View
def logout_view(request):
    logout(request)
    return redirect('login')

# Candidate Profile View (IntegrityError Fix ke sath)
@login_required(login_url='login')
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            request.user.email = email
            request.user.save()

        profile.qualification = request.POST.get('qualification') or 'Graduate'
        profile.preferred_category = request.POST.get('category') or 'Railway'
        # NOT NULL error rokne ke liye fallback 'General'
        profile.caste_category = request.POST.get('caste_category') or 'General'
        profile.save()
        messages.success(request, 'Preferences saved successfully!')
        return redirect('profile')

    matched_jobs = JobPost.objects.filter(
        models.Q(category__iexact=profile.preferred_category) |
        models.Q(qualification__icontains=profile.qualification)
    ).order_by('-created_at')
    
    saved_jobs = SavedJob.objects.filter(user=request.user).select_related('job')

    return render(request, 'profile.html', {
        'profile': profile,
        'matched_jobs': matched_jobs,
        'saved_jobs': saved_jobs
    })

# Resizer Tool View
def resizer_view(request):
    return render(request, 'resizer.html')

# Bookmark Job View
@login_required(login_url='login')
def bookmark_job(request, job_id):
    job = get_object_or_404(JobPost, id=job_id)
    saved = SavedJob.objects.filter(user=request.user, job=job).first()
    if saved:
        saved.delete()
        messages.info(request, f'Removed {job.title} from Saved Jobs.')
    else:
        SavedJob.objects.create(user=request.user, job=job)
        messages.success(request, f'Saved {job.title} to your profile!')
    return redirect(request.META.get('HTTP_REFERER', 'home'))

# Newsletter Subscribe View
def subscribe_newsletter(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            sub, created = NewsletterSubscriber.objects.get_or_create(email=email)
            if created:
                messages.success(request, 'Subscribed for alerts!')
            else:
                messages.info(request, 'Already subscribed!')
    return redirect('home')

# Forgot Password View
def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()

        if user:
            otp_code = str(random.randint(100000, 999999))
            PasswordResetOTP.objects.filter(user=user).delete()
            PasswordResetOTP.objects.create(user=user, otp=otp_code)

            subject = 'Password Reset OTP - GovJobAlert'
            body = f'Hello {user.username},\n\nYour OTP to reset password is: {otp_code}\nValid for 5 minutes.'
            
            try:
                send_mail(subject, body, settings.EMAIL_HOST_USER, [email], fail_silently=False)
                request.session['reset_email'] = email
                messages.success(request, 'OTP sent to your email!')
                return redirect('verify_otp')
            except Exception as e:
                messages.error(request, f'Email error: {e}')
        else:
            messages.error(request, 'Email not registered.')
    return render(request, 'forgot_password.html')

# Verify OTP View
def verify_otp_view(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')

        user = User.objects.filter(email=email).first()
        otp_record = PasswordResetOTP.objects.filter(user=user, otp=entered_otp).first()

        if not otp_record or not otp_record.is_valid():
            messages.error(request, 'Invalid or expired OTP.')
        elif new_pass != confirm_pass:
            messages.error(request, 'Passwords do not match.')
        else:
            user.set_password(new_pass)
            user.save()
            otp_record.delete()
            del request.session['reset_email']
            messages.success(request, 'Password changed! Please log in.')
            return redirect('login')

    return render(request, 'verify_otp.html')