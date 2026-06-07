from client import LlamaAPIClient

class MultiPOVSynthesizer:
    """
    2-Step Pipeline: Multi-POV Synthesizer
    Step 1: Generate individual POV for characters.
    Step 2: Merge into a fast-paced 3rd-person omniscient view.
    """
    def __init__(self, client: LlamaAPIClient):
        self.client = client

    def generate_individual_pov(self, context: str, character_name: str, scene_instruction: str, system_prompt: str = None, positive: str = None, negative: str = None) -> str:
        sys_prompt = system_prompt if system_prompt else (
            "당신은 메소드 연기자입니다. 주어진 장면에서 해당 인물의 내면 독백과 신체적 반응을 한국어로 작성하세요. "
            "불필요한 설명이나 지시문 없이 순수한 소설 본문만 출력하세요."
        )
        
        user_prompt = f"{context}\n\n[씬 지시사항]\n{scene_instruction}\n\n{character_name}의 시점에서 서술하세요."
        if positive:
            user_prompt += f"\n\n[문체 지시 (적용)]\n{positive}"
        if negative:
            user_prompt += f"\n\n[문체 지시 (금지)]\n{negative}"
            
        result = self.client.send_chat_completion(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.8
        )
        return result if isinstance(result, str) else str(result)

    def synthesize_to_omniscient(self, context: str, pov_texts: dict[str, str], system_prompt: str = None, positive: str = None, negative: str = None) -> str:
        sys_prompt = system_prompt if system_prompt else (
            "당신은 빠른 전개와 밀도 있는 문장을 구사하는 3인칭 전지적 시점의 마스터 소설가입니다. "
            "제시된 다수 인물의 시점과 심리, 그리고 관능적 장치들을 유기적으로 통합하여, "
            "단순한 행위의 나열이 아닌 마스터피스 형태로 집필하세요. "
            "절대 프롬프트, 설명, 지시문, 주석은 출력하지 마세요. 순수한 소설 본문만 출력하세요."
        )
        
        pov_combined = ""
        for char, text in pov_texts.items():
            pov_combined += f"[{char}의 행동/심리]\n{text}\n\n"
            
        user_prompt = f"{context}\n\n[등장인물별 개별 시점]\n{pov_combined}\n위 시점들을 통합하여 하나의 완성된 소설 씬으로 작성하세요."
        if positive:
            user_prompt += f"\n\n[문체 지시 (적용)]\n{positive}"
        if negative:
            user_prompt += f"\n\n[문체 지시 (금지)]\n{negative}"
            
        result = self.client.send_chat_completion(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.6
        )
        return result if isinstance(result, str) else str(result)

    def run_pipeline(self, context: str, scene_instruction: str, characters: list[str], system_prompt: str = None, positive: str = None, negative: str = None) -> str:
        pov_texts = {}
        for char in characters:
            pov = self.generate_individual_pov(context, char, scene_instruction, system_prompt, positive, negative)
            pov_texts[char] = pov
        
        final_scene = self.synthesize_to_omniscient(context, pov_texts, system_prompt, positive, negative)
        return final_scene

    def run_pipeline_streaming(self, context: str, scene_instruction: str, characters: list[str], system_prompt: str = None, positive: str = None, negative: str = None):
        """
        스트리밍 파이프라인: 
        Step 1 - 각 인물 POV 병렬 생성 (진행 상황 표시)
        Step 2 - 통합 씬을 실시간 스트리밍
        """
        import concurrent.futures
        pov_texts = {}
        
        # Step 1: 각 인물별 POV 병렬 생성 (진행 표시)
        if characters:
            yield "status", f"⏳ 선택된 {len(characters)}명 인물의 시점(POV) 분석 시작 (병렬 처리 중)..."
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(characters)) as executor:
                future_to_char = {
                    executor.submit(
                        self.generate_individual_pov,
                        context, char, scene_instruction, system_prompt, positive, negative
                    ): char for char in characters
                }
                
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_char):
                    char = future_to_char[future]
                    completed_count += 1
                    try:
                        pov = future.result()
                        pov_texts[char] = pov
                        yield "status", f"⏳ POV 분석 진행 상황: {char} 완료 ({completed_count}/{len(characters)})..."
                    except Exception as exc:
                        print(f"Error generating POV for {char}: {exc}")
                        pov_texts[char] = f"[{char}의 시점 분석 실패]"
                        yield "status", f"⚠️ {char}의 시점 분석 실패: {exc}"
        else:
            yield "status", "⚠️ 선택된 등장인물이 없어 POV 분석을 건너뜁니다."
        
        yield "status", "⏳ 등장인물별 시점 분석 완료. 전체 씬 통합 집필 중..."
        
        # Step 2: 통합 씬 스트리밍
        merge_sys_prompt = system_prompt if system_prompt else (
            "당신은 빠른 전개와 밀도 있는 문장을 구사하는 3인칭 전지적 시점의 마스터 소설가입니다. "
            "제시된 다수 인물의 시점과 심리, 그리고 관능적 장치들을 유기적으로 통합하여, "
            "단순한 행위의 나열이 아닌 마스터피스 형태로 집필하세요. "
            "절대 프롬프트, 설명, 지시문, 주석은 출력하지 마세요. 순수한 소설 본문만 출력하세요."
        )
        
        pov_combined = ""
        for char, text in pov_texts.items():
            pov_combined += f"[{char}의 행동/심리]\n{text}\n\n"
        
        merge_user_prompt = f"{context}\n\n[등장인물별 개별 시점]\n{pov_combined}\n위 시점들을 통합하여 하나의 완성된 소설 씬으로 작성하세요."
        if positive:
            merge_user_prompt += f"\n\n[문체 지시 (적용)]\n{positive}"
        if negative:
            merge_user_prompt += f"\n\n[문체 지시 (금지)]\n{negative}"
        
        for token in self.client.stream_chat_completion(
            system_prompt=merge_sys_prompt,
            user_prompt=merge_user_prompt,
            temperature=0.6
        ):
            yield "text", token
