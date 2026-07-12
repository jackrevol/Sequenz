from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MemberBenefitAccount, MemberCoupon, PointLedger, ShippingPolicy
from .serializers import MemberBenefitSerializer, MemberCouponSerializer, PointLedgerSerializer


class MyBenefitsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account, _ = MemberBenefitAccount.objects.select_related("tier").get_or_create(user=request.user)
        coupons = MemberCoupon.objects.filter(user=request.user).select_related("coupon")
        return Response({
            "account": MemberBenefitSerializer(account).data,
            "coupons": MemberCouponSerializer(coupons, many=True).data,
        })


class PointLedgerListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PointLedgerSerializer

    def get_queryset(self):
        account, _ = MemberBenefitAccount.objects.get_or_create(user=self.request.user)
        return PointLedger.objects.filter(account=account)


class ShippingPolicyView(APIView):
    def get(self, request):
        policy = ShippingPolicy.objects.filter(is_active=True, is_default=True).first()
        return Response({
            "base_fee": policy.base_fee if policy else 0,
            "free_shipping_threshold": policy.free_shipping_threshold if policy else 0,
        })
