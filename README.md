# Paper Translate

로컬 Codex 플러그인 `paper-translate`는 Obsidian 볼트 안에 `논문` 작업 폴더를 두고, 논문 PDF를 번역 노트로 정리하는 흐름을 다룬다.

## 워크스페이스 구조

플러그인의 기본 작업 폴더는 아래와 같다.

```text
논문/
  pdf/   # 번역 대기 PDF
  fin/   # 번역 완료 후 이동된 PDF
  trn/   # 번역 마크다운 출력
```

## 설치

플러그인을 `<vault>/plugins/paper-translate`에 둔 상태라면, 플러그인 폴더에서 아래 명령을 한 번 실행하면 된다.

```bash
cd "<vault>/plugins/paper-translate"
bash scripts/install.sh
```

Java가 없는 apt 기반 Linux에서는 아래처럼 Java 설치까지 함께 시도할 수 있다.

```bash
cd "<vault>/plugins/paper-translate"
bash scripts/install.sh \
  --install-java
```

볼트 루트에서 실행하고 싶다면 아래처럼 명시적으로 볼트 경로를 넘기면 된다.

```bash
bash plugins/paper-translate/scripts/install.sh --vault "$PWD"
```

설치 스크립트는 `/tmp` 아래 로컬 가상환경 생성, Python 패키지 설치, Java 확인, 레거시 `thesis/` 마이그레이션, `논문` 폴더 생성을 한 번에 처리한다. 가상환경 경로를 바꾸고 싶으면 `PAPER_TRANSLATE_VENV=/custom/path` 환경변수를 사용할 수 있다.

## `/trans` 동작 규칙

`/trans` 요청을 받으면 Codex는 다음 순서로 처리한다.

1. `논문/pdf` 폴더를 확인한다.
2. 안에 있는 PDF를 번역 대상으로 잡는다.
3. `scripts/trans.py prepare`로 PDF 본문, JSON, 이미지, 복합 그림을 추출한다.
4. 생성된 `논문/trn/*__source.md`를 바탕으로 Codex가 번역 마크다운을 작성한다.
5. 번역 마크다운을 `논문/trn`에 저장한다.
6. `scripts/trans.py finish`로 처리가 끝난 PDF를 `논문/fin`으로 이동한다.

`prepare`와 `finish`는 내부 단계다. 평소에는 사용자가 이 둘을 직접 순서대로 실행할 필요 없이, Codex에서 `/trans`를 요청하면 준비 추출과 완료 이동을 묶어서 처리한다.

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
  Codex가 `/trans`를 처리할 때 따를 규칙
- `scripts/setup_workspace.py`
  `논문/pdf`, `논문/fin`, `논문/trn` 폴더 생성과 레거시 `thesis/` 마이그레이션
- `scripts/install.sh`
  로컬 가상환경 생성, Python 의존성 설치, Java 확인, 워크스페이스 생성
- `scripts/check_environment.py`
  Java와 Python 패키지 설치 상태 점검
- `scripts/trans.py`
  PDF 추출, 이미지 복사, 복합 그림 crop, 번역용 소스 노트 생성, 완료 PDF 이동
- `scripts/composite_figure_crop.py`
  복합 그림 감지 및 통합 crop 생성
- `requirements.txt`
  실행에 필요한 Python 패키지 목록

## 현재 상태

- 설치 스크립트 포함
- 로컬 플러그인 구조와 기계적 파싱 실행기 포함
- `논문` 워크스페이스 자동 생성
- 실제 문장 번역은 Codex 스킬이 수행
- Codex marketplace 등록은 이 작업 환경에서 `.agents/plugins/` 경로 쓰기가 막혀 있어 보류

## 예시 사용

```text
/trans
```

또는

```bash
bash plugins/paper-translate/scripts/install.sh \
  --vault "$PWD"
```

PDF 파싱 준비:

```bash
python3 plugins/paper-translate/scripts/trans.py prepare \
  --vault "$PWD"
```

번역 완료 PDF 이동:

```bash
python3 plugins/paper-translate/scripts/trans.py finish \
  --vault "$PWD" \
  --manifest "$PWD/논문/trn/.paper-translate/paper.json"
```
