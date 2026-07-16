from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("community", "0003_alter_productreviewimage_image")]
    operations = [
        migrations.AlterField(model_name="customerinquiry", name="category", field=models.CharField(choices=[("order", "주문"), ("delivery", "배송"), ("product", "상품"), ("return", "교환·반품"), ("other", "기타")], default="other", max_length=20)),
        migrations.AlterField(model_name="customerinquiry", name="status", field=models.CharField(choices=[("open", "답변 대기"), ("answered", "답변 완료"), ("closed", "종료")], db_index=True, default="open", max_length=20)),
    ]
