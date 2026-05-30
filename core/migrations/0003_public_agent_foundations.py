import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_application_ai_metadata_application_error_message_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(db_index=True, default="manual", max_length=60)),
                ("source_name", models.CharField(blank=True, max_length=120)),
                ("external_id", models.CharField(blank=True, max_length=200)),
                ("job_url", models.URLField(blank=True, max_length=700, null=True)),
                ("title", models.CharField(blank=True, max_length=240)),
                ("company", models.CharField(blank=True, max_length=240)),
                ("location", models.CharField(blank=True, max_length=240)),
                ("remote_type", models.CharField(blank=True, max_length=60)),
                ("salary_text", models.CharField(blank=True, max_length=240)),
                ("description", models.TextField(blank=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("discovered_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("scored", "Scored"),
                            ("matched", "Matched"),
                            ("low_match", "Low Match"),
                            ("dismissed", "Dismissed"),
                            ("kit_ready", "Kit Ready"),
                            ("applied", "Applied"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="new",
                        max_length=20,
                    ),
                ),
                ("fingerprint", models.CharField(db_index=True, max_length=64, unique=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("match_score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("match_summary", models.TextField(blank=True)),
                ("ai_metadata", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="JobSourceRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(db_index=True, max_length=60)),
                ("source_name", models.CharField(blank=True, max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("started", "Started"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="started",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("discovered_count", models.PositiveIntegerField(default=0)),
                ("imported_count", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="NotificationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("telegram", "Telegram"),
                            ("discord", "Discord"),
                            ("email", "Email"),
                            ("webhook", "Webhook"),
                            ("web", "Web"),
                        ],
                        max_length=20,
                    ),
                ),
                ("event_type", models.CharField(max_length=80)),
                ("recipient", models.CharField(blank=True, max_length=160)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name="application",
            name="follow_up_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="application",
            name="interview_prep_notes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="application",
            name="recruiter_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="application",
            name="source_lead",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applications",
                to="core.joblead",
            ),
        ),
        migrations.AddIndex(
            model_name="joblead",
            index=models.Index(fields=["status", "-discovered_at"], name="core_joblea_status_384921_idx"),
        ),
        migrations.AddIndex(
            model_name="joblead",
            index=models.Index(fields=["source_type", "-discovered_at"], name="core_joblea_source__42dccd_idx"),
        ),
        migrations.AddIndex(
            model_name="joblead",
            index=models.Index(fields=["company", "title"], name="core_joblea_company_c76373_idx"),
        ),
    ]
