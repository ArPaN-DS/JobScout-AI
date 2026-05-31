from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_discovery_preferences"),
    ]

    operations = [
        migrations.CreateModel(
            name="LLMUsageEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_type", models.CharField(db_index=True, max_length=40)),
                ("provider", models.CharField(blank=True, max_length=40)),
                ("model", models.CharField(blank=True, max_length=80)),
                ("token_usage", models.JSONField(blank=True, default=dict)),
                ("estimated_cost_usd", models.FloatField(default=0)),
                ("related_type", models.CharField(blank=True, max_length=40)),
                ("related_id", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name="PipelineJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("discovery", "Discovery"), ("score", "Score Leads"), ("bulk_kit", "Bulk Kit Generation"), ("generate_kit", "Generate Kit")], db_index=True, max_length=32)),
                ("idempotency_key", models.CharField(db_index=True, max_length=48)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="queued", max_length=20)),
                ("progress_current", models.PositiveIntegerField(default=0)),
                ("progress_total", models.PositiveIntegerField(default=0)),
                ("message", models.CharField(blank=True, max_length=240)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="llmusageevent",
            index=models.Index(fields=["-created_at"], name="core_llmusa_created_6e0f0d_idx"),
        ),
        migrations.AddIndex(
            model_name="llmusageevent",
            index=models.Index(fields=["task_type", "-created_at"], name="core_llmusa_task_ty_8c8f1a_idx"),
        ),
        migrations.AddIndex(
            model_name="pipelinejob",
            index=models.Index(fields=["kind", "status", "-created_at"], name="core_pipeli_kind_4a8b2c_idx"),
        ),
    ]
