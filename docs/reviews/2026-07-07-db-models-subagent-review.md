# DB 모델 서브에이전트 리뷰 결과

작성일: 2026-07-07

대상 문서: `docs/db-models.md`

## 리뷰 관점

4개 서브에이전트가 다음 관점으로 독립 검토했다.

| 관점 | 검토 범위 |
| --- | --- |
| 외부 API 정합성 | 사방넷, 토스페이먼츠 연동 식별자, 상태, 멱등성, 재시도 |
| 커머스 도메인 | 상품 옵션, 주문, 배송, 쿠폰, 적립금, 리뷰, 클레임 |
| Django/PostgreSQL 구현성 | FK, unique, nullable, JSONField, on_delete, 성능 |
| 보안/운영 | PII, 동의 이력, 감사 로그, 웹훅 replay, 대사, 장애 대응 |

## Critical

### 부분 취소/반품/교환 정산 부족

기존 `Claim`은 단일 `order_item`과 수량만 갖고, `Refund`는 주문 단위 취소 금액만 저장했다. 다중 상품 클레임, 부분 수량 반품, 배송비 재계산, 쿠폰 회수, 적립금 복원/회수를 안정적으로 처리하기 어렵다.

반영:

- `ClaimLine`
- `RefundAllocation`
- `OrderItem` 수량 상태 필드
- 주문상품별 환불/쿠폰/포인트/배송비 배부 필드

### 사방넷 주문 식별자가 주문 단위에만 존재

사방넷 주문/송장/클레임 응답은 `sbOrderNo`와 상품/sku 행 단위 처리가 필요할 수 있다. 주문 단위 `sabangnet_order_no`만으로는 split shipment, line claim, waybill sync 매핑이 불안정하다.

반영:

- `SabangnetOrderLine`
- `Shipment`/`ClaimLine`에서 라인 단위 사방넷 식별자를 참조하는 원칙

### 외부 API 멱등성 제약 부족

기존 문서는 `idempotency_key`를 로그 인덱스로만 다뤘다. 결제 승인, 결제 취소, 사방넷 주문 전송은 timeout/retry 상황에서 중복 처리 위험이 있다.

반영:

- `PaymentAttempt.confirm_idempotency_key`
- `SabangnetOrderSubmission.operation_idempotency_key`
- `ExternalOperationAttempt`
- `Refund.transaction_key` 조건부 unique 원칙

## Important

### 상품 옵션이 SKU 조합을 표현하지 못함

의류 상품은 색상+사이즈 조합이 실제 SKU이고, 재고/바코드/판매상태도 조합에 붙는다.

반영:

- `ProductOptionGroup`
- `ProductOptionValue`
- `ProductVariant`
- `ProductVariantOptionValue`
- 장바구니/주문/재고는 variant 기준으로 처리

### 결제 시도 모델 부족

토스 결제는 결제위젯 호출, 성공/실패 redirect, 승인, 조회, 웹훅, 취소가 분리된다. `Payment`를 주문과 1:1로 두면 실패/재시도/unknown 상태를 표현하기 어렵다.

반영:

- `PaymentAttempt`
- `Payment`는 승인된 결제 객체 중심으로 저장
- 주문당 성공 결제 1개 조건부 unique 원칙

### 쿠폰/배송비 스냅샷 부족

주문 단위 할인 총액만으로는 부분취소 때 쿠폰 복구, 배송비 재부과, 무료배송 기준 재계산을 증명하기 어렵다.

반영:

- `OrderCoupon`
- `OrderCouponAllocation`
- `OrderShippingCharge`

### 리뷰 구매자 검증 약함

리뷰가 `OrderItem`과 연결되더라도 `Review.user == Order.user`를 강제하는 원칙이 필요하다.

반영:

- 구매자 리뷰 hard invariant를 문서화
- 구현 시 `ReviewEligibility` 또는 validation/constraint로 보강 필요

### raw polymorphic reference 문제

`link_type + object_id` 형태는 DB FK 무결성을 보장하지 못한다.

반영:

- `HomeBanner`는 대상별 nullable FK + CheckConstraint로 변경
- `PromotionProduct`, `CollectionProduct`, `LookbookProduct` 별도 through 모델 원칙

### 조건부 unique와 nullable/blank 명확화 필요

기본 배송지, active cart, 대표 이미지, 기본 배송정책, root category slug, webhook event 중복 방지는 DB 제약으로 강제해야 한다.

반영:

- 필수 DB 제약 요약 추가

### PII, 동의, 삭제 감사 부족

회원, 주문, 주소, 문의에 PII가 있고 마케팅 동의는 boolean만 있었다.

반영:

- `ConsentRecord`
- `DataDeletionAudit`
- guest token hash 저장 원칙

### 운영 감사와 대사 모델 부족

상태 변경, 수동 보정, 토스/사방넷/내부 주문 대사, 장애 대응을 추적할 모델이 부족했다.

반영:

- `AdminAuditLog`
- `StatusHistory`
- `ReconciliationRun`
- `ReconciliationIssue`
- `OpsAlert`

### Webhook replay 보호 부족

event id가 없거나 중복 전송될 때 payload hash, signature verification, replay count가 필요하다.

반영:

- `WebhookEvent` 보강 필드와 unique 원칙 추가

## Minor

- 금액 필드는 `PositiveBigIntegerField`/`BigIntegerField` 사용으로 변경.
- 상태 필드는 `TextChoices`, `max_length`, 기본값, `CheckConstraint` 사용 원칙 추가.
- 큰 JSON payload는 도메인 테이블에서 분리하는 원칙 추가.
- `on_delete` 정책 명시 원칙 추가.
- 운영 알림/장애 lifecycle을 `OpsAlert`로 보강.

## 추가 사용자 리뷰 반영

### 상품과 판매 공고 책임 혼합

기존 `Product`가 사방넷 원천 상품과 쇼핑몰 판매 공고의 역할을 함께 갖고 있었다. 이 경우 상품 동기화, 진열, 판매 기간, 고객 표시 가격, 기획전 연결, 장바구니 검증이 모두 상품 마스터에 묶인다.

반영:

- `Product`는 사방넷 원천 상품 마스터로 재정의.
- `ProductListing`을 판매 공고로 추가.
- `ProductListingVariant`, `ProductListingImage` 추가.
- 주문상품, 콘텐츠 연결, 장바구니가 `Product` 대신 `ProductListing` 기준으로 동작하도록 원칙 보강.

## 반영 위치

대부분의 보강은 `docs/db-models.md`의 `16. 서브에이전트 리뷰 반영 보강안`에 반영했다. 구현 시 이 섹션은 기존 초안보다 우선한다.
