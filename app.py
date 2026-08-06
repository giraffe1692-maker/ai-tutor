
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from openai import OpenAI
from datetime import datetime
from pathlib import Path
from collections import Counter
from uuid import uuid4
import os

st.set_page_config(
    page_title="가우스 법칙 적응형 문제풀이",
    page_icon="⚡",
    layout="wide",
)

LOG_PATH = Path("learning_log.csv")
TABLE_NAME = "learning_logs"
CHAT_TABLE_NAME = "ai_chat_logs"

@st.cache_resource
def get_supabase_client():
    """Create one server-side Supabase client per app process."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["service_role_key"]
        return create_client(url, key)
    except Exception:
        return None

def database_mode():
    return "Supabase" if get_supabase_client() is not None else "로컬 CSV"


@st.cache_resource
def get_ai_client():
    """Create a Groq client (OpenAI-compatible API)."""
    try:
        api_key = st.secrets["groq"]["api_key"]
        return OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    except Exception:
        return None
def get_ai_model():
    try:
        return str(st.secrets["groq"].get("model", "llama-3.3-70b-versatile"))
    except Exception:
        return "llama-3.3-70b-versatile"
def ai_tutor_available():
    return get_ai_client() is not None


ERROR_FEEDBACK = {
    "S1": {
        "name": "대칭성 및 가우스 면 선택 오류",
        "feedback": "구대칭 전하분포에서는 중심이 같은 구형 가우스 면을 선택해야 합니다. 그래야 구면 위에서 전기장의 크기가 일정하고 전기장과 면적벡터가 나란해집니다.",
        "focus": "다음 수준에서는 먼저 전하분포의 대칭성과 가우스 면의 중심이 일치하는지 확인하세요.",
    },
    "Q1": {
        "name": "외부 영역 포함 전하 판단 오류",
        "feedback": "r>R인 가우스 면은 대전체 전체를 둘러싸므로 포함 전하는 Q입니다.",
        "focus": "가우스 면이 전체 전하를 포함하는지, 일부만 포함하는지를 먼저 판단하세요.",
    },
    "F1": {
        "name": "구면적 및 전기선속 계산 오류",
        "feedback": "구형 가우스 면의 넓이는 4πr²입니다. πr²은 구의 단면적입니다.",
        "focus": "가우스 법칙에는 실제 대전체가 아니라 선택한 가우스 면의 넓이를 사용하세요.",
    },
    "M1": {
        "name": "외부 전기장 식 정리 오류",
        "feedback": "E·4πr²=Q/ε₀에서 E를 정리하면 E=Q/(4πε₀r²)입니다.",
        "focus": "식의 분모에 가우스 면 반지름 r의 제곱이 들어가는지 확인하세요.",
    },
    "R1": {
        "name": "내부·외부 영역 구분 오류",
        "feedback": "균일한 부도체 구에서는 r=R을 기준으로 포함 전하의 식이 바뀌므로 내부와 외부를 나누어야 합니다.",
        "focus": "문제를 풀기 전에 물질의 경계를 기준으로 공간을 나누세요.",
    },
    "Q2": {
        "name": "부피 전하밀도 정의 오류",
        "feedback": "부피 전하밀도는 전체 전하를 실제 대전 부피로 나눈 값입니다. ρ=Q/[(4/3)πR³]입니다.",
        "focus": "전하가 선, 면, 부피 중 어디에 분포하는지 먼저 판단하세요.",
    },
    "Q3": {
        "name": "구 내부 포함 전하 계산 오류",
        "feedback": "균일한 부피 전하분포에서 포함 전하는 부피비에 비례하므로 Qenc=Q(r³/R³)입니다.",
        "focus": "길이비나 면적비가 아니라 부피비를 사용하세요.",
    },
    "M2": {
        "name": "내부·외부 전기장 식 구성 오류",
        "feedback": "내부에서는 Qenc∝r³이고 구면적은 r²이므로 E∝r입니다. 외부에서는 E∝1/r²입니다.",
        "focus": "각 영역에서 Qenc와 가우스 면적을 따로 적은 뒤 E를 정리하세요.",
    },
    "G1": {
        "name": "전기장-거리 그래프 해석 오류",
        "feedback": "전기장은 중심에서 0이고 내부에서 선형 증가하며, 표면에서 최대가 된 뒤 외부에서 1/r²로 감소합니다.",
        "focus": "식의 r 의존성을 이용해 그래프의 증가와 감소를 판단하세요.",
    },
    "R2": {
        "name": "세 영역 구분 오류",
        "feedback": "두꺼운 구껍질은 공동 내부, 대전된 물질 내부, 외부의 세 영역으로 나누어야 합니다.",
        "focus": "r=a와 r=b를 경계로 먼저 세 영역을 표시하세요.",
    },
    "Q4": {
        "name": "구껍질 전하밀도 계산 오류",
        "feedback": "실제 대전 부피는 바깥 구 부피에서 빈 공동 부피를 뺀 (4/3)π(b³-a³)입니다.",
        "focus": "전체 공간이 아니라 실제로 전하가 존재하는 부피만 사용하세요.",
    },
    "Q5": {
        "name": "공동 내부 전기장 판단 오류",
        "feedback": "중심이 일치하는 구대칭 공동에서는 포함 전하가 0이고 대칭성이 성립하므로 E=0입니다.",
        "focus": "포함 전하와 대칭성을 함께 확인하세요.",
    },
    "Q6": {
        "name": "구껍질 내부 포함 전하 계산 오류",
        "feedback": "a≤r<b에서는 반지름 r인 구 전체가 아니라 a부터 r까지의 대전 부피만 포함하므로 r³-a³이 나타납니다.",
        "focus": "포함 부피에서 빈 공동의 부피를 빼세요.",
    },
    "M3": {
        "name": "세 영역 전기장 식 구성 오류",
        "feedback": "세 영역의 포함 전하는 각각 0, 부분 전하, 전체 전하입니다. 이를 각각 가우스 법칙에 대입해야 합니다.",
        "focus": "먼저 영역별 Qenc 표를 완성한 뒤 전기장 식을 작성하세요.",
    },
    "C1": {
        "name": "경계 연속성 판단 오류",
        "feedback": "별도의 표면전하가 없으므로 r=a와 r=b에서 전기장은 연속입니다.",
        "focus": "각 구간 식에 경계값을 직접 대입해 확인하세요.",
    },
}

LEVELS = {
    1: {
        "title": "1수준 · 균일하게 대전된 부도체 구의 외부 전기장",
        "problem": r"""반지름 \(R\)인 부도체 구에 전체 전하 \(Q>0\)가 균일하게 분포한다.
