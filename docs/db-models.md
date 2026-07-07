# 의류 쇼핑몰 DB 모델 설계

작성일: 2026-07-07

## 1. 설계 원칙

- Django 모델로 옮기기 쉬운 관계형 DB 구조를 기준으로 한다.
- 상품, 가격, 옵션, 재고의 원천은 사방넷으로 둔다.
- 쇼핑몰 자체 DB는 판매 화면, 주문, 결제, 혜택, 콘텐츠, 운영 로그를 안정적으로 관리한다.
- 외부 API 장애가 있어도 내부 주문과 결제 기록은 유실되지 않아야 한다.
- API 키, 비밀번호, 토큰, 시크릿은 DB 모델에 저장하지 않고 배포 시크릿 또는 환경변수로 관리한다.
- 외부 서비스 식별자, 요청/응답 요약, 상태, 실패 사유, 재시도 횟수는 DB에 저장한다.

## 2. 앱 경계

| 앱 | 역할 |
| --- | --- |
| `accounts` | 회원, 소셜 로그인, 본인인증, 주소록 |
| `catalog` | 브랜드, 카테고리, 상품, 옵션, 이미지, 필터 속성, 사방넷 상품 매핑 |
| `content` | 홈 배너, 기획전, 컬렉션, 룩북 |
| `commerce` | 장바구니, 주문, 배송, 결제, 환불 |
| `benefits` | 쿠폰, 적립금, 회원등급 |
| `reviews` | 구매자 리뷰와 리뷰 이미지 |
| `support` | 1:1 문의, 공지, FAQ |
| `integrations` | 사방넷/토스페이먼츠 연동 로그, 웹훅, 동기화 작업 |

## 3. 공통 필드 규칙

대부분의 운영 테이블은 다음 필드를 가진다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | BigAutoField | 내부 PK |
| `created_at` | DateTime | 생성 시각 |
| `updated_at` | DateTime | 수정 시각 |
| `is_active` | Boolean | 운영 노출 또는 사용 여부 |

금액 필드는 원화 정수 기준 `PositiveIntegerField`를 사용한다. 비율은 `DecimalField(max_digits=5, decimal_places=2)`를 사용한다.

## 4. accounts

### User

Django 기본 `AbstractUser` 확장을 전제로 한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `id` | BigAutoField | 회원 PK |
| `username` | CharField unique | 로그인 ID |
| `email` | EmailField | 이메일 |
| `name` | CharField | 실명 또는 가입 이름 |
| `phone` | CharField index | 휴대폰 번호 |
| `is_phone_verified` | Boolean | 회원가입 본인인증 완료 여부 |
| `marketing_email_opt_in` | Boolean | 이메일 마케팅 동의 |
| `marketing_sms_opt_in` | Boolean | SMS/알림톡 마케팅 동의 |
| `last_login_at` | DateTime nullable | 마지막 로그인 |
| `status` | CharField choices | `active`, `dormant`, `blocked`, `withdrawn` |

인덱스/제약:

- `username` unique
- `phone` index
- `status`, `created_at` 복합 index

### SocialAccount

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 연결 회원 |
| `provider` | CharField | `kakao`, `naver` |
| `provider_user_id` | CharField | 소셜 제공자 사용자 ID |
| `email` | EmailField nullable | 제공자 이메일 |
| `connected_at` | DateTime | 연결 시각 |

제약:

- `(provider, provider_user_id)` unique
- `(user, provider)` unique

### IdentityVerification

회원가입 본인인증 기록이다. 본인인증 업체가 확정되면 provider 값과 응답 필드를 확장한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User nullable | 가입 완료 전이면 null 가능 |
| `provider` | CharField | 본인인증 업체 |
| `transaction_id` | CharField unique | 인증 거래 ID |
| `name` | CharField | 인증된 이름 |
| `phone` | CharField | 인증된 휴대폰 |
| `birth_date` | DateField nullable | 인증된 생년월일 |
| `gender` | CharField nullable | 인증된 성별 |
| `verified_at` | DateTime | 인증 완료 시각 |
| `raw_response_summary` | JSONField | 민감정보 제외 응답 요약 |

### Address

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 회원 |
| `label` | CharField | 배송지명 |
| `recipient_name` | CharField | 수령자 |
| `phone` | CharField | 연락처 |
| `postal_code` | CharField | 우편번호 |
| `address1` | CharField | 기본 주소 |
| `address2` | CharField | 상세 주소 |
| `delivery_memo` | CharField nullable | 배송 메모 |
| `is_default` | Boolean | 기본 배송지 여부 |

