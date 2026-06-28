from client import LlamaAPIClient

class NCSGenerator:
    """
    NCS (National Competency Standards) Content Generator using Llama.cpp.
    """
    def __init__(self, client: LlamaAPIClient):
        self.client = client

    def generate_ksa_stream(self, job_name: str, additional_info: str = ""):
        """
        NCS 직무(세분류)의 지식(Knowledge), 기술(Skills), 태도(Attitudes)를 공공기관 가이드라인에 맞춘 문체로 스트리밍 생성합니다.
        """
        system_prompt = (
            "당신은 대한민국 산업인력공단(HRDK) 소속의 NCS(국가직무능력표준) 개발 위원회 위원이자 연구원입니다. "
            "국가 표준 직무 정의 양식에 맞추어 전문적이고 명확하며 엄격한 공적 양식의 한국어 문체로 작성하십시오.\n\n"
            "지식(K), 기술(S), 태도(A)의 집필 스타일 규칙:\n"
            "- 지식(Knowledge): 반드시 명사구 또는 '~에 관한 지식', '~에 대한 이해'로 끝나야 합니다.\n"
            "- 기술(Skills): 반드시 '~하는 기술', '~할 수 있는 능력', '~ 기법 활용 능력' 등 구체적인 실무 역량으로 끝나야 합니다.\n"
            "- 태도(Attitudes): 반드시 '~하려는 의지', '~준수 태도', '~적극적 자세', '~세심함' 등으로 서술해야 합니다.\n"
            "- 절대로 주석, 머리말/꼬리말, 서론/결론, 또는 프롬프트 지시 내용을 본문에 출력하지 마십시오."
        )

        user_prompt = f"""[대상 NCS 직무명 (세분류)]
{job_name}

[추가 개발 지시사항 및 참고 조건]
{additional_info or "없음"}

위 직무에 적합한 NCS '지식(K)', '기술(S)', '태도(A)' 목록을 다음 구조로 구체적이고 체계적으로 정의해 주세요.
반드시 각 항목당 최소 5개 이상의 구체적인 항목을 도출해야 합니다.

### 1. 지식 (Knowledge - K)
* (여기에 구체적이고 명확한 직무 지식 나열, 예: "~ 설계에 관한 지식", "~ 알고리즘에 대한 이해")

### 2. 기술 (Skills - S)
* (여기에 구체적이고 측정 가능한 실무 기술 나열, 예: "~ 도구를 활용하는 기술", "~ 모형을 분석할 수 있는 능력")

### 3. 태도 (Attitudes - A)
* (여기에 직무 수행 시 필요한 전문가적 자세와 태도 나열, 예: "~ 규정을 준수하려는 태도", "~ 문제를 적극적으로 해결하려는 의지")
"""
        return self.client.stream_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

    def generate_range_of_variables_stream(self, job_name: str, additional_info: str = ""):
        """
        NCS 적용범위 및 작업상황(Range of Variables)을 공공기관 표준 서식에 맞춰 스트리밍 생성합니다.
        """
        system_prompt = (
            "당신은 대한민국 국가직무능력표준(NCS) 개발 및 표준화 마스터 연구원입니다. "
            "직무 수행 시 적용되는 한계 및 범위, 필요한 장비, 도구, 관련 법령 및 문서를 체계적인 규격 양식으로 기술해야 합니다.\n"
            "- 어조는 정중하고 건조하며 명확한 공공 표준 문서 양식입니다.\n"
            "- 주석이나 프롬프트 설명 글은 출력하지 마십시오."
        )

        user_prompt = f"""[대상 NCS 직무명 (세분류)]
{job_name}

[추가 개발 지시사항 및 참고 조건]
{additional_info or "없음"}

위 직무에 대한 NCS '적용범위 및 작업상황(Range of Variables)'을 아래 4가지 핵심 항목으로 나누어 체계적으로 나열해 주세요.

### 1. 적용 범위 (Range of Variables)
* (이 직무가 적용되는 주요 범위 및 분야, 업무 환경을 정의)

### 2. 작업 상황 및 환경 (Work Contexts)
* (업무를 수행할 때 마주하게 되는 구체적인 작업 상황 및 조건 예시)

### 3. 필수 장비 및 도구 (Equipment & Tools)
* (하드웨어, 소프트웨어, 분석 도구 등 직무 수행에 꼭 필요한 도구 목록)

### 4. 관련 법령, 규정 및 자료 (Relevant Documents & Regulations)
* (참고해야 할 표준 운영 절차(SOP), 기술 표준 문서, 관련 법률 등)
"""
        return self.client.stream_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

    def generate_assessment_guidelines_stream(self, job_name: str, additional_info: str = ""):
        """
        NCS 평가방법 및 지침(Assessment Guidelines)을 공공기관 표준 서식에 맞춰 스트리밍 생성합니다.
        """
        system_prompt = (
            "당신은 NCS(국가직무능력표준) 검증 및 산업계 평가 가이드라인 설계 연구원입니다. "
            "특정 직무 수행자의 능력을 합리적이고 객관적으로 평가하기 위한 방법과 기준을 제시하십시오.\n"
            "- 어조는 문장형 종결어미 '~한다' 또는 개조식 표현으로 통일해야 합니다.\n"
            "- 주석이나 프롬프트 설명 글은 배제하고 순수한 항목 및 세부 설명만 출력하십시오."
        )

        user_prompt = f"""[대상 NCS 직무명 (세분류)]
{job_name}

[추가 개발 지시사항 및 참고 조건]
{additional_info or "없음"}

위 직무의 능력 검증을 위한 NCS '평가방법 및 지침(Assessment Guidelines)'을 다음 분류 양식에 맞추어 작성해 주세요.

### 1. 포트폴리오 및 결과물 평가 (Portfolio Review)
* (피평가자가 제출할 실제 산출물의 검증 기준 및 내용)

### 2. 작업장 평가 및 관찰법 (Workplace Observation)
* (실무 환경에서 행동 지표를 평가자가 직접 관찰하여 채점하는 기준)

### 3. 서면 시험 및 구술 시험 (Written & Oral Assessment)
* (핵심 이론 지식 및 상황 판단 능력을 검증하기 위한 문제 출제 가이드라인)

### 4. 평가 시 주의사항 및 환경 조건 (Key Assessment Considerations)
* (공정한 평가를 위해 평가자가 반드시 사전에 인지하고 조율해야 할 제약 및 안전 수칙)
"""
        return self.client.stream_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )
