# 사방넷 개발용 API 문서

확인일: 2026-07-13

원본:

- 사방넷 개발자센터: `https://developer.sabangnet.co.kr/docs/guides/intro`
- 샘플 코드: `https://github.com/sabangnet-api/sabangnet-api`

본 문서는 외부 문서 장애 또는 접근 지연에 대비한 개발용 요약이다. 실제 구현 전에는 원본 문서와 테스트 계정으로 요청/응답 필드를 재검증해야 한다. 인증 정보, 비밀번호, 토큰, 시크릿은 이 문서에 기록하지 않는다.

## 1. 연동 범위

사방넷 샘플 코드 기준 API는 두 묶음으로 나뉜다.

| 묶음 | 설명 | 주요 용도 |
| --- | --- | --- |
| 사방넷 API | 쇼핑몰 관리 API | 상품, 주문, 카테고리, 운송장, 클레임, CS |
| 풀필먼트 API | 창고관리 API | 재고, 입고, 발주, 출고, 반품 |

쇼핑몰 1차 오픈에서는 사방넷 API를 우선 검증하고, 재고 정확도와 배송 처리 범위에 따라 풀필먼트 API 사용 여부를 결정한다.

## 2. 인증

샘플 코드 기준 인증 방식은 Client Credentials와 bcrypt `secretSign` 방식이다.

필요 환경변수:

| 이름 | 설명 | 저장 위치 |
| --- | --- | --- |
| `CLIENT_ID` | 앱 Client ID | 배포 시크릿 |
| `SECRET_KEY` | bcrypt 형식 Secret Key | 배포 시크릿 |
| `SVC_ACNT_ID` | 서비스 계정 ID | 배포 시크릿 |
| `CLIENT_TYPE` | 앱 유형, 코드 기본값 `SB_APP` | 코드 설정 |
| `AUTH_MODE` | `SANDBOX` 또는 `PRODUCTION`. 생략 시 `PRODUCTION` | 환경 설정 |
| `BEARER_TOKEN` | 선택. 직접 지정 시 토큰 발급 생략 | 로컬 테스트 전용 |

토큰 발급 흐름:

1. 현재 시각 밀리초 timestamp를 생성한다.
2. `{CLIENT_ID}_{timestamp}` 형태의 데이터를 만든다.
3. `SECRET_KEY`로 bcrypt hash를 생성한 뒤 Base64 인코딩해 `secretSign`을 만든다.
4. 샌드박스 Secret을 사용할 때 `authMode=SANDBOX`를 포함해 OAuth 토큰 API를 호출한다.
5. access token을 받는다.
6. 이후 API 요청에 `Authorization: Bearer {token}`과 `X-Svc-Acnt-Id: {SVC_ACNT_ID}`를 포함한다.

주의:

- 서버 시간이 5분 이상 어긋나면 인증 실패 가능성이 있다.
- `SECRET_KEY`, access token, 서비스 계정 ID는 로그에 남기지 않는다.

### 2.1 샌드박스 실검증 결과

2026-07-13 `https://sandbox.sabangnet.co.kr`에서 읽기 및 변경 API를 확인했다.

- 허용 IP 미등록 시 `AUTH_008`, 잘못된 환경 모드/서명은 `AUTH_003`으로 응답한다.
- 샌드박스 Secret으로 토큰을 발급할 때 `authMode=SANDBOX`가 필요하다.
- 실제 성공 응답 envelope는 `{"code": 200, "message": "...", "data": ...}` 형식이다.
- 목록 pagination은 `data.results`, `totalItemCnt`, `totalPage`, `hasNext` 필드를 사용한다.
- 주문 배송사 코드는 `LOGISTICS_CD`, 배송사명은 `LOGISTICS_NM`, 송장번호는 `WAYBILL_NO`로 확인됐다.
- 상품 카테고리는 `myCategoryCodeL`, `myCategoryCodeM`, `myCategoryCodeS`로 내려온다.
- 주문 상태 변경, 운송장, 문의 답변, 추가상품, 채널상품 변경 API는 개별 결과 `status=true`, 성공 1건으로 확인됐다.
- 상품·카테고리 upsert는 envelope `200`을 반환하지만 샌드박스 조회가 고정 fixture를 반환하므로 변경값 재조회 검증은 불가능했다.
- 변경 API는 HTTP/envelope 성공 외에 `successCount`, `failCount`, `results[].status`를 반드시 확인해야 한다.
- 샌드박스는 존재하지 않는 주문번호와 잘못된 상태 코드에도 변경 성공을 반환했고, 주문·문의·카테고리·상품 재조회 결과도 바뀌지 않았다.
- 따라서 샌드박스 변경 API는 인증, endpoint, 요청/응답 계약 smoke test에만 사용하고 실제 영속성·상태 전이 검증은 운영 전 별도 검증 환경에서 수행해야 한다.