제약:

- 회원별 기본 배송지는 애플리케이션 레벨에서 1개만 유지한다.

## 5. catalog

### Brand

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `name` | CharField | 브랜드명 |
| `slug` | SlugField unique | URL 식별자 |
| `logo_image` | ImageField nullable | 로고 |
| `hero_image` | ImageField nullable | 브랜드 대표 이미지 |
| `description` | TextField blank | 브랜드 설명 |
| `sort_order` | PositiveIntegerField | 노출 순서 |
| `is_visible` | Boolean | 고객 화면 노출 여부 |

### Category

사방넷 마이카테고리와 쇼핑몰 상품군을 함께 매핑한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `parent` | FK self nullable | 상위 카테고리 |
| `name` | CharField | 카테고리명 |
| `slug` | SlugField | URL 식별자 |
| `level` | PositiveSmallIntegerField | 깊이 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 고객 화면 노출 |
| `sabangnet_code` | CharField nullable index | 사방넷 카테고리 코드 |

제약:

- `(parent, slug)` unique
- `sabangnet_code`는 null 허용, 값이 있으면 unique 권장

### Product

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `brand` | FK Brand nullable | 내부 브랜드 |
| `category` | FK Category nullable | 대표 카테고리 |
| `sabangnet_product_code` | CharField unique | 사방넷 상품코드 |
| `custom_product_code` | CharField unique nullable | 자체상품코드 |
| `name` | CharField | 상품명 |
| `english_name` | CharField blank | 영문명 |
| `model_name` | CharField blank | 모델명 |
| `manufacturer_name` | CharField blank | 제조사 |
| `origin_name` | CharField blank | 원산지 코드/명 |
| `consumer_price` | PositiveIntegerField | 정상가 |
| `selling_price` | PositiveIntegerField | 판매가 |
| `cost_price` | PositiveIntegerField nullable | 원가 |
| `tax_code` | CharField | 과세 구분 |
| `supply_status` | CharField index | 사방넷 공급 상태 |
| `target_code` | CharField blank | 남성/여성/공용 등 |
| `season_code` | CharField blank | 시즌 |
| `product_tags` | CharField blank | 사방넷 태그 원문 |
| `detail_html` | TextField blank | 사방넷 상세설명 |
| `extra_detail_html` | TextField blank | 쇼핑몰 보강 상세설명 |
| `is_visible` | Boolean | 쇼핑몰 노출 |
| `is_featured` | Boolean | 추천 상품 |
| `is_new_label` | Boolean | 신상품 라벨 수동 표시 |
| `synced_at` | DateTime nullable | 마지막 사방넷 동기화 |
| `raw_sabangnet_payload` | JSONField | 민감정보 제외 원본 요약 |

인덱스:

- `sabangnet_product_code` unique
- `custom_product_code` unique where not null
- `brand`, `category`, `is_visible`, `supply_status`
- `selling_price`
- 전문 검색은 별도 검색 인덱스 또는 검색 서비스 도입 전까지 `name`, `product_tags` 기준으로 시작한다.

원칙:

- `consumer_price`, `selling_price`, `supply_status`, 옵션/재고는 사방넷 동기화로 갱신한다.
- 쇼핑몰 관리자는 `is_visible`, `is_featured`, `extra_detail_html`, 검색/진열 보강 필드만 수정한다.

### ProductOption

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `product` | FK Product | 상품 |
| `option_name` | CharField | 옵션명. 예: 색상 |
| `option_detail_name` | CharField | 옵션값. 예: 화이트 |
| `abbreviation_name` | CharField blank | 축약명 |
| `barcode` | CharField blank index | 바코드 |
| `additional_amount` | IntegerField | 옵션 추가금 |
| `stock_quantity` | IntegerField | 사방넷 옵션 재고 |
| `safety_stock_quantity` | IntegerField | 안전 재고 |
| `supply_status` | CharField index | `SALE`, `SOLD_OUT`, `NOT_USE` 등 |
| `synced_at` | DateTime nullable | 마지막 동기화 |

제약:

- `(product, option_name, option_detail_name, barcode)` unique 권장

