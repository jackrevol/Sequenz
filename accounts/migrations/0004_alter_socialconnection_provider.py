from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_shippingaddress")]
    operations = [
        migrations.AlterField(
            model_name="socialconnection",
            name="provider",
            field=models.CharField(choices=[("kakao", "카카오"), ("naver", "네이버")], max_length=20),
        ),
    ]