구의 중심으로부터 \(r>R\) 떨어진 지점의 전기장을 가우스 법칙으로 구하시오.""",
        "image": "img/1-1.png",
        "steps": [
            {
                "id": "symmetry",
                "question": "적절한 대칭성과 가우스 면은?",
                "options": [
                    ("구대칭 · 중심이 같은 반지름 r의 구면", None),
                    ("원통대칭 · 반지름 r의 원통면", "S1"),
                    ("평면대칭 · 필박스", "S1"),
                    ("어떤 닫힌 면도 동일하다", "S1"),
                ],
                "answer": "구대칭 · 중심이 같은 반지름 r의 구면",
                "hints": [
                    "중심에서 같은 거리의 모든 점을 생각하세요.",
                    "전하분포와 중심이 같은 면을 선택해야 합니다.",
                    "구형 가우스 면을 선택하세요.",
                ],
            },
            {
                "id": "charge",
                "question": r"\(r>R\)에서 포함 전하는?",
                "options": [
                    (r"\(Q_{\mathrm{enc}}=Q\)", None),
                    (r"\(Q_{\mathrm{enc}}=Q(r/R)\)", "Q1"),
                    (r"\(Q_{\mathrm{enc}}=Q(r^2/R^2)\)", "Q1"),
                    (r"\(Q_{\mathrm{enc}}=Q(r^3/R^3)\)", "Q1"),
                ],
                "answer": r"\(Q_{\mathrm{enc}}=Q\)",
                "hints": [
                    "가우스 면이 실제 구 전체를 둘러쌉니다.",
                    "일부가 아니라 전체 전하가 포함됩니다.",
                    "정답은 Q입니다.",
                ],
            },
            {
                "id": "flux",
                "question": r"\(\oint \vec E\cdot d\vec A\)의 올바른 단순화는?",
                "options": [
                    (r"\(E(r)4\pi r^2\)", None),
                    (r"\(E(r)\pi r^2\)", "F1"),
                    (r"\(E(r)4\pi R^2\)", "F1"),
                    (r"\(0\)", "F1"),
                ],
                "answer": r"\(E(r)4\pi r^2\)",
                "hints": [
                    "가우스 면은 반지름 r인 구면입니다.",
                    "구면 전체의 넓이를 사용하세요.",
                    r"구면적은 \(4\pi r^2\)입니다.",
                ],
            },
            {
                "id": "final",
                "question": "최종 전기장 식은?",
                "options": [
                    (r"\(E=\dfrac{Q}{4\pi\varepsilon_0r^2}\)", None),
                    (r"\(E=\dfrac{Qr}{4\pi\varepsilon_0R^3}\)", "M1"),
                    (r"\(E=\dfrac{Q}{4\pi\varepsilon_0R^2}\)", "M1"),
                    (r"\(E=0\)", "M1"),
                ],
                "answer": r"\(E=\dfrac{Q}{4\pi\varepsilon_0r^2}\)",
                "hints": [
                    r"\(E4\pi r^2=Q/\varepsilon_0\)에서 E를 정리하세요.",
                    r"양변을 \(4\pi r^2\)로 나누세요.",
                    "외부에서는 점전하의 전기장과 같습니다.",
                ],
            },
        ],
    },
    2: {
        "title": "2수준 · 균일하게 대전된 부도체 구의 내부와 외부 전기장",
        "problem": r"""반지름 \(R\)인 부도체 구에 전체 전하 \(Q>0\)가 균일하게 분포한다.
