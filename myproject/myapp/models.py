import datetime
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

# 1. User Profile (Candidate Skills & Preferences)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    qualification = models.CharField(max_length=100, blank=True, null=True, default='Graduate')
    preferred_category = models.CharField(max_length=50, blank=True, null=True, default='Railway')
    dob = models.DateField(null=True, blank=True)
    caste_category = models.CharField(max_length=50, default='General', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.preferred_category} - {self.qualification})"

@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

# 2. Main Job Post Model
class JobPost(models.Model):
    CATEGORY_CHOICES = [
        ('Railway', 'Indian Railways'),
        ('SSC', 'Staff Selection Commission (SSC)'),
        ('Banking', 'Banking (IBPS/SBI)'),
        ('Defense', 'Defense & Police'),
        ('State PSC', 'State PSC'),
        ('Teaching', 'Teaching / Education'),
    ]

    STATE_CHOICES = [
        ('All India', 'All India (Central)'),
        ('Maharashtra', 'Maharashtra'),
        ('Uttar Pradesh', 'Uttar Pradesh'),
        ('Bihar', 'Bihar'),
        ('Delhi', 'Delhi NCR'),
    ]

    title = models.CharField(max_length=200)
    department = models.CharField(max_length=150)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default='All India')
    qualification = models.CharField(max_length=100)
    vacancies = models.PositiveIntegerField(default=1)
    min_age = models.PositiveIntegerField(default=18)
    max_age = models.PositiveIntegerField(default=30)
    last_date = models.DateField()
    apply_url = models.URLField()
    notification_pdf = models.FileField(upload_to='notifications/', blank=True, null=True)
    
    exam_pattern = models.TextField(default="Tier-1: General Intelligence, Aptitude, GS & English.")
    cutoff_summary = models.CharField(max_length=255, default="UR: 135.5 | OBC: 128.2 | SC: 112.0 | ST: 104.5")
    pyq_url = models.URLField(blank=True, null=True, default="https://ssc.gov.in")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def days_remaining(self):
        today = datetime.date.today()
        return (self.last_date - today).days

    @property
    def is_expired(self):
        return self.last_date < datetime.date.today()

    def get_google_calendar_url(self):
        date_str = self.last_date.strftime('%Y%m%d')
        title_str = f"Last Date: {self.title}"
        details_str = f"Application deadline for {self.department}. Apply at: {self.apply_url}"
        return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title_str}&dates={date_str}/{date_str}&details={details_str}"

    def __str__(self):
        return f"{self.title} - {self.department}"

# 3. User Web Notification History
class UserNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.title}"

# 4. Multi-User Dynamic Matching Signal (Email + Web Inbox)
@receiver(post_save, sender=JobPost)
def send_job_notification(sender, instance, created, **kwargs):
    if not created:
        return

    matching_profiles = UserProfile.objects.filter(
        models.Q(preferred_category__iexact=instance.category) |
        models.Q(qualification__icontains=instance.qualification) |
        models.Q(qualification__iexact=instance.qualification)
    ).select_related('user')

    for profile in matching_profiles:
        candidate = profile.user
        candidate_email = candidate.email

        if not candidate_email or '@' not in candidate_email:
            continue

        # 1. In-App Notification entry
        UserNotification.objects.create(
            user=candidate,
            job=instance,
            title=f"New Job Match: {instance.title}",
            message=f"{instance.department} | Eligibility: {instance.qualification} | Deadline: {instance.last_date}"
        )

        # 2. Personalized Email Dispatch
        subject = f"🎯 Job Match: {instance.title}"
        body = (
            f"Dear {candidate.username},\n\n"
            f"Aapki profile preferences ke matching nayi vacancy aayi hai:\n\n"
            f"🏢 Department: {instance.department}\n"
            f"📌 Post: {instance.title}\n"
            f"🎓 Qualification: {instance.qualification}\n"
            f"👥 Total Vacancies: {instance.vacancies}\n"
            f"🎂 Age: {instance.min_age} - {instance.max_age} Years\n"
            f"⏳ Last Date: {instance.last_date}\n\n"
            f"👉 Apply Online: {instance.apply_url}\n\n"
            f"GovJobAlert Career Portal"
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[candidate_email],
                fail_silently=False
            )
        except Exception as e:
            print(f"Email delivery error for {candidate_email}: {e}")

# 5. Newsletter Subscribers
class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

# 6. Admit Card & Results Updates
class JobUpdate(models.Model):
    UPDATE_TYPES = [
        ('Admit Card', 'Admit Card'),
        ('Result', 'Result'),
        ('Answer Key', 'Answer Key'),
    ]
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name='updates', null=True, blank=True)
    title = models.CharField(max_length=200)
    update_type = models.CharField(max_length=20, choices=UPDATE_TYPES)
    download_url = models.URLField()
    released_date = models.DateField(default=datetime.date.today)

    def __str__(self):
        return f"{self.update_type}: {self.title}"

# 7. Bookmarked Jobs
class SavedJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(JobPost, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')

# 8. Password Reset OTP
class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + datetime.timedelta(minutes=5)