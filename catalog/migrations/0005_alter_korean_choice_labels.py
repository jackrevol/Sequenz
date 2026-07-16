from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_productvariant_reserved_quantity")]
    operations = [
        migrations.AlterField(model_name="productimage", name="source", field=models.CharField(choices=[("sabangnet", "사방넷"), ("admin", "관리자 등록")], default="sabangnet", max_length=20)),
        migrations.AlterField(model_name="productlisting", name="status", field=models.CharField(choices=[("draft", "작성 중"), ("scheduled", "게시 예정"), ("active", "판매 중"), ("paused", "판매 일시중지"), ("ended", "판매 종료"), ("archived", "보관")], db_index=True, default="draft", max_length=20)),
        migrations.AlterField(model_name="productlistingvariant", name="status", field=models.CharField(choices=[("active", "판매 중"), ("hidden", "숨김"), ("sold_out", "품절"), ("paused", "판매 일시중지")], db_index=True, default="active", max_length=20)),
        migrations.AlterField(model_name="productsyncsnapshot", name="status", field=models.CharField(choices=[("created", "신규 등록"), ("updated", "정보 갱신"), ("failed", "실패")], db_index=True, max_length=20)),
    ]