중심으로부터 거리 \(r\)인 지점의 전기장을 내부와 외부에서 각각 구하시오.""",
        "image": "img/1-1.png",
        "steps": [
            {
                "id": "regions",
                "question": "공간을 어떻게 나누어야 하는가?",
                "options": [
                    (r"\(0\le r<R\), \(r\ge R\)", None),
                    (r"\(0\le r\le R/2\), \(r>R/2\)", "R1"),
                    (r"\(r<R\)만 고려", "R1"),
                    ("나눌 필요가 없다", "R1"),
                ],
                "answer": r"\(0\le r<R\), \(r\ge R\)",
                "hints": [
                    "포함 전하의 식이 바뀌는 경계를 찾으세요.",
                    "실제 구의 표면이 경계입니다.",
                    "r=R을 기준으로 나눕니다.",
                ],
            },
            {
                "id": "density",
                "question": "균일한 부피 전하밀도는?",
                "options": [
                    (r"\(\rho=\dfrac{Q}{(4/3)\pi R^3}\)", None),
                    (r"\(\rho=\dfrac{Q}{4\pi R^2}\)", "Q2"),
                    (r"\(\rho=\dfrac{Q}{2\pi R}\)", "Q2"),
                    (r"\(\rho=\dfrac{Q}{R}\)", "Q2"),
                ],
                "answer": r"\(\rho=\dfrac{Q}{(4/3)\pi R^3}\)",
                "hints": [
                    "전하는 부피 전체에 분포합니다.",
                    "전체 전하를 전체 부피로 나눕니다.",
                    r"구의 부피는 \((4/3)\pi R^3\)입니다.",
                ],
            },
            {
                "id": "inside_charge",
                "question": r"\(r<R\)에서 포함 전하는?",
                "options": [
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r^3}{R^3}\)", None),
                    (r"\(Q_{\mathrm{enc}}=Q\)", "Q3"),
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r^2}{R^2}\)", "Q3"),
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r}{R}\)", "Q3"),
                ],
                "answer": r"\(Q_{\mathrm{enc}}=Q\dfrac{r^3}{R^3}\)",
                "hints": [
                    "포함 전하는 포함 부피에 비례합니다.",
                    "반지름 r과 R인 구의 부피비를 구하세요.",
                    r"부피비는 \(r^3/R^3\)입니다.",
                ],
            },
            {
                "id": "field",
                "question": "내부와 외부 전기장 식은?",
                "options": [
                    (r"\(\begin{cases} E(r)=\dfrac{Qr}{4\pi\varepsilon_0R^3}, & 0\le r<R \\[6pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge R \end{cases}\)", None),
                    (r"\(E=\dfrac{Q}{4\pi\varepsilon_0r^2}\) (모든 영역)", "M2"),
                    (r"\(\begin{cases} E(r)=0, & 0\le r<R \\[6pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge R \end{cases}\)", "M2"),
                    (r"\(\begin{cases} E(r)=\dfrac{QR}{4\pi\varepsilon_0r^3}, & 0\le r<R \\[6pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0R^2}, & r\ge R \end{cases}\)", "M2"),
                ],
                "answer": r"\(\begin{cases} E(r)=\dfrac{Qr}{4\pi\varepsilon_0R^3}, & 0\le r<R \\[6pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge R \end{cases}\)",
                "hints": [
                    "내부에서는 Qenc∝r³입니다.",
                    "구면적은 r²에 비례합니다.",
                    "따라서 내부는 E∝r, 외부는 E∝1/r²입니다.",
                ],
            },
            {
                "id": "graph",
                "question": "전기장-거리 그래프의 특징으로 옳은 것은?",
                "options": [
                    ("중심에서 0, 내부에서 선형 증가, 표면에서 최대, 외부에서 역제곱 감소", None),
                    ("중심에서 무한대, 이후 계속 감소", "G1"),
                    ("내부에서 항상 0, 외부에서 일정", "G1"),
                    ("모든 영역에서 선형 증가", "G1"),
                ],
                "answer": "중심에서 0, 내부에서 선형 증가, 표면에서 최대, 외부에서 역제곱 감소",
                "hints": [
                    "내부와 외부 식의 r 의존성을 확인하세요.",
                    "내부는 E∝r입니다.",
                    "외부는 E∝1/r²입니다.",
                ],
            },
        ],
    },
    3: {
        "title": "3수준 · 두께가 있는 부도체 구껍질의 전기장",
        "problem": r"""안쪽 반지름이 \(a\), 바깥쪽 반지름이 \(b\)인 두꺼운 부도체 구껍질에
