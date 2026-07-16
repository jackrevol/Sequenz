from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("benefits", "0002_alter_pointledger_reason")]
    operations = [
        migrations.AlterField(model_name="coupon", name="discount_type", field=models.CharField(choices=[("fixed", "정액 할인"), ("percent", "정률 할인"), ("free_shipping", "무료배송")], max_length=20)),
        migrations.AlterField(model_name="membercoupon", name="status", field=models.CharField(choices=[("available", "사용 가능"), ("used", "사용 완료"), ("expired", "기간 만료")], db_index=True, default="available", max_length=20)),
        migrations.AlterField(model_name="pointledger", name="reason", field=models.CharField(choices=[("order_use", "주문 사용"), ("order_earn", "주문 적립"), ("order_earn_reversal", "주문 적립 취소"), ("review_earn", "리뷰 적립"), ("cancel_restore", "취소 복원"), ("admin", "관리자 조정"), ("expire", "유효기간 만료")], max_length=30)),
    ]
