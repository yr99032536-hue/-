# Paper Translate

로컬 Codex 플러그인 `paper-translate`는 Obsidian 볼트 안에 `thesis` 작업 폴더를 두고, 논문 PDF를 번역 노트로 정리하는 흐름을 다룬다.

## 워크스페이스 구조

플러그인의 기본 작업 폴더는 아래와 같다.

```text
thesis/
  pdf/   # 번역 대기 PDF
  fin/   # 번역 완료 후 이동된 PDF
  trn/   # 번역 마크다운 출력
```

## `/trans` 동작 규칙

`/trans` 요청을 받으면 Codex는 다음 순서로 처리한다.

1. `thesis/pdf` 폴더를 확인한다.
2. 안에 있는 PDF를 번역 대상으로 잡는다.
3. `scripts/trans.py prepare`로 PDF 본문, JSON, 이미지, 복합 그림을 추출한다.
4. 생성된 `thesis/trn/*__source.md`를 바탕으로 Codex가 번역 마크다운을 작성한다.
5. 번역 마크다운을 `thesis/trn`에 저장한다.
6. `scripts/trans.py finish`로 처리가 끝난 PDF를 `thesis/fin`으로 이동한다.

## 포함 내용

- `skills/paper-translate/SKILL.md`
  Codex가 `/trans`를 처리할 때 따를 규칙
- `scripts/setup_thesis_workspace.py`
  `thesis/pdf`, `thesis/fin`, `thesis/trn` 폴더 생성
- `scripts/trans.py`
  PDF 추출, 이미지 복사, 복합 그림 crop, 번역용 소스 노트 생성, 완료 PDF 이동
- `scripts/composite_figure_crop.py`
  복합 그림 감지 및 통합 crop 생성
- `requirements.txt`
  실행에 필요한 Python 패키지 목록

## 현재 상태

- 로컬 플러그인 구조와 기계적 파싱 실행기는 완성
- `thesis` 워크스페이스 초기화 스크립트 포함
- 실제 문장 번역은 Codex 스킬이 수행
- Codex marketplace 등록은 이 작업 환경에서 `.agents/plugins/` 경로 쓰기가 막혀 있어 보류

## 예시 사용

```text
/trans
```

또는

```bash
python3 plugins/paper-translate/scripts/setup_thesis_workspace.py \
  --vault "/home/iy/GDrive/Obsidian Vault"
```

PDF 파싱 준비:

```bash
python3 plugins/paper-translate/scripts/trans.py prepare \
  --vault "/home/iy/GDrive/Obsidian Vault"
```

번역 완료 PDF 이동:

```bash
python3 plugins/paper-translate/scripts/trans.py finish \
  --vault "/home/iy/GDrive/Obsidian Vault" \
  --manifest "/home/iy/GDrive/Obsidian Vault/thesis/trn/.paper-translate/OA-NBV.json"
```