전체 전하 \(Q>0\)가 균일하게 분포한다. 모든 영역의 전기장을 구하시오.""",
        "image": "img/3-1.png",
        "steps": [
            {
                "id": "regions",
                "question": "공간을 어떻게 나누어야 하는가?",
                "options": [
                    (r"\(0\le r<a\), \(a\le r<b\), \(r\ge b\)", None),
                    (r"\(0\le r<b\), \(r\ge b\)", "R2"),
                    (r"\(0\le r<a\), \(r\ge a\)", "R2"),
                    ("나눌 필요가 없다", "R2"),
                ],
                "answer": r"\(0\le r<a\), \(a\le r<b\), \(r\ge b\)",
                "hints": [
                    "빈 공동과 바깥 표면을 모두 고려하세요.",
                    "경계는 r=a와 r=b입니다.",
                    "세 영역으로 나눕니다.",
                ],
            },
            {
                "id": "density",
                "question": "부피 전하밀도는?",
                "options": [
                    (r"\(\rho=\dfrac{Q}{(4/3)\pi(b^3-a^3)}\)", None),
                    (r"\(\rho=\dfrac{Q}{(4/3)\pi b^3}\)", "Q4"),
                    (r"\(\rho=\dfrac{Q}{4\pi(b^2-a^2)}\)", "Q4"),
                    (r"\(\rho=\dfrac{Q}{b-a}\)", "Q4"),
                ],
                "answer": r"\(\rho=\dfrac{Q}{(4/3)\pi(b^3-a^3)}\)",
                "hints": [
                    "반지름 a 안쪽은 비어 있습니다.",
                    "바깥 구 부피에서 안쪽 구 부피를 빼세요.",
                    r"대전 부피는 \((4/3)\pi(b^3-a^3)\)입니다.",
                ],
            },
            {
                "id": "cavity",
                "question": r"\(0\le r<a\)에서 전기장은?",
                "options": [
                    (r"\(E=0\)", None),
                    (r"\(E=\dfrac{Q}{4\pi\varepsilon_0r^2}\)", "Q5"),
                    (r"\(E=\dfrac{\rho r}{3\varepsilon_0}\)", "Q5"),
                    ("정보가 부족하다", "Q5"),
                ],
                "answer": r"\(E=0\)",
                "hints": [
                    "가우스 면 내부에 전하가 있는지 확인하세요.",
                    "공동 내부에는 전하가 없습니다.",
                    "구대칭이므로 E=0입니다.",
                ],
            },
            {
                "id": "shell_charge",
                "question": r"\(a\le r<b\)에서 포함 전하는?",
                "options": [
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r^3-a^3}{b^3-a^3}\)", None),
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r^3}{b^3}\)", "Q6"),
                    (r"\(Q_{\mathrm{enc}}=Q\dfrac{r-a}{b-a}\)", "Q6"),
                    (r"\(Q_{\mathrm{enc}}=Q\)", "Q6"),
                ],
                "answer": r"\(Q_{\mathrm{enc}}=Q\dfrac{r^3-a^3}{b^3-a^3}\)",
                "hints": [
                    "반지름 r인 구 전체가 대전된 것은 아닙니다.",
                    "빈 공동의 부피를 빼세요.",
                    r"포함 대전 부피는 \((4/3)\pi(r^3-a^3)\)입니다.",
                ],
            },
            {
                "id": "field",
                "question": "세 영역의 전기장 식은?",
                "options": [
                    (r"\(\begin{cases} E(r)=0, & 0\le r<a \\[6pt] E(r)=\dfrac{Q(r^3-a^3)}{4\pi\varepsilon_0r^2(b^3-a^3)}, & a\le r<b \\[10pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge b \end{cases}\)", None),
                    (r"\(E=\dfrac{Q}{4\pi\varepsilon_0r^2}\) (모든 영역)", "M3"),
                    (r"\(\begin{cases} E(r)=0, & 0\le r<b \\[6pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge b \end{cases}\)", "M3"),
                    (r"\(E=\dfrac{\rho r}{3\varepsilon_0}\) (모든 영역)", "M3"),
                ],
                "answer": r"\(\begin{cases} E(r)=0, & 0\le r<a \\[6pt] E(r)=\dfrac{Q(r^3-a^3)}{4\pi\varepsilon_0r^2(b^3-a^3)}, & a\le r<b \\[10pt] E(r)=\dfrac{Q}{4\pi\varepsilon_0r^2}, & r\ge b \end{cases}\)",
                "hints": [
                    "세 영역의 포함 전하는 0, 부분 전하, 전체 전하입니다.",
                    "각 영역에 가우스 법칙을 적용하세요.",
                    "영역별 Qenc를 먼저 적으세요.",
                ],
            },
            {
                "id": "boundary",
                "question": "경계에서 전기장의 특징은?",
                "options": [
                    (r"\(r=a\)와 \(r=b\)에서 연속", None),
                    (r"\(r=a\)에서 무한대로 발산", "C1"),
                    (r"\(r=b\)에서 0으로 불연속", "C1"),
                    ("두 경계에서 모두 불연속", "C1"),
                ],
                "answer": r"\(r=a\)와 \(r=b\)에서 연속",
                "hints": [
                    "각 식에 r=a와 r=b를 대입하세요.",
                    "별도의 표면전하는 없습니다.",
                    "경계값이 서로 일치합니다.",
                ],
            },
        ],
    },
}


def latex_to_markdown(text):
    """Convert \( ... \) delimiters to Streamlit-compatible inline math."""
    if not isinstance(text, str):
        return str(text)
    return text.replace(r"\(", "$").replace(r"\)", "$")

def is_formula_only(text):
    """Return True when an option consists only of one LaTeX expression."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    return stripped.startswith(r"\(") and stripped.endswith(r"\)") and stripped.count(r"\(") == 1

def latex_body(text):
    """Remove outer \( \) delimiters for st.latex."""
    stripped = text.strip()
    if stripped.startswith(r"\(") and stripped.endswith(r"\)"):
        return stripped[2:-2]
    return stripped

def render_question(text):
    """Render a question with inline LaTeX."""
    st.markdown(latex_to_markdown(text))

def render_options(options):
    """Render option contents separately so LaTeX is not trapped inside st.radio."""
    letters = ["A", "B", "C", "D", "E", "F"]
    for idx, (label, _) in enumerate(options):
        letter = letters[idx]
        with st.container(border=True):
            st.markdown(f"**{letter}.**")
            if is_formula_only(label):
                st.latex(latex_body(label))
            else:
                st.markdown(latex_to_markdown(label))

def option_letter_map(options):
    letters = ["A", "B", "C", "D", "E", "F"]
    return {
        letters[idx]: {
            "label": label,
            "error_code": error_code,
        }
        for idx, (label, error_code) in enumerate(options)
    }



def current_step_key(level, step_id):
    return f"{level}:{step_id}"

def build_tutor_context(level, level_data, step, selected_response=None, error_code=None):
    error_info = ERROR_FEEDBACK.get(error_code, {}) if error_code else {}
    options_text = "\n".join(
        f"- {chr(65+i)}: {label}"
        for i, (label, _) in enumerate(step["options"])
    )

    return f"""
현재 학습 수준: {level}수준
문제 제목: {level_data['title']}
문제 상황:
{level_data['problem']}

현재 풀이 단계 질문:
{step['question']}

선택지:
{options_text}

학생이 현재 선택한 답:
{selected_response or '아직 선택하지 않음'}

자동 진단 오류 코드:
{error_code or '없음'}

자동 진단 설명:
{error_info.get('feedback', '없음')}
""".strip()

def tutor_system_prompt():
    return """
당신은 대학 일반물리학의 가우스 법칙 문제풀이를 돕는 소크라테스식 AI 튜터이다.

반드시 지킬 규칙:
1. 학생에게 최종 정답 선택지, 최종 전기장 식, 완성된 전체 풀이를 즉시 알려주지 않는다.
2. 한 번의 답변에서는 핵심 질문 또는 힌트를 최대 2개만 제공한다.
3. 현재 단계에서 필요한 개념만 다룬다.
4. 먼저 학생이 무엇을 생각했는지 확인하고, 그 응답에 따라 힌트의 구체성을 높인다.
5. 대칭성, 영역 구분, 포함 전하, 가우스 면적, 경계조건의 순서를 우선 활용한다.
6. 학생이 정답을 직접 요구해도 바로 답하지 말고, 계산의 다음 한 단계만 안내한다.
7. 학생의 선택이 틀렸다면 비난하지 않고 어떤 물리적 판단을 다시 확인해야 하는지 설명한다.
8. 수식은 LaTeX로 쓰되 짧고 명료하게 제시한다.
9. 가우스 법칙과 구대칭 문제의 범위를 벗어난 질문에는 현재 문제와 관련된 내용으로 돌아오도록 안내한다.
10. 한국어로 응답한다.
""".strip()

def call_ai_tutor(level, level_data, step, user_message, selected_response=None, error_code=None):
    client = get_ai_client()  # 또는 get_openai_client() 이름 유지
    if client is None:
        return None, "AI API가 연결되지 않았습니다."

    key = current_step_key(level, step["id"])
    history = st.session_state.ai_histories.get(key, [])
    context = build_tutor_context(
        level,
        level_data,
        step,
        selected_response,
        error_code,
    )

    conversation = [
        {
            "role": "system",
            "content": tutor_system_prompt(),
        },
        {
            "role": "developer",
            "content": (
                "다음은 앱이 제공한 현재 문항 정보이다. "
                "학생에게는 이 정보 중 정답을 직접 노출하지 말고 힌트 생성에만 활용하라.\n\n"
                + context
            ),
        },
    ]

    for item in history[-8:]:
        conversation.append(
            {
                "role": item["role"],
                "content": item["content"],
            }
        )

    conversation.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    try:
        response = client.chat.completions.create(
            model=get_ai_model(),
            messages=conversation,
            max_tokens=350,
        )
        text = response.choices[0].message.content.strip()
        return text, None
    except Exception as exc:
        return None, str(exc)

def render_ai_tutor(level, level_data, step, selected_response=None, error_code=None):
    st.markdown("---")
    st.markdown("## 🤖 AI 튜터에게 힌트 묻기")
    st.caption(
        "AI 튜터는 정답을 바로 제공하지 않고, 현재 풀이 단계에 필요한 질문과 힌트를 제공합니다."
    )

    if not ai_tutor_available():
        st.warning(
            "AI API가 연결되지 않았습니다. "
            "Streamlit Secrets에 ai.api_key를 설정하면 이 기능을 사용할 수 있습니다."
        )
        return

    key = current_step_key(level, step["id"])
    if key not in st.session_state.ai_histories:
        st.session_state.ai_histories[key] = []

    history = st.session_state.ai_histories[key]

    if history:
        with st.container(border=True):
            for item in history:
                with st.chat_message("assistant" if item["role"] == "assistant" else "user"):
                    st.markdown(latex_to_markdown(item["content"]))

    prompts = [
        "어디서부터 생각해야 할지 모르겠어요.",
        "제가 선택한 답이 왜 문제인지 힌트를 주세요.",
        "포함 전하를 어떻게 판단해야 하나요?",
    ]
    quick_prompt = st.selectbox(
        "빠른 질문",
        ["직접 입력"] + prompts,
        key=f"quick_prompt_{key}",
    )

    typed = st.chat_input(
        "현재 단계에서 궁금한 점을 입력하세요.",
        key=f"ai_chat_{key}",
    )

    submitted_message = typed
    if quick_prompt != "직접 입력":
        if st.button(
            "선택한 빠른 질문 보내기",
            key=f"send_quick_{key}",
        ):
            submitted_message = quick_prompt

    if submitted_message:
        clean_message = submitted_message.strip()
        if not clean_message:
            return

        if st.session_state.ai_usage_count >= 20:
            st.warning(
                "현재 학습 세션의 AI 튜터 사용 한도 20회에 도달했습니다."
            )
            return

        history.append(
            {
                "role": "user",
                "content": clean_message,
            }
        )
        save_ai_chat_log(
            level, step["id"], "user", clean_message,
            error_code=error_code,
            selected_response=selected_response,
            status="submitted",
        )

        with st.spinner("AI 튜터가 힌트를 구성하고 있습니다..."):
            answer, error = call_ai_tutor(
                level,
                level_data,
                step,
                clean_message,
                selected_response,
                error_code,
            )

        if error:
            st.error(f"AI 튜터 호출 오류: {error}")
            save_ai_chat_log(
                level, step["id"], "system_error", error,
                error_code=error_code,
                selected_response=selected_response,
                status="failed",
            )
            history.append(
                {
                    "role": "assistant",
                    "content": "AI 튜터가 현재 응답하지 않습니다. 기본 힌트를 이용해 주세요.",
                }
            )
        else:
            history.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )
            save_ai_chat_log(
                level, step["id"], "assistant", answer,
                error_code=error_code,
                selected_response=selected_response,
                status="success",
            )
            st.session_state.ai_usage_count += 1
        st.rerun()

    col_reset, col_usage = st.columns([1, 2])
    with col_reset:
        if st.button(
            "현재 단계 대화 초기화",
            key=f"reset_ai_{key}",
        ):
            st.session_state.ai_histories[key] = []
            st.rerun()
    with col_usage:
        st.caption(
            f"이 세션의 AI 튜터 사용: {st.session_state.ai_usage_count}/20회"
        )


