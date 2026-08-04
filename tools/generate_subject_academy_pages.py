from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import zipfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
COMMON = SITE.parent / "참고자료" / "공통자료"
USED_DRAFTS = SITE.parent / "참고자료" / "사용한 원고" / "전국학원.com 추가 원고"
BASE_URL = "https://xn--3e0bl59bm0ad17a.com"
SITE_NAME = "전국학원 영어수학 전문학원 찾기"
PHONE_DISPLAY = "010-3957-8283"
PHONE_LINK = "01039578283"
PUBLISH_DATE = "2026-08-04"
MODIFIED_DATE = "2026-08-04"


CONFIGS = {
    "중1수학학원": {
        "zip": "중1 수학학원.zip",
        "label": "중1 수학학원",
        "grade": "중학교 1학년",
        "grade_token": "중1",
        "subject": "수학",
        "school_field": "타깃학교\n(중)",
        "grade_field": "가능학년\n(수학)",
        "national_category": "중학생학원",
    },
    "중1영어학원": {
        "zip": "중1 영어학원.zip",
        "label": "중1 영어학원",
        "grade": "중학교 1학년",
        "grade_token": "중1",
        "subject": "영어",
        "school_field": "타깃학교\n(중)",
        "grade_field": "가능학년\n(영어)",
        "national_category": "중학생학원",
    },
    "초6수학학원": {
        "zip": "초6 수학학원.zip",
        "label": "초6 수학학원",
        "grade": "초등학교 6학년",
        "grade_token": "초6",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
        "national_category": "초등학생학원",
    },
    "초6영어학원": {
        "zip": "초6 영어학원.zip",
        "label": "초6 영어학원",
        "grade": "초등학교 6학년",
        "grade_token": "초6",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
        "national_category": "초등학생학원",
    },
    "초5수학학원": {
        "zip": "초5 수학학원.zip",
        "label": "초5 수학학원",
        "grade": "초등학교 5학년",
        "grade_token": "초5",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
        "national_category": "초등학생학원",
    },
    "초5영어학원": {
        "zip": "초5 영어학원.zip",
        "label": "초5 영어학원",
        "grade": "초등학교 5학년",
        "grade_token": "초5",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
        "national_category": "초등학생학원",
    },
    "초4수학학원": {
        "zip": "초4 수학학원.zip",
        "label": "초4 수학학원",
        "grade": "초등학교 4학년",
        "grade_token": "초4",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
        "national_category": "초등학생학원",
    },
    "초4영어학원": {
        "zip": "초4 영어학원.zip",
        "label": "초4 영어학원",
        "grade": "초등학교 4학년",
        "grade_token": "초4",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
        "national_category": "초등학생학원",
    },
}


SECTION_RE = re.compile(r"^\[(페이지타이틀|메타설명|본문|FAQ|학부모후기|JSON-LD 요약)\]\s*$", re.M)
FAQ_RE = re.compile(r"Q\d+[.)]?\s*(.*?)\s*\nA(?:\d+)?[.)]?\s*(.*?)(?=\n\s*Q\d+[.)]?|\Z)", re.S)


# 원고 생성 과정에서 쓰인 표현은 검색 방문자에게는 제작 메모처럼 읽힙니다.
# 아래 치환은 사실관계를 건드리지 않고 교사·상담자가 설명하는 문장으로만 다듬습니다.
EDITORIAL_REPLACEMENTS = (
    ("이 이 안내", "이 안내"),
    ("합니다 이 기록", "합니다. 이 기록"),
    ("계산 정확도을", "계산 정확도를"),
    ("혼합 계산 순서을", "혼합 계산 순서를"),
    ("참고 확인 항목", "참고 항목"),
    ("참고 키워드 항목", "상담 참고 항목"),
    ("참고 키워드", "상담 주제"),
    ("키워드 항목", "확인 항목"),
    ("참고 항목 항목", "참고 항목"),
    ("항목로", "항목으로"),
    ("학원를", "학원을"),
    (" 단원이 아직 불안한 ", " 부분이 아직 불안하고 "),
    ("D열에 적힌 수업 학교", "센터 안내에서 확인되는 수업 가능 학교"),
    ("D열에 적힌 수업학교", "센터 안내에서 확인되는 수업 가능 학교"),
    ("D열 학교명이 공란인 경우라서", "센터 안내에 학교 목록이 따로 표시되지 않아"),
    ("D열 학교명", "센터 안내의 학교명"),
    ("D열", "센터 안내"),
    ("행에 적힌 수업 학교", "센터 안내에서 확인되는 수업 가능 학교"),
    ("정보형 페이지", "학습 안내"),
    ("페이지의 설득력", "상담 안내의 구체성"),
    ("설득력을 높입니다", "상담 내용을 구체화합니다"),
    ("보호자 신뢰", "학부모가 확인할 근거"),
    ("구조화 데이터에 넣기 좋게", "상담 전에 이해하기 쉽게"),
    ("구조화 데이터에 활용하기 좋게", "상담 전에 이해하기 쉽게"),
    ("생성형 검색에서", "질문에 바로 답할 수 있도록"),
    ("생성형 검색", "질문형 학습 안내"),
    ("검색 품질", "정보의 정확성"),
    ("검색 노출", "정보 전달"),
    ("검색엔진", "학습 정보를 찾는 보호자"),
    ("SEO", "학습 안내"),
    ("AEO", "답변형 안내"),
    ("GEO", "질문형 안내"),
    ("센터 안내에 표시된 수업 가능 학교에 포함된", "센터 안내에 수업 가능 학교로 표시된"),
    ("센터 자료에서 확인되는 수업 가능 학교에 있는", "센터 안내에 수업 가능 학교로 표시된"),
    ("가까운 곳인지보다 학원 위치만 비교하지 않고", "가까운지만 비교하기보다"),
    ("보는 것을 먼저 따져보는 것이 좋습니다", "먼저 살펴보는 것이 좋습니다"),
    ("상담 질문을 구체화해 확인하는 질문으로 활용", "상담에서 확인할 질문으로 활용"),
    ("특정 학교의 시험 범위를 이 안내에서 단정하기보다", "특정 학교의 시험 범위를 미리 단정하기보다"),
    ("학원 선택 과정에서 확인할 학원 이전 항목", "학원을 옮길 때 확인할 항목"),
    ("학원 이전 항목을", "학원을 옮길 때 확인할 기준을"),
    ("실제 만족도를 가르는 기준이 될 수 있습니다", "학습 일정을 꾸준히 유지하는 데 영향을 줄 수 있습니다"),
    ("센터 자료에서 확인되는", "센터 안내에 표시된"),
    ("센터 자료에 표시된", "센터 안내에 표시된"),
    ("센터 자료", "센터 안내"),
    ("이 안내에서 기준으로 삼은 학생 유형", "현재 살펴볼 학생 유형"),
    ("학원이전", "학원 이전"),
    ("상담 상담", "상담"),
    ("수업 수업", "수업"),
    ("학습 학습", "학습"),
    ("학생 학생", "학생"),
    ("지역명만 바꾼 설명이 아니라", "학생의 현재 학습 상황을 중심으로"),
    ("지역명만 바꾼", "학생 상황을 충분히 반영하지 않은"),
    ("학부모가 남길 법한", "학부모 상담에서 자주 나오는"),
    ("정보성 페이지 형태로 정리했습니다", "상담 전에 확인하기 쉽게 정리했습니다"),
    ("정보성 학원 페이지 요약입니다", "학습 상담에 필요한 내용을 요약했습니다"),
    ("정보성 학원 페이지입니다", "학습 상담 안내입니다"),
    ("정보성 학원 페이지", "학습 상담 안내"),
    ("정보성 안내 페이지입니다", "학습 상담 안내입니다"),
    ("정보성 학습 안내입니다", "학습 상담 안내입니다"),
    ("정보성 원고이다", "학습 상담 안내입니다"),
    ("정보성 원고입니다", "학습 상담 안내입니다"),
    ("정보성 페이지", "학습 안내"),
    ("구조화 데이터 설명문에 활용할 수 있습니다", "상담 안내에 반영합니다"),
    ("구조화 데이터", "학습 안내"),
    ("JSON-LD", "학습 안내"),
    ("이 페이지", "이 안내"),
    ("검색 의도", "상담 목적"),
    ("검색어", "상담 주제"),
    ("검색한 학부모", "학원을 알아보는 학부모"),
    ("검색하는 학부모", "학원을 알아보는 학부모"),
    ("검색자", "학습 정보를 찾는 보호자"),
    ("제공된 수업 학교 정보", "센터 자료에서 확인되는 수업 가능 학교"),
    ("제공된 학교 정보", "센터 자료에서 확인되는 학교 정보"),
    ("제공된 학교명", "센터 자료에서 확인되는 학교명"),
    ("제공 학교", "확인 가능한 학교"),
    ("제공된 주소", "확인된 센터 주소"),
    ("제공 주소", "센터 주소"),
    ("제공된 자료", "센터 안내 자료"),
    ("제공 자료", "센터 안내 자료"),
    ("제공된", "확인된"),
    ("임의로", "근거 없이"),
)


PHRASE_VARIANTS = {
    "확인하는 것이 좋습니다": (
        "확인해 보는 편이 좋습니다",
        "먼저 점검해 두는 것이 좋습니다",
        "상담 전에 살펴보는 편이 좋습니다",
        "확인 항목으로 삼는 것이 좋습니다",
    ),
    "살펴보는 것이 좋습니다": (
        "차근히 확인하는 편이 좋습니다",
        "상담 전에 점검해 보세요",
        "우선 확인할 필요가 있습니다",
        "판단 기준으로 두는 편이 좋습니다",
    ),
    "중요합니다": (
        "핵심 확인 항목입니다",
        "먼저 챙겨야 할 부분입니다",
        "학습 흐름을 정할 때 중요하게 봐야 합니다",
        "상담에서 빠뜨리지 말아야 합니다",
    ),
    "도움이 됩니다": (
        "유용합니다",
        "참고가 됩니다",
        "의미가 있습니다",
        "도움이 될 수 있습니다",
    ),
    "확인할 수 있습니다": (
        "구체적으로 점검할 수 있습니다",
        "상담 과정에서 살펴볼 수 있습니다",
        "학습 기록으로 비교할 수 있습니다",
        "다음 점검 때 다시 확인할 수 있습니다",
    ),
}