### ProductImage

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `product` | FK Product | 상품 |
| `source` | CharField | `sabangnet`, `admin` |
| `sabangnet_image_srno` | CharField nullable | 사방넷 이미지 순번 |
| `image_url` | URLField | 외부 이미지 URL 또는 저장소 URL |
| `alt_text` | CharField blank | 대체 텍스트 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_primary` | Boolean | 대표 이미지 |

### ProductAttribute

필터와 검색을 위한 유연한 속성 테이블이다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `product` | FK Product | 상품 |
| `key` | CharField | `size`, `color`, `style`, `delivery`, `gender` 등 |
| `value` | CharField | 속성값 |
| `display_value` | CharField blank | 표시값 |
| `color_hex` | CharField blank | 컬러 스와치 |
| `sort_order` | PositiveIntegerField | 정렬 |

인덱스:

- `(key, value)`
- `(product, key)`

### ProductSyncSnapshot

사방넷 상품 동기화 결과를 추적한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `product` | FK Product nullable | 내부 상품 |
| `sabangnet_product_code` | CharField index | 사방넷 상품코드 |
| `sync_job` | FK IntegrationJob | 동기화 작업 |
| `status` | CharField | `created`, `updated`, `skipped`, `failed` |
| `field_changes` | JSONField | 변경 필드 요약 |
| `error_message` | TextField blank | 실패 사유 |

### InventorySnapshot

사방넷 상품 재고 또는 풀필먼트 재고 조회 결과를 시점별로 저장한다. 실제 원천은 사방넷 상품 API와 풀필먼트 API 검증 후 확정한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `product` | FK Product | 상품 |
| `option` | FK ProductOption nullable | 옵션 |
| `source` | CharField | `sabangnet_product`, `fulfillment_stock` |
| `shipping_product_id` | CharField blank index | 풀필먼트 출고상품 ID |
| `sales_product_id` | CharField blank index | 풀필먼트 판매상품 ID |
| `stock_quantity` | IntegerField | 총 재고 |
| `available_quantity` | IntegerField nullable | 판매 가능 재고 |
| `allocated_quantity` | IntegerField nullable | 출고/주문 할당 재고 |
| `safety_stock_quantity` | IntegerField nullable | 안전 재고 |
| `location_code` | CharField blank | 풀필먼트 로케이션 |
| `expire_date` | DateField nullable | 유통기한별 재고 사용 시 |
| `captured_at` | DateTime index | 재고 조회 시각 |
| `raw_response_summary` | JSONField | 민감정보 제외 응답 요약 |

인덱스:

- `(product, option, captured_at)`
- `(source, captured_at)`
- `shipping_product_id`

## 6. content

### HomeBanner

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `title` | CharField | 내부 관리명 |
| `media_type` | CharField | `image`, `video` |
| `image` | ImageField nullable | 이미지 배너 |
| `video_url` | URLField blank | 외부 영상 URL |
| `poster_image` | ImageField nullable | 영상 포스터 |
| `link_type` | CharField | `product`, `product_list`, `promotion`, `collection`, `lookbook`, `external_url`, `none` |
| `link_object_id` | PositiveIntegerField nullable | 내부 대상 ID |
| `external_url` | URLField blank | 외부 링크 |
| `starts_at` | DateTime nullable | 공개 시작 |
| `ends_at` | DateTime nullable | 공개 종료 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 노출 여부 |

### Promotion

기획전 모델이다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `title` | CharField | 제목 |
| `slug` | SlugField unique | URL 식별자 |
| `summary` | TextField blank | 요약 |
| `hero_image` | ImageField nullable | 대표 이미지 |
| `body_html` | TextField blank | 상세 콘텐츠 |
| `starts_at` | DateTime nullable | 시작일 |
| `ends_at` | DateTime nullable | 종료일 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 노출 |

### Collection

컬렉션은 `Promotion`과 유사하지만 시즌/캠페인성 묶음이다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `title` | CharField | 제목 |
| `slug` | SlugField unique | URL 식별자 |
| `summary` | TextField blank | 요약 |
| `hero_image` | ImageField nullable | 대표 이미지 |
| `body_html` | TextField blank | 상세 콘텐츠 |
| `starts_at` | DateTime nullable | 시작일 |
| `ends_at` | DateTime nullable | 종료일 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 노출 |

### Lookbook

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `brand` | FK Brand nullable | 브랜드 |
| `title` | CharField | 제목 |
| `slug` | SlugField unique | URL 식별자 |
| `season_label` | CharField blank | 시즌 표기 |
| `summary` | TextField blank | 요약 |
| `body_html` | TextField blank | 상세 설명 |
| `cover_image` | ImageField nullable | 대표 이미지 |
| `starts_at` | DateTime nullable | 공개 시작 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 노출 |

### LookbookImage

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `lookbook` | FK Lookbook | 룩북 |
| `image` | ImageField | 이미지 |
| `caption` | CharField blank | 캡션 |
| `sort_order` | PositiveIntegerField | 정렬 |

### ContentProduct

기획전/컬렉션/룩북과 상품 연결을 일반화한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `content_type` | CharField | `promotion`, `collection`, `lookbook` |
| `object_id` | PositiveIntegerField | 콘텐츠 ID |
| `product` | FK Product | 연결 상품 |
| `sort_order` | PositiveIntegerField | 정렬 |

제약:

- `(content_type, object_id, product)` unique

## 7. commerce

### Cart

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User nullable | 회원 장바구니 |
| `guest_key` | CharField nullable index | 비회원 장바구니 키 |
| `status` | CharField | `active`, `ordered`, `abandoned` |
| `expires_at` | DateTime nullable | 비회원 장바구니 만료 |

제약:

- 회원은 active cart 1개.
- 비회원은 `guest_key` 기준 active cart 1개.

### CartItem

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `cart` | FK Cart | 장바구니 |
| `product` | FK Product | 상품 |
| `option` | FK ProductOption | 옵션 |
| `quantity` | PositiveIntegerField | 수량 |
| `unit_price_snapshot` | PositiveIntegerField | 담은 시점 판매가 |

제약:

- `(cart, product, option)` unique

### Order

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order_number` | CharField unique | 내부 주문번호. 토스 `orderId`로 사용 가능 |
| `user` | FK User nullable | 회원 주문 |
| `guest_order_key` | CharField nullable index | 비회원 주문조회 키 |
| `status` | CharField index | 주문 상태 |
| `buyer_name` | CharField | 주문자명 |
| `buyer_phone` | CharField | 주문자 연락처 |
| `buyer_email` | EmailField blank | 주문자 이메일 |
| `recipient_name` | CharField | 수령자 |
| `recipient_phone` | CharField | 수령자 연락처 |
| `postal_code` | CharField | 우편번호 |
| `address1` | CharField | 기본 주소 |
| `address2` | CharField | 상세 주소 |
| `delivery_memo` | CharField blank | 배송 메모 |
| `items_subtotal` | PositiveIntegerField | 상품 금액 |
| `shipping_fee` | PositiveIntegerField | 배송비 |
| `coupon_discount_amount` | PositiveIntegerField | 쿠폰 할인 |
| `point_used_amount` | PositiveIntegerField | 사용 적립금 |
| `payment_amount` | PositiveIntegerField | 최종 결제 금액 |
| `sabangnet_status` | CharField index | `not_sent`, `pending`, `sent`, `failed` |
| `sabangnet_order_no` | CharField blank index | 사방넷 주문번호 |
| `paid_at` | DateTime nullable | 결제 완료 시각 |
| `ordered_at` | DateTime | 주문 생성 시각 |