### 2.2 환경별 고정 주소

| 모드 | API Base URL | OAuth Token URL |
| --- | --- | --- |
| `PRODUCTION` | `https://api.sabangnet.co.kr` | `https://api.sabangnet.co.kr/oauth2/token` |
| `SANDBOX` | `https://sandbox.sabangnet.co.kr` | `https://sandbox.sabangnet.co.kr/oauth2/token` |

애플리케이션은 `SABANGNET_AUTH_MODE`로 위 주소를 자동 선택한다. 운영 모드가 기본값이므로 운영 배포에서는 별도 설정이 필요 없다.

## 3. 사방넷 API 엔드포인트

샘플 코드 기준 모든 사방넷 API는 `/v3/sb/` 접두사를 사용한다.

| 카테고리 | 기능 | 메서드 | 경로 |
| --- | --- | --- | --- |
| 문의사항 | 문의사항 정보 조회 | GET | `/v3/sb/cs` |
| 문의사항 | 문의사항 답변 저장 | POST | `/v3/sb/cs/answer` |
| 상품 | 상품 조회 | GET | `/v3/sb/product` |
| 상품 | 상품 등록/수정 | POST | `/v3/sb/product/upsert` |
| 상품정보제공고시 | 목록 조회 | GET | `/v3/sb/product-info-notice/{noticeType}` |
| 쇼핑몰 | 쇼핑몰 정보 조회 | GET | `/v3/sb/mall/{shopDivCode}` |
| 운송장 | 운송장 저장/수정 | POST | `/v3/sb/waybill` |
| 주문 | 주문 목록 조회 | GET | `/v3/sb/order` |
| 주문 | 주문 상태 변경 | POST | `/v3/sb/order-status` |
| 추가상품 | 추가상품 등록/수정 | POST | `/v3/sb/additional-product` |
| 카테고리 | 전체 마이카테고리 목록 조회 | GET | `/v3/sb/category` |
| 카테고리 | 마이카테고리 등록/수정 | POST | `/v3/sb/category` |
| 카테고리 | 마이카테고리 목록 조회 | GET | `/v3/sb/category/{lCategoryCode}` |
| 클레임 | 클레임 목록 조회 | GET | `/v3/sb/claim` |
| 판매채널별 상품 | 채널별 상품 등록/수정 | POST | `/v3/sb/channels-product` |

## 4. 사방넷 API 상세

아래 입력 형태는 공개 샘플 코드의 `dummy_data/sabangnet_data.py`와 `sabangnet/test_sabangnet_api.py` 기준이다. 응답 형태는 샘플 코드에 전체 스키마가 포함되어 있지 않으므로, 개발에 필요한 저장 필드 후보와 검증 포인트를 함께 둔다.

### 4.1 문의사항 정보 조회

- Method/Path: `GET /v3/sb/cs`
- 용도: 사방넷에 수집된 문의를 조회해 내부 문의 또는 CS 운영 화면과 대조한다.
- 입력 위치: JSON body

```json
{
  "startDate": "20260101000000",
  "endDate": "20260421235959",
  "page": 1,
  "perPage": 100,
  "csStatus": "NEW_RECEIPT"
}
```

| 필드 | 설명 |
| --- | --- |
| `startDate`, `endDate` | 조회 기간. 8자리 또는 14자리 날짜 문자열 |
| `page` | 1 이상 |
| `perPage` | 샘플 주석 기준 50~1000 |
| `csStatus` | `NEW_RECEIPT`, `ANSWER_SAVED`, `ANSWER_SENT`, `FORCED_CONVERSION` |

응답 저장 후보:

| 필드 후보 | 설명 |
| --- | --- |
| `csSrno` | 문의 식별자. 답변 저장 시 필요 |
| `csStatus` | 문의 상태 |
| `questionContent` | 문의 내용 |
| `answerContent` | 답변 내용 |
| `createdAt` | 문의 등록 시각 |
| `orderNo`, `productCode` | 주문/상품 연결 정보가 응답에 있으면 저장 |

