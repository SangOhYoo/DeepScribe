import gradio as gr
from client import LlamaAPIClient
from generator import NCSGenerator

# Instantiate llama client and generator
llama_client = LlamaAPIClient()
ncs_generator = NCSGenerator(llama_client)

def generate_ksa_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명(세분류)을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
    
    gr.Info("KSA (지식/기술/태도) 생성을 시작합니다...")
    ksa_text = ""
    for chunk in ncs_generator.generate_ksa_stream(job_name, additional_info):
        if chunk:
            ksa_text += chunk
            yield ksa_text

def generate_range_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명(세분류)을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
        
    gr.Info("적용범위 및 작업상황 생성을 시작합니다...")
    range_text = ""
    for chunk in ncs_generator.generate_range_of_variables_stream(job_name, additional_info):
        if chunk:
            range_text += chunk
            yield range_text

def generate_assessment_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명(세분류)을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
        
    gr.Info("평가방법 및 지침 생성을 시작합니다...")
    assessment_text = ""
    for chunk in ncs_generator.generate_assessment_guidelines_stream(job_name, additional_info):
        if chunk:
            assessment_text += chunk
            yield assessment_text

def generate_all_ncs_stream(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명(세분류)을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다.", "대기 중...", "대기 중..."
        return
        
    ksa_text = ""
    range_text = ""
    assessment_text = ""
    
    # 1. KSA
    gr.Info("[Step 1/3] KSA 지식/기술/태도 도출 중...")
    yield "🔄 지식/기술/태도(KSA) 생성 중...", "대기 중...", "대기 중..."
    for chunk in ncs_generator.generate_ksa_stream(job_name, additional_info):
        if chunk:
            ksa_text += chunk
            yield ksa_text, "대기 중...", "대기 중..."
            
    # 2. Range of Variables
    gr.Info("[Step 2/3] 적용범위 및 작업상황 도출 중...")
    yield ksa_text, "🔄 적용범위/작업상황 생성 중...", "대기 중..."
    for chunk in ncs_generator.generate_range_of_variables_stream(job_name, additional_info):
        if chunk:
            range_text += chunk
            yield ksa_text, range_text, "대기 중..."
            
    # 3. Assessment Guidelines
    gr.Info("[Step 3/3] 평가방법 및 지침 도출 중...")
    yield ksa_text, range_text, "🔄 평가방법/지침 생성 중..."
    for chunk in ncs_generator.generate_assessment_guidelines_stream(job_name, additional_info):
        if chunk:
            assessment_text += chunk
            yield ksa_text, range_text, assessment_text
            
    gr.Info("🎉 NCS 직무 표준서 일괄 작성이 완료되었습니다!")

def build_ui():
    custom_css = """
    .ncs-title {
        text-align: center;
        margin-bottom: 20px;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .ncs-title h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .ncs-title p {
        margin: 8px 0 0 0;
        font-size: 15px;
        opacity: 0.9;
    }
    .gradio-container button {
        min-height: 44px !important;
        font-weight: 600 !important;
    }
    """
    
    # Check Gradio version to set parameters properly
    from gradio import __version__ as gradio_version
    is_gradio_6 = int(gradio_version.split(".")[0]) >= 6
    
    blocks_kwargs = {
        "title": "NCS 직무 집필 지원 시스템",
        "theme": gr.themes.Soft(primary_hue="indigo", secondary_hue="slate", neutral_hue="slate")
    }
    if not is_gradio_6:
        blocks_kwargs["css"] = custom_css
        
    with gr.Blocks(**blocks_kwargs) as app:
        if is_gradio_6:
            gr.HTML(f"<style>{custom_css}</style>")
            
        gr.HTML("""
            <div class="ncs-title">
                <h1>📋 NCS 국가직무능력표준 집필 지원 엔진</h1>
                <p>산업 현장의 요구 조건에 부합하는 고품질 직무별 지식(K), 기술(S), 태도(A) 및 작업상황과 평가지침을 AI로 고속 개발합니다.</p>
            </div>
        """)
            
        with gr.Row():
            # Left Panel: Configuration
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ 직무 정의 및 지시사항")
                job_name = gr.Textbox(
                    label="🏷️ NCS 직무명 (세분류)",
                    placeholder="예: 빅데이터 분석, 스마트 공장 구축, 정보보안 감리",
                    lines=1,
                    interactive=True
                )
                
                additional_info = gr.Textbox(
                    label="📝 추가 개발 조건 및 지시사항 (선택)",
                    placeholder="예: 클라우드 기반 환경 중심, 또는 2026년 최신 보안 가이드라인 준수 등",
                    lines=4,
                    interactive=True
                )
                
                with gr.Accordion("⚙️ 고급 설정", open=False):
                    api_status = gr.Textbox(
                        label="Llama API 상태",
                        value=f"연결 대상: {llama_client.api_url}",
                        interactive=False
                    )
                
                btn_gen_all = gr.Button("🪄 NCS 표준 직무서 일괄 생성", variant="primary")
                
            # Right Panel: Output Tabs
            with gr.Column(scale=2):
                gr.Markdown("### 📄 표준 직무 능력 명세서 결과")
                
                with gr.Tabs():
                    with gr.Tab("📚 지식 / 기술 / 태도 (KSA)"):
                        with gr.Row():
                            btn_gen_ksa = gr.Button("📚 KSA 단독 생성/갱신", variant="secondary")
                        out_ksa = gr.Textbox(
                            label="지식(K), 기술(S), 태도(A) 목록",
                            placeholder="직무명을 입력하고 생성 버튼을 누르면 NCS 표준 문체로 도출됩니다.",
                            lines=18,
                            interactive=True
                        )
                        
                    with gr.Tab("🔍 적용범위 및 작업상황"):
                        with gr.Row():
                            btn_gen_range = gr.Button("🔍 적용범위/작업상황 단독 생성/갱신", variant="secondary")
                        out_range = gr.Textbox(
                            label="적용 범위 및 작업 상황 고지",
                            placeholder="직무에 활용되는 도구, 환경, 법률 양식이 작성됩니다.",
                            lines=18,
                            interactive=True
                        )
                        
                    with gr.Tab("📝 평가방법 및 지침"):
                        with gr.Row():
                            btn_gen_assessment = gr.Button("📝 평가방법/지침 단독 생성/갱신", variant="secondary")
                        out_assessment = gr.Textbox(
                            label="직무 능력 평가 지침 및 주의사항",
                            placeholder="평가관이 참고할 검증 항목 및 채점 가이드라인이 작성됩니다.",
                            lines=18,
                            interactive=True
                        )
                        
        # Event Bindings
        # 1. Generate All Components
        btn_gen_all.click(
            fn=generate_all_ncs_stream,
            inputs=[job_name, additional_info],
            outputs=[out_ksa, out_range, out_assessment]
        )
        
        # 2. Individual Generators
        btn_gen_ksa.click(
            fn=generate_ksa_single,
            inputs=[job_name, additional_info],
            outputs=[out_ksa]
        )
        
        btn_gen_range.click(
            fn=generate_range_single,
            inputs=[job_name, additional_info],
            outputs=[out_range]
        )
        
        btn_gen_assessment.click(
            fn=generate_assessment_single,
            inputs=[job_name, additional_info],
            outputs=[out_assessment]
        )
        
    return app
