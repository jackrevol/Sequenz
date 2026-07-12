import django.db.models.deletion
from django.db import migrations, models


def normalize_statuses(apps, schema_editor):
    export_model = apps.get_model("integrations", "SabangnetOrderExport")
    export_model.objects.filter(status="sent").update(status="registered")
    export_model.objects.filter(status__in=["failed", "retrying"]).update(status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0001_initial"),
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="SabangnetOrderSubmission",
            new_name="SabangnetOrderExport",
        ),
        migrations.RemoveConstraint(
            model_name="sabangnetorderexport",
            name="unique_sabangnet_submission_idempotency",
        ),
        migrations.RunPython(normalize_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sabangnetorderexport",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("generated", "File generated"),
                    ("registered", "Registered"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="sabangnetorderexport",
            name="order",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sabangnet_export",
                to="commerce.order",
            ),
        ),
        migrations.AddField(
            model_name="sabangnetorderexport",
            name="generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sabangnetorderexport",
            name="filename",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="sabangnetorderexport",
            name="row_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RemoveField(model_name="sabangnetorderexport", name="attempt_count"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="external_request_id"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="last_attempt_at"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="last_error_message"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="next_retry_at"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="operation_idempotency_key"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="sabangnet_order_no"),
        migrations.RemoveField(model_name="sabangnetorderexport", name="terminal_failure_at"),
    ]
