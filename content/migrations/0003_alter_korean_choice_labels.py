from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0002_faq_notice_policypage_promotion_lookbook_and_more")]
    operations = [
        migrations.AlterField(model_name="homebanner", name="link_type", field=models.CharField(choices=[("none", "연결 없음"), ("listing", "판매 상품"), ("brand", "브랜드"), ("collection", "컬렉션"), ("external", "외부 URL")], default="none", max_length=20)),
        migrations.AlterField(model_name="homebanner", name="media_type", field=models.CharField(choices=[("image", "이미지"), ("video", "동영상")], default="image", max_length=10)),
        migrations.AlterField(model_name="policypage", name="policy_type", field=models.CharField(choices=[("terms", "이용약관"), ("privacy", "개인정보처리방침"), ("shipping", "배송 정책"), ("returns", "교환·반품 정책")], max_length=30, unique=True)),
    ]