### 4.2 문의사항 답변 저장

- Method/Path: `POST /v3/sb/cs/answer`
- 용도: 사방넷 문의에 답변을 저장한다.
- 입력 위치: JSON body

```json
{
  "items": [
    {
      "csSrno": 51280395,
      "answerContent": "고객님, 문의하신 사항에 대해 안내드립니다."
    }
  ]
}
```

| 필드 | 설명 |
| --- | --- |
| `items[].csSrno` | 답변할 문의 식별자 |
| `items[].answerContent` | 답변 내용 |

응답 형태:

- 전체 성공: HTTP `200`
- 부분 성공: HTTP `206`
- 실패: HTTP 오류 코드와 에러 본문
- 저장할 값: 요청 ID, `csSrno`, 성공/실패 여부, 실패 사유

### 4.3 상품 조회

- Method/Path: `GET /v3/sb/product`
- 용도: 상품 원천 데이터를 조회해 내부 상품 DB와 동기화한다.
- 입력 위치: query string

```json
{
  "productCode": "12345678"
}
```

| 필드 | 설명 |
| --- | --- |
| `productCode` | 사방넷 상품코드 |
| `customProductCode` | 자체 상품코드. 둘 다 전달 시 샘플 주석 기준 자체상품코드 우선 |

응답 저장 후보:

| 필드 후보 | 내부 매핑 |
| --- | --- |
| `productCode` | 사방넷 상품코드 |
| `customProductCode` | 내부 상품 매칭 키 |
| `productName`, `engProductName` | 상품명 |
| `brandName`, `manufacturerName`, `modelName` | 브랜드/제조사/모델 |
| `consumerPrice`, `sellingPrice`, `costPrice` | 정상가/판매가/원가 |
| `productSupplyStatusCode` | 판매/품절 상태 |
| `myCategoryCodeL/M/S` | 카테고리 |
| `productDetailDescription` | 상세 설명 |
| `productTag`, `seasonCode`, `productTargetCode` | 검색/필터 속성 |
| `optionInfo.options[]` | 옵션, 바코드, 옵션 재고, 옵션 판매 상태 |
| `imageInfo[]` | 대표/추가 이미지 |

### 4.4 상품 등록/수정

- Method/Path: `POST /v3/sb/product/upsert`
- 용도: 사방넷에 상품을 등록하거나 수정한다. 본 쇼핑몰에서는 사방넷을 원천으로 삼으므로 1차에서는 조회 검증용이며, 역방향 등록은 별도 승인 후 사용한다.
- 입력 위치: JSON body

```json
{
  "products": [
    {
      "customProductCode": "SAMPLE-PRD-001",
      "productName": "테스트 반팔티셔츠 (S/M/L)",
      "consumerPrice": 25000,
      "sellingPrice": 19900,
      "deliveryCostCode": "FREE",
      "taxCode": "TAXABLE",
      "productSupplyStatusCode": "IN_SUPPLY",
      "brandName": "샘플브랜드",
      "productDetailDescription": "<p>고품질 면 100% 반팔티셔츠입니다.</p>",
      "optionInfo": {
        "stockUseYn": "Y",
        "optionEditCode": "RESET",
        "options": [
          {
            "optionName": "색상",
            "optionDetailName": "화이트",
            "stockQuantity": 50,
            "optionSupplyStatusCode": "SALE"
          }
        ]
      },
      "imageInfo": [
        {
          "imageSrno": "1",
          "imagePath": "https://example.com/images/tshirt_main.jpg"
        }
      ]
    }
  ]
}
```

처리 규칙:

- 샘플 주석 기준 자체상품코드가 있으면 수정, 없으면 등록한다.
- 최대 5,000건까지 처리한다.
- 필드 누락 또는 `null`은 미수정, 빈 문자열은 클리어로 해석된다. 단, 상세설명과 관리자 메모는 예외가 있다.
- 전체 성공은 HTTP `200`, 부분 성공은 HTTP `206`이다.

### 4.5 상품정보제공고시 목록 조회

- Method/Path: `GET /v3/sb/product-info-notice/{noticeType}`
- 용도: 의류 상품정보제공고시 항목을 조회해 상품 상세/관리자 필드와 매핑한다.
- 입력 위치: path

```json
{
  "noticeType": "WEAR"
}
```

응답 저장 후보:

| 필드 후보 | 설명 |
| --- | --- |
| `noticeType` | 고시 유형 |
| `itemCode` | 고시 항목 코드 |
| `itemName` | 고시 항목명 |
| `requiredYn` | 필수 여부 |

### 4.6 쇼핑몰 정보 조회

- Method/Path: `GET /v3/sb/mall/{shopDivCode}`
- 용도: 사방넷에 등록된 쇼핑몰/채널 정보를 확인한다.
- 입력 위치: path, optional query

```json
{
  "shopDivCode": "SHOP",
  "shopLoginId": "optional"
}
```

| 필드 | 설명 |
| --- | --- |
| `shopDivCode` | 샘플 기준 `CHOP`, `SHOP`, `GLOBAL` |
| `shopLoginId` | 특정 쇼핑몰만 조회할 때 선택 전달 |

응답 저장 후보: `shopCode`, `shopName`, `shopLoginId`, `shopDivCode`, 사용 여부.

### 4.7 운송장 저장/수정

- Method/Path: `POST /v3/sb/waybill`
- 용도: 송장번호와 택배사를 사방넷에 저장하거나 수정한다.
- 입력 위치: JSON body

```json
{
  "forceUpdateYn": "N",
  "waybillList": [
    {
      "sbOrderNo": "20240101-001",
      "deliveryCompanyCode": "CJGLS",
      "wayBillNo": "123456789012",
      "hopeDeliveryDate": ""
    }
  ]
}
```

처리 규칙:

- 등록 가능 상태: 주문확인, 출고대기, 교환발송준비.
- 주문확인 상태에서 송장 등록 시 출고대기로 전환될 수 있다.
- 송장 전송완료, 강제완료 상태는 수정 불가로 본다.
- 전체 성공은 HTTP `200`, 부분 성공은 HTTP `206`이다.

### 4.8 주문 목록 조회

- Method/Path: `GET /v3/sb/order`
- 용도: 사방넷 주문을 조회한다. 시퀸즈 쇼핑몰은 결제 완료 후 사방넷으로 주문을 보내는 방향이므로, 이 API는 상태 대조와 사방넷 수집 주문 확인에 사용한다.
- 입력 위치: JSON body

```json
{
  "startDate": "20260101",
  "endDate": "20260421",
  "dateSearchCondition": 1,
  "page": 1,
  "perPage": 100,
  "updateOrderStsYn": "N",
  "orderStatusList": ["001", "002"],
  "responseItems": [
    "SB_ORD_NO",
    "SHOP_ORD_NO",
    "ORDER_STATUS",
    "RECEIVER_NM",
    "CM_PRD_NM",
    "CM_SKU_NM",
    "ORD_CNT",
    "CT_DELIVERY_COST"
  ]
}
```

| 필드 | 설명 |
| --- | --- |
| `dateSearchCondition` | `1`: 주문일, `2`: 수집일, `3`: 발송처리일 |
| `updateOrderStsYn` | `Y`이면 조건 충족 신규주문이 주문확인으로 변경될 수 있음 |
| `responseItems` | 응답으로 받을 항목 코드 목록 |

응답 저장 후보:

| 응답 항목 코드 | 내부 매핑 |
| --- | --- |
| `SB_ORD_NO` | 사방넷 주문번호 |
| `SHOP_ORD_NO` | 쇼핑몰 주문번호 |
| `ORDER_STATUS` | 주문 상태 |
| `RECEIVER_NM` | 수령자명 |
| `CM_PRD_NM` | 상품명 |
| `CM_SKU_NM` | 옵션명 |
| `ORD_CNT` | 주문 수량 |
| `CT_DELIVERY_COST` | 배송비 |

### 4.8.1 주문 상태 변경

- Method/Path: `POST /v3/sb/order-status`
- 용도: 사방넷 주문을 주문확인, 출고완료, 취소·교환·반품 접수/완료 상태로 변경한다.
- 입력 위치: JSON body

```json
{
  "orders": [
    {
      "sbOrderNo": "20260101000001",
      "targetStatusCode": "ORDER_CONFIRM"
    }
  ]
}
```

허용 상태 코드는 `ORDER_CONFIRM`, `DELIVERY_COMPLETED`, `CANCEL_RECEIPT`, `EXCHANGE_RECEIPT`,
`RETURN_RECEIPT`, `CANCEL_COMPLETED`, `EXCHANGE_COMPLETED`, `RETURN_COMPLETED`이다. 현재 상태에서
허용되는 전이만 성공하며, 응답의 `failCount`와 `results[].status`를 확인해야 한다.