상태 후보:

- `draft`
- `payment_pending`
- `payment_failed`
- `paid`
- `sabangnet_pending`
- `sabangnet_failed`
- `order_confirmed`
- `shipping_ready`
- `shipping`
- `delivered`
- `cancel_requested`
- `cancelled`
- `return_requested`
- `returned`

인덱스:

- `order_number` unique
- `user`, `ordered_at`
- `guest_order_key`
- `status`, `ordered_at`
- `sabangnet_status`, `ordered_at`

### OrderItem

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order` | FK Order | 주문 |
| `product` | FK Product | 상품 |
| `option` | FK ProductOption nullable | 옵션 |
| `product_name_snapshot` | CharField | 주문 시점 상품명 |
| `option_name_snapshot` | CharField blank | 주문 시점 옵션명 |
| `sabangnet_product_code` | CharField | 주문 시점 사방넷 상품코드 |
| `custom_product_code` | CharField blank | 주문 시점 자체상품코드 |
| `quantity` | PositiveIntegerField | 수량 |
| `unit_price` | PositiveIntegerField | 단가 |
| `discount_amount` | PositiveIntegerField | 상품 단위 할인 |
| `line_total` | PositiveIntegerField | 라인 합계 |
| `review_status` | CharField | `not_available`, `available`, `written` |

### Shipment

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order` | FK Order | 주문 |
| `carrier_code` | CharField blank | 택배사 코드. 예: `CJGLS` |
| `carrier_name` | CharField blank | 택배사명 |
| `tracking_number` | CharField blank index | 송장번호 |
| `status` | CharField | `ready`, `shipped`, `delivered`, `returned` |
| `shipped_at` | DateTime nullable | 발송 시각 |
| `delivered_at` | DateTime nullable | 배송 완료 시각 |
| `sabangnet_waybill_synced_at` | DateTime nullable | 사방넷 송장 동기화 시각 |

