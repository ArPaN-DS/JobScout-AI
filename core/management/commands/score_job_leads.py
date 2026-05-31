from django.core.management.base import BaseCommand

from core.tasks import score_unscored_leads


class Command(BaseCommand):
    help = "Score imported job leads using the configured provider router."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        count = score_unscored_leads(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Scored {count} job lead(s)."))