### 4.9 추가상품 등록/수정

- Method/Path: `POST /v3/sb/additional-product`
- 용도: 사방넷 추가상품 그룹을 등록/수정한다. 의류 쇼핑몰 1차에서는 필수 범위가 아니며 세트/추가구성 상품 정책 확정 후 사용한다.
- 입력 위치: JSON body

```json
{
  "productInfoList": [
    {
      "actionType": "I",
      "shopCode": "shop0001",
      "groupCode": "G001",
      "groupName": "소이캔들세트",
      "groupType": "G",
      "salesType": "CONSIGNMENT",
      "deliveryType": "SELF_COMPANY",
      "groupInfoList": [
        {
          "sbPrdSkuCode": "100001-0001",
          "addProductOptionName": "바닐라향 소이캔들",
          "salesPrice": 15000,
          "productSupplyStatusCode": "SALE"
        }
      ]
    }
  ]
}
```

응답 형태: 전체 성공 HTTP `200`, 부분 성공 HTTP `206`, 실패 시 에러 본문.

### 4.10 전체 마이카테고리 목록 조회

- Method/Path: `GET /v3/sb/category`
- 용도: 사방넷 마이카테고리를 조회해 내부 카테고리와 매핑한다.
- 입력: 없음

응답 저장 후보:

| 필드 후보 | 설명 |
| --- | --- |
| `code` | 카테고리 코드 |
| `name` | 카테고리명 |
| `level` | 카테고리 깊이 |
| `sortSrno` | 정렬 순서 |
| `useYn` | 사용 여부 |
| `leafCode` | 최하위 여부 확인에 사용 |

### 4.11 마이카테고리 등록/수정

- Method/Path: `POST /v3/sb/category`
- 용도: 사방넷 마이카테고리를 등록/수정한다. 1차에서는 사방넷 카테고리 원천 확인 후 사용 여부를 결정한다.
- 입력 위치: JSON body

```json
{
  "categories": [
    {
      "category": [
        {
          "code": "01",
          "name": "의류/패션",
          "level": 1,
          "sortSrno": 1,
          "useYn": "Y",
          "comment": ""
        }
      ]
    }
  ]
}
```

규칙:

- 최대 4레벨.
- 상위 레벨부터 순서대로 입력한다.
- 카테고리 코드는 영문과 숫자만 사용한다.
- 동일 코드가 있으면 수정, 없으면 등록한다.

### 4.12 마이카테고리 목록 조회

- Method/Path: `GET /v3/sb/category/{lCategoryCode}`
- 용도: 특정 대분류의 하위 카테고리를 조회한다.
- 입력 위치: path

```json
{
  "lCategoryCode": "01"
}
```

응답 저장 후보는 전체 카테고리 조회와 동일하다.

### 4.13 클레임 목록 조회

- Method/Path: `GET /v3/sb/claim`
- 용도: 취소, 교환, 반품 등 클레임 상태를 사방넷과 대조한다.
- 입력 위치: JSON body

```json
{
  "startDate": "20260101",
  "endDate": "20260421",
  "page": 1,
  "perPage": 100,
  "responseItems": [
    "SB_ORD_NO",
    "SHOP_ORD_NO",
    "CLAIM_TEXT",
    "CLAIM_STS_DIV_CD"
  ]
}
```

| 필드 | 설명 |
| --- | --- |
| `startDate`, `endDate` | 조회 기간. 최대 180일 |
| `perPage` | 샘플 주석 기준 50~500 |
| `responseItems` | 응답 항목 코드 목록 |

응답 저장 후보:

| 응답 항목 코드 | 내부 매핑 |
| --- | --- |
| `SB_ORD_NO` | 사방넷 주문번호 |
| `SHOP_ORD_NO` | 쇼핑몰 주문번호 |
| `CLAIM_TEXT` | 클레임 내용 |
| `CLAIM_STS_DIV_CD` | 클레임 상태 코드 |

### 4.14 채널별 상품 등록/수정

- Method/Path: `POST /v3/sb/channels-product`
- 용도: 쇼핑몰 채널별 판매가, 노출명, 상세설명, 재고비율 등을 관리한다. 시퀸즈 쇼핑몰에서는 사방넷 제공 범위 확인 후 사용 여부를 결정한다.
- 입력 위치: JSON body

