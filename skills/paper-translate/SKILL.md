---
name: paper-translate
description: thesis/pdf의 논문 PDF를 번역하고, 결과 마크다운을 thesis/trn에 만들고, 처리 완료 PDF는 thesis/fin으로 이동한다.
---

# Paper Translate

학술 논문 PDF를 한국어 Obsidian 노트로 재구성한다. 이 플러그인은 Obsidian 볼트 안의 `thesis` 작업 폴더를 기준으로 동작한다.

## 기본 폴더 구조

```text
thesis/
  pdf/
  fin/
  trn/
```

- `thesis/pdf`: 번역 대기 PDF 입력 폴더
- `thesis/fin`: 번역 완료 후 원본 PDF 이동 폴더
- `thesis/trn`: 번역 마크다운 출력 폴더

필요하면 `scripts/setup_thesis_workspace.py` 로 폴더를 생성한다.

## 설치 규칙

플러그인 설치 또는 초기 준비 요청을 받으면 아래 명령을 기본으로 사용한다.

```bash
bash plugins/paper-translate/scripts/install.sh --vault "<vault>"
```

Java가 없고 사용자가 시스템 설치까지 원하면 아래 명령을 사용한다.

```bash
bash plugins/paper-translate/scripts/install.sh --vault "<vault>" --install-java
```

이 설치 스크립트는 Python 의존성 설치, Java 확인, `thesis` 폴더 생성을 처리한다.

## 언제 사용하나

- 사용자가 `/trans`를 입력했을 때
- 사용자가 thesis 폴더 안의 논문들을 번역하라고 요청했을 때

## `/trans` 처리 규칙

`/trans` 요청을 받으면 아래 순서를 따른다.

1. 볼트 루트에 `thesis/pdf`, `thesis/fin`, `thesis/trn`가 없으면 생성한다.
2. `thesis/pdf` 안의 PDF 파일 목록을 확인한다.
3. PDF가 여러 개면 전부 순서대로 처리한다.
4. 각 PDF마다:
   - `python3 plugins/paper-translate/scripts/trans.py prepare --vault "<vault>" --pdf "<pdf>"` 로 추출한다
   - 생성된 `thesis/trn/{파일명}__source.md`와 manifest를 읽는다
   - 제목과 소제목은 영어 원문 병기 규칙으로 번역한다
   - 번역 노트를 `thesis/trn/{파일명} 번역.md` 로 저장한다
   - `python3 plugins/paper-translate/scripts/trans.py finish --vault "<vault>" --manifest "<manifest>"` 로 완료된 PDF를 `thesis/fin/` 으로 이동한다

## 전제 조건

- `java -version` 이 정상 동작해야 한다
- `pip show opendataloader-pdf` 로 패키지가 설치되어 있어야 한다
- GUI가 없는 환경에서는 `JAVA_TOOL_OPTIONS='-Djava.awt.headless=true'` 를 붙여 추출한다

## 번역 규칙

- 제목: `번역 제목 (Original Title)`
- 섹션 제목과 소제목도 영어 원문 병기
- 전문 용어는 처음 등장할 때 원어 병기
- 수식과 참고문헌은 원문 유지
- 수식은 항상 `$$ ... $$` 블록 수식으로 작성한다
- 알고리즘과 의사코드는 fenced code block으로 쓰지 말고, 일반 마크다운 문단/번호 목록 형식으로 작성한다
- 복합 그림은 개별 조각 대신 통합 crop 사용

## 복합 그림 처리

같은 페이지에서 작은 `image` 요소가 여러 개 격자 형태로 밀집해 있으면 복합 그림 후보로 본다. 이 경우 `scripts/composite_figure_crop.py` 로:

- 이미지 묶음의 bounding box를 합치고
- 상단/좌측 라벨 텍스트를 포함하도록 영역을 넓히고
- PDF에서 통째로 crop한 PNG를 만든다

노트에는 개별 이미지 여러 장 대신 이 통합 이미지 한 장만 넣는다.

## 참고 스크립트

설치 및 환경 준비:

```bash
bash plugins/paper-translate/scripts/install.sh \
  --vault "/path/to/Obsidian Vault"
```

환경 점검:

```bash
python3 plugins/paper-translate/scripts/check_environment.py \
  --vault "/path/to/Obsidian Vault"
```

PDF 파싱 준비:

```bash
python3 plugins/paper-translate/scripts/trans.py prepare \
  --vault "/path/to/Obsidian Vault"
```

완료 PDF 이동:

```bash
python3 plugins/paper-translate/scripts/trans.py finish \
  --vault "/path/to/Obsidian Vault" \
  --manifest "/path/to/Obsidian Vault/thesis/trn/.paper-translate/paper.json"
```

복합 그림 crop:

```bash
python3 plugins/paper-translate/scripts/composite_figure_crop.py \
  --pdf "/path/to/paper.pdf" \
  --json "/tmp/paper-123/paper.json" \
  --out-dir "/path/to/vault/_attachments/paper/composite"
```
