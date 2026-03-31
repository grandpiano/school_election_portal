from django.db import models
from django.utils import timezone
from datetime import timedelta

class UserRoles:
    COMMISSIONER_HEAD = 'Commissioner Head'
    ADMIN_REGISTRAR = 'Admin Registrar'
    STUDENT_DIRECTOR = 'Student Director'
    OBSERVER = 'Observer'
    ALL_ROLES = [COMMISSIONER_HEAD, ADMIN_REGISTRAR, STUDENT_DIRECTOR, OBSERVER]

class Position(models.Model):
    title = models.CharField(max_length=100, unique=True)
    order = models.IntegerField(default=0)
    def __str__(self): return self.title

class Candidate(models.Model):
    name = models.CharField(max_length=200)
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    # CHANGED: Switched from ImageField to URLField for persistent free hosting
    photo_url = models.URLField(
        max_length=500, 
        blank=True, 
        null=True, 
        help_text="Upload to ImgBB and paste the 'Direct Link' here"
    )
    manifesto = models.TextField(blank=True)
    def __str__(self): return f"{self.name} ({self.position.title})"

class Voter(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    has_voted = models.BooleanField(default=False)
    def __str__(self): return f"{self.student_id} - {self.name}"

class VotingToken(models.Model):
    token = models.CharField(max_length=6, unique=True)
    voter = models.OneToOneField('Voter', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        now = timezone.now()
        return not self.used and now <= (self.expires_at + timedelta(seconds=30))

    def __str__(self):
        return f"Token {self.token} for {self.voter.name}"

class Vote(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    user = models.CharField(max_length=100)
    action = models.CharField(max_length=255)
    details = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

class ElectionConfig(models.Model):
    title = models.CharField(max_length=200, default="University General Election 2026")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    results_certified = models.BooleanField(default=False)
    certified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Election Configuration"
        verbose_name_plural = "Election Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1  
        super(ElectionConfig, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1, defaults={
            'start_time': timezone.now() - timedelta(hours=1),
            'end_time': timezone.now() + timedelta(hours=8)
        })
        return obj

    def is_open(self):
        now = timezone.now()
        if not self.start_time or not self.end_time:
            return False
        return self.start_time <= now <= self.end_time