```json
{
  "products": [
    {
      "customProductCode": "SAMPLE-PRD-001",
      "shopCode": "shop0001",
      "productName": "테스트 반팔티셔츠 (쇼핑몰노출명)",
      "productDetailDescription": "<p>상품 상세 설명입니다.</p>",
      "salePrice": 19900,
      "shopMallShippingPolicyId": "B0000001",
      "shopMallStockRate": 100,
      "productAttributeClassificationCode": "001"
    }
  ]
}
```

응답 형태: 전체 성공 HTTP `200`, 부분 성공 HTTP `206`, 실패 시 에러 본문.

## 5. 풀필먼트 API 엔드포인트

| 카테고리 | 기능 | 메서드 | 경로 |
| --- | --- | --- | --- |
| 상품 | 출고상품 조회 | GET | `/v3/product/shipping_products` |
| 상품 | 판매상품 조회 | GET | `/v3/product/sales_products` |
| 재고 | 재고조회 단일 | GET | `/v3/inventory/stock/{id}` |
| 재고 | 재고조회 벌크 | GET | `/v3/inventory/stocks` |
| 재고 | 로케이션 재고조회 | POST | `/v3/inventory/stock/locations` |
| 재고 | 유통기한별 재고조회 | GET | `/v3/inventory/stock_expire` |
| 입고 | 입고예정 등록 | POST | `/v3/inventory/receiving_plan` |
| 입고 | 입고예정 조회 | GET | `/v3/inventory/receiving_plans` |
| 입고 | 예정대비입고현황 조회 | GET | `/v3/inventory/receiving_plan_result/{id}` |
| 입고 | 입고작업내역 조회 | GET | `/v3/inventory/receiving_works` |
| 발주 | 발주 등록 단일 | POST | `/v3/request/order` |
| 발주 | 발주 등록 벌크 | POST | `/v3/request/orders` |
| 발주 | 발주 조회 벌크 | GET | `/v3/request/orders` |
| 출고 | 출고 조회 | GET | `/v3/releases` |
| 출고 | 출고대상상품 조회 | GET | `/v3/release/items` |
| 출고 | 출고대상상품재고할당 조회 | GET | `/v3/release/item_stocks` |
| 출고 | 출고회차 조회 | GET | `/v3/release/shipping_work` |
| 출고 | 운송장 일반 조회 | GET | `/v3/release/shipping_codes` |
| 반품 | 반품 조회 | GET | `/v3/release_return/searchs` |
| 관리 | 로케이션 조회 | GET | `/v3/locations` |

## 6. 풀필먼트 API 상세

풀필먼트 API는 창고관리 사용 여부가 확정된 뒤 적용한다. 1차 개발에서는 재고 정확도와 출고/반품 추적이 사방넷 API만으로 충분한지 먼저 검증한다.

공통 query 입력:

```json
{
  "page": 1,
  "page_size": 20,
  "member_id": 70
}
```

공통 응답 저장 후보:

| 필드 후보 | 설명 |
| --- | --- |
| `page`, `page_size`, `total_count` | 페이지 정보 |
| `items[]` 또는 목록 배열 | 실제 데이터 목록. 원본 응답 구조 확인 필요 |
| `id` | 각 도메인 식별자 |
| `member_id` | 사방넷 풀필먼트 회원 식별자 |

### 6.1 상품 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 출고상품 조회 | `GET /v3/product/shipping_products` | `page`, `page_size`, `member_id` | `shipping_product_id`, 상품명, 바코드, 출고 기준 상품 정보 |
| 판매상품 조회 | `GET /v3/product/sales_products` | `page`, `page_size`, `member_id` | `sales_product_id`, 판매상품명, 연결 출고상품, 판매 상태 |

### 6.2 재고 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 재고조회 단일 | `GET /v3/inventory/stock/{id}` | path `shipping_product_id` | 현재 재고, 가용 재고, 할당 재고, 로케이션 |
| 재고조회 벌크 | `GET /v3/inventory/stocks` | `page`, `page_size`, `member_id` | 상품별 재고 목록 |
| 로케이션 재고조회 | `POST /v3/inventory/stock/locations` | JSON body | 상품별 로케이션 재고 |
| 유통기한별 재고조회 | `GET /v3/inventory/stock_expire` | query | 유통기한별 재고 수량 |

로케이션 재고조회 입력:

```json
{
  "member_id": 70,
  "shipping_product_id_list": [43778, 43779]
}
```

유통기한별 재고조회 입력:

```json
{
  "page": 1,
  "page_size": 20,
  "member_id": 70,
  "shipping_product_id": 43778
}
```

### 6.3 입고 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 입고예정 등록 | `POST /v3/inventory/receiving_plan` | JSON body | 입고예정 ID, 등록 상태 |
| 입고예정 조회 | `GET /v3/inventory/receiving_plans` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 입고예정 목록 |
| 예정대비입고현황 조회 | `GET /v3/inventory/receiving_plan_result/{id}` | path `receiving_plan_id` | 예정 수량, 실제 입고 수량 |
| 입고작업내역 조회 | `GET /v3/inventory/receiving_works` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 입고 작업 이력 |

입고예정 등록 입력:

```json
{
  "member_id": 70,
  "receiving_plan_code": 506,
  "plan_date": 20260501,
  "memo": "테스트 입고예정 등록",
  "plan_product_list": [
    {
      "shipping_product_id": 43778,
      "quantity": 100,
      "expire_date": 20271231,
      "make_date": 20260401
    }
  ]
}
```

### 6.4 발주 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 발주 등록 단일 | `POST /v3/request/order` | JSON body | 발주 ID, 발주 코드, 등록 상태 |
| 발주 등록 벌크 | `POST /v3/request/orders` | JSON body | 발주별 성공/실패 결과 |
| 발주 조회 벌크 | `GET /v3/request/orders` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 발주 목록, 수령자, 상품, 수량, 배송 상태 |

발주 등록 단일 입력:

```json
{
  "member_id": 70,
  "company_order_code": "ORD-20260421-001",
  "shipping_method_id": 1,
  "request_shipping_dt": 20260425,
  "buyer_name": "홍길동",
  "receiver_name": "홍길동",
  "tel1": "010-1234-5678",
  "zipcode": 12345,
  "shipping_address1": "서울시 강남구 테헤란로 152",
  "shipping_address2": "강남파이낸스센터 10층",
  "shipping_message": "문 앞에 놓아주세요",
  "channel_id": 1,
  "order_product_list": [
    {
      "shipping_product_id": 43778,
      "quantity": 2
    }
  ]
}
```

발주 등록 벌크 입력:

```json
{
  "member_id": 70,
  "order_list": [
    {
      "company_order_code": "ORD-20260421-002",
      "shipping_method_id": 1,
      "request_shipping_dt": 20260425,
      "buyer_name": "김철수",
      "receiver_name": "김철수",
      "tel1": "010-9876-5432",
      "zipcode": 54321,
      "shipping_address1": "경기도 성남시 분당구 판교역로 235",
      "order_product_list": [
        {
          "shipping_product_id": 43778,
          "quantity": 1
        }
      ]
    }
  ]
}
```

### 6.5 출고 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 출고 조회 | `GET /v3/releases` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 출고 ID, 출고 상태, 출고일 |
| 출고대상상품 조회 | `GET /v3/release/items` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 출고 대상 상품과 수량 |
| 출고대상상품재고할당 조회 | `GET /v3/release/item_stocks` | `page`, `page_size`, `member_id` | 상품별 할당 재고 |
| 출고회차 조회 | `GET /v3/release/shipping_work` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 출고 회차, 작업 상태 |
| 운송장 일반 조회 | `GET /v3/release/shipping_codes` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 택배사, 송장번호, 출고 연결 정보 |

### 6.6 반품/관리 API

| 기능 | Method/Path | 입력 | 응답 저장 후보 |
| --- | --- | --- | --- |
| 반품 조회 | `GET /v3/release_return/searchs` | `page`, `page_size`, `member_id`, `start_dt`, `end_dt` | 반품 ID, 주문/출고 연결, 반품 상태, 반품 수량 |
| 로케이션 조회 | `GET /v3/locations` | `page`, `page_size`, `member_id` | 로케이션 ID, 로케이션명, 사용 여부 |

## 7. 쇼핑몰 사용 시나리오

### 상품 동기화

1. 주기적으로 상품 조회 API를 호출한다.
2. 상품코드 또는 자체상품코드를 기준으로 내부 상품과 매칭한다.
3. 가격, 옵션, 재고, 판매 상태는 사방넷 값을 원천으로 저장한다.
4. 쇼핑몰 전용 노출 정보, 검색 태그, 추가 이미지, 추가 상세 설명은 내부 DB에 별도 저장한다.
5. 동기화 실패 시 실패 로그를 남기고 관리자에서 재시도한다.