LEARNING_PROFILES = {
    "중1수학학원": (
        "정수와 유리수 계산에서 부호 실수가 반복되는 경우",
        "문자와 식의 뜻은 알지만 식을 세우는 단계에서 멈추는 경우",
        "기본 문제는 풀지만 서술형 풀이 과정을 생략하는 경우",
        "좌표와 그래프에서 조건을 읽는 시간이 오래 걸리는 경우",
        "시험 전에는 공부하지만 평소 복습 간격이 길어지는 경우",
        "답은 맞혀도 검산 기준이 일정하지 않은 경우",
        "새 단원에 들어가면 앞 단원의 개념을 연결하지 못하는 경우",
        "문제 풀이 속도와 정확도의 균형이 흔들리는 경우",
    ),
    "중1영어학원": (
        "단어 뜻은 외우지만 문장 안에서 품사를 구분하기 어려운 경우",
        "문법 설명은 이해해도 서술형 문장으로 옮기지 못하는 경우",
        "교과서 지문을 읽고도 답의 근거를 표시하지 않는 경우",
        "듣기와 독해 중 한 영역의 학습 간격이 길어지는 경우",
        "과제는 끝내지만 틀린 문장을 다시 해석하지 않는 경우",
        "새로운 지문에서 문장 구조를 잡는 시간이 오래 걸리는 경우",
        "시험 직전에만 단어를 몰아서 외우는 경우",
        "해석은 가능하지만 핵심 내용을 짧게 정리하기 어려운 경우",
    ),
    "초6수학학원": (
        "분수와 소수 계산에서 검산을 생략하는 경우",
        "비와 비율 문제에서 기준량과 비교하는 양을 혼동하는 경우",
        "도형 공식은 외웠지만 그림의 조건을 식으로 옮기기 어려운 경우",
        "문장제에서 필요한 조건을 표시하지 않는 경우",
        "정답을 확인한 뒤 틀린 이유를 기록하지 않는 경우",
        "중등 선행보다 초등 핵심 단원의 복습이 먼저 필요한 경우",
        "풀이를 말로 설명할 때 계산 과정이 빠지는 경우",
        "문제 난도가 올라가면 시도하기 전에 답부터 확인하는 경우",
    ),
    "초6영어학원": (
        "단어 시험은 통과하지만 며칠 뒤 뜻이 흐려지는 경우",
        "기초 문법을 알고도 문장 해석에 적용하지 못하는 경우",
        "독해 문제에서 답의 근거 문장을 찾지 않는 경우",
        "짧은 영작에서도 어순을 자주 바꾸는 경우",
        "듣기 학습과 어휘 복습이 따로 진행되는 경우",
        "새 지문을 만나면 첫 문장부터 해석이 멈추는 경우",
        "문법 문제는 풀지만 왜 그 답인지 설명하기 어려운 경우",
        "중학교 영어를 앞두고 복습 순서를 정하지 못한 경우",
    ),
    "초5수학학원": (
        "분수의 덧셈과 뺄셈에서 통분 과정을 자주 생략하는 경우",
        "소수 계산은 가능하지만 자릿값을 맞추는 실수가 이어지는 경우",
        "약수와 배수 개념을 문장제에 적용하기 어려운 경우",
        "도형의 넓이 공식을 외웠지만 조건에 맞게 선택하지 못하는 경우",
        "풀이 과정은 맞아도 마지막 계산을 검산하지 않는 경우",
        "문제 수는 채우지만 틀린 유형을 다시 분류하지 않는 경우",
        "문장제에서 필요한 수와 묻는 내용을 구분하지 못하는 경우",
        "새 단원 진도보다 이전 단원의 빈틈을 먼저 확인해야 하는 경우",
    ),
    "초5영어학원": (
        "단어 뜻은 기억하지만 문장 속 쓰임을 연결하기 어려운 경우",
        "be동사와 일반동사 문장의 차이가 아직 흔들리는 경우",
        "짧은 지문을 읽고도 핵심 문장을 고르기 어려운 경우",
        "듣기에서 아는 표현도 문장으로 이어지면 놓치는 경우",
        "영작할 때 우리말 어순을 그대로 옮기는 경우",
        "숙제는 끝내지만 틀린 문장을 소리 내어 다시 읽지 않는 경우",
        "새 단어를 외운 뒤 이전 어휘를 함께 복습하지 않는 경우",
        "문법 문제의 답은 맞혀도 선택 이유를 설명하기 어려운 경우",
    ),
    "초4수학학원": (
        "큰 수의 자릿값을 읽고 쓰는 과정에서 혼동이 생기는 경우",
        "곱셈과 나눗셈 계산 순서를 급하게 처리하는 경우",
        "분수의 크기를 그림과 수로 연결하기 어려운 경우",
        "각도와 도형 문제에서 주어진 조건을 표시하지 않는 경우",
        "계산 답은 맞아도 풀이 과정을 문장으로 남기기 어려운 경우",
        "틀린 문제를 지우고 정답만 다시 적는 경우",
        "문장제에서 어떤 연산을 써야 할지 결정하는 시간이 긴 경우",
        "학습량보다 매일 같은 시간에 복습하는 습관이 먼저 필요한 경우",
    ),
    "초4영어학원": (
        "알파벳 소리와 단어 철자를 연결하는 과정이 아직 불안한 경우",
        "기초 단어는 알지만 짧은 문장을 끝까지 읽기 어려운 경우",
        "인칭대명사와 be동사 짝을 자주 바꾸어 쓰는 경우",
        "듣고 따라 말할 수 있어도 뜻을 설명하기 어려운 경우",
        "단어를 한 번에 몰아서 외우고 복습 간격이 길어지는 경우",
        "문장을 쓸 때 대문자와 문장부호를 자주 빠뜨리는 경우",
        "영어 문제를 만나면 소리 내어 읽기 전에 답부터 고르는 경우",
        "교과 학습과 기초 읽기 연습의 순서를 정하기 어려운 경우",
    ),
}


LEARNING_ACTIONS = {
    "수학": (
        "풀이 첫 줄과 마지막 검산을 함께 확인합니다",
        "틀린 문제를 계산·개념·조건 해석으로 나누어 기록합니다",
        "같은 유형을 일정 간격 뒤 다시 풀어 이해가 남았는지 봅니다",
        "학교 진도와 현재 약점의 순서를 나누어 주간 계획을 세웁니다",
        "정답 수보다 풀이 과정을 말로 설명할 수 있는지 확인합니다",
        "과제량을 늘리기 전에 미완료 원인과 소요 시간을 먼저 봅니다",
        "기본 유형과 서술형을 분리해 보완 순서를 정합니다",
        "한 단원의 오답이 다음 단원에 미치는 영향을 함께 점검합니다",
    ),
    "영어": (
        "어휘·문법·독해를 따로 외우지 않고 한 문장 안에서 연결합니다",
        "틀린 문장의 근거를 지문에서 다시 표시하게 합니다",
        "단어 뜻과 품사, 예문을 같은 복습 주기 안에서 확인합니다",
        "학교 진도와 현재 어휘량을 나누어 주간 계획을 세웁니다",
        "해석한 문장을 짧게 요약해 이해 여부를 확인합니다",
        "과제량보다 틀린 문장을 다시 읽는 시간을 먼저 확보합니다",
        "문법 개념을 교과서 문장과 짧은 영작으로 옮겨 봅니다",
        "듣기·독해·서술형의 약점을 구분해 우선순위를 정합니다",
    ),
}


DECISION_LENSES = (
    "문제를 시작하기까지 걸리는 시간과 첫 풀이 행동을 함께 기록합니다",
    "정답을 본 뒤 스스로 다시 푸는 데 필요한 간격을 확인합니다",
    "질문을 표시한 문제와 그냥 넘긴 문제를 구분해 살펴봅니다",
    "설명할 수 있는 개념과 공식만 외운 개념을 따로 점검합니다",
    "과제 미완료의 원인이 분량인지 이해 부족인지 먼저 나눕니다",
    "쉬운 문제의 실수와 어려운 문제의 접근 실패를 분리해 봅니다",
    "학교 진도표와 실제로 혼자 풀 수 있는 단원을 나란히 놓고 봅니다",
    "수업 직후 이해와 며칠 뒤 남아 있는 이해를 따로 확인합니다",
    "풀이를 고친 흔적과 같은 유형을 다시 시도한 기록을 비교합니다",
    "공부 시간을 늘리기 전 집중이 끊기는 시점부터 파악합니다",
    "교재 권수보다 각 교재가 맡는 복습 역할을 분명히 정합니다",
    "시험 전 몰아 공부한 양보다 평소 복습 간격의 규칙성을 봅니다",
    "학생이 답을 묻는 순간과 스스로 조건을 다시 읽는 순간을 관찰합니다",
    "오답 이유를 말로 설명한 뒤 다음 행동까지 적을 수 있는지 봅니다",
    "학습 계획의 완료 칸보다 중단된 지점에 남긴 메모를 확인합니다",
    "한 번 맞힌 문제보다 일주일 뒤에도 해결할 수 있는 문제를 봅니다",
)

EVIDENCE_CHECKS = (
    "도움 없이 시작한 문제와 힌트를 받은 문제를 구분해 남깁니다",
    "정답을 고친 뒤 풀이 이유까지 다시 설명했는지 확인합니다",
    "과제를 멈춘 시각과 다시 시작한 시각을 함께 적어 봅니다",
    "질문 표시를 남긴 문제를 다음 수업에서 해결했는지 비교합니다",
    "같은 유형을 사흘 뒤 다시 풀었을 때의 정확도를 확인합니다",
    "문제 조건을 소리 내어 읽은 뒤 식으로 옮길 수 있는지 봅니다",
    "계획한 분량보다 실제로 끝낸 범위와 걸린 시간을 기록합니다",
    "틀린 이유를 계산·개념·조건 해석 가운데 하나로 분류합니다",
    "정답을 보기 전 스스로 시도한 흔적이 남아 있는지 확인합니다",
    "수업 직후 이해한 내용이 다음 복습 때도 유지되는지 살펴봅니다",
    "쉬운 문제의 실수와 낯선 문제의 접근 실패를 따로 적습니다",
    "숙제를 시작하기까지 걸린 시간과 집중이 끊긴 지점을 봅니다",
    "설명을 들은 문제를 자기 말로 다시 정리할 수 있는지 확인합니다",
    "오답을 고친 날짜와 같은 유형을 다시 확인할 날짜를 함께 정합니다",
    "교재마다 진도·복습·오답 중 어떤 역할을 맡는지 구분합니다",
    "완료한 계획뿐 아니라 미완료 이유와 다음 행동까지 남깁니다",
)


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def has_batchim(value: str) -> bool:
    if not value:
        return False
    code = ord(value[-1])
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def normalize_particles(value: str) -> str:
    def particle(match: re.Match[str], consonant: str, vowel: str) -> str:
        word = match.group(1)
        return word + (consonant if has_batchim(word) else vowel) + match.group(2)

    # 문맥을 제한해 정상 문장까지 과도하게 바꾸지 않으면서 자주 발생한 조사 오류를 바로잡습니다.
    value = re.sub(
        r"([가-힣]+)(?:와|과)(\s+(?:관련|함께|비교|연결|같이|같은|달리|더불어))",
        lambda match: particle(match, "과", "와"), value,
    )
    value = re.sub(
        r"([가-힣]+)(?:이|가)(\s+(?:필요|있|없|되|맞|중요|좋|어렵|가능|안전|현실적|적절|포함))",
        lambda match: particle(match, "이", "가"), value,
    )
    value = re.sub(
        r"([가-힣]+)\s*(?:을|를)(\s+(?:(?:먼저|함께|직접)\s+)?(?:확인|비교|선택|준비|점검|참고|활용|검토|결정|사용|반영|정리|살피|질문|요청|기록|설명|구분|조절|연결|나누|바꾸|줄이|늘리|풀|보|기준|중심|정확히))",
        lambda match: particle(match, "을", "를"), value,
    )
    value = re.sub(
        r"([가-힣]+)\s*(?:으로|로)(\s+(?:제시|표시|분류|구분|활용|사용|연결|이어|정리|확인))",
        lambda match: particle(match, "으로", "로"), value,
    )
    return value