### ShippingPolicy

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `name` | CharField | 정책명 |
| `base_fee` | PositiveIntegerField | 기본 배송비 |
| `free_shipping_threshold` | PositiveIntegerField nullable | 무료배송 기준 |
| `remote_area_fee` | PositiveIntegerField | 도서산간 추가비 |
| `is_default` | Boolean | 기본 정책 |
| `is_active` | Boolean | 사용 여부 |

### Payment

토스페이먼츠 Payment 객체의 핵심 필드를 저장한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order` | OneToOne Order | 주문 |
| `provider` | CharField | `toss_payments` |
| `payment_key` | CharField unique | 토스 `paymentKey` |
| `order_id` | CharField index | 토스 `orderId`, 내부 주문번호 |
| `payment_type` | CharField | `NORMAL`, `BRANDPAY`, `KEYIN` |
| `method` | CharField blank | 결제수단 |
| `status` | CharField index | 토스 결제 상태 |
| `currency` | CharField | `KRW` |
| `total_amount` | PositiveIntegerField | 최초 결제 금액 |
| `balance_amount` | PositiveIntegerField | 취소 가능 잔액 |
| `requested_at` | DateTime nullable | 결제 요청 시각 |
| `approved_at` | DateTime nullable | 승인 시각 |
| `raw_response_summary` | JSONField | 민감정보 제외 응답 요약 |

상태 후보:

- `READY`
- `IN_PROGRESS`
- `WAITING_FOR_DEPOSIT`
- `DONE`
- `CANCELED`
- `PARTIAL_CANCELED`
- `ABORTED`
- `EXPIRED`

### PaymentEvent

결제 승인, 조회, 웹훅, 취소 결과를 이벤트로 남긴다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `payment` | FK Payment nullable | 결제 |
| `order` | FK Order nullable | 주문 |
| `event_type` | CharField | `confirm`, `lookup`, `cancel`, `webhook`, `fail_redirect` |
| `provider_event_id` | CharField blank index | 웹훅 이벤트 ID가 있으면 저장 |
| `payment_key` | CharField blank index | 이벤트 수신 시 결제키 |
| `order_id` | CharField blank index | 이벤트 수신 시 주문번호 |
| `status` | CharField blank | 토스 상태 |
| `payload_summary` | JSONField | 민감정보 제외 본문 요약 |
| `processed_at` | DateTime nullable | 처리 완료 시각 |
| `error_message` | TextField blank | 실패 사유 |

### Refund

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `payment` | FK Payment | 결제 |
| `order` | FK Order | 주문 |
| `refund_number` | CharField unique | 내부 환불 번호 |
| `transaction_key` | CharField blank index | 토스 취소 거래 키 |
| `cancel_reason` | CharField | 취소 사유 |
| `cancel_amount` | PositiveIntegerField | 취소 금액 |
| `tax_free_amount` | PositiveIntegerField | 면세 취소 금액 |
| `refundable_amount_after` | PositiveIntegerField nullable | 취소 후 환불 가능 잔액 |
| `status` | CharField index | `requested`, `succeeded`, `failed` |
| `requested_by` | FK User nullable | 처리 운영자 |
| `requested_at` | DateTime | 요청 시각 |
| `completed_at` | DateTime nullable | 완료 시각 |
| `raw_response_summary` | JSONField | 민감정보 제외 응답 요약 |

### Claim

취소, 교환, 반품 요청을 통합 관리한다. 토스 결제 취소와 사방넷 클레임 동기화는 이 모델을 기준으로 연결한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order` | FK Order | 주문 |
| `order_item` | FK OrderItem nullable | 상품 단위 클레임이면 연결 |
| `claim_number` | CharField unique | 내부 클레임 번호 |
| `claim_type` | CharField | `cancel`, `exchange`, `return` |
| `reason_code` | CharField | 사유 코드 |
| `reason_text` | TextField blank | 상세 사유 |
| `status` | CharField index | `requested`, `approved`, `rejected`, `processing`, `completed`, `failed` |
| `quantity` | PositiveIntegerField nullable | 상품 단위 수량 |
| `refund` | FK Refund nullable | 환불이 발생하면 연결 |
| `sabangnet_claim_code` | CharField blank index | 사방넷 클레임 상태/식별 코드 |
| `requested_by` | FK User nullable | 회원 또는 운영자 |
| `requested_at` | DateTime | 요청 시각 |
| `completed_at` | DateTime nullable | 완료 시각 |

