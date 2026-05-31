from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Register a daily django-q2 schedule for the discovery pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cron",
            default="0 6 * * *",
            help="Cron expression (default 06:00 daily).",
        )
        parser.add_argument("--score-limit", type=int, default=25)

    def handle(self, *args, **options):
        try:
            from django_q.models import Schedule
        except ImportError as exc:
            self.stderr.write("django-q2 is required: pip install django-q2")
            raise SystemExit(1) from exc

        schedule, created = Schedule.objects.update_or_create(
            name="daily_job_discovery",
            defaults={
                "func": "core.tasks.run_discovery_pipeline",
                "kwargs": {"score_after": True, "score_limit": options["score_limit"]},
                "schedule_type": Schedule.CRON,
                "cron": options["cron"],
                "repeats": -1,
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} schedule '{schedule.name}' ({options['cron']})"))
