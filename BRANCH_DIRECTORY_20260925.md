# 전국학원.com 지점안내

## 범위

- 지점안내 루트 1개, 지역 허브 16개, 실제 지점 193개 = 신규 210개.
- 과목·학년별 지점 하위 페이지는 이번에 만들지 않았다.
- 기존 페이지 7,186개의 원고·URL·메타 설명은 보존했다. 상단·하단 메뉴에 지점안내를 추가하고 홈·전국학원·과목별학원·상담문의 4곳에 진입 안내를 추가했다.
- 기존 초록색 디자인과 16px 이상 본문을 사용한다. 320/390/768/1280px 화면 검사, 검색 조건·초기화·지점 이동·목차·FAQ를 확인했다. 모바일 교육비는 카드형이다.

## 자료 기준

2026-09-25에 소유자가 제공한 `센터정보` 폴더의 네 자료 파일 해시를 확인하고 센터 데이터와 대조했다. 371개 동네는 실제 지점 수가 아니며 이 자료에는 188개 실제 지점이 연결되어 있다. 센터 원본에 있는 다른 5개 지점을 포함해 총 193개를 안내한다.

- 주소·등록명·등록번호·과목별 학년·학교 참고 자료·방문 조건을 지점에 맞춰 표시.
- 지점별 교육비 안내 36곳과 지역 공통 참고표 157곳을 구분. 공통 금액을 확정 교습비로 표기하지 않음.
- 화성태안점은 현재 센터 엑셀에 행이 없어 최신 371개 코드의 등록 정보·주소·학년을 사용. 운영 시간은 확인 필요로 유지.
- 지점 사진이 없는 경우 학습 공간 안내 이미지를 사용하고 실제 지점 사진으로 구조화하지 않음.
- 대표이미지(숨김) → 본문 공간 이미지 → 지도 → 이후 학습 공간 사진 순서. 루트와 지역 허브에는 긴 본문 이미지를 삽입하지 않음.
- 타 사이트의 원고가 아닌 전국학원용 설명·상담 질문을 작성. 주소·등록 정보 같은 사실은 임의로 바꾸지 않음.

## 검색·연결

- 210개 페이지 모두 개별 title, 56~71자 설명, meta/OG/Twitter 설명 일치, self-canonical, Breadcrumb.
- 실제 센터에 EducationalOrganization/LocalBusiness, 확인된 과목에 Service. 허브에 CollectionPage/ItemList. 보이는 문답과 일치하는 FAQPage.
- 지점 안내를 Article로 위장하거나 후기·평점·성과·시간표를 추가하지 않음.
- 신규 URL 210개를 사이트맵에 추가해 7,396개. 기존 URL은 제거하지 않음.
- `/branch-updates.xml`은 최근 추가한 안내 중 50개를 제공하며, 모든 페이지 목록은 사이트맵에 있음.
- 문맥상 관련된 기존 동네 허브 링크 362개. 지역 허브·같은 구의 다른 지점·학습코칭·상담 안내 연결.
- 검색 순위, 색인, 검색 결과 문구나 AI 답변 채택을 보장하지 않음.

## 검증·빌드

원본 엑셀·CSV·자료 대조 기록은 공개 결과에서 제외한다. 로컬 기록은 `tools/reports/branch-directory-20260925/`, 확인된 사실은 `tools/data/branch-directory/`에 있다. 처음 원본을 읽는 스크립트는 기존의 검증된 사실 매핑을 재대조하므로 지정된 로컬 참고 폴더가 필요하다.

```powershell
python tools/prepare_branch_directory.py
python tools/build_branch_directory.py
python tools/audit_branch_directory.py
node build-public.mjs
node wawa-analytics-build.mjs wawa-02 .public-release
node seo-descriptions.mjs --root=.public-release --check
python tools/verify_branch_directory_live.py
```

자동 검사: 68,590개 확인, 내부 링크 8,134개, 이미지 705개, 기존 원고 7,186개 보존, 오류 0건. 설명·제목 중복 0건. 다음 페이지 추가 시 빌드 파일의 예상 페이지 수 7,396도 함께 갱신한다.

## 배포 경로

기존 Vercel 프로젝트 `jeonguk-academy`와 GitHub `01039578283-hub/jeonguk-academy`의 `main` 연결을 사용한다. CLI 개별·압축 업로드는 `api-upload-free` 일일 한도로 중단되었다. 다른 계정이나 프로젝트를 만들지 않는다. 검증한 공개 파일 및 필요한 빌드 도구만 별도 Git 작업 디렉터리에서 커밋한다. 원래 작업 폴더의 기존 미커밋 변경을 초기화하지 않는다.

배포 후 실제 완료 여부는 로컬 `production-verification.json`과 Vercel의 운영 배포 상태에서 확인한다. 이전 운영 배포 ID는 `dpl_GaTWo3Vv1m1vv4Nu54kgmfWYksxa`이다.