인덱스:

- `(order, claim_type, status)`
- `sabangnet_claim_code`

## 8. benefits

### MembershipTier

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `name` | CharField | 등급명 |
| `code` | CharField unique | 등급 코드 |
| `min_purchase_amount` | PositiveIntegerField | 산정 기간 구매금액 기준 |
| `min_order_count` | PositiveIntegerField | 산정 기간 주문 수 기준 |
| `discount_rate` | DecimalField | 등급 할인율 |
| `point_earn_rate` | DecimalField | 구매 적립률 |
| `sort_order` | PositiveIntegerField | 등급 순서 |
| `is_active` | Boolean | 사용 여부 |

### UserMembership

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | OneToOne User | 회원 |
| `tier` | FK MembershipTier | 현재 등급 |
| `calculation_start` | DateField | 산정 시작일 |
| `calculation_end` | DateField | 산정 종료일 |
| `expires_at` | DateField nullable | 등급 만료일 |
| `purchase_amount_snapshot` | PositiveIntegerField | 산정 구매금액 |
| `order_count_snapshot` | PositiveIntegerField | 산정 주문 수 |

### Coupon

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `name` | CharField | 쿠폰명 |
| `code` | CharField unique | 쿠폰 코드 |
| `discount_type` | CharField | `fixed`, `percent`, `free_shipping` |
| `discount_value` | PositiveIntegerField | 정액 또는 정률 값 |
| `max_discount_amount` | PositiveIntegerField nullable | 최대 할인 |
| `min_order_amount` | PositiveIntegerField | 최소 주문금액 |
| `starts_at` | DateTime | 사용 시작 |
| `ends_at` | DateTime | 사용 종료 |
| `is_stackable` | Boolean | 중복 사용 가능 여부 |
| `brand_limit` | FK Brand nullable | 브랜드 제한 |
| `category_limit` | FK Category nullable | 상품군 제한 |
| `is_active` | Boolean | 사용 여부 |

### UserCoupon

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 회원 |
| `coupon` | FK Coupon | 쿠폰 |
| `status` | CharField index | `issued`, `used`, `expired`, `restored` |
| `issued_at` | DateTime | 발급 시각 |
| `used_at` | DateTime nullable | 사용 시각 |
| `used_order` | FK Order nullable | 사용 주문 |

### PointLedger

적립금은 잔액 컬럼 하나보다 원장 방식으로 관리한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 회원 |
| `order` | FK Order nullable | 관련 주문 |
| `review` | FK Review nullable | 관련 리뷰 |
| `change_type` | CharField | `earn_pending`, `earn_confirmed`, `use`, `restore`, `revoke`, `expire` |
| `amount` | IntegerField | 증감액. 사용/회수는 음수 |
| `balance_after` | IntegerField | 반영 후 잔액 |
| `available_at` | DateTime nullable | 사용 가능 시각 |
| `expires_at` | DateTime nullable | 만료 시각 |
| `memo` | CharField blank | 사유 |

인덱스:

- `user`, `created_at`
- `change_type`, `created_at`

## 9. reviews

### Review

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 작성자 |
| `order_item` | OneToOne OrderItem | 구매 상품 단위 리뷰 |
| `product` | FK Product | 상품 |
| `rating` | PositiveSmallIntegerField | 1~5 |
| `content` | TextField | 리뷰 내용 |
| `status` | CharField index | `visible`, `hidden`, `deleted` |
| `point_awarded` | Boolean | 리뷰 적립금 지급 여부 |
| `written_at` | DateTime | 작성 시각 |

제약:

- `order_item` unique로 구매 상품 1개당 리뷰 1개만 허용한다.
- 주문 상태가 배송완료 이후일 때만 작성 가능하다.

### ReviewImage

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `review` | FK Review | 리뷰 |
| `image` | ImageField | 이미지 |
| `sort_order` | PositiveIntegerField | 정렬 |