검증 필요:

- 대표 이미지와 상세 이미지 제공 방식
- 상세 설명 제공 여부
- 옵션, 사이즈, 컬러 구조
- 상품정보제공고시 매핑 방식
- 품절/숨김 상태 값

### 주문 전송

확정 원칙:

- 내부 주문은 토스페이먼츠 결제 승인 후 `결제완료`가 된 뒤 사방넷으로 전송한다.
- 사방넷 전송 실패는 결제 성공을 취소하지 않는다. 내부 주문에 `사방넷 전송 실패` 상태를 남기고 재시도한다.

검증 필요:

- 주문 목록 조회 API는 배송상태·운송장 동기화에 사용한다.
- 사방넷 문의 결과 쇼핑몰 주문 신규 등록 API는 현재 제공되지 않으며 웹훅도 사용할 수 없다.
- 신규 주문은 `주문관리 → 주문서입력(대량) → 쇼핑몰[일반] → 시퀸즈 [20316]`의 엑셀 대량등록을 사용한다.
- 시퀸즈 전용 열은 `상품명, 상품코드, 주문번호, 수취인명, 수취인우편번호, 수취인주소, 주문금액, 수량` 순서이며 A~H가 모두 필수다.
- `저장` 클릭은 확인 단계 없이 실제 주문등록을 시작하므로 자동화에서 최종 실행 경계로 취급한다. 현재 구현은 엑셀 생성까지 수행하며 브라우저 업로드·저장은 운영 승인 전까지 실행하지 않는다.

### 운송장/배송

가능한 방식:

- 사방넷에서 운송장과 배송 상태를 가져와 내부 주문에 반영한다.
- 또는 내부 관리자에서 운송장을 입력하고 사방넷에 저장/수정한다.

검증 필요:

- 송장번호 입력 주체
- 배송사 코드 체계
- 배송 상태 값
- 부분 배송 가능 여부

### 클레임/반품

가능한 방식:

- 내부에서 취소/교환/반품 요청을 받고 사방넷 클레임과 동기화한다.
- 사방넷 클레임 목록을 조회해 내부 상태를 보정한다.

검증 필요:

- 클레임 생성 API 존재 여부
- 클레임 목록 조회 응답 필드
- 토스페이먼츠 취소와 사방넷 클레임 상태 매칭 방식

## 8. 내부 데이터 매핑 초안

| 내부 개념 | 사방넷 매핑 후보 |
| --- | --- |
| 브랜드 | 상품 조회 응답의 브랜드 또는 제조사 계열 필드 |
| 상품코드 | `productCode` 또는 `customProductCode` |
| 카테고리 | 마이카테고리 |
| 옵션 | 상품 옵션 필드 |
| 재고 | 상품 재고 또는 풀필먼트 재고 |
| 정상가/판매가 | 상품 가격 필드 |
| 대표 이미지 | 상품 이미지 필드 |
| 상세 이미지/설명 | 상품 상세 필드. 제공 범위 검증 필요 |
| 주문번호 | 내부 주문번호와 사방넷 주문 식별자 매핑 |
| 송장번호 | 운송장 API |
| 취소/반품 | 클레임 API |

## 9. 장애와 재시도

- 모든 API 호출은 요청 ID를 부여해 로그를 남긴다.
- 인증 실패, 네트워크 실패, 5xx 응답은 재시도 가능 상태로 처리한다.
- 4xx 응답은 요청 데이터 오류로 분류하고 관리자 확인이 필요하다.
- 상품 동기화 실패는 기존 상품 노출을 즉시 내리지 않고 마지막 정상 데이터를 유지한다.
- 주문 전송 실패는 관리자 알림과 수동 재시도 기능을 제공한다.
- 재시도는 같은 주문이 중복 등록되지 않도록 멱등 키 또는 내부 전송 이력을 사용한다.

## 10. 구현 전 체크리스트

- [ ] 테스트 계정으로 토큰 발급 성공 확인
- [ ] 상품 조회 응답 샘플 20개 확보
- [ ] 옵션/재고/이미지/상세 설명 필드 확인
- [ ] 카테고리 조회와 브랜드 매핑 기준 확인
- [ ] 결제 완료 주문의 사방넷 등록 방식 확인
- [ ] 송장번호와 배송 상태 동기화 방향 확정
- [ ] 클레임 처리 방식 확정
- [ ] 풀필먼트 API 사용 여부 결정
