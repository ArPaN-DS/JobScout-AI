from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_application_screenshot_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidatepreference",
            name="min_match_score",
            field=models.PositiveSmallIntegerField(default=60),
        ),
        migrations.AddField(
            model_name="candidatepreference",
            name="min_match_confidence",
            field=models.PositiveSmallIntegerField(default=50),
        ),
    ]