## 10. support

### Inquiry

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User nullable | 회원 문의 |
| `guest_email` | EmailField blank | 비회원 문의 허용 시 |
| `guest_phone` | CharField blank | 비회원 문의 허용 시 |
| `order` | FK Order nullable | 관련 주문 |
| `category` | CharField | 문의 유형 |
| `title` | CharField | 제목 |
| `content` | TextField | 내용 |
| `status` | CharField index | `open`, `answered`, `closed` |
| `answered_by` | FK User nullable | 답변 운영자 |
| `answered_at` | DateTime nullable | 답변 시각 |
| `answer_content` | TextField blank | 답변 |

### Notice

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `title` | CharField | 제목 |
| `content` | TextField | 내용 |
| `is_pinned` | Boolean | 상단 고정 |
| `is_visible` | Boolean | 노출 |
| `published_at` | DateTime nullable | 공개 시각 |

### FAQ

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `category` | CharField | 분류 |
| `question` | CharField | 질문 |
| `answer` | TextField | 답변 |
| `sort_order` | PositiveIntegerField | 정렬 |
| `is_visible` | Boolean | 노출 |

## 11. integrations

### IntegrationJob

사방넷 상품 동기화, 주문 전송, 토스 결제 재조회 같은 작업 단위다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `provider` | CharField | `sabangnet`, `toss_payments` |
| `job_type` | CharField | `product_sync`, `order_submit`, `waybill_sync`, `claim_sync`, `payment_lookup` |
| `status` | CharField index | `queued`, `running`, `succeeded`, `failed`, `partial` |
| `started_at` | DateTime nullable | 시작 |
| `finished_at` | DateTime nullable | 종료 |
| `total_count` | PositiveIntegerField | 전체 건수 |
| `success_count` | PositiveIntegerField | 성공 건수 |
| `failure_count` | PositiveIntegerField | 실패 건수 |
| `requested_by` | FK User nullable | 수동 실행 운영자 |
| `error_summary` | TextField blank | 실패 요약 |

### ExternalApiLog

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `provider` | CharField | `sabangnet`, `toss_payments` |
| `job` | FK IntegrationJob nullable | 작업 |
| `direction` | CharField | `request`, `response`, `webhook` |
| `method` | CharField | HTTP method |
| `path` | CharField | API path |
| `request_id` | CharField index | 내부 요청 ID |
| `idempotency_key` | CharField blank index | 멱등키 |
| `status_code` | PositiveIntegerField nullable | HTTP status |
| `request_summary` | JSONField | 민감정보 제외 요청 요약 |
| `response_summary` | JSONField | 민감정보 제외 응답 요약 |
| `error_code` | CharField blank | 외부 에러 코드 |
| `error_message` | TextField blank | 에러 메시지 |
| `duration_ms` | PositiveIntegerField nullable | 소요 시간 |

### SabangnetOrderSubmission

결제 완료 후 사방넷 전송 상태를 주문과 분리해 기록한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `order` | OneToOne Order | 주문 |
| `job` | FK IntegrationJob nullable | 전송 작업 |
| `status` | CharField index | `pending`, `sent`, `failed`, `retrying` |
| `sabangnet_order_no` | CharField blank index | 사방넷 주문번호 |
| `attempt_count` | PositiveIntegerField | 시도 횟수 |
| `last_attempt_at` | DateTime nullable | 마지막 시도 |
| `next_retry_at` | DateTime nullable | 다음 재시도 |
| `last_error_message` | TextField blank | 마지막 실패 사유 |
| `payload_summary` | JSONField | 민감정보 제외 전송 본문 |

### WebhookEvent

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `provider` | CharField | `toss_payments` 등 |
| `event_id` | CharField blank index | 외부 이벤트 ID |
| `event_type` | CharField | 이벤트 종류 |
| `payment_key` | CharField blank index | 결제키 |
| `order_id` | CharField blank index | 주문번호 |
| `received_at` | DateTime | 수신 시각 |
| `processed_at` | DateTime nullable | 처리 시각 |
| `status` | CharField index | `received`, `processed`, `ignored`, `failed` |
| `payload_summary` | JSONField | 민감정보 제외 본문 요약 |
| `error_message` | TextField blank | 실패 사유 |

제약:

- `provider`, `event_id` unique where `event_id` is not null.
- `event_id`가 없으면 `provider + event_type + payment_key + received_at bucket` 또는 payload hash로 중복 방지한다.

