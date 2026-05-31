from django.core.management.base import BaseCommand

from core.tasks import run_discovery_pipeline


class Command(BaseCommand):
    help = "Run the discovery pipeline (all enabled sources) and score new leads."

    def add_arguments(self, parser):
        parser.add_argument("--no-score", action="store_true", help="Only ingest jobs, do not score.")
        parser.add_argument("--score-limit", type=int, default=20)

    def handle(self, *args, **options):
        result = run_discovery_pipeline(
            score_after=not options["no_score"],
            score_limit=options["score_limit"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Discovery complete: imported {result['total_imported']} new leads, "
                f"scored {result.get('scored', 0)}."
            )
        )
        for row in result.get("results", []):
            line = f"  {row['source_id']}: +{row['imported']} imported ({row['discovered']} found)"
            if row.get("error"):
                line += f" — {row['error'][:80]}"
            self.stdout.write(line)