def init_state():
    defaults = {
        "student_id": "",
        "session_uuid": str(uuid4()),
        "consent": False,
        "started": False,
        "level": 1,
        "step": 0,
        "hint_index": 0,
        "attempts": 0,
        "answered": False,
        "last_correct": None,
        "latest_error": None,
        "level_errors": [],
        "session_records": [],
        "ai_histories": {},
        "ai_chat_records": [],
        "ai_usage_count": 0,
        "completed": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def save_log(level, step_id, response, correct, error_code, hint_count, attempt):
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_uuid": st.session_state.session_uuid,
        "student_id": str(st.session_state.student_id).strip(),
        "level": int(level),
        "step_id": str(step_id),
        "response": str(response),
        "correct": bool(correct),
        "error_code": str(error_code or ""),
        "hint_count": int(hint_count),
        "attempt_number": int(attempt),
    }

    # 현재 학생의 결과 화면을 위해 세션에도 보관한다.
    st.session_state.session_records.append(row.copy())

    client = get_supabase_client()
    if client is not None:
        try:
            client.table(TABLE_NAME).insert(row).execute()
            return True
        except Exception as exc:
            st.session_state["database_error"] = str(exc)

    # 개발용 또는 데이터베이스 장애 시 로컬 백업
    df = pd.DataFrame([row])
    try:
        if LOG_PATH.exists():
            df.to_csv(
                LOG_PATH,
                mode="a",
                index=False,
                header=False,
                encoding="utf-8-sig",
            )
        else:
            df.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")
        return False
    except Exception as exc:
        st.session_state["database_error"] = str(exc)
        return False


