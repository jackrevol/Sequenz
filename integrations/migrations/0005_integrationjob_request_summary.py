from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0004_alter_integrationjob_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationjob",
            name="request_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
