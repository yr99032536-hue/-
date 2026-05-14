# Paper Translate

로컬 플러그인 `paper-translate`는 Obsidian 볼트 안에 `논문` 작업 폴더를 두고, 논문 PDF를 번역 노트로 정리하는 흐름을 다룬다. Windows, Linux, macOS 모두 지원한다.

## 워크스페이스 구조

플러그인의 기본 작업 폴더는 아래와 같다.

```text
논문/
  pdf/   # 번역 대기 PDF
  fin/   # 번역 완료 후 이동된 PDF
  trn/   # 번역 마크다운 출력
```

## 설치

플러그인을 `<vault>/plugins/paper-translate`에 둔 상태에서 아래 명령을 실행한다. OS에 상관없이 동일하다.

```bash
python plugins/paper-translate/scripts/install.py
```

볼트 경로가 자동 감지되지 않으면 명시적으로 지정한다.

```bash
python plugins/paper-translate/scripts/install.py --vault "/path/to/Obsidian Vault"
```

가상환경 경로를 바꾸고 싶으면 `PAPER_TRANSLATE_VENV=/custom/path` 환경변수를 사용할 수 있다.

설치 스크립트는 다음을 한 번에 처리한다:

- OS 임시 디렉토리에 로컬 가상환경 생성
- Python 의존성 설치 (`opendataloader-pdf`, `PyMuPDF`)
- Java 확인 (없으면 설치 안내 출력)
- 레거시 `thesis/` 마이그레이션
- `논문/pdf`, `논문/fin`, `논문/trn` 폴더 생성
- 환경 점검 결과 출력

### 수동 설치

설치 스크립트 없이 직접 설치하려면:

```bash
pip install opendataloader-pdf>=2.4.1 PyMuPDF>=1.27.0
```

Java 11+도 필요하다:

- **Windows**: `winget install Microsoft.OpenJDK.21` 또는 https://adoptium.net/
- **Linux**: `sudo apt install openjdk-21-jdk`
- **macOS**: `brew install openjdk`

## `/trans` 동작 규칙

`/trans` 요청을 받으면 다음 순서로 처리한다.

1. `논문/pdf` 폴더를 확인한다.
2. 안에 있는 PDF를 번역 대상으로 잡는다.
3. `scripts/trans.py prepare`로 PDF 본문, JSON, 이미지, 복합 그림을 추출한다.
4. 생성된 `논문/trn/*__source.md`를 바탕으로 번역 마크다운을 작성한다.
5. 번역 마크다운을 `논문/trn`에 저장한다.
6. `scripts/trans.py finish`로 처리가 끝난 PDF를 `논문/fin`으로 이동한다.

`prepare`와 `finish`는 내부 단계다. 평소에는 사용자가 이 둘을 직접 순서대로 실행할 필요 없이, `/trans`를 요청하면 준비 추출과 완료 이동을 묶어서 처리한다.

## 번역 규칙

- 논문 제목도 번역하고, 원어는 괄호로 병기한다. 예: `3D 정보 추출 (3D Information Extraction)`
- 섹션 제목과 소제목도 번역 후 영어 원문을 병기한다. 예: `## III. 방법 (Methods)`, `### A. 3D 정보 추출 (3D Information Extraction)`
- 중요 전문 용어는 처음 등장할 때 괄호로 원어를 병기한다. 예: `합성곱(Convolution)`, `주의(Attention)`
- 수식과 참고문헌은 원문을 유지한다
- 수식은 항상 `$$ ... $$` 블록 수식으로 작성한다
- 알고리즘과 의사코드는 fenced code block으로 쓰지 않고 일반 마크다운 문단/번호 목록 형식으로 작성한다
- 복합 그림은 개별 조각 대신 통합 crop을 사용한다

## 포함 내용

- `skills/paper-translate/SKILL.md`
  `/trans`를 처리할 때 따를 규칙
- `scripts/install.py`
  크로스 플랫폼 설치 스크립트 (Windows, Linux, macOS)
- `scripts/install.sh`
  Linux/macOS용 bash 설치 스크립트 (레거시)
- `scripts/setup_workspace.py`
  `논문/pdf`, `논문/fin`, `논문/trn` 폴더 생성과 레거시 `thesis/` 마이그레이션
- `scripts/check_environment.py`
  Java와 Python 패키지 설치 상태 점검
- `scripts/trans.py`
  PDF 추출, 이미지 복사, 복합 그림 crop, 번역용 소스 노트 생성, 완료 PDF 이동
- `scripts/composite_figure_crop.py`
  복합 그림 감지 및 통합 crop 생성
- `requirements.txt`
  실행에 필요한 Python 패키지 목록

## 예시 사용

```text
/paper-translate
```

PDF 파싱 준비:

```bash
python plugins/paper-translate/scripts/trans.py prepare \
  --vault "$PWD"
```

번역 완료 PDF 이동:

```bash
python plugins/paper-translate/scripts/trans.py finish \
  --vault "$PWD" \
  --manifest "$PWD/논문/trn/.paper-translate/paper.json"
```
