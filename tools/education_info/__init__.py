"""Original educational articles adapted from the owner's 30 selected topics."""

def article(number, slug, title, description, category, audience, intro, sections, example, checks, faq, sources, related):
    return dict(number=number, slug=slug, title=title, description=description,
                category=category, audience=audience, intro=intro, sections=sections,
                example=example, checks=checks, faq=faq, sources=sources, related=related)

CATEGORIES = {'exam':'시험 준비', 'subject':'과목별 공부', 'plan':'계획과 습관', 'support':'학생·학부모 도움'}
SOURCES = {
 'study':('IES · 학습과 수업을 구성하는 방법','https://ies.ed.gov/ncee/wwc/PracticeGuide/1','간격을 둔 복습과 기억에서 꺼내 보는 연습을 다룬 교육 연구 안내입니다.'),
 'meta':('EEF · 메타인지와 자기조절학습','https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition','계획·점검·평가를 실제 과목 학습에 연결하는 방법을 다룹니다.'),
 'styles':('EEF · 학습 유형에 관한 근거 검토','https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/learning-styles','고정된 학습 유형에 맞춰 가르치는 접근의 근거가 충분하지 않음을 설명합니다.'),
 'stress':('NHS · 자녀의 시험 스트레스 돕기','https://www.nhs.uk/mental-health/children-and-young-adults/advice-for-parents/help-your-child-beat-exam-stress/','시험을 앞둔 자녀의 긴장과 일상생활을 돕는 보호자 안내입니다.'),
 'digital':('EEF · 디지털 기술과 학습','https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/digital','도구의 기능보다 수업과 연습의 목적을 먼저 살펴봅니다.'),
 'parents':('EEF · 학부모와 함께 학습 지원하기','https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/supporting-parents','학교와 가정이 학생의 학습을 함께 지원하는 방법을 다룹니다.'),
 'science':('EEF · 중등 과학 학습 지원','https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/science-ks3-ks4','중등 과학의 개념 이해와 수업을 지원하는 교육 자료입니다.'),
 'math':('IES · 수학 문제 해결 지도','https://ies.ed.gov/ncee/wwc/PracticeGuide/16','문제의 표현과 풀이 과정 점검을 다룹니다. 대상은 미국 4~8학년입니다.'),
 'feedback':('EEF · 학습에 도움이 되는 피드백','https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/feedback','설명을 전달하는 방식보다 학생의 이해와 다음 학습을 살펴봅니다.'),
 'school':('학교알리미 · 항목별 공시정보','https://www.schoolinfo.go.kr/ei/ss/pneiss_a05_s1.do','학교·연도를 선택해 교과별 교수·학습 및 평가계획 공시항목을 찾아볼 수 있습니다.'),
 'english':('British Council · 영어 현재시제','https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/present-simple','현재시제의 주어와 동사, 의문문·부정문 구조를 확인하는 자료입니다.'),
}