def save_ai_chat_log(level, step_id, role, content, error_code="", selected_response="", status="success"):
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_uuid": st.session_state.session_uuid,
        "student_id": str(st.session_state.student_id).strip(),
        "level": int(level),
        "step_id": str(step_id),
        "role": str(role),
        "content": str(content),
        "error_code": str(error_code or ""),
        "selected_response": str(selected_response or ""),
        "status": str(status),
    }
    st.session_state.ai_chat_records.append(row.copy())

    client = get_supabase_client()
    if client is not None:
        try:
            client.table(CHAT_TABLE_NAME).insert(row).execute()
            return True
        except Exception as exc:
            st.session_state["database_error"] = str(exc)

    path = Path("ai_chat_log.csv")
    df = pd.DataFrame([row])
    try:
        if path.exists():
            df.to_csv(path, mode="a", index=False, header=False, encoding="utf-8-sig")
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")
    except Exception as exc:
        st.session_state["database_error"] = str(exc)
    return False

def load_all_chat_logs():
    client = get_supabase_client()
    if client is not None:
        try:
            response = (
                client.table(CHAT_TABLE_NAME)
                .select("*")
                .order("timestamp", desc=True)
                .execute()
            )
            return pd.DataFrame(response.data or [])
        except Exception as exc:
            st.error(f"AI 대화 로그 조회 오류: {exc}")
            return pd.DataFrame()

    path = Path("ai_chat_log.csv")
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as exc:
            st.error(f"로컬 AI 대화 로그 조회 오류: {exc}")
    return pd.DataFrame()

def load_all_logs():
    """Load all records for the researcher dashboard."""
    client = get_supabase_client()
    if client is not None:
        try:
            response = (
                client.table(TABLE_NAME)
                .select("*")
                .order("timestamp", desc=True)
                .execute()
            )
            return pd.DataFrame(response.data or [])
        except Exception as exc:
            st.error(f"Supabase 조회 오류: {exc}")
            return pd.DataFrame()

    if LOG_PATH.exists():
        try:
            return pd.read_csv(LOG_PATH)
        except Exception as exc:
            st.error(f"로컬 로그 조회 오류: {exc}")
    return pd.DataFrame()