def clean_text(value: str) -> str:
    value = value.replace("\ufeff", "").replace("내신성적와", "내신성적과")
    # 일부 앞쪽 치환 결과가 뒤쪽의 제작 표현을 만들 수 있어 두 번만 안정적으로 정규화합니다.
    for _ in range(2):
        for before, after in EDITORIAL_REPLACEMENTS:
            value = value.replace(before, after)
    boundary_terms = (
        ("원고에서 제공된", "센터 자료에서 확인한"),
        ("원고에서는", "이 안내에서는"),
        ("원고에서", "이 안내에서"),
        ("원고에는", "이 안내에는"),
        ("원고이므로", "안내이므로"),
        ("원고의", "안내의"),
        ("원고는", "안내는"),
        ("원고를", "안내 내용을"),
        ("원고에", "안내에"),
        ("페이지에서는", "안내에서는"),
        ("페이지에서", "안내에서"),
        ("페이지이므로", "안내이므로"),
        ("페이지의", "안내의"),
        ("페이지는", "안내는"),
        ("페이지를", "안내를"),
        ("페이지에", "안내에"),
    )
    for before, after in boundary_terms:
        value = re.sub(rf"(?<![가-힣A-Za-z0-9]){re.escape(before)}", after, value)
    value = value.replace(
        "학교명 외 이름은 안내에 추가하지 않는 구성이 적절합니다",
        "학교별 범위는 학생이 가져온 최신 진도 자료를 확인한 뒤 상담에서 정하는 편이 적절합니다",
    )
    value = re.sub(
        r"센터 안내에 표시된 학교명 외(?:의)? 이름은 안내에 추가하지 않는 구성이 적절합니다",
        "학교별 범위는 학생이 가져온 최신 진도 자료를 확인한 뒤 상담에서 정하는 편이 적절합니다",
        value,
    )
    value = re.sub(
        r"[^.]{0,60}(?:은|는) 초4 영어학원 안내이므로 고등 입시 결과를 보장하는 표현보다,",
        "초4 영어 상담에서는 고등 입시 결과를 단정하기보다,",
        value,
    )
    value = re.sub(
        r"([^.]*) 안내의 핵심은 (.+?) 학생이면서 (.+?) 흐름을 보이는 경우인 학생이 무리하지 않고 다음 단계로 넘어가도록 점검 기준을 세우는 데 있습니다",
        r"\1 상담에서는 \2 학생이 \3 흐름도 함께 보이는지 살펴보고, 무리하지 않는 다음 학습 단계를 정합니다",
        value,
    )
    value = re.sub(r"확인되지 않은 (?:학교|시설|차량) 정보를 임의로 (?:만들거나 )?추정하지 말고", "확인 가능한 자료를 기준으로 하고", value)
    value = re.sub(r"성적 (?:상승|향상|결과)을 보장하지 (?:않습니다|않는 안내입니다)", "학생마다 학습 속도와 결과가 다를 수 있습니다", value)
    value = value.replace("함께 요청하는 것을 함께 고려", "함께 요청하는 방안을 고려")
    value = value.replace("항목는", "항목은")
    value = value.replace("조절를", "조절을")
    value = value.replace("정확도이나", "정확도나")
    value = value.replace("않고이 안내", "않고 이 안내")
    value = value.replace("학교명을 추정하지 않고 이 안내는", "학교명은 추정하지 않았으며, 이 안내는")
    value = value.replace("수업 이 안내", "수업 안내")
    value = value.replace("학원 이 안내", "학원 안내")
    value = value.replace("수학 이 안내", "수학 안내")
    value = value.replace("영어 이 안내", "영어 안내")
    value = value.replace("자기 말으로", "자기 말로")
    value = value.replace(
        "특정 학교를 근거 없이 만들지 않고",
        "재학 학교와 최근 진도 자료를 상담에서 확인하고",
    )
    value = value.replace(
        "없는 학교를 만들지 않고",
        "재학 학교와 최근 진도 자료를 상담에서 확인하고",
    )
    value = value.replace(
        "동화중학교 맞은편/ 주민센터 뒷 건물 로 설명 드립니다",
        "동화중학교 맞은편, 주민센터 뒤 건물로 안내드립니다",
    )
    value = value.replace("수지구청 맞으면", "수지구청 맞은편")
    value = value.replace("건겅검진센터", "건강검진센터")
    value = value.replace(
        "자료의 보조 키워드로 ‘영어 수학’이 제시되어 있어도",
        "영어와 수학을 함께 알아보는 경우에도",
    )
    value = re.sub(
        r"([^.!?]{1,80})은 초등 5학년 영어를 중학교 전 단계로 이어 가려는 학부모에게 특히 많이 검색되는 페이지입니다",
        r"\1을 알아보는 학부모라면 중학교 전 단계에서 어휘·문법·독해 중 어디가 흔들리는지 먼저 확인해야 합니다",
        value,
    )
    value = re.sub(
        r"([^.!?]{1,70})의? 정보성 안내는 확인된 센터 주소, 과목, 상담 주제만 사용해 과장 없이 작성되어야 합니다",
        r"\1 상담에서는 확인된 센터 정보와 학생의 최근 학습 기록을 바탕으로 현재 상태를 설명합니다",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)([을를]) 학습 관리 언어로 바꾸는 기준",
        r"\1\2 상담에서 확인하는 기준",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)(?:은|는) ([^.!?]{1,90})에서 단순 광고 표현으로만 쓰이면 설득력이 약합니다",
        r"\1 관련 안내는 \2에서 이름만 확인하기보다 실제 관리 방식과 연결해 살펴봐야 합니다",
        value,
    )
    value = re.sub(
        r"([^.!?]{1,80}) 수업에서는 이 키워드가 아이의 진단, 과제 확인, 오답 재점검 중 어디에 연결되는지 설명되어야 합니다",
        r"\1 수업에서는 해당 관리 방식이 진단, 과제 확인, 오답 재점검 중 어디에 연결되는지 확인해야 합니다",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)(?:은|는) ([^.!?]{1,90})의 차별점을 설명하는 단어가 될 수 있지만, 초5 수학 수업에서는 구체적인 행동으로 번역되어야 합니다",
        r"‘\1’ 관련 내용을 확인할 때는 이름보다 초5 수학 수업에서 어떤 학습 행동으로 이어지는지 살펴봐야 합니다",
        value,
    )
    value = value.replace(
        "어떤 좋은 키워드도 학습 개선으로 이어지기 어렵습니다",
        "관리 방식이 구체적이지 않으면 학습 개선으로 이어지기 어렵습니다",
    )
    value = re.sub(
        r"[^.!?]{1,70} 키워드는 수업 품질을 설명하는 시작점일 뿐입니다",
        "해당 표현만으로는 수업 품질을 판단하기 어렵습니다",
        value,
    )
    value = value.replace(
        "이 행에는 수업 학교명이 제공되지 않았습니다",
        "센터 안내에는 수업 가능 학교가 별도로 표시되지 않았습니다",
    )
    value = re.sub(
        r"센터 안내에 표시된 수업 가능 학교가 없는 [^.!?]{1,60} 행은",
        "센터 안내에 수업 가능 학교가 별도로 표시되지 않은 경우에는",
        value,
    )
    value = re.sub(
        r"[가-힣0-9 ]{1,30}(?:초4|초5)\s+(?:영어|수학)학원\s+이 안내에서는",
        "이 안내에서는",
        value,
    )
    value = re.sub(
        r"([^.!?]{1,80})([을를])\s+검토할 때는\s+([^.!?]{2,160}?)(?:을|를)\s+기준으로 상담을 준비할 때는",
        r"\1\2 검토하려면 상담 장소가 \3인지 먼저 확인하고, 준비 단계에서는",
        value,
    )
    value = re.sub(
        r"확인된 상담 주제인\s+([가-힣A-Za-z0-9·]+)도\s+운영 확인 항목",
        r"\1 운영 여부도 확인 항목",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)(?:이|가)\s+상담 주제로 제시되어 있더라도",
        r"\1 관련 안내가 있더라도",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)와 같은 상담 주제가 있더라도",
        r"\1 관련 안내가 있더라도",
        value,
    )
    value = re.sub(
        r"([가-힣A-Za-z0-9·]+)(?:와)? 같은 상담 주제는 광고 문구로 받아들이기보다 관리 체계를 묻는 질문으로 바꾸는 편이 좋습니다",
        r"\1 관련 안내가 있다면 실제 관리 체계와 확인 방법을 구체적으로 물어보는 편이 좋습니다",
        value,
    )
    value = re.sub(r"상담 주제\s+", "", value)
    value = value.replace("안내의 핵심 답변은 명확합니다", "상담에서 먼저 확인할 답은 다음과 같습니다")
    value = re.sub(r"(?<![가-힣A-Za-z0-9])본문(?=(?:은|는|을|를|에|에서|의)\b)", "안내", value)
    value = value.replace("주소 항목에는", "확인된 센터 주소는")
    value = re.sub(r"확인된 센터 주소는 (.+?)가 제공되어 있으니,", r"확인된 센터 주소는 \1이며,", value)
    def school_sentence(match: re.Match[str]) -> str:
        names = match.group(1).strip(" ,·/")
        if names:
            return (
                f"센터 안내에서 확인되는 수업 가능 학교는 {names}입니다. "
                "학교 진도는 학생이 가져온 최신 자료와 함께 확인합니다"
            )
        return "센터 안내에 학교 목록이 따로 표시되지 않아 재학 학교의 최신 진도 자료를 상담 때 직접 확인합니다"

    value = re.sub(
        r"(?:[가-힣]+(?:\s+[가-힣]+){0,3})\s+행에 적힌 수업학교는\s*(.*?)\s*이며,\s*본문에서는 해당 이름을 과도하게 반복하지 않고 필요한 곳에만 반영합니다",
        school_sentence,
        value,
    )
    value = re.sub(r"(?<=[초중고])\s*,\s*(?=(?:처럼|범위의)\b)", " ", value)
    value = value.replace("처럼 확인된 학교 흐름", "처럼 확인 가능한 학교 자료")
    value = value.replace("범위의 학교 정보를", "의 학교 자료를")
    value = value.replace("예를 들어와 같이 자료에 있는 학교명을 상담에 활용하더라도", "재학 학교의 최신 진도 자료를 상담에 활용할 때는")
    value = re.sub(
        r"센터 안내에서 확인되는 수업 가능 학교는\s*[,·/ ]*\s*입니다",
        "센터 안내에 학교 목록이 따로 표시되지 않습니다",
        value,
    )
    value = re.sub(
        r"센터 안내에서 확인되는 수업 가능 학교는\s*[,·/ ]*(?:이므로|이며),?",
        "센터 안내에 학교 목록이 따로 표시되지 않아,",
        value,
    )
    value = re.sub(
        r"(센터 안내에서 확인되는 수업 가능 학교는\s+[^.!?]{1,160}?)[,\s]+이므로,",
        r"\1이며,",
        value,
    )
    value = re.sub(r"(?<=[가-힣])\s*,\s*(?=(?:이므로|이며|입니다|을|를|은|는|이|가|와|과|의|에서|으로|로)\b)", " ", value)
    value = re.sub(
        r"(?<=[초중고])\s*[,·/]\s*(?=(?:을|를|은|는|이|가|와|과|의|에|에서|으로|로|도|만|입니다|이며|이고)\b)",
        "",
        value,
    )
    value = re.sub(r"\s*[·,/]\s*(?=등\b)", " ", value)
    value = re.sub(r"(?:[.!?]\s*)?[,·/ ]+등\s+센터 안내에 표시된 학교명을 볼 때는", " 센터 안내에 학교명이 표시되어 있다면", value)
    value = value.replace("학교에는 등이 포함되어 있으므로", "학교 정보가 따로 표시되지 않은 경우에는")
    value = value.replace("참고 항목 항목", "참고 항목")
    value = re.sub(
        r"[가-힣A-Za-z0-9· ]{1,30}(?:이|가) 참고 항목으로 제시되어 있더라도",
        "참고 항목이 표시되어 있더라도",
        value,
    )
    value = re.sub(r"\s*;\s*", ". ", value)
    value = re.sub(r"합니다,\s*(?=[가-힣])", "합니다. ", value)
    value = re.sub(r"([가-힣]+습니다)\s+(?=이\s+(?:기록|자료|과정|안내))", r"\1. ", value)
    value = normalize_particles(value)
    # 종성 ㄹ 뒤의 방향 조사도 normalize_particles에서 일반 받침으로 처리될 수 있어
    # 최종 공개 문장에서는 표준형을 한 번 더 보장합니다.
    value = value.replace("자기 말으로", "자기 말로")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s+([,.!?])", r"\1", value)
    value = re.sub(r"([.!?]){2,}", r"\1", value)
    value = re.sub(r"([.!?])(?=[가-힣])", r"\1 ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def stable_index(seed: str, namespace: str, size: int) -> int:
    if size <= 0:
        raise ValueError("size must be positive")
    digest = hashlib.sha256(f"{seed}|{namespace}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def row_school_names(row: dict[str, str]) -> list[str]:
    names: list[str] = []
    for field, value in row.items():
        if field.startswith("타깃학교"):
            names.extend(split_school_values(value))
    return list(dict.fromkeys(names))


def direct_center_area(local: str, center: str, address: str) -> bool:
    """센터명·주소에서 동네명이 확인될 때만 해당 동네의 직접 센터로 표현합니다."""
    compact_local = re.sub(r"\s+", "", local)
    root = re.sub(r"(?:동|가|지구|신도시|읍|면|리)$", "", compact_local)
    haystack = re.sub(r"\s+", "", center + " " + address)
    return compact_local in haystack or (len(root) >= 2 and root in haystack)


def normalize_school_delimiters(value: str, school_names: list[str]) -> str:
    """센터 자료에 실제로 있는 학교명 사이의 빠진 쉼표와 중복 표기를 정리합니다."""
    names = sorted(set(school_names), key=len, reverse=True)
    if len(names) < 2:
        return value
    alternation = "|".join(re.escape(name) for name in names)
    sequence = re.compile(
        rf"(?<![가-힣A-Za-z0-9])(?:{alternation})(?:(?:\s*,\s*|\s+)(?:{alternation}))+(?![가-힣A-Za-z0-9])"
    )
    token = re.compile(alternation)

    def replace(match: re.Match[str]) -> str:
        found = list(dict.fromkeys(token.findall(match.group(0))))
        return ", ".join(found)

    return sequence.sub(replace, value)


def editorialize(
    value: str,
    row: dict[str, str],
    *,
    allowed_schools: list[str] | None = None,
    known_schools: set[str] | None = None,
    seed: str = "",
) -> str:
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    local = row.get("근처 수업가능 동네", "").strip()
    original_area = " ".join(x for x in (region, district, local) if x)
    if original_area:
        value = value.replace(original_area, natural_area(row))
    if local:
        value = value.replace(f"{local} 이 안내에서는", "이 안내에서는")
        value = value.replace(f"{local} 이 안내는", "이 안내는")
    if region == "세종" or "세종특별자치시" in row.get("센터 주소", ""):
        value = value.replace("충청 새롬중앙로", "세종특별자치시")
    if allowed_schools is not None and known_schools is not None:
        # 주소와 위치안내의 일부가 학교명과 같아도 지워지지 않도록
        # 학교 필터링 동안 센터의 검증된 사실 문자열을 임시 보호합니다.
        protected: list[tuple[str, str]] = []
        for field in ("센터명", "센터 주소", "위치안내", "교육지원청명칭", "교육지원청 등록번호"):
            fact = row.get(field, "").strip()
            if fact and fact in value:
                token = f"__CENTER_FACT_{len(protected)}__"
                value = value.replace(fact, token)
                protected.append((token, fact))
        value = sanitize_school_references(value, allowed_schools, known_schools)
        for token, fact in protected:
            value = value.replace(token, fact)
        value = repair_school_sentences(value, allowed_schools, seed or local)
    value = clean_text(normalize_school_delimiters(value, allowed_schools or row_school_names(row)))
    return diversify_common_phrases(value, seed) if seed else value


def finish_sentence(value: str) -> str:
    value = clean_text(value)
    return value if not value or value.endswith((".", "?", "!")) else value + "."


def soften_keyword_repetition(value: str, title: str, seed: str, keep: int) -> str:
    """타이틀은 검색 의도를 알릴 만큼만 남기고 나머지는 자연스러운 지칭으로 바꿉니다."""
    matches = list(re.finditer(re.escape(title), value))
    if len(matches) <= keep:
        return value
    if keep <= 1:
        kept = {0}
    else:
        kept = {round(index * (len(matches) - 1) / (keep - 1)) for index in range(keep)}
    label = re.sub(r"학원$", "", re.sub(r"^\S+\s+", "", title)).strip()
    local = title.split()[0]
    alternatives = (
        f"{local} {label} 수업",
        f"{local} 지역 {label} 학습",
        f"{label} 상담",
        f"이 {label} 수업",
        "해당 학습 과정",
    )
    occurrence = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal occurrence
        current = occurrence
        occurrence += 1
        if current in kept:
            return match.group(0)
        return alternatives[stable_index(seed, f"keyword-{current}", len(alternatives))]

    return normalize_particles(re.sub(re.escape(title), replace, value))


def dedupe_sentences(parts: list[str], seen: set[str] | None = None) -> list[str]:
    """한 페이지 안에서 완전히 같은 긴 문장이 되풀이되면 첫 문장만 남깁니다."""
    seen = seen if seen is not None else set()
    result: list[str] = []
    for part in parts:
        sentences = re.split(r"(?<=[.!?])\s+", part.strip())
        kept: list[str] = []
        for sentence in sentences:
            key = re.sub(r"\s+", " ", sentence).strip()
            comparable = re.sub(r"[^가-힣A-Za-z0-9]", "", key)
            if len(comparable) >= 35 and comparable in seen:
                continue
            if len(comparable) >= 35:
                seen.add(comparable)
            if key:
                kept.append(key)
        if kept:
            result.append(" ".join(kept))
    return result


def split_values(value: str) -> list[str]:
    values = [x.strip() for x in re.split(r"[,/\n·]+", value or "") if x.strip()]
    return list(dict.fromkeys(values))


def split_school_values(value: str) -> list[str]:
    """학교 목록의 쉼표·마침표·공백 혼용을 모두 안전하게 분리합니다."""
    values = [
        x.strip()
        for x in re.split(r"[,/\n·.\s]+", value or "")
        if x.strip()
        and x.strip() not in {"초등학교", "중학교", "고등학교"}
        and re.search(r"(?:초등학교|중학교|고등학교|초|중|고)$", x.strip())
    ]
    return list(dict.fromkeys(values))


def target_grade_supported(row: dict[str, str], config: dict[str, str]) -> bool:
    """센터 자료의 학년 목록에 이번 페이지 학년이 실제로 포함되는지 확인합니다."""
    return config["grade_token"] in split_values(row.get(config["grade_field"], ""))


def school_universe(rows: list[dict[str, str]]) -> set[str]:
    names: set[str] = set()
    for row in rows:
        for field, value in row.items():
            if "타깃학교" in field:
                names.update(split_school_values(value))
    return names


@lru_cache(maxsize=4)
def school_reference_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(name) for name in names)
    # 학교명이 일반 단어의 일부로 우연히 등장할 때 삭제되는 일을 막습니다.
    # 뒤에는 실제 학교명 뒤에 붙을 수 있는 조사·서술어만 허용합니다.
    return re.compile(
        rf"(?<![가-힣A-Za-z0-9])(?:{alternatives})"
        rf"(?=$|[^가-힣A-Za-z0-9]|(?:은|는|이|가|을|를|와|과|의|에|에서|으로|로|도|만|처럼|학생|재학생|이며|이고|입니다|이라|이었|였|까지|부터))"
    )


def sanitize_school_references(value: str, allowed: list[str], universe: set[str]) -> str:
    """다른 학년 학교명이 섞인 원고를 해당 행의 검증된 학교 범위로 제한합니다."""
    allowed_set = set(allowed)
    # 입력 원고에서 학교명 끝의 '원고'가 제작 용어로 오인되어 '안내'로
    # 바뀐 경우를 먼저 복원한 뒤, 해당 학년 허용 목록으로 다시 제한합니다.
    for school in universe:
        if school.endswith("원고"):
            value = value.replace(school[:-2] + "안내", school)
    ordered = tuple(sorted(universe, key=lambda name: (-len(name), name)))
    if ordered:
        value = school_reference_pattern(ordered).sub(
            lambda match: match.group(0) if match.group(0) in allowed_set else "",
            value,
        )
    value = re.sub(r"(?:\s*,\s*){2,}", ", ", value)
    value = re.sub(r"(?:\s*[·/]\s*){2,}", " · ", value)
    value = re.sub(r"(?<=\s)[,·/]+|[,·/]+(?=\s*[.!?])", "", value)
    value = re.sub(r"(?<=[초중고])\s*[,·/]\s*(?=(?:을|를|은|는|이|가|와|과|의|에|에서|으로|로|도|만|이며|이고)\b)", "", value)
    return value


def repair_school_sentences(value: str, allowed: list[str], seed: str) -> str:
    """타 학제 학교명 제거 뒤 남는 조사·'등' 잔재를 검증된 학교 문장으로 교체합니다."""
    issue = re.compile(
        r"(?:^|[\s,·/])등(?:을|은|이|에서|으로|\s+센터|\s+수업)"
        r"|학교(?:명|로| 정보인)?.{0,28}등(?:을|은|이|에서|으로|\s)"
        r"|학교 이름을 많이 나열|학교명 외|학교 정보인|없는 행|임의 학교"
        r"|수업학교|행에 적힌|D열|처럼 확인 가능한 학교 자료"
    )
    school_text = "·".join(allowed)
    if school_text:
        replacements = (
            f"센터 안내에서 수업 가능 학교로 확인되는 곳은 {school_text}입니다. 실제 진도는 학생이 가져온 최신 과제와 평가 안내를 기준으로 상담합니다.",
            f"수업 가능 학교 목록은 {school_text}입니다. 학교명만으로 범위를 추정하지 않고 최근 진도 자료를 함께 확인합니다.",
            f"상담 전에 확인할 수업 가능 학교는 {school_text}입니다. 학교별 학습 순서는 최신 학교 자료와 학생의 현재 풀이를 함께 보고 정합니다.",
        )
    else:
        replacements = (
            "센터 안내에 학교 목록이 따로 표시되지 않은 경우에는 재학 학교의 최신 진도표와 과제를 상담 때 직접 확인합니다.",
            "학교 정보가 비어 있다면 상담에서 재학 학교와 최근 진도를 먼저 확인한 뒤 학습 순서를 정합니다.",
            "수업 가능 학교가 별도로 적혀 있지 않은 지역은 최근 학교 과제와 평가 안내를 상담 자료로 사용합니다.",
        )
    parts = re.split(r"(?<=[.!?])(\s+)", value)
    occurrence = 0
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        if issue.search(sentence):
            parts[index] = replacements[stable_index(seed, f"school-repair-{occurrence}", len(replacements))]
            occurrence += 1
    return "".join(parts)


def display_geography(row: dict[str, str]) -> tuple[str, str]:
    """URL 분류용 광역명이 아닌 센터 주소에서 확인되는 실제 시·도를 표시합니다."""
    address = row.get("센터 주소", "").strip()
    if "세종특별자치시" in address:
        return "세종", "세종특별자치시"
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    if address:
        head = address.split()[0]
        aliases = {
            "서울특별시": "서울", "서울시": "서울", "서울": "서울",
            "경기도": "경기", "경기": "경기",
            "인천광역시": "인천", "인천시": "인천", "인천": "인천",
            "충청남도": "충남", "충남": "충남", "충청북도": "충북", "충북": "충북",
            "대전광역시": "대전", "대전시": "대전", "대전": "대전",
            "대구광역시": "대구", "대구시": "대구", "대구": "대구",
            "울산광역시": "울산", "울산시": "울산", "울산": "울산",
            "부산광역시": "부산", "부산시": "부산", "부산": "부산",
            "광주광역시": "광주", "광주시": "광주", "광주": "광주",
            "경상남도": "경남", "경남": "경남", "경상북도": "경북", "경북": "경북",
            "전라남도": "전남", "전남": "전남", "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북",
            "강원특별자치도": "강원", "강원도": "강원", "강원": "강원",
            "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
        }
        region = aliases.get(head, region)
    return region, district


def natural_area(row: dict[str, str]) -> str:
    region, district = display_geography(row)
    local = row.get("근처 수업가능 동네", "").strip()
    local_piece = local
    region_tokens = {region, region.replace("특별자치시", ""), region.replace("광역시", "")}
    district_root = re.sub(r"(?:시|군|구)$", "", district)
    prefixes = {x for x in (*region_tokens, district_root) if len(x) >= 2}
    for prefix in sorted(prefixes, key=len, reverse=True):
        if local_piece.startswith(prefix + " "):
            local_piece = local_piece[len(prefix):].strip()
            break
    if district.startswith(region):
        region = ""
    return " ".join(x for x in (region, district, local_piece) if x)


def diversify_common_phrases(value: str, seed: str) -> str:
    """의미를 바꾸지 않는 안전한 종결 표현만 페이지별로 다르게 다듬습니다."""
    for phrase, variants in PHRASE_VARIANTS.items():
        occurrence = 0

        def replace(_: re.Match[str]) -> str:
            nonlocal occurrence
            chosen = variants[stable_index(seed, f"{phrase}-{occurrence}", len(variants))]
            occurrence += 1
            return chosen

        value = re.sub(re.escape(phrase), replace, value)
    return clean_text(value)


def slug_local(value: str) -> str:
    return re.sub(r"\s+", "", value.strip())


def trim_description(value: str, fallback: str) -> str:
    text = re.sub(r"\s+", " ", clean_text(value)) or fallback
    if len(text) <= 100:
        return text
    clipped = text[:96]
    for stop in (". ", "다. ", "요. "):
        pos = clipped.rfind(stop)
        if pos >= 72:
            return clipped[: pos + len(stop.strip())].strip()
    return clipped.rstrip(" ,·") + "…"


def apply_curriculum_corrections(value: str, category: str) -> str:
    """명확히 다른 학년의 교과 용어만 해당 학년 범위로 바로잡습니다."""
    if category == "초4수학학원":
        value = value.replace("약수와 배수", "곱셈과 나눗셈")
    return value


def conditionalize_unconfirmed_service(value: str) -> str:
    """CSV에서 해당 학년 운영이 확인되지 않은 페이지의 수업 전제 표현을 조건형으로 바꿉니다."""
    replacements = (
        ("학원을 선택한 뒤", "수업 가능 여부를 먼저 확인한 뒤"),
        ("학원 수업에서", "수업 가능 여부를 확인하는 상담에서"),
        ("학원 등록 후", "수업 가능 여부를 확인한 후"),
        ("수업을 시작한 뒤", "수업이 가능하다고 확인된 뒤"),
        ("수업을 시작하면", "수업이 가능하다고 확인되면"),
        ("수업을 시작했다면", "수업이 가능하다고 확인되었다면"),
        ("등록한 뒤", "수업 가능 여부를 확인한 뒤"),
        ("등록했다면", "수업 가능 여부를 확인했다면"),
        (
            "오답 노트가 실제 수업에서 어떻게 활용되는지",
            "수업 가능 여부를 확인한 뒤 오답 노트를 어떻게 활용하는지도",
        ),
        (
            "오답 관리가 실제 수업에서 어떻게 활용되는지",
            "수업 가능 여부를 확인한 뒤 오답 관리를 어떻게 진행하는지도",
        ),
        (
            "그 노트가 실제 수업에서 다시 활용되는지",
            "수업 가능 여부를 확인한 뒤 그 노트를 어떻게 다시 활용하는지도",
        ),
        (
            "오답 관리가 실제 수업에서 어떻게 이루어지는지",
            "수업 가능 여부를 확인한 뒤 오답 관리를 어떻게 진행하는지도",
        ),
    )
    for before, after in replacements:
        value = value.replace(before, after)
    return value


def local_meta_description(
    title: str, region: str, district: str, center: str, config: dict[str, str], supported: bool,
) -> str:
    """검증된 센터 정보만 사용해 70~100자의 검색 요약을 만듭니다."""
    location = district if region and district.startswith(region) else " ".join(value for value in (region, district) if value)
    if not supported:
        return trim_description(
            f"{title}: {location}에서 {config['grade']} {config['subject']} 학원을 비교할 때 볼 진단·학교 진도·오답 기준과 실제 수업 가능 여부 확인 방법을 안내합니다.",
            f"{title} 수업 가능 여부와 학습 기준을 안내합니다.",
        )
    candidates = [
        f"{title}: {location} {center}의 {config['grade']} {config['subject']} 진단·학교 진도·오답 관리 기준을 안내합니다.",
        f"{title}: {center}의 {config['grade']} {config['subject']} 진단·내신·오답 관리 기준을 안내합니다.",
        f"{title}: {location} 지역의 {config['grade']} {config['subject']} 진단·내신·오답 관리 안내입니다.",
    ]
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if 70 <= len(candidate) <= 100:
            return candidate
    result = trim_description(candidates[0], candidates[-1])
    if len(result) < 70:
        result = trim_description(
            result.rstrip(". ") + ". 상담 전 실제 반 편성과 시간표도 함께 확인하세요.",
            candidates[-1],
        )
    return result


def center_entity_id(center: str, address: str, reg_office: str, reg_number: str) -> str:
    """같은 실제 센터가 카테고리마다 다른 엔터티로 쪼개지지 않게 고정 ID를 만듭니다."""
    identity = "|".join(value.strip() for value in (reg_office, reg_number, center, address) if value.strip())
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{BASE_URL}/#center-{digest}"


def center_identity_for_row(row: dict[str, str]) -> str:
    local = row.get("근처 수업가능 동네", "").strip()
    center = row.get("센터명", "").strip() or f"{local} 학습코칭센터"
    return center_entity_id(
        center,
        row.get("센터 주소", "").strip(),
        row.get("교육지원청명칭", "").strip(),
        row.get("교육지원청 등록번호", "").strip(),
    )


def stable_center_areas(rows: list[dict[str, str]], org_id: str) -> list[dict[str, str]]:
    """동일 센터 엔터티에는 어느 페이지에서도 같은 서비스 지역 집합을 제공합니다."""
    names: list[str] = []
    for candidate in rows:
        if center_identity_for_row(candidate) != org_id:
            continue
        display_region, display_district = display_geography(candidate)
        for value in (display_region, display_district, candidate.get("근처 수업가능 동네", "").strip()):
            if value and value not in names:
                names.append(value)
    return [{"@type": "AdministrativeArea", "name": value} for value in names]


def stable_center_topics(row: dict[str, str]) -> list[str]:
    topics = ["학습 진단", "내신 관리", "오답 재학습", "학습 플래너"]
    if row.get("가능학년\n(수학)", "").strip():
        topics.insert(0, "수학")
    if row.get("가능학년\n(영어)", "").strip():
        topics.insert(0, "영어")
    return topics


def absolute(path: str) -> str:
    if re.match(r"^https?://", path, re.I):
        return path
    return BASE_URL + (path if path.startswith("/") else "/" + path)


def parse_sections(raw: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(raw))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections[match.group(1)] = clean_text(raw[match.end():end])
    required = {"페이지타이틀", "메타설명", "본문", "FAQ", "학부모후기", "JSON-LD 요약"}
    missing = required - sections.keys()
    if missing:
        raise ValueError(f"원고 구역 누락: {sorted(missing)}")
    return sections


def decode_zip_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", data, 0, 1, "지원하는 인코딩이 아닙니다")


def load_manuscripts(zip_path: Path, category_label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".txt") or name.endswith("/"):
                continue
            sections = parse_sections(decode_zip_text(archive.read(name)))
            title = sections["페이지타이틀"].strip()
            local = re.sub(rf"\s*{re.escape(category_label)}\s*$", "", title).strip()
            if not local:
                raise ValueError(f"동네명을 찾을 수 없습니다: {name}")
            key = slug_local(local)
            if key in result:
                raise ValueError(f"중복 동네 원고: {local}")
            sections["동네"] = local
            sections["파일"] = name
            result[key] = sections
    return result


def load_centers() -> list[dict[str, str]]:
    with (COMMON / "센터정보 정리.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_body(body: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    chunks = re.split(r"^##\s+", clean_text(body), flags=re.M)
    intro = [p.strip() for p in chunks[0].split("\n\n") if p.strip()]
    sections: list[tuple[str, list[str]]] = []
    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        heading = lines[0].strip().strip("# ")
        paragraphs = [p.strip() for p in "\n".join(lines[1:]).split("\n\n") if p.strip()]
        if heading:
            sections.append((heading, paragraphs))
    return intro, sections


def parse_faq(value: str) -> list[tuple[str, str]]:
    pairs = [(clean_text(q), clean_text(a)) for q, a in FAQ_RE.findall(value)]
    if len(pairs) < 3:
        raise ValueError(f"FAQ를 3개 이상 해석하지 못했습니다: {value[:120]}")
    return pairs


def parse_reviews(value: str) -> list[str]:
    value = clean_text(value)
    numbered = re.findall(r"(?:^|\n)\s*\d+[.)]\s*[“\"]?(.*?)[”\"]?\s*(?=\n\s*\d+[.)]|\Z)", value, re.S)
    paragraphs = numbered or re.split(r"\n\s*\n", value)
    result = []
    for paragraph in paragraphs:
        paragraph = re.sub(
            r"^\s*[-*]?\s*(?:[^\n:]{0,30}\s+)?(?:학부모\s*)?후기\s*예시\s*\d*\s*[:.]?\s*",
            "", paragraph.strip(),
        )
        paragraph = paragraph.strip(" \t\n\r“”\"")
        if not paragraph or re.search(r"아래 내용은|특정 학생의 .*결과", paragraph):
            continue
        result.append(paragraph)
    return result


def rotate_unique(values: list[tuple[str, str]], seed: str, namespace: str, count: int) -> list[tuple[str, str]]:
    if not values:
        return []
    ranked = sorted(
        range(len(values)),
        key=lambda index: hashlib.sha256(f"{seed}|{namespace}|{index}".encode("utf-8")).hexdigest(),
    )
    return [values[index] for index in ranked[: min(count, len(values))]]


def build_page_faqs(
    source: list[tuple[str, str]], row: dict[str, str], config: dict[str, str], title: str, category: str,
    *, supported: bool,
) -> list[tuple[str, str]]:
    """질문과 답이 어긋난 입력은 게시하지 않고 검증된 사실로 답변형 FAQ를 만듭니다."""
    local = row["근처 수업가능 동네"].strip()
    center = row.get("센터명", "").strip() or f"{local} 학습코칭센터"
    address = row.get("센터 주소", "").strip()
    location = row.get("위치안내", "").strip()
    schools = split_school_values(row.get(config["school_field"], ""))
    grade_range = row.get(config["grade_field"], "").strip()
    subject = config["subject"]
    grade = config["grade"]
    seed = f"{category}|{local}|faq"
    profile = LEARNING_PROFILES[category][stable_index(seed, "profile", len(LEARNING_PROFILES[category]))]
    action = LEARNING_ACTIONS[subject][stable_index(seed, "action", len(LEARNING_ACTIONS[subject]))]
    school_text = "·".join(schools)
    error_stages = "계산·개념·조건 해석" if subject == "수학" else "어휘·문법·문장 해석"

    candidates: list[tuple[str, str]] = [
        (
            f"{title} 상담에서는 아이의 어떤 자료를 준비하면 좋을까요?",
            f"최근에 풀었던 {subject} 문제집이나 학교 과제 중 풀이 흔적이 남은 자료 한 가지면 충분합니다. "
            f"정답 개수만 보지 않고 {profile}인지 살핀 뒤 첫 학습 순서를 정하는 데 활용합니다.",
        ),
        (
            f"{local} {grade} {subject} 수업은 선행과 복습 중 무엇을 먼저 보나요?",
            f"현재 단원을 혼자 설명하고 다시 풀 수 있는지를 먼저 확인합니다. 기초가 안정적이면 다음 단원으로 이어가고, "
            f"오답 이유가 반복되면 {action}",
        ),
        (
            f"과제량은 어떤 기준으로 정하는 것이 좋을까요?",
            f"학생이 실제로 사용할 수 있는 요일과 시간을 먼저 확인한 뒤 수업 내용, 오답 재풀이, 다음 수업 준비를 나누어 정하는 편이 좋습니다. "
            f"완료 여부뿐 아니라 막힌 지점이 다음 수업 기록에 이어지는지도 함께 확인하세요.",
        ),
        (
            f"{subject} 오답 관리는 무엇을 확인해야 하나요?",
            f"틀린 문제를 다시 푸는 데서 끝내지 않고 {error_stages} 중 어느 단계에서 막혔는지 기록하는 것이 중요합니다. "
            f"비슷한 문제를 일정 간격 뒤 다시 풀어 같은 이유의 실수가 줄었는지 확인할 수 있어야 합니다.",
        ),
        (
            f"학부모에게 수업 내용은 어떻게 공유하는 것이 좋을까요?",
            f"진도만 전달하기보다 이번 주에 이해한 내용, 남은 오답, 다음 주 우선순위를 구분해 확인하는 방식이 좋습니다. "
            f"상담 때 피드백 주기와 과제 미완료 시의 보완 절차를 함께 물어보세요.",
        ),
        (
            f"{local}에서 수업 시간표를 정할 때 무엇을 고려해야 하나요?",
            f"등원 가능한 요일뿐 아니라 수업 뒤 복습 시간을 확보할 수 있는지도 확인해야 합니다. "
            f"센터 위치는 {address or center}이며, 실제 이동 동선과 상담 가능 시간은 방문 전에 확인하는 편이 좋습니다.",
        ),
        (
            f"첫 상담 뒤에는 어떤 목표를 세우는 것이 현실적인가요?",
            f"처음부터 성적이나 진도를 크게 약속하기보다 2~4주 동안 관찰할 행동을 정하는 것이 좋습니다. "
            f"과제 시작 시간, 오답 재풀이, 질문 기록처럼 확인 가능한 항목을 정하면 다음 상담도 구체적으로 이어집니다.",
        ),
        (
            f"{grade} {subject}에서 학습 우선순위는 어떻게 정하나요?",
            f"학교 진도와 최근 오답을 함께 놓고 가장 자주 막히는 한두 가지부터 정합니다. "
            f"{profile}에는 진도를 넓히기보다 {action}",
        ),
    ]
    if schools:
        candidates.append((
            f"{school_text} 학생도 학교 진도를 반영해 상담할 수 있나요?",
            f"센터 안내에서 수업 가능 학교로 표시된 곳은 {school_text}입니다. 학교 이름만으로 범위를 단정하지 않고, "
            f"학생이 가져온 최근 진도표·과제·평가 안내를 기준으로 {subject} 보완 순서를 상담합니다.",
        ))
    if grade_range:
        candidates.append((
            f"{center}의 {subject} 수업 가능 학년은 어떻게 확인하나요?",
            f"센터 자료에 표시된 {subject} 수업 가능 학년은 {'·'.join(split_values(grade_range))}입니다. 다만 실제 반 편성, 시간표와 학생의 현재 진도는 달라질 수 있으므로 상담 시 함께 확인해야 합니다.",
        ))
    if location:
        candidates.append((
            f"센터 방문 전에 위치를 어떻게 확인하면 좋을까요?",
            f"센터 주소는 {address or '상담 시 안내'}이며 위치 안내는 ‘{location}’입니다. 처음 방문할 때는 건물명과 층, 이동 시간을 미리 확인하면 상담 시간을 여유 있게 잡을 수 있습니다.",
        ))
    if not supported:
        candidates.insert(0, (
            f"{center}에서 {config['grade']} {subject} 수업이 가능한가요?",
            f"센터 자료의 {subject} 가능 학년 목록에는 {config['grade_token']} 표기가 확인되지 않습니다. "
            "이 안내는 학원 선택 기준을 제공하며, 실제 수업 가능 여부와 반 편성은 상담 전에 반드시 확인해야 합니다.",
        ))

    # source는 형식 검증을 위해 전달받지만 질문·답변 의미가 엇갈린 항목이 있어 화면에는 사용하지 않습니다.
    if len(source) < 3:
        raise ValueError(f"FAQ 원문 형식이 부족합니다: {title}")
    result = rotate_unique(candidates, seed, "custom", 4)
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for question, answer in result:
        key = re.sub(r"[^가-힣A-Za-z0-9]", "", question)
        if key not in seen:
            unique.append((clean_text(question), finish_sentence(answer)))
            seen.add(key)
    return unique


def build_consultation_scenarios(
    row: dict[str, str], config: dict[str, str], title: str, category: str,
) -> list[str]:
    """실제 후기처럼 오해되지 않도록 상담에서 다루는 상황을 사실 기반 서술로 만듭니다."""
    local = row["근처 수업가능 동네"].strip()
    schools = split_school_values(row.get(config["school_field"], ""))
    subject = config["subject"]
    grade = config["grade"]
    seed = f"{category}|{local}|scenario"
    profiles = LEARNING_PROFILES[category]
    actions = LEARNING_ACTIONS[subject]
    profile_indexes = []
    for offset in range(3):
        index = stable_index(seed, f"profile-{offset}", len(profiles))
        while index in profile_indexes:
            index = (index + 1) % len(profiles)
        profile_indexes.append(index)
    scenarios = [
        f"{local} 학부모 상담에서는 {profiles[profile_indexes[0]]}에 대한 고민을 먼저 정리할 수 있습니다. "
        f"이때는 진도를 서두르기보다 학생의 최근 풀이를 보고 {actions[stable_index(seed, 'action-0', len(actions))]}",
        f"{grade} {subject} 과제를 꾸준히 했는데도 비슷한 실수가 이어진다면 과제량보다 복습 간격을 확인할 필요가 있습니다. "
        f"상담에서는 {profiles[profile_indexes[1]]}인지 살피고 {actions[stable_index(seed, 'action-1', len(actions))]}",
        f"수업을 결정하기 전에는 학생이 실제로 사용할 수 있는 요일과 혼자 복습할 시간을 함께 계산하는 것이 좋습니다. "
        f"{local} 생활 일정 안에서 {profiles[profile_indexes[2]]}에는 {actions[stable_index(seed, 'action-2', len(actions))]}",
    ]
    if schools:
        index = stable_index(seed, "school-slot", len(scenarios))
        school_text = "·".join(schools)
        scenarios[index] = finish_sentence(scenarios[index])
        scenarios[index] += f" {school_text} 재학생은 최신 학교 진도와 과제 자료를 가져오면 상담 내용을 더 구체화할 수 있습니다."
    return [finish_sentence(scenario) for scenario in scenarios]


def build_context_section(
    row: dict[str, str], config: dict[str, str], title: str, category: str, *, supported: bool,
) -> tuple[str, list[str]]:
    local = row["근처 수업가능 동네"].strip()
    center = row.get("센터명", "").strip() or f"{local} 학습코칭센터"
    address = row.get("센터 주소", "").strip()
    location = row.get("위치안내", "").strip()
    schools = split_school_values(row.get(config["school_field"], ""))
    grade_range = row.get(config["grade_field"], "").strip()
    subject = config["subject"]
    grade = config["grade"]
    seed = f"{category}|{local}|context"
    profile = LEARNING_PROFILES[category][stable_index(seed, "profile", len(LEARNING_PROFILES[category]))]
    action = LEARNING_ACTIONS[subject][stable_index(seed, "action", len(LEARNING_ACTIONS[subject]))]
    direct_area = direct_center_area(local, center, address)
    headings = (
        f"{local} 상담에서 확인할 {grade} {subject} 우선순위",
        f"{local} 학생의 현재 기록으로 시작하는 {subject} 계획",
        f"{grade} {subject} 상담을 구체화하는 세 가지 자료",
        f"{local} 생활 일정과 함께 보는 {subject} 학습 흐름",
    )
    paragraphs = [
        f"{title} 상담에서는 학생을 한 가지 점수로 판단하기보다 최근 풀이, 과제 수행 시간, 다시 풀 수 있는 문제를 함께 봅니다. "
        f"특히 {profile}에는 {action}",
        f"{'상담 장소는' if direct_area else local + ' 학생의 상담 가능 여부는 인근 센터 기준으로 안내하며, 실제 센터 위치는'} "
        f"{center}{'(' + address + ')' if address else ''}입니다. "
        f"{('위치 안내는 ‘' + location.rstrip(' .') + '’입니다. ') if location else ''}실제 등원 요일과 수업 뒤 복습 시간을 함께 정하면 계획을 무리 없이 이어가기 좋습니다.",
    ]
    if schools:
        paragraphs.append(
            f"센터 자료에서 확인되는 수업 가능 학교는 {'·'.join(schools)}입니다. 학교별 범위를 미리 단정하지 않고 최신 진도표와 과제 안내를 상담 자료로 활용합니다."
        )
    else:
        paragraphs.append("수업 가능 학교 정보가 따로 표시되지 않은 경우에는 재학 학교와 최근 진도 자료를 상담 때 직접 확인해 학습 순서를 정합니다.")
    if supported and grade_range:
        paragraphs.append(f"센터 자료에 표시된 {subject} 수업 가능 학년은 {'·'.join(split_values(grade_range))}이며, 실제 반 편성과 시간표는 상담 시 확인합니다.")
    else:
        paragraphs.append(
            f"센터 자료의 {subject} 가능 학년 목록에는 {config['grade_token']} 표기가 확인되지 않습니다. "
            "이 안내는 학습 기준을 비교하기 위한 정보이며 실제 수업 가능 여부는 상담 전에 확인해야 합니다."
        )
    return headings[stable_index(seed, "heading", len(headings))], [finish_sentence(p) for p in paragraphs]


def build_route_sections(
    row: dict[str, str], config: dict[str, str], title: str, category: str, *, supported: bool,
) -> list[tuple[str, list[str]]]:
    """센터 사실과 학생 상황을 조합해 원고 밖의 페이지별 판단 근거를 보강합니다."""
    local = row["근처 수업가능 동네"].strip()
    center = row.get("센터명", "").strip() or f"{local} 학습코칭센터"
    subject = config["subject"]
    grade = config["grade"]
    schools = split_school_values(row.get(config["school_field"], ""))
    seed = f"{category}|{local}|route"
    profiles = LEARNING_PROFILES[category]
    actions = LEARNING_ACTIONS[subject]
    profile_a = profiles[stable_index(seed, "profile-a", len(profiles))]
    profile_b = profiles[stable_index(seed, "profile-b", len(profiles))]
    if profile_b == profile_a:
        profile_b = profiles[(profiles.index(profile_b) + 1) % len(profiles)]
    action_a = actions[stable_index(seed, "action-a", len(actions))]
    action_b = actions[stable_index(seed, "action-b", len(actions))]
    decision_lens = DECISION_LENSES[stable_index(seed, "decision-lens", len(DECISION_LENSES))]
    evidence_check = EVIDENCE_CHECKS[stable_index(seed, "evidence-check", len(EVIDENCE_CHECKS))]
    school_sentence = (
        f"{'·'.join(schools)}처럼 센터 안내에 표시된 학교의 학생은 최근 진도표와 과제 자료를 가져오면 학교별 범위를 추측하지 않고 현재 학습 순서를 정할 수 있습니다."
        if schools else
        "수업 가능 학교 목록이 따로 표시되지 않은 경우에는 재학 학교와 최근 진도 자료를 상담 때 확인해 학습 순서를 정합니다."
    )
    availability = (
        f"{center} 자료에서 {config['grade_token']} {subject} 가능 표기를 확인했습니다. 반 편성·시간표·현재 진도는 상담 시 다시 확인합니다."
        if supported else
        f"{center} 자료의 {subject} 가능 학년 목록에는 {config['grade_token']} 표기가 없습니다. 실제 수업 가능 여부를 확인하기 전에는 개설 수업으로 단정하지 않습니다."
    )
    heading_sets = (
        (f"{local} 학생에게 맞는 첫 점검 순서", f"상담 뒤 2주 동안 확인할 {subject} 기록"),
        (f"{grade} {subject} 계획을 세우기 전 구분할 것", f"{local} 생활 일정에 맞춘 재학습 기준"),
        (f"최근 학습 기록으로 좁히는 {subject} 우선순위", f"다음 상담에서 비교할 실행 기준"),
        (f"{local} {subject} 상담을 준비하는 방법", f"진도보다 먼저 확인할 학습 행동"),
    )
    first_heading, second_heading = heading_sets[stable_index(seed, "headings", len(heading_sets))]
    first = [
        f"{title}을 알아볼 때는 학생이 어느 단원까지 나갔는지만 묻기보다 최근에 막힌 장면을 구분해야 합니다. {profile_a}라면 {action_a}",
        f"{local} 상담에서는 {finish_sentence(decision_lens)} 이 기록을 최근 오답과 연결하면 복습과 다음 진도 중 어느 쪽을 먼저 둘지 더 구체적으로 정할 수 있습니다.",
        f"{school_sentence} {availability}",
    ]
    second = [
        f"첫 상담 뒤에는 과제 시작 시간, 질문 표시, 오답 재풀이 중 한두 가지를 정해 기록하는 편이 좋습니다. {profile_b}에는 {action_b}",
        "다음 상담에서는 계획한 분량 자체보다 어떤 항목이 실행되었고 어디에서 멈췄는지를 비교합니다. 그 기록이 있어야 복습량과 다음 진도를 학생 상황에 맞게 조정할 수 있습니다.",
        f"학습 기록을 비교할 때는 {evidence_check}",
    ]
    return [
        (first_heading, [finish_sentence(p) for p in first]),
        (second_heading, [finish_sentence(p) for p in second]),
    ]


def representative_images() -> list[str]:
    """공통 URL 목록을 사용해 저장소 용량을 늘리지 않고 대표 이미지를 배정합니다."""
    source = (COMMON / "대표 이미지 url.csv").read_text(encoding="utf-8-sig")
    urls = list(dict.fromkeys(re.findall(r'https?://[^"\s<>]+\.(?:jpg|jpeg|png|webp|gif)', source, re.I)))
    if not urls:
        raise FileNotFoundError("대표 이미지 url.csv에서 이미지 URL을 찾지 못했습니다")
    return urls


def pick_representative(images: list[str], local: str, category: str) -> str:
    digest = hashlib.sha256(f"{category}|{local}|6839".encode()).digest()
    index = int.from_bytes(digest[:4], "big") % len(images)
    return images[index]


def find_map(row: dict[str, str]) -> str:
    maps_dir = SITE / "assets" / "maps"
    raw = row.get("동 영어", "").strip()
    candidates = [raw, raw.replace(" ", "-"), raw.replace(" ", ""), raw.replace("_", "-")]
    for base in dict.fromkeys(candidates):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = maps_dir / f"{base}{ext}"
            if candidate.exists():
                return "/assets/maps/" + candidate.name
    raise FileNotFoundError(f"지도 이미지를 찾지 못했습니다: {row.get('근처 수업가능 동네', '')} / {raw}")


def national_local_path(row: dict[str, str]) -> str:
    """기존 URL은 바꾸지 않고 실제 저장된 전국학원 동네 경로를 찾아 연결합니다."""
    region = row.get("지역", "").strip()
    district = row.get("시or구", "").strip()
    local = row.get("근처 수업가능 동네", "").strip()
    direct = SITE / "전국학원" / region / district / local / "index.html"
    if direct.exists():
        return "/" + direct.parent.relative_to(SITE).as_posix() + "/"
    matches = list((SITE / "전국학원" / region).glob(f"*/{local}/index.html"))
    if len(matches) == 1:
        return "/" + matches[0].parent.relative_to(SITE).as_posix() + "/"
    raise FileNotFoundError(f"기존 전국학원 동네 페이지를 찾지 못했습니다: {region}/{district}/{local}")


def fee_link(row: dict[str, str]) -> str:
    value = row.get("센터 교습비", "").strip()
    match = re.search(r"https?://[^\s\"'<>]+", value)
    if not match:
        return ""
    return match.group(0)


def head_html(
    title: str,
    description: str,
    canonical: str,
    image: str,
    graph: list[dict],
    *,
    og_type: str = "article",
) -> str:
    payload = {"@context": "https://schema.org", "@graph": graph}
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} | {SITE_NAME}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:type" content="{esc(og_type)}">
  <meta property="og:title" content="{esc(title)} | {SITE_NAME}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{esc(absolute(image))}">
  <link rel="alternate" type="text/plain" href="{BASE_URL}/llms.txt" title="LLM 안내">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&amp;family=Noto+Serif+KR:wght@500;600;700;800&amp;display=swap" rel="stylesheet">
  <link rel="icon" type="image/png" href="/assets/favicon.png">
  <link rel="apple-touch-icon" href="/assets/favicon.png">
  <link rel="stylesheet" href="/assets/site.css">
  <link rel="stylesheet" href="/assets/subject-academy.css">
  <script type="application/ld+json">{json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>
</head>'''


def nav(active: str) -> str:
    links = [
        ("홈", "/"),
        ("학습코칭", "/학습코칭/"),
        ("학습가이드", "/학습가이드/"),
        ("과목별학원", "/과목별학원/"),
        ("전국학원", "/전국학원/"),
        ("상담문의", "/상담문의/"),
    ]
    items = "\n".join(
        f'        <a{" class=\"active\" aria-current=\"page\"" if name == active else ""} href="{href}">{name}</a>'
        for name, href in links
    )
    return f'''  <a class="skip-link" href="#main">본문 바로가기</a>
  <header class="site-header">
    <nav class="nav" aria-label="주요 메뉴">
      <a class="brand" href="/" aria-label="{SITE_NAME} 홈"><span class="brand-mark">W</span><span>{SITE_NAME}</span></a>
      <div class="nav-links">
{items}
      </div>
      <a class="nav-cta" href="/상담문의/">상담 신청</a>
    </nav>
  </header>'''


def footer() -> str:
    return f'''  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div><strong>{SITE_NAME}</strong><p>학생별 학습관리와 공부습관 코칭 안내 홈페이지</p></div>
      <div class="footer-links"><a href="/">홈</a><a href="/학습코칭/">학습코칭</a><a href="/과목별학원/">과목별학원</a><a href="/전국학원/">전국학원</a><a href="/상담문의/">상담문의</a></div>
    </div>
  </footer>
  <div class="wawa-fixed-fab-container" aria-label="빠른 문의 버튼">
    <a href="tel:{PHONE_DISPLAY}" class="wawa-fab-item fab-call"><span class="fab-icon">📞</span><span class="fab-text">전화문의</span></a>
    <a href="https://blogsms.net/{PHONE_LINK}" target="_blank" rel="noopener noreferrer" class="wawa-fab-item fab-sms"><span class="fab-icon">💬</span><span class="fab-text">문자문의</span></a>
    <a href="https://docs.google.com/forms/d/e/1FAIpQLSdb2oE5Qk5YS0TfYDxyV1w-IOTkhkjOCmmpAKTI9FmqpVj6Yg/viewform" target="_blank" rel="noopener noreferrer" class="wawa-fab-item fab-consult pulse-effect"><span class="fab-icon">📝</span><span class="fab-text">상담신청</span></a>
  </div>'''


def shell(head: str, body: str) -> str:
    rendered = f'''{head}
<body>
{body}
</body>
</html>
'''
    return re.sub(r"[ \t]+(?=\n)", "", rendered)


def body_html(intro: list[str], sections: list[tuple[str, list[str]]]) -> str:
    intro_html = "".join(f"<p>{esc(p)}</p>" for p in intro)
    cards = []
    for index, (heading, paragraphs) in enumerate(sections, 1):
        cards.append(
            f'<article class="subject-copy-card"><span class="subject-copy-index">{index:02d}</span>'
            f'<h2>{esc(heading)}</h2>{"".join(f"<p>{esc(p)}</p>" for p in paragraphs)}</article>'
        )
    return f'<div class="subject-intro">{intro_html}</div><div class="subject-copy-grid">{"".join(cards)}</div>'


def local_page(
    row: dict[str, str], manuscript: dict[str, str], config: dict[str, str], category: str,
    rep_images: list[str], ordered_rows: list[dict[str, str]], known_schools: set[str],
) -> str:
    # 검증된 사실값은 바꾸지 않되, 원천 표의 명백한 맞춤법·띄어쓰기만
    # 페이지 전 영역(본문·FAQ·센터카드·JSON-LD)에 동일하게 정규화합니다.
    row = dict(row)
    row["위치안내"] = clean_text(row.get("위치안내", "").strip())
    local = row["근처 수업가능 동네"].strip()
    slug = slug_local(local)
    title = manuscript["페이지타이틀"].strip()
    path_region = row.get("지역", "").strip()
    path_district = row.get("시or구", "").strip()
    region, district = display_geography(row)
    center = row.get("센터명", "").strip() or f"{local} 학습코칭센터"
    address = row.get("센터 주소", "").strip()
    location = row.get("위치안내", "").strip()
    schools = split_school_values(row.get(config["school_field"], ""))
    grade_range = row.get(config["grade_field"], "").strip()
    supported = target_grade_supported(row, config)
    reg_office = row.get("교육지원청명칭", "").strip()
    reg_number = row.get("교육지원청 등록번호", "").strip()
    description = local_meta_description(title, region, district, center, config, supported)
    page_seed = f"{category}|{local}"
    summary = trim_description(editorialize(
        manuscript["JSON-LD 요약"], row,
        allowed_schools=schools, known_schools=known_schools, seed=page_seed + "|summary-edit",
    ), description)
    summary = apply_curriculum_corrections(summary, category)
    summary = clean_text(soften_keyword_repetition(summary, title, page_seed + "|summary", 1))
    body_source = editorialize(
        manuscript["본문"], row,
        allowed_schools=schools, known_schools=known_schools, seed=page_seed + "|body-edit",
    )
    body_source = apply_curriculum_corrections(body_source, category)
    if not supported:
        body_source = conditionalize_unconfirmed_service(body_source)
    keyword_budget = 4 if category == "초6영어학원" else 5
    body_source = soften_keyword_repetition(body_source, title, page_seed + "|body", keyword_budget)
    body_source = re.sub(rf"{re.escape(local)}에서\s+{re.escape(local)}\s+", f"{local}에서 ", body_source)
    body_source = re.sub(
        rf"{re.escape(local)}의\s+{re.escape(config['grade'])}\s+학생이\s+{re.escape(local)}의\s+{re.escape(config['grade'])}\s+중\s+",
        f"{local}의 {config['grade']} 학생이 ",
        body_source,
    )
    body_source = clean_text(body_source)
    intro, body_sections = parse_body(body_source)
    seen_sentences: set[str] = set()
    intro = dedupe_sentences(intro, seen_sentences)
    body_sections = [
        (heading, dedupe_sentences(paragraphs, seen_sentences))
        for heading, paragraphs in body_sections
    ]
    body_sections = [(heading, paragraphs) for heading, paragraphs in body_sections if paragraphs]
    context_section = build_context_section(row, config, title, category, supported=supported)
    insert_at = 1 + stable_index(page_seed, "context-position", max(1, len(body_sections) - 1))
    body_sections.insert(min(insert_at, len(body_sections)), context_section)
    route_sections = build_route_sections(row, config, title, category, supported=supported)
    for offset, route_section in enumerate(route_sections):
        route_position = 1 + stable_index(page_seed, f"route-position-{offset}", max(1, len(body_sections)))
        body_sections.insert(min(route_position, len(body_sections)), route_section)
    # 원문과 동적 보강 문단을 합친 뒤 한 번 더 교정해야 학교명 뒤 조사와
    # 센터 위치 문장처럼 조합 과정에서 생기는 오류가 최종 HTML에 남지 않습니다.
    intro = [clean_text(paragraph) for paragraph in intro]
    body_sections = [
        (clean_text(heading), [clean_text(paragraph) for paragraph in paragraphs])
        for heading, paragraphs in body_sections
    ]
    source_faqs = parse_faq(editorialize(
        manuscript["FAQ"], row,
        allowed_schools=schools, known_schools=known_schools, seed=page_seed + "|faq-edit",
    ))
    faqs = build_page_faqs(source_faqs, row, config, title, category, supported=supported)
    faqs = [
        (
            question.replace(f"{local}에서 {local}", f"{local}에서"),
            answer.replace(f"{local}에서 {local}", f"{local}에서"),
        )
        for question, answer in faqs
    ]
    # 입력 후기 구역도 파싱해 파일 형식 오류를 잡되, 화면에는 실제 후기처럼 오해되지 않는 상담 상황을 사용합니다.
    parse_reviews(editorialize(
        manuscript["학부모후기"], row,
        allowed_schools=schools, known_schools=known_schools, seed=page_seed + "|scenario-source",
    ))
    reviews = build_consultation_scenarios(row, config, title, category)
    path = f"/과목별학원/{category}/{slug}/"
    canonical = absolute(path)
    rep = pick_representative(rep_images, local, category)
    center_image = "/assets/centers/common/seoul.jpg" if region == "서울" else "/assets/centers/common/local.jpg"
    map_image = find_map(row)
    fee = fee_link(row)

    nearby: list[str] = []
    pools = [
        [r for r in ordered_rows if r.get("지역", "").strip() == path_region and r.get("시or구", "").strip() == path_district],
        [r for r in ordered_rows if r.get("지역", "").strip() == path_region],
        ordered_rows,
    ]
    for pool in pools:
        ranked = sorted(
            pool,
            key=lambda r: hashlib.sha256(f"{local}|{r['근처 수업가능 동네']}|nearby".encode()).hexdigest(),
        )
        for other in ranked:
            other_local = other["근처 수업가능 동네"].strip()
            if other_local != local and other_local not in nearby:
                nearby.append(other_local)
            if len(nearby) == 4:
                break
        if len(nearby) == 4:
            break

    related = [
        (f"{category} 전체 지역", f"/과목별학원/{category}/", "지역별 목록으로 돌아가기"),
        (f"{local} 지역 학원", national_local_path(row), "기존 지역 학습관리 확인"),
    ]
    related.extend(
        (f"{local} {other_config['label']}", f"/과목별학원/{other_category}/{slug}/", "같은 동네 다른 학년·과목")
        for other_category, other_config in CONFIGS.items() if other_category != category
    )
    related.extend(
        (f"{name} {config['label']}", f"/과목별학원/{category}/{slug_local(name)}/", "가까운 지역 안내")
        for name in nearby
    )

    org_id = center_entity_id(center, address, reg_office, reg_number)
    page_id = canonical + "#webpage"
    article_id = canonical + "#article"
    service_id = canonical + "#service"
    faq_id = canonical + "#faq"
    breadcrumb_id = canonical + "#breadcrumb"
    school_items = [
        {"@type": "ListItem", "position": i + 1, "name": school}
        for i, school in enumerate(schools)
    ]
    offer = {
        "@type": "Offer",
        "url": canonical,
        "itemOffered": {
            "@type": "Service",
            "name": f"{title} {'학습 상담' if supported else '수업 가능 여부 상담'}",
            "serviceType": "TutoringService" if supported else "EducationalConsulting",
        },
    }
    organization_offer = {
        "@type": "Offer",
        "url": absolute("/상담문의/"),
        "itemOffered": {
            "@type": "Service",
            "name": "학습 상담",
            "serviceType": "TutoringService",
        },
    }
    postal_address: dict[str, str] = {"@type": "PostalAddress", "addressCountry": "KR"}
    if address:
        postal_address["streetAddress"] = address
    if region:
        postal_address["addressRegion"] = region
    if district:
        postal_address["addressLocality"] = district

    org: dict = {
        "@type": ["EducationalOrganization", "LocalBusiness"],
        "@id": org_id,
        "name": center,
        "alternateName": [SITE_NAME],
        "telephone": PHONE_DISPLAY,
        "image": [absolute(center_image)],
        "address": postal_address,
        "areaServed": stable_center_areas(ordered_rows, org_id),
        "knowsAbout": stable_center_topics(row),
        "makesOffer": [organization_offer],
    }
    if reg_office or reg_number:
        org["identifier"] = " · ".join(x for x in (reg_office, reg_number) if x)

    graph = [
        {
            "@type": "WebPage", "@id": page_id, "url": canonical, "name": title,
            "description": description, "inLanguage": "ko-KR", "about": {"@id": org_id},
            "mentions": [config["grade"], config["subject"], local, *schools],
            "primaryImageOfPage": {"@type": "ImageObject", "url": absolute(rep)},
            "breadcrumb": {"@id": breadcrumb_id},
            "mainEntity": {"@id": article_id},
            "hasPart": [{"@id": article_id}, {"@id": service_id}, {"@id": faq_id}],
        },
        {"@type": "ImageObject", "@id": canonical + "#primaryimage", "url": absolute(rep), "caption": f"{title} {SITE_NAME} 대표"},
        {
            "@type": "BreadcrumbList", "@id": breadcrumb_id,
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": BASE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "과목별학원", "item": absolute("/과목별학원/")},
                {"@type": "ListItem", "position": 3, "name": config["label"], "item": absolute(f"/과목별학원/{category}/")},
                {"@type": "ListItem", "position": 4, "name": title, "item": canonical},
            ],
        },
        org,
        {
            "@type": "Article", "@id": article_id, "mainEntityOfPage": {"@id": page_id},
            "headline": title, "name": title, "description": summary,
            "image": [absolute(rep), absolute(center_image), absolute(map_image)],
            "datePublished": PUBLISH_DATE, "dateModified": MODIFIED_DATE,
            "author": {"@id": org_id}, "publisher": {"@id": org_id}, "inLanguage": "ko-KR",
            "articleSection": [heading for heading, _ in body_sections],
            "about": [title, config["grade"], config["subject"], "학습 진단", "오답 관리"],
            "mentions": [local, district, region, *schools],
        },
        {
            "@type": "Service", "@id": service_id,
            "name": f"{title} {'학습관리' if supported else '학습 선택 상담'}",
            "serviceType": "TutoringService" if supported else "EducationalConsulting", "provider": {"@id": org_id},
            "description": summary, "areaServed": {"@type": "Place", "name": local},
            "audience": {"@type": "EducationalAudience", "educationalRole": "student", "audienceType": config["grade"]},
            "about": [config["subject"], "내신 대비", "개념 점검"],
            "mentions": ["학습 플래너", "오답 재학습", *schools], "offers": [offer],
        },
        {
            "@type": "FAQPage", "@id": faq_id,
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs],
        },
        {
            "@type": "ItemList", "@id": canonical + "#related", "name": f"{local} 관련 학원 페이지",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": name, "url": absolute(url)} for i, (name, url, _) in enumerate(related)],
        },
    ]
    if school_items:
        graph.insert(-1, {
            "@type": "ItemList", "@id": canonical + "#schools", "name": f"{local} 수업 가능 학교 참고",
            "numberOfItems": len(school_items), "itemListElement": school_items,
        })

    school_html = "".join(f"<li>{esc(school)}</li>" for school in schools) or "<li>상담 시 재학 학교와 진도를 확인합니다.</li>"
    fee_html = f'<a class="btn btn-ghost" href="{esc(fee)}" target="_blank" rel="noopener">센터 교습비 확인</a>' if fee else ""
    faq_html = "".join(f'<details class="faq-item"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faqs)
    review_html = "".join(f'<article class="review-card"><span class="review-label">상담 상황 {i}</span><p>{esc(review)}</p></article>' for i, review in enumerate(reviews, 1))
    link_html = "".join(f'<a class="subject-related-link" href="{url}"><strong>{esc(name)}</strong><small>{esc(note)}</small></a>' for name, url, note in related)
    registration = " · ".join(x for x in (reg_office, reg_number) if x)
    visible_description = description.removeprefix(f"{title}: ").strip()
    service_area_notice = ""
    if not direct_center_area(local, center, address):
        service_area_notice = (
            f'<p class="subject-service-area-notice">{esc(local)} 학생의 상담 가능 여부는 인근 센터 기준으로 안내합니다. '
            f'실제 센터 위치는 아래 주소에서 확인해 주세요.</p>'
        )
    availability_notice = (
        f'<p class="subject-availability is-confirmed"><strong>{esc(config["grade_token"])} {esc(config["subject"])} 가능 학년 표기 확인</strong>'
        '<span>반 편성과 시간표, 학생의 현재 진도는 상담에서 다시 확인합니다.</span></p>'
        if supported else
        f'<p class="subject-availability is-check"><strong>{esc(config["grade_token"])} {esc(config["subject"])} 수업 가능 여부 확인 필요</strong>'
        '<span>센터 자료의 가능 학년 목록에 해당 학년 표기가 없어 개설 수업으로 단정하지 않습니다.</span></p>'
    )

    body = f'''{nav("과목별학원")}
  <main>
    <section class="page-hero subject-local-hero">
      <nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span aria-hidden="true">/</span><a href="/과목별학원/">과목별학원</a><span aria-hidden="true">/</span><a href="/과목별학원/{category}/">{esc(config['label'])}</a><span aria-hidden="true">/</span><span aria-current="page">{esc(title)}</span></nav>
      <p class="eyebrow">LOCAL SUBJECT ACADEMY</p>
      <h1>{esc(title)}</h1>
      <p class="lead">{esc(description)}</p>
      <div class="hero-actions"><a class="btn btn-primary" href="tel:{PHONE_DISPLAY}">{'학습 상담하기' if supported else '수업 가능 여부 확인'}</a>{fee_html}</div>
    </section>

    <section class="section subject-media-section" aria-label="{esc(title)} 이미지 안내">
      <img class="subject-hidden-representative" src="{esc(rep)}" alt="{esc(title)} {SITE_NAME} 대표" style="display:none;">
      <div class="media-row">
        <figure class="frame"><img src="{center_image}" alt="{esc(title)} {SITE_NAME} 본문" width="1200" height="900" fetchpriority="high"><figcaption>{esc(local)} 학습관리 안내</figcaption></figure>
        <figure class="frame"><img src="{map_image}" alt="{esc(title)} {SITE_NAME} 지도" width="1200" height="900" loading="lazy"><figcaption>{esc(center)} 위치 안내</figcaption></figure>
      </div>
    </section>

    <section class="section subject-answer-summary">
      <div class="section-head"><p class="eyebrow">핵심 답변</p><h2>{esc(local)}에서 {esc(config['grade'])} {esc(config['subject'])} 학원을 찾을 때 무엇부터 확인해야 할까요?</h2><p class="lead">{esc(visible_description)}</p></div>
      {availability_notice}
      <div class="subject-fact-grid">
        <article><span>대상</span><strong>{esc(config['grade'])}</strong><p>{esc(('가능 학년 ' + '·'.join(split_values(grade_range))) if supported and grade_range else '실제 수업 가능 여부 상담 확인')}</p></article>
        <article><span>과목</span><strong>{esc(config['subject'])}</strong><p>개념·내신·오답 흐름 점검</p></article>
        <article><span>지역</span><strong>{esc(local)}</strong><p>{esc(' · '.join(x for x in (region, district) if x))}</p></article>
      </div>
    </section>

    <section class="section subject-manuscript">
      <div class="section-head"><p class="eyebrow">학습 안내</p><h2>{esc(local)} {esc(config['grade'])} {esc(config['subject'])} 학습 설계</h2></div>
      {body_html(intro, body_sections)}
    </section>

    <section class="section subject-center-card">
      <div class="section-head"><p class="eyebrow">센터 정보</p><h2>{esc(center)}</h2><p class="lead">센터의 주소·위치·수업 가능 학교를 상담 전에 확인할 수 있도록 정리했습니다.</p></div>
      {service_area_notice}
      <dl class="subject-center-facts">
        <div><dt>주소</dt><dd>{esc(address or '상담 시 안내')}</dd></div>
        <div><dt>위치 안내</dt><dd>{esc(location or '상담 시 상세 안내')}</dd></div>
        <div><dt>학교 참고</dt><dd><ul>{school_html}</ul><small>학교별 범위와 실제 수업 가능 여부는 최신 자료로 확인합니다.</small></dd></div>
        <div><dt>등록 정보</dt><dd>{esc(registration or '센터별 등록 정보는 상담 시 확인')}</dd></div>
      </dl>
      {fee_html}
    </section>

    <section class="section">
      <div class="section-head"><p class="eyebrow">FAQ</p><h2>{esc(local)} {esc(config['grade'])} {esc(config['subject'])} 자주 묻는 질문</h2><p class="lead">상담 전에 자주 확인하는 내용을 학년과 과목 기준으로 정리했습니다.</p></div>
      <div class="faq-list">{faq_html}</div>
    </section>

    <section class="section">
      <div class="section-head"><p class="eyebrow">상담 상황 예시</p><h2>{esc(local)} 학부모 상담에서 확인할 학습 장면</h2><p class="lead">실제 이용 후기나 성과 사례가 아니라, 상담에서 다룰 수 있는 대표적인 학습 상황을 재구성한 예시입니다.</p></div>
      <div class="review-grid subject-review-grid">{review_html}</div>
    </section>

    <section class="section">
      <div class="section-head"><p class="eyebrow">내부 안내</p><h2>{esc(local)}에서 함께 확인할 페이지</h2></div>
      <div class="subject-related-grid">{link_html}</div>
    </section>
  </main>
{footer()}'''
    return shell(head_html(title, description, canonical, rep, graph), body)


def region_directory(rows: list[dict[str, str]], category: str, config: dict[str, str]) -> str:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row.get("지역", "기타").strip() or "기타"][row.get("시or구", "기타").strip() or "기타"].append(row)
    jump = "".join(f'<a href="#region-{i}">{esc(region)}</a>' for i, region in enumerate(grouped))
    blocks = []
    for region_index, (region, districts) in enumerate(grouped.items()):
        district_html = []
        for district, district_rows in districts.items():
            links = "".join(
                f'<a href="/과목별학원/{category}/{slug_local(r["근처 수업가능 동네"])}/"><strong>{esc(r["근처 수업가능 동네"])}</strong><small>{esc(config["label"])}</small></a>'
                for r in district_rows
            )
            district_html.append(f'<section class="subject-district"><h3>{esc(district)} <small>{len(district_rows)}곳</small></h3><div class="subject-local-grid">{links}</div></section>')
        blocks.append(f'<section class="region-block" id="region-{region_index}"><div class="region-title"><h2>{esc(region)}</h2><span>{sum(len(v) for v in districts.values())}개 지역</span></div>{"".join(district_html)}</section>')
    return f'<nav class="region-jump" aria-label="광역 지역 바로가기">{jump}</nav>{"".join(blocks)}'


def category_page(rows: list[dict[str, str]], category: str, config: dict[str, str]) -> None:
    path = f"/과목별학원/{category}/"
    canonical = absolute(path)
    title = config["label"]
    description = f"전국 371개 동네의 {title} 학습 안내를 지역별로 정리했습니다. {config['grade']} {config['subject']} 진단, 내신 관리, 오답 재학습 기준을 확인할 수 있습니다."
    item_list = [
        {"@type": "ListItem", "position": i + 1, "name": f"{r['근처 수업가능 동네']} {title}", "url": absolute(f"{path}{slug_local(r['근처 수업가능 동네'])}/")}
        for i, r in enumerate(rows)
    ]
    graph = [
        {"@type": "CollectionPage", "@id": canonical + "#webpage", "url": canonical, "name": title, "description": description, "inLanguage": "ko-KR", "hasPart": {"@id": canonical + "#regions"}},
        {"@type": "BreadcrumbList", "@id": canonical + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "과목별학원", "item": absolute("/과목별학원/")},
            {"@type": "ListItem", "position": 3, "name": title, "item": canonical},
        ]},
        {"@type": "ItemList", "@id": canonical + "#regions", "name": f"{title} 지역 목록", "numberOfItems": len(item_list), "itemListElement": item_list},
    ]
    body = f'''{nav("과목별학원")}
  <main>
    <section class="page-hero">
      <nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span aria-hidden="true">/</span><a href="/과목별학원/">과목별학원</a><span aria-hidden="true">/</span><span aria-current="page">{esc(title)}</span></nav>
      <p class="eyebrow">SUBJECT ACADEMY DIRECTORY</p><h1>{esc(title)}</h1><p class="lead">{esc(description)}</p>
      <div class="subject-count"><strong>{len(rows)}</strong><span>지역별 학습 안내</span></div>
    </section>
    <section class="section subject-directory"><div class="section-head"><p class="eyebrow">지역 찾기</p><h2>광역 지역과 시·군·구 순서로 찾기</h2><p class="lead">먼저 광역 지역을 고른 뒤 시·군·구별 동네 버튼을 확인할 수 있습니다.</p></div>{region_directory(rows, category, config)}</section>
  </main>
{footer()}'''
    out = SITE / "과목별학원" / category / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        shell(
            head_html(
                title,
                description,
                canonical,
                "/assets/title.png",
                graph,
                og_type="website",
            ),
            body,
        ),
        encoding="utf-8",
    )


def subject_root() -> None:
    category_dirs = sorted(p for p in (SITE / "과목별학원").iterdir() if p.is_dir() and (p / "index.html").exists())
    categories = [p.name for p in category_dirs]
    cards = "".join(
        f'<a class="subject-category-card" href="/과목별학원/{name}/"><span>{i:02d}</span><strong>{esc(CONFIGS.get(name, {}).get("label", name))}</strong><small>371개 지역별 안내 보기</small></a>'
        for i, name in enumerate(categories, 1)
    )
    canonical = absolute("/과목별학원/")
    description = "학년과 과목 기준으로 전국 371개 지역의 학습 안내를 찾는 전국학원 과목별학원 허브입니다. 학생 상황에 맞는 진단·내신·오답 관리 기준을 확인하세요."
    graph = [
        {"@type": "CollectionPage", "@id": canonical + "#webpage", "url": canonical, "name": "과목별학원", "description": description, "inLanguage": "ko-KR", "hasPart": {"@id": canonical + "#categories"}},
        {"@type": "BreadcrumbList", "@id": canonical + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": BASE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "과목별학원", "item": canonical},
        ]},
        {"@type": "ItemList", "@id": canonical + "#categories", "name": "과목별학원 카테고리", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": CONFIGS.get(name, {}).get("label", name), "url": absolute(f"/과목별학원/{name}/")}
            for i, name in enumerate(categories)
        ]},
    ]
    body = f'''{nav("과목별학원")}
  <main>
    <section class="page-hero"><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span aria-hidden="true">/</span><span aria-current="page">과목별학원</span></nav><p class="eyebrow">SUBJECT ACADEMY HUB</p><h1>과목별학원</h1><p class="lead">{esc(description)}</p></section>
    <section class="section"><div class="section-head"><p class="eyebrow">학년·과목 선택</p><h2>필요한 학습 안내부터 확인하세요</h2><p class="lead">학년과 과목을 선택한 뒤, 광역 지역과 시·군·구 순서로 가까운 동네의 학습 안내를 찾을 수 있습니다.</p></div><div class="subject-category-grid">{cards}</div></section>
    <section class="section"><div class="section-head"><p class="eyebrow">전국학원 관리 기준</p><h2>과목 이름보다 학생이 막힌 지점을 먼저 봅니다</h2></div><div class="card-grid"><article class="info-card"><span class="tag">01</span><h3>현재 상태 진단</h3><p>최근 시험과 오답에서 개념, 계산, 적용 중 어디에서 흐름이 끊기는지 확인합니다.</p></article><article class="info-card"><span class="tag">02</span><h3>학년별 우선순위</h3><p>학교 진도와 시험 일정을 함께 보고 복습과 내신 준비의 순서를 정합니다.</p></article><article class="info-card"><span class="tag">03</span><h3>기록 기반 재학습</h3><p>틀린 이유와 다시 풀 시점을 기록해 같은 실수가 반복되지 않도록 관리합니다.</p></article></div></section>
  </main>
{footer()}'''
    out = SITE / "과목별학원" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        shell(
            head_html(
                "과목별학원",
                description,
                canonical,
                "/assets/title.png",
                graph,
                og_type="website",
            ),
            body,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="중1수학학원", choices=sorted(CONFIGS))
    args = parser.parse_args()
    category = args.category
    config = CONFIGS[category]
    zip_path = USED_DRAFTS / config["zip"]
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    rows = load_centers()
    manuscripts = load_manuscripts(zip_path, config["label"])
    row_keys = {slug_local(row["근처 수업가능 동네"]): row for row in rows}
    missing_drafts = sorted(set(row_keys) - set(manuscripts))
    unknown_drafts = sorted(set(manuscripts) - set(row_keys))
    if missing_drafts or unknown_drafts:
        raise RuntimeError(f"센터/원고 불일치 missing={missing_drafts[:8]} unknown={unknown_drafts[:8]}")
    if len(rows) != 371 or len(manuscripts) != 371:
        raise RuntimeError(f"371개가 아닙니다: centers={len(rows)} drafts={len(manuscripts)}")
    reps = representative_images()
    known_schools = school_universe(rows)
    category_page(rows, category, config)
    for row in rows:
        slug = slug_local(row["근처 수업가능 동네"])
        out = SITE / "과목별학원" / category / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(local_page(row, manuscripts[slug], config, category, reps, rows, known_schools), encoding="utf-8")
    subject_root()
    print(f"generated category={category} local_pages={len(rows)} source={zip_path.name}")


if __name__ == "__main__":
    main()
