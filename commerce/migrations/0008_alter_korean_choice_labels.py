from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("commerce", "0007_alter_orderclaim_claim_type")]
    operations = [
        migrations.AlterField(model_name="cart", name="status", field=models.CharField(choices=[("active", "사용 중"), ("ordered", "주문 완료"), ("abandoned", "이탈")], db_index=True, default="active", max_length=20)),
        migrations.AlterField(model_name="order", name="fulfillment_status", field=models.CharField(choices=[("pending", "상품 준비 전"), ("preparing", "상품 준비 중"), ("ready_to_ship", "출고 대기"), ("shipped", "출고 완료"), ("in_transit", "배송 중"), ("delivered", "배송 완료"), ("cancelled", "배송 취소"), ("returned", "반품 완료")], db_index=True, default="pending", max_length=30)),
        migrations.AlterField(model_name="order", name="inventory_reservation_status", field=models.CharField(choices=[("none", "예약 없음"), ("reserved", "재고 예약"), ("consumed", "원천 재고 반영"), ("released", "예약 해제")], db_index=True, default="none", max_length=20)),
        migrations.AlterField(model_name="order", name="status", field=models.CharField(choices=[("payment_pending", "결제 대기"), ("paid", "결제 완료"), ("payment_failed", "결제 실패"), ("cancelled", "주문 취소")], db_index=True, default="payment_pending", max_length=30)),
        migrations.AlterField(model_name="ordercancellation", name="status", field=models.CharField(choices=[("requested", "요청"), ("completed", "완료"), ("failed", "실패")], db_index=True, default="requested", max_length=20)),
        migrations.AlterField(model_name="orderclaim", name="claim_type", field=models.CharField(choices=[("exchange", "교환"), ("return", "반품")], db_index=True, max_length=30)),
        migrations.AlterField(model_name="orderclaim", name="status", field=models.CharField(choices=[("requested", "요청"), ("processing", "처리 중"), ("completed", "완료"), ("rejected", "거절"), ("failed", "실패")], db_index=True, default="requested", max_length=20)),
        migrations.AlterField(model_name="orderstatushistory", name="source", field=models.CharField(choices=[("system", "시스템"), ("sabangnet", "사방넷"), ("admin", "관리자")], max_length=20)),
        migrations.AlterField(model_name="paymentattempt", name="status", field=models.CharField(choices=[("created", "생성"), ("confirmed", "승인 완료"), ("failed", "실패"), ("unknown", "상태 미확인")], db_index=True, default="created", max_length=20)),
    ]
