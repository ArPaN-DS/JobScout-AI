from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_match_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidatepreference",
            name="job_freshness_hours",
            field=models.PositiveSmallIntegerField(default=24),
        ),
        migrations.AddField(
            model_name="candidatepreference",
            name="discovery_sources",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
