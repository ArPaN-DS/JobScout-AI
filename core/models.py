from django.db import models
from django.utils import timezone

class Application(models.Model):
    job_url = models.URLField(max_length=500, blank=True, null=True)
    job_description = models.TextField()
    match_score = models.IntegerField(null=True, blank=True)
    tailored_resume = models.JSONField(null=True, blank=True)
    cover_letter = models.TextField(null=True, blank=True)
    submitted = models.BooleanField(default=False)
    date_submitted = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def mark_submitted(self):
        self.submitted = True
        self.date_submitted = timezone.now()
        self.save()

    def __str__(self):
        return f"App for {self.job_url[:50]}... ({'Submitted' if self.submitted else 'Draft'})"
