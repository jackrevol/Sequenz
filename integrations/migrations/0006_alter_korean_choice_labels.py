from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0005_integrationjob_request_summary")]
    operations = [
        migrations.AlterField(model_name="integrationjob", name="status", field=models.CharField(choices=[("queued", "대기"), ("running", "진행 중"), ("succeeded", "성공"), ("failed", "실패"), ("partial", "일부 성공")], db_index=True, default="queued", max_length=20)),
        migrations.AlterField(model_name="sabangnetorderexport", name="status", field=models.CharField(choices=[("pending", "대기"), ("generated", "파일 생성"), ("registered", "사방넷 등록 완료"), ("failed", "실패")], db_index=True, default="pending", max_length=20)),
    ]