def render_admin_dashboard():
    st.title("📊 연구자 관리자 화면")

    expected_password = str(
        st.secrets.get("admin_password", "")
        if hasattr(st, "secrets")
        else ""
    )
    password = st.text_input("관리자 비밀번호", type="password")

    if not expected_password:
        st.warning("관리자 비밀번호가 설정되지 않았습니다. Streamlit Secrets에 admin_password를 등록하세요.")
        st.stop()

    if password != expected_password:
        if password:
            st.error("비밀번호가 올바르지 않습니다.")
        st.stop()

    logs = load_all_logs()
    if logs.empty:
        st.info("저장된 학습 기록이 없습니다.")
        st.stop()

    st.success(f"총 {len(logs):,}개의 응답 기록을 불러왔습니다.")

    col1, col2, col3 = st.columns(3)
    col1.metric("학생 ID 수", logs["student_id"].astype(str).nunique())
    col2.metric("학습 세션 수", logs["session_uuid"].astype(str).nunique())
    col3.metric(
        "전체 정답률",
        f"{pd.to_numeric(logs['correct'], errors='coerce').fillna(0).mean() * 100:.1f}%",
    )

    st.subheader("오류 유형 집계")
    error_logs = logs[
        logs["error_code"].fillna("").astype(str).str.strip() != ""
    ].copy()

    if error_logs.empty:
        st.info("오류 기록이 없습니다.")
    else:
        error_summary = (
            error_logs.groupby("error_code")
            .size()
            .reset_index(name="발생 횟수")
            .sort_values("발생 횟수", ascending=False)
        )
        error_summary["오류 유형"] = error_summary["error_code"].map(
            lambda x: ERROR_FEEDBACK.get(
                x, {"name": "미분류 오류"}
            )["name"]
        )
        error_summary = error_summary[
            ["error_code", "오류 유형", "발생 횟수"]
        ].rename(columns={"error_code": "오류 코드"})
        st.dataframe(error_summary, use_container_width=True, hide_index=True)

    st.subheader("학생별 진행 현황")
    student_summary = (
        logs.groupby(["student_id", "session_uuid"], dropna=False)
        .agg(
            최고_수준=("level", "max"),
            응답_횟수=("step_id", "count"),
            정답_횟수=("correct", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
            오류_횟수=("error_code", lambda s: (s.fillna("").astype(str).str.strip() != "").sum()),
            마지막_응답=("timestamp", "max"),
        )
        .reset_index()
    )
    student_summary["정답률(%)"] = (
        student_summary["정답_횟수"]
        / student_summary["응답_횟수"]
        * 100
    ).round(1)
    st.dataframe(student_summary, use_container_width=True, hide_index=True)

    st.subheader("전체 상세 학습 로그")
    st.dataframe(logs, use_container_width=True, hide_index=True)

    st.download_button(
        "전체 학습 로그 CSV 다운로드",
        logs.to_csv(index=False).encode("utf-8-sig"),
        file_name="gauss_learning_logs.csv",
        mime="text/csv",
    )

    st.markdown("---")
    st.subheader("학습자–AI 튜터 대화 로그")
    chat_logs = load_all_chat_logs()

    if chat_logs.empty:
        st.info("저장된 AI 대화 기록이 없습니다.")
    else:
        st.success(f"총 {len(chat_logs):,}개의 AI 대화 기록을 불러왔습니다.")
        c1, c2, c3 = st.columns(3)
        c1.metric("AI 대화 학생 수", chat_logs["student_id"].astype(str).nunique())
        c2.metric("AI 대화 세션 수", chat_logs["session_uuid"].astype(str).nunique())
        c3.metric("AI 응답 성공 수", int((chat_logs["role"].astype(str) == "assistant").sum()))

        student_filter = st.multiselect(
            "학습자 ID 필터",
            sorted(chat_logs["student_id"].astype(str).unique().tolist()),
        )
        role_filter = st.multiselect(
            "메시지 역할 필터",
            sorted(chat_logs["role"].astype(str).unique().tolist()),
        )
        filtered = chat_logs.copy()
        if student_filter:
            filtered = filtered[filtered["student_id"].astype(str).isin(student_filter)]
        if role_filter:
            filtered = filtered[filtered["role"].astype(str).isin(role_filter)]

        cols = [
            "timestamp", "student_id", "session_uuid", "level", "step_id",
            "role", "content", "selected_response", "error_code", "status",
        ]
        cols = [c for c in cols if c in filtered.columns]
        st.dataframe(filtered[cols], use_container_width=True, hide_index=True)
        st.download_button(
            "AI 대화 로그 CSV 다운로드",
            filtered[cols].to_csv(index=False).encode("utf-8-sig"),
            file_name="gauss_ai_chat_logs.csv",
            mime="text/csv",
        )

def reset_step():
    st.session_state.step += 1
    st.session_state.hint_index = 0
    st.session_state.attempts = 0
    st.session_state.answered = False
    st.session_state.last_correct = None
    st.session_state.latest_error = None

def next_level():
    st.session_state.level += 1
    st.session_state.step = 0
    st.session_state.hint_index = 0
    st.session_state.attempts = 0
    st.session_state.answered = False
    st.session_state.last_correct = None
    st.session_state.latest_error = None
    st.session_state.level_errors = []

def render_feedback(level_errors):
    st.markdown("## 수준별 진단 피드백")
    if not level_errors:
        st.success("모든 단계를 첫 시도에 정확하게 해결했습니다.")
        st.info("다음 수준에서도 대칭성 → 영역 구분 → 포함 전하 → 선속 → 전기장 식의 순서를 유지하세요.")
        return

    counts = Counter(level_errors)
    total = sum(counts.values())
    st.warning(f"이 수준에서 총 {total}회의 오류가 진단되었습니다.")

    for idx, (code, count) in enumerate(counts.most_common(), start=1):
        info = ERROR_FEEDBACK[code]
        with st.expander(f"{idx}. {info['name']} · {count}회", expanded=(idx <= 2)):
            st.markdown(latex_to_markdown(info["feedback"]))
            st.markdown(f"**다음 수준에서 집중할 점:** {info['focus']}")

    top_code = counts.most_common(1)[0][0]
    top = ERROR_FEEDBACK[top_code]
    st.markdown("### 핵심 처방")
    st.info(f"가장 빈번한 오류는 **{top['name']}**입니다. {top['focus']}")

init_state()

page_mode = st.sidebar.radio(
    "화면 선택",
    ["학생 학습 화면", "연구자 관리자 화면"],
)

st.sidebar.caption(f"저장 방식: {database_mode()}")
st.sidebar.caption(
    f"AI 튜터: {'연결됨' if ai_tutor_available() else '연결 안 됨'}"
)

if page_mode == "연구자 관리자 화면":
    render_admin_dashboard()
    st.stop()

st.title("⚡ 가우스 법칙 적응형 문제풀이")
st.caption("선택한 답에 따라 오류 유형을 진단하고, 각 수준이 끝날 때 개인화 피드백을 제공합니다.")

if get_supabase_client() is None:
    st.warning(
        "현재 중앙 데이터베이스가 연결되지 않아 로컬 CSV 백업 모드로 실행 중입니다. "
        "온라인 다중 사용자 운영 전 Supabase Secrets를 설정하세요."
    )

if st.session_state.get("database_error"):
    st.error(
        "응답 저장 중 데이터베이스 오류가 발생했습니다. "
        "현재 응답은 이 세션과 로컬 백업에 보관되었습니다."
    )


with st.sidebar:
    st.header("학습 정보")
    if not st.session_state.started:
        sid = st.text_input(
            "익명 학습자 ID",
            placeholder="예: S001",
            help="실명이나 학번 전체 대신 연구용 익명 코드를 사용하세요.",
        )
        consent = st.checkbox(
            "학습 응답이 연구 및 수업 개선을 위해 저장되는 것에 동의합니다."
        )
        if st.button("학습 시작", type="primary", use_container_width=True):
            clean_id = sid.strip()
            if not clean_id:
                st.warning("학습자 ID를 입력하세요.")
            elif len(clean_id) > 50:
                st.warning("학습자 ID는 50자 이하로 입력하세요.")
            elif not consent:
                st.warning("응답 저장 동의가 필요합니다.")
            else:
                st.session_state.student_id = clean_id
                st.session_state.consent = True
                st.session_state.session_uuid = str(uuid4())
                st.session_state.started = True
                st.rerun()
    else:
        st.write(f"학습자: **{st.session_state.student_id}**")
        st.write(f"현재 수준: **{st.session_state.level}/3**")
        if st.button("처음부터 다시 시작", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if not st.session_state.started:
    st.info("왼쪽에서 학습자 ID를 입력한 뒤 시작하세요.")
    st.stop()

if st.session_state.completed:
    st.success("세 수준을 모두 완료했습니다.")
    st.balloons()

    # 학생 결과 화면에서는 현재 브라우저 세션의 기록만 표시한다.
    mine = pd.DataFrame(st.session_state.session_records)

    st.subheader("전체 오류 유형 요약")

    if mine.empty:
        st.warning("현재 학습 세션의 저장된 응답 기록이 없습니다.")
    else:
        mine["correct_bool"] = (
            mine["correct"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
        )
        wrong = mine[mine["correct_bool"] == False].copy()

        if wrong.empty:
            st.success("기록된 오류가 없습니다. 모든 문항을 정확하게 해결했습니다.")
        else:
            wrong["error_code"] = (
                wrong["error_code"].fillna("").astype(str).str.strip()
            )
            wrong = wrong[wrong["error_code"] != ""]

            if wrong.empty:
                st.info("오답 기록은 있으나 오류 코드가 저장되지 않았습니다.")
            else:
                counts = wrong["error_code"].value_counts()
                summary_rows = []
                for code_value, count in counts.items():
                    info = ERROR_FEEDBACK.get(
                        code_value,
                        {
                            "name": f"미분류 오류({code_value})",
                            "focus": "해당 풀이 단계를 다시 확인하세요.",
                        },
                    )
                    summary_rows.append(
                        {
                            "오류 코드": code_value,
                            "오류 유형": info["name"],
                            "발생 횟수": int(count),
                            "다음 학습 초점": info["focus"],
                        }
                    )
                st.dataframe(
                    pd.DataFrame(summary_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                top_code = counts.index[0]
                top = ERROR_FEEDBACK.get(top_code)
                if top:
                    st.info(
                        f"가장 빈번한 오류는 **{top['name']}**입니다. "
                        f"{top['focus']}"
                    )

        st.subheader("상세 학습 로그")
        display_columns = [
            "timestamp",
            "student_id",
            "level",
            "step_id",
            "response",
            "correct",
            "error_code",
            "hint_count",
            "attempt_number",
        ]
        available_columns = [c for c in display_columns if c in mine.columns]
        st.dataframe(
            mine[available_columns],
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "내 학습 로그 다운로드",
            mine[available_columns].to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{st.session_state.student_id}_learning_log.csv",
            mime="text/csv",
        )

        student_chat = pd.DataFrame(st.session_state.ai_chat_records)
        if not student_chat.empty:
            st.subheader("내 AI 튜터 대화 기록")
            chat_cols = [
                "timestamp", "level", "step_id", "role", "content",
                "selected_response", "error_code", "status",
            ]
            chat_cols = [c for c in chat_cols if c in student_chat.columns]
            st.dataframe(student_chat[chat_cols], use_container_width=True, hide_index=True)
            st.download_button(
                "내 AI 대화 로그 다운로드",
                student_chat[chat_cols].to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{st.session_state.student_id}_ai_chat_log.csv",
                mime="text/csv",
            )
    st.stop()

level_data = LEVELS[st.session_state.level]
steps = level_data["steps"]

st.subheader(level_data["title"])
st.markdown(latex_to_markdown(level_data["problem"]))
if "image" in level_data:
    st.image(level_data["image"], use_container_width=True)
st.progress(
    st.session_state.step / len(steps),
    text=f"진행 단계 {min(st.session_state.step + 1, len(steps))}/{len(steps)}",
)

if st.session_state.step >= len(steps):
    st.success(f"{st.session_state.level}수준을 완료했습니다.")
    render_feedback(st.session_state.level_errors)
    st.markdown("---")

    if st.session_state.level < 3:
        if st.button("피드백을 확인하고 다음 수준으로 이동", type="primary"):
            next_level()
            st.rerun()
    else:
        if st.button("피드백을 확인하고 최종 결과 보기", type="primary"):
            st.session_state.completed = True
            st.rerun()
    st.stop()

step = steps[st.session_state.step]
choices = option_letter_map(step["options"])

st.markdown("---")
st.markdown(f"### 단계 {st.session_state.step + 1}")
render_question(step["question"])

st.markdown("#### 선택지")
render_options(step["options"])

selected_letter = st.radio(
    "정답 기호를 선택하세요.",
    list(choices.keys()),
    index=None,
    horizontal=True,
    key=f"answer_{st.session_state.level}_{st.session_state.step}_{st.session_state.attempts}",
)

response = choices[selected_letter]["label"] if selected_letter else None

if selected_letter:
    st.caption(f"선택한 답: {selected_letter}")
    selected_label = choices[selected_letter]["label"]
    if is_formula_only(selected_label):
        st.latex(latex_body(selected_label))
    else:
        st.markdown(latex_to_markdown(selected_label))

c1, c2 = st.columns(2)

with c1:
    if st.button("정답 확인", type="primary", use_container_width=True, disabled=response is None):
        st.session_state.attempts += 1
        correct = response == step["answer"]
        error_code = None if correct else choices[selected_letter]["error_code"]

        save_log(
            st.session_state.level,
            step["id"],
            response,
            correct,
            error_code,
            st.session_state.hint_index,
            st.session_state.attempts,
        )

        st.session_state.answered = True
        st.session_state.last_correct = correct
        st.session_state.latest_error = error_code

        if error_code:
            st.session_state.level_errors.append(error_code)

        st.rerun()

with c2:
    if st.button("힌트 보기", use_container_width=True):
        if st.session_state.hint_index < len(step["hints"]):
            st.session_state.hint_index += 1
        st.rerun()

if st.session_state.hint_index > 0:
    hint_text = step["hints"][st.session_state.hint_index - 1]
    st.warning(f"힌트 {st.session_state.hint_index}")
    st.markdown(latex_to_markdown(hint_text))

if st.session_state.answered:
    if st.session_state.last_correct:
        st.success("정답입니다.")
        if st.button("다음 단계", type="primary"):
            reset_step()
            st.rerun()
    else:
        info = ERROR_FEEDBACK[st.session_state.latest_error]
        st.error(f"진단: {info['name']} ({st.session_state.latest_error})")
        st.markdown(latex_to_markdown(info["feedback"]))
        st.caption("힌트를 확인한 뒤 다시 답을 선택하세요.")



# 각 풀이 단계 하단의 대화형 AI 힌트
render_ai_tutor(
    st.session_state.level,
    level_data,
    step,
    selected_response=response,
    error_code=st.session_state.latest_error,
)
