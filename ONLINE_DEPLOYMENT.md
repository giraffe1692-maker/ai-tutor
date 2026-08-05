# 온라인 다중 사용자 배포 안내

## 구성

- 화면: Streamlit
- 호스팅: Streamlit Community Cloud
- 중앙 데이터베이스: Supabase PostgreSQL
- 학생별 브라우저 세션: Streamlit `session_state`
- 전체 응답 저장: Supabase `learning_logs`
- 관리자 화면: Secrets에 저장한 비밀번호로 보호

## 1. Supabase 데이터베이스 만들기

1. Supabase에서 새 프로젝트를 만듭니다.
2. SQL Editor를 엽니다.
3. `supabase_schema.sql`의 내용을 붙여 넣고 실행합니다.
4. Project Settings → API에서 다음 값을 확인합니다.
   - Project URL
   - `service_role` key

`service_role` key는 관리자 권한이므로 GitHub에 올리면 안 됩니다.

## 2. GitHub 저장소 만들기

이 폴더의 파일을 GitHub 저장소에 올립니다.

다음 파일은 올리지 않습니다.

- `.streamlit/secrets.toml`
- `learning_log.csv`

`.gitignore`에 이미 등록되어 있습니다.

## 3. Streamlit Community Cloud 배포

1. Streamlit Community Cloud에 GitHub 계정으로 로그인합니다.
2. Create app을 선택합니다.
3. 저장소와 브랜치를 선택합니다.
4. Main file path를 `app.py`로 설정합니다.
5. Advanced settings → Secrets에 다음 내용을 입력합니다.

```toml
admin_password = "충분히 긴 관리자 비밀번호"

[supabase]
url = "https://YOUR_PROJECT.supabase.co"
service_role_key = "YOUR_SERVICE_ROLE_KEY"
```

6. Deploy를 누릅니다.
7. 생성된 URL을 학생들에게 공유합니다.

## 4. 여러 학생이 동시에 사용하는 방식

- 각 학생 브라우저에는 독립적인 Streamlit 세션이 생성됩니다.
- 각 시작 시 고유한 `session_uuid`가 생성됩니다.
- 학생이 같은 ID를 입력해도 세션 UUID로 서로 구분됩니다.
- 모든 응답은 중앙 Supabase 테이블에 저장됩니다.
- 학생 결과 화면은 자신의 현재 세션만 보여 줍니다.
- 연구자 관리자 화면에서는 전체 학생의 기록을 조회할 수 있습니다.

## 5. 연구자 관리자 화면

왼쪽 메뉴에서 `연구자 관리자 화면`을 선택합니다.

Streamlit Secrets의 `admin_password`를 입력하면 다음 내용을 확인할 수 있습니다.

- 전체 학생 수
- 전체 세션 수
- 전체 정답률
- 오류 유형별 빈도
- 학생별 진행 현황
- 전체 상세 로그
- 전체 CSV 다운로드

## 6. 연구 적용 전 권장사항

- 학습자 ID에는 실명이나 학번 전체를 사용하지 않습니다.
- 연구용 익명 코드표는 앱 밖에서 별도로 보관합니다.
- 개인정보 처리, 연구 동의 및 IRB 절차를 확인합니다.
- 실제 적용 전 3~5명으로 동시 접속과 데이터 저장을 시험합니다.


## 7. AI 튜터 기능 연결

OpenAI API 키를 발급한 후 Streamlit Community Cloud의 Secrets에 추가합니다.

```toml
[openai]
api_key = "YOUR_OPENAI_API_KEY"
model = "gpt-4.1-mini"
```

전체 Secrets 예시는 다음과 같습니다.

```toml
admin_password = "충분히 긴 관리자 비밀번호"

[supabase]
url = "https://YOUR_PROJECT.supabase.co"
service_role_key = "YOUR_SERVICE_ROLE_KEY"

[openai]
api_key = "YOUR_OPENAI_API_KEY"
model = "gpt-4.1-mini"
```

주의사항:

- API 키를 `app.py`나 GitHub 저장소에 직접 입력하지 않습니다.
- OpenAI API 사용에는 별도의 사용 요금이 발생합니다.
- 모델 이름은 계정에서 사용할 수 있는 모델로 변경할 수 있습니다.
- 현재 앱은 학생 한 세션당 AI 튜터 호출을 20회로 제한합니다.
- AI 튜터는 시스템 지침에 따라 정답 대신 단계적 힌트를 제공하도록 설계되어 있습니다.


## AI 대화 로그 테이블 추가
기존 Supabase 프로젝트에서는 SQL Editor에서 `supabase_ai_chat_migration.sql`을 실행하세요. 연구 동의서에는 AI 대화 저장 사실과 이용 목적을 명시하세요.
