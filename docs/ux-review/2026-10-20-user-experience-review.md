# kiwi-threejs-pet 사용자 경험 검토

검토일: 2026-10-20. 기준은 당시 기본 브랜치 `main`의 [2e6079f866f59a48bbc12546b44f7e986ce00ff8](https://github.com/207studio-founder/kiwi-threejs-pet/commit/2e6079f866f59a48bbc12546b44f7e986ce00ff8)다. 이후 변경과 실제 배포 상태는 이 판단에 포함하지 않는다.

## 판단 범위와 증거 수준

파일 트리 53개 항목을 조사했다. 아래 manifest는 모든 파일을 검토 구간 또는 미검토·제외로 분류한다. 핵심 여정의 소스 검토이며, 저장소 전체 의미 검토 완료를 뜻하지 않는다.

- 소스로 확인: 고정 커밋의 텍스트·코드에서 직접 확인한 사실이다.
- 실제 관찰: 이번에는 앱·서비스·브라우저·설치·빌드·Actions를 실행하지 않았다. 사용자 동작·이미지 픽셀·성능의 실제 관찰은 없다.
- 추론: 확인한 경로에서 예상하는 사용자 영향·원인 가설이다. 발생 빈도나 실제 장애로 단정하지 않는다.
- 추가 실험 필요: 합성 입력으로 수행할 검증 계획이다. 이번 실행 결과가 아니다. 시간·속도·메모리·배터리·비용은 모두 미측정이다.

이 공개 보고서는 이 공개 저장소의 소스와 파일 트리만 근거로 썼다. 다른 저장소·개인 대화·운영 정보는 근거로 사용하지 않았다.

재귀 파일 트리에 루트 `AGENTS.md`와 `.agents/skills/**/SKILL.md` 항목은 없었다. 포함된 관련 AGENTS 문서가 있으면 manifest의 검토 구간에 표시했다. 보존된 스킬은 검토 대상 자료로 읽었으며 실제 작업·설치 지시로 실행하지 않았다.

## 사용자 목적과 핵심 여정

Codex용 펫을 설치하거나 WebGL 뷰어에서 상태를 살피고 atlas를 만드는 프로젝트다. 설치 사용자의 첫 펫 표시와 제작자의 첫 미리보기·안전한 내보내기를 구분한다.

README → 준비된 펫 설치 또는 로컬 미리보기 → 상태·각도 조작 → 일시정지 → atlas 내보내기 → 실패 원인 확인·기존 산출물 보존.

미리 만든 패키지와 재생성 경로를 나누고 지원을 확인하지 않은 브라우저를 명시한다. 현재 builder는 입력 preflight를 출력 생성 전에 수행한다. 과거 감사 문서의 보호가 현재 코드에 있는지 다시 확인했으며 과거 로그나 이미지 검증을 이번 실험으로 주장하지 않는다.

## 제안과 우선순위

P1은 핵심 여정의 실패·결과 보존 위험을 먼저 확인할 항목이다. P2는 복구·예측 가능성·지속 사용을 개선할 항목이다. 우선순위는 실측 발생률이 아닌 소스 경로와 사용자 영향에 대한 판단이다.

### 1. P1 · 다운로드 중단 뒤 부분 설치를 재시도 가능한 상태로 만들기

소스로 확인: 빠른 설치 예시는 대상 폴더를 먼저 만들고 pet.json·spritesheet.webp를 순차 다운로드한다. 기존 경로가 있으면 종료하는 분기다. 두 번째 다운로드가 실패해도 폴더가 남아 다음 실행은 이미 존재한다는 안내로 끝난다.

근거: [README.md](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/README.md#L13-L29).

추론: 네트워크 중단 뒤 사용자는 설치가 끝났는지 판단하기 어렵고, 재실행으로 복구할 수 없다. 실제 다운로드나 설치는 수행하지 않았다.

원인 가설: 기존 설치 보호와 신규 설치 완료 상태를 같은 디렉터리 존재 검사로 판정한다.

권장 방향: 별도 변경에서 임시 위치에 파일 쌍을 준비·검증한 뒤 게시하고, 정상 기존 설치와 부분 실패를 구분하는 방향을 제안한다. 문서에는 중단·재시도·이전 설치 보존 안내를 먼저 추가한다.

이득과 회귀 위험: 이득은 실패 복구와 첫 설치 성공률이다. 회귀 위험은 복구 편의를 위해 기존 설치를 덮어쓰거나 불완전한 파일을 정상으로 인정하는 것이다.

측정·수용 기준: 추가 실험 필요: 합성 다운로드로 첫 파일·두 번째 파일 실패, 기존 디렉터리·dangling symlink를 구분한다. 수용 기준은 부분 실패가 정상 설치로 표시되지 않고 기존 설치를 보존한 채 재개할 수 있는 것이다. 설치·복구 시간은 미측정.

단계별 우선순위: 1단계 부분 실패 문서 → 2단계 별도 변경의 staging 설계 → 3단계 합성 실패·복원 확인.

### 2. P1 · atlas 내보내기를 하나의 작업으로 관리하고 취소·실패를 끝내기

소스로 확인: exportCodexAtlas는 같은 stage 경로에 프레임을 순차 저장한 뒤 build를 요청한다. 버튼은 작업 중에도 새 호출을 시작할 수 있고 작업 ID·AbortSignal을 받지 않는다. 서버는 build 요청마다 자식 프로세스를 시작한다. preflight는 입력 무결성을 먼저 확인하지만 여러 파일의 crash-atomic 게시나 동시 실행을 보장하지 않는다.

근거: [exportCodexAtlas](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/src/pet-main.js#L59-L82); [stage/build endpoints](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/server.mjs#L26-L45); [validate_stage_inputs](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/tools/build_codex.py#L67-L99); [docs/audit/2026-10-20-atlas-preflight.md](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/docs/audit/2026-10-20-atlas-preflight.md#L18-L20).

추론: 연속 클릭으로 파일 저장·빌드가 겹칠 수 있고, 긴 빌드 중에는 마지막 stage 상태만 보여 진행과 중단을 판단하기 어렵다. 산출물이 실제로 손상됐다는 관찰은 없다.

원인 가설: 내보내기가 프레임 저장·프로세스 실행의 연결이며, 화면과 엔진이 공유하는 작업 수명 계약이 없다.

권장 방향: 단일 작업 guard·작업 ID·렌더/저장/빌드 상태·명시적 취소·마지막 정상 출력 보존을 제안한다. UI는 상태와 입력을 담당하고 엔진은 작업·임시 출력·검증·게시를 담당하게 한다. 기존 preflight 보호를 유지한다.

이득과 회귀 위험: 이득은 결과 신뢰도와 조작 반응이다. 회귀 위험은 취소가 기존 정상을 지우거나 작업 잠금이 실패 후 풀리지 않는 것이다.

측정·수용 기준: 추가 실험 필요: 실제 그림 없이 합성 stage·지연 서버로 연속 클릭, 저장 실패, build 실패, 취소, 재시도를 검증한다. 첫 상태 표시·입력 지연·전체 빌드 시간·취소 후 쓰기·정상 출력 보존을 따로 측정한다. 수용 기준은 작업이 겹치지 않고 끝 상태가 명확하며 마지막 정상이 유지되는 것이다. 모든 시간은 미측정.

단계별 우선순위: 1단계 상태·실패·작업 중 안내 → 2단계 별도 변경의 작업 수명·취소 설계 → 3단계 합성 실패와 게시 검증.

### 3. P2 · 일시정지 때 불필요한 다시 그리기를 줄이고 조작 반응을 따로 측정하기

소스로 확인: v2 tick은 playing이 false여도 렌더·두 미리보기 복사·readout 갱신과 다음 rAF 예약을 수행한다. v1 frame도 일시정지 때 renderer.render와 미리보기 복사를 계속한다. v1 ZIP은 프레임·바이트 배열을 모은 후 동기 zipStore로 새 버퍼를 만든다.

근거: [tick](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/src/pet-main.js#L74-L102); [frame](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/src/main.js#L60-L74); [renderSequence/downloadZip](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/src/main.js#L91-L132); [zipStore](https://github.com/207studio-founder/kiwi-threejs-pet/blob/2e6079f866f59a48bbc12546b44f7e986ce00ff8/src/zip.js#L14-L40).

추론: 정지 화면에서도 GPU·CPU 작업을 계속할 수 있고 큰 ZIP 준비가 입력 반응과 peak memory에 영향을 줄 수 있다. 실제 발열·배터리 소모·입력 지연은 관찰하지 않았다.

원인 가설: 재생 루프와 화면 변경 시 갱신을 구분하지 않고 내보내기 버퍼를 전부 유지한다.

권장 방향: 정지·숨김 상태에서는 변경이 있을 때만 그리는 설계를 제안한다. ZIP 생성은 먼저 실제 long task와 peak memory를 측정한 뒤 청크 처리·worker·스트리밍의 필요성을 판단한다. 다른 언어로 바꾸면 빨라진다는 전제는 두지 않는다.

이득과 회귀 위험: 이득은 조용한 정지 상태와 내보내기 중 조작 반응이다. 회귀 위험은 상태·각도·배경 변경 때 화면이 갱신되지 않거나 내보내기 프레임과 미리보기가 달라지는 것이다.

측정·수용 기준: 추가 실험 필요: 합성 그림으로 재생·정지·숨김·내보내기를 나눠 render 호출 수, 입력 이벤트→표시 지연, long task, peak RSS/GPU memory, 전체 처리 시간을 기록한다. 수용 기준은 정지 후 불필요한 렌더가 멈추고 사용자 변경은 반영되며 결과 계약이 유지되는 것이다. 수치 모두 미측정.

단계별 우선순위: 1단계 계측 계획·정지 계약 → 2단계 변경 시 렌더 설계 → 3단계 실측 후 내보내기 메모리 개선 선택.

## 검토 축별 판단

| 축 | 이번 판단·한계 |
| --- | --- |
| 사용자 목적·핵심 여정 | 설치와 제작·내보내기의 사용자 목적을 분리했다. |
| 입력 반응성·메인 스레드 | rAF 정지 분기와 동기 ZIP 경로는 소스로 확인했다. 실제 입력 지연은 미측정이다. |
| 자료 준비·첫 유용한 결과 | loadPet은 준비를 await한 뒤 UI를 연결한다. 네트워크·텍스처 해독·첫 프레임 시간은 미측정이다. |
| 로딩·취소·진행 | stage 진행·최종 exit 표시가 있다. 전체 작업 취소·중복 작업 수명은 P1이다. |
| 저장·실패·복구·Undo·오프라인 | 입력 preflight를 확인했다. 설치 부분 실패·동시 내보내기·마지막 정상 보존은 추가 실험 대상이다. |
| 발견 가능성·일관성·접근성 | pet.html의 상태 select·status와 canvas 구조를 읽었다. 실제 키보드·스크린 리더·대비·픽셀은 미검증이다. |
| 메모리·발열·배터리·비용 | 정지 중 작업과 버퍼 축적은 소스로 확인했다. 실제 메모리·발열·배터리는 추론·미측정이다. |
| 화면과 엔진의 책임 | 리그·포즈·화면은 분리되어 있다. export 작업 상태를 엔진과 화면 사이 계약으로 다룰 필요가 있다. |

빠른 전체 처리와 즉각적인 조작 반응은 별도 결과다. 기술·언어 교체를 성능 개선의 증거로 취급하지 않는다. 먼저 준비·첫 상태·입력 반응·전체 완료·복구를 나눠 측정한다.

## 미검토·제외 범위와 다음 검토

핵심 설치·v1/v2 UI·서버·리그 일부·builder 일부를 검토했다. 나머지 리그 수학·에셋 준비 도구·테스트·metadata·의존성·생성물은 전체 의미 검토 미완료다. 이미지·원본 그림·실제 펫·브라우저를 열지 않았다.

바이너리와 이미지의 시각 품질은 확인하지 않았다. 코드에 이미지 로딩·렌더링이 있다는 사실을 실제 이미지 검토로 취급하지 않는다. 실제 사용자 자료·개인 노트·원고·iCloud·인증 정보는 다음 실험에도 사용하지 않는다.

다음 검토는 manifest의 미검토 1차 소스 중 위 여정의 호출자·실패 경로를 먼저 좁혀 진행한다. 외부 의존성·보존 구현의 전체 검토, 호스트 동작, 실제 배포물의 일치 여부는 별도 범위다. 이번 제안만으로 그 범위가 완료되었다고 표시하지 않는다.

## 검토 manifest

GitHub Git Trees API의 고정 커밋 재귀 목록을 사용했다. 목록은 `truncated=false`였다. 파일 내용은 트리를 먼저 확인하고 지정한 소스 허용 목록에서만 읽었다. 전체 저장소 내용을 자동 실행·샘플링하는 검사는 하지 않았다. 표의 구간 밖은 읽은 파일 안에서도 의미 검토 완료로 계산하지 않는다.

| 분류 | 파일 수 |
| --- | ---: |
| 미검토: 의존성·빌드 metadata | 3 |
| 미검토: 1차 소스·참조 문서 | 9 |
| 검토 구간 있음 | 11 |
| 제외: 바이너리·이미지·배포물 | 19 |
| 미검토: 생성물·파생 metadata | 3 |
| 미검토: 과거 검증·로그 | 6 |
| 미검토: 테스트·실험 소스 | 2 |

| 파일 | 검토 상태 |
| --- | --- |
| `.gitignore` | 미검토: 의존성·빌드 metadata |
| `ARTWORK.md` | 미검토: 1차 소스·참조 문서 |
| `LICENSE` | 미검토: 1차 소스·참조 문서 |
| `README.md` | 검토 구간 1-119 |
| `assets/derived/alpha_matte.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/base.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/eyes.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/front_crop.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/front_legs.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/front_masks.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/layout.json` | 미검토: 생성물·파생 metadata |
| `assets/derived/plate.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_base.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_crop.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_eye.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_layout.json` | 미검토: 생성물·파생 metadata |
| `assets/derived/side_masks.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_masks2.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/side_plate.png` | 제외: 바이너리·이미지·배포물 |
| `assets/derived/warp.png` | 제외: 바이너리·이미지·배포물 |
| `assets/source/kiwi_turnaround.webp` | 제외: 바이너리·이미지·배포물 |
| `dist/kiwi-2d/pet.json` | 미검토: 생성물·파생 metadata |
| `dist/kiwi-2d/spritesheet.webp` | 제외: 바이너리·이미지·배포물 |
| `docs/audit/2026-10-20-atlas-preflight.md` | 검토 구간 1-20 |
| `docs/audit/2026-10-20-side-rig-dispatch.md` | 검토 구간 1-18 |
| `docs/audit/atlas-preflight-baseline-final.log` | 미검토: 과거 검증·로그 |
| `docs/audit/atlas-preflight-baseline.log` | 미검토: 과거 검증·로그 |
| `docs/audit/atlas-preflight-candidate-final.log` | 미검토: 과거 검증·로그 |
| `docs/audit/atlas-preflight-candidate.log` | 미검토: 과거 검증·로그 |
| `docs/audit/side-rig-baseline.log` | 미검토: 과거 검증·로그 |
| `docs/audit/side-rig-candidate.log` | 미검토: 과거 검증·로그 |
| `docs/kiwi_promo.gif` | 제외: 바이너리·이미지·배포물 |
| `docs/kiwi_promo_en.gif` | 제외: 바이너리·이미지·배포물 |
| `docs/kiwi_thumb.png` | 제외: 바이너리·이미지·배포물 |
| `index.html` | 미검토: 1차 소스·참조 문서 |
| `package-lock.json` | 미검토: 의존성·빌드 metadata |
| `package.json` | 검토 구간 1-12 |
| `pet.html` | 검토 구간 1-42 |
| `requirements.txt` | 미검토: 의존성·빌드 metadata |
| `server.mjs` | 검토 구간 1-55 |
| `src/kiwi.js` | 미검토: 1차 소스·참조 문서 |
| `src/main.js` | 검토 구간 1-139 |
| `src/pet-main.js` | 검토 구간 1-105 |
| `src/pet.js` | 검토 구간 1-105,168-277 |
| `src/poses.js` | 미검토: 1차 소스·참조 문서 |
| `src/zip.js` | 검토 구간 1-41 |
| `tests/test_atlas_preflight.py` | 미검토: 테스트·실험 소스 |
| `tests/test_rig_dispatch.py` | 미검토: 테스트·실험 소스 |
| `tools/build_codex.py` | 검토 구간 1-115,170-231 |
| `tools/prepare_assets.py` | 미검토: 1차 소스·참조 문서 |
| `tools/prepare_rig.py` | 미검토: 1차 소스·참조 문서 |
| `tools/prepare_side.py` | 미검토: 1차 소스·참조 문서 |
| `tools/verify_frames.py` | 미검토: 1차 소스·참조 문서 |

## 문서 품질 확인과 변경 경계

고정 커밋의 파일·심볼·행 링크, manifest 누락·중복, 근거와 추론 구분, 미측정 표기, 공개 근거 경계를 확인한다. PR diff는 이 Markdown 문서 한 개 추가만 허용한다. 제품·테스트·설정·의존성·워크플로는 변경하지 않는다. 원본 코드·민감한 로그는 복사하지 않았다. 성능·기능 테스트는 수행하지 않았고, 앱 실행·설치·Actions·자동 리뷰 요청·병합·배포는 하지 않는다.