## 12. 찜/히스토리

### WishlistItem

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User | 회원 |
| `product` | FK Product | 상품 |
| `created_at` | DateTime | 추가 시각 |

제약:

- `(user, product)` unique

### RecentlyViewedProduct

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `user` | FK User nullable | 회원 |
| `guest_key` | CharField nullable index | 비회원 |
| `product` | FK Product | 상품 |
| `viewed_at` | DateTime index | 조회 시각 |

인덱스:

- `(user, viewed_at)`
- `(guest_key, viewed_at)`

## 13. 핵심 관계 요약

- `Product`는 `Brand`, `Category`와 연결되고 `ProductOption`, `ProductImage`, `ProductAttribute`를 가진다.
- `InventorySnapshot`은 사방넷 상품 재고 또는 풀필먼트 재고 조회 결과를 시점별로 남긴다.
- `Order`는 `OrderItem` 여러 개를 가지며, `Payment`와 1:1로 연결된다.
- `Payment`는 `PaymentEvent`, `Refund` 여러 개를 가진다.
- `Claim`은 취소, 교환, 반품 요청을 주문/주문상품/환불과 연결한다.
- `Order`는 사방넷 전송 상태를 `SabangnetOrderSubmission`으로 별도 추적한다.
- `Coupon`은 `UserCoupon`으로 발급되고 주문 사용 시 `Order`에 할인 금액 스냅샷을 남긴다.
- 적립금은 `PointLedger` 원장으로만 잔액을 계산한다.
- 리뷰는 `OrderItem`과 1:1로 묶어 구매자만 작성 가능하게 한다.
- 외부 API 호출은 모두 `ExternalApiLog`와 필요 시 `IntegrationJob`에 연결한다.

## 14. API 연동별 DB 처리

### 사방넷 상품 조회

1. `IntegrationJob(provider=sabangnet, job_type=product_sync)` 생성.
2. 상품 조회 API 호출 로그를 `ExternalApiLog`에 저장.
3. `sabangnet_product_code` 또는 `custom_product_code`로 `Product` upsert.
4. 옵션은 `ProductOption` upsert.
5. 이미지는 `ProductImage(source=sabangnet)` upsert.
6. 필터 속성은 `ProductAttribute` upsert.
7. 변경 요약은 `ProductSyncSnapshot`에 저장.

### 사방넷 주문 전송

1. 토스 결제 승인 후 `Order.status=paid`.
2. `SabangnetOrderSubmission(status=pending)` 생성.
3. 사방넷 주문 전송 API 확인 후 payload 생성.
4. 성공 시 `Order.sabangnet_status=sent`, `sabangnet_order_no` 저장.
5. 실패 시 `Order.sabangnet_status=failed`, `next_retry_at` 설정.

### 토스페이먼츠 결제 승인

1. 결제 요청 전 `Order.status=payment_pending`.
2. 성공 URL의 `paymentKey`, `orderId`, `amount` 검증.
3. 승인 성공 응답을 `Payment`에 저장.
4. `PaymentEvent(event_type=confirm)` 저장.
5. `Order.status=paid`, `paid_at` 저장.
6. 사방넷 전송 작업 enqueue.

### 토스페이먼츠 취소

1. 내부 `Refund(status=requested)` 생성.
2. 토스 취소 API 호출.
3. 성공 시 `Refund.status=succeeded`, `Payment.status/balance_amount/cancels` 보정.
4. 쿠폰 복구와 적립금 회수는 `UserCoupon`, `PointLedger`에 기록.
5. 사방넷 클레임 또는 주문 상태 동기화 작업 생성.

## 15. 미확정으로 남길 모델 확장 포인트

| 항목 | 이유 |
| --- | --- |
| 사방넷 주문 신규 등록 모델 | 공개 샘플에서 정확한 주문 등록 API가 확인되지 않음 |
| 상품 상세 이미지/설명 필드 | 테스트 상품 응답으로 제공 범위 확인 필요 |
| 재고 원천 | 사방넷 상품 API 재고와 풀필먼트 재고 중 선택 필요 |
| 본인인증 응답 필드 | 업체 확정 후 필드 확정 |
| 부분 취소 정책 | 토스 계약/운영 정책 확정 필요 |
| 비회원 문의 | 허용 여부 미확정 |
| 회원등급 산정 배치 | 산정 주기와 기준 확정 필요 |
