# MapleStory Janus Timer

게임 스킬 쿨다운을 감지하고 표시하는 데스크톱 오버레이 타이머.

지정한 키를 누르면 쿨다운 카운트다운이 뜨고, 끝나면 알림음이 울립니다. 일반 창과 "클릭이 통과하는 투명 오버레이"라는 두 얼굴(Janus)을 단축키로 오갈 수 있어, 게임 화면 위에 띄워둔 채로 플레이할 수 있습니다.

<!-- 스크린샷을 여기에 추가하세요 (일반 모드 / 오버레이 모드) -->
<!-- ![일반 모드](docs/normal.png) ![오버레이 모드](docs/overlay.png) -->

## 기능

- 전역 키 감지로 쿨다운 시작 (쿨다운 중 재입력은 무시)
- 카운트다운 숫자 + 배경이 아래에서 위로 밝아지는 진행 연출
- 완료 시 알림음 (wav / mp3, 볼륨 조절)
- 일반 / 오버레이(투명·항상 위·클릭 통과) 모드 토글
- 설정창에서 키·시간·크기·이미지·알림음·투명도 편집 후 즉시 반영
- 설정은 `settings.json`에 자동 저장

## 다운로드 (실행 파일)

[Releases](../../releases)에서 최신 `JanusTimer.zip`을 받아 압축을 풀고 `JanusTimer.exe`를 실행하세요. 파이썬 설치는 필요 없습니다.

```
JanusTimer.zip
├─ JanusTimer.exe
├─ background.png   (기본 배경 이미지)
└─ alarm.wav        (기본 알림음)
```

`background.png`와 `alarm.wav`는 같은 폴더에 두면 됩니다. 원하는 이미지·소리로 교체하거나, 설정창에서 다른 파일을 직접 지정할 수 있습니다.

## 조작

| 동작 | 방법 |
| --- | --- |
| 쿨다운 시작 | 트리거 키 (기본 `3`) |
| 오버레이 모드 토글 | `Ctrl+Alt+O` (설정에서 변경 가능) |
| 위치 이동 | 본문 드래그 (일반 모드) |
| 설정 / 종료 | 우클릭 (일반 모드) |

> 오버레이 모드는 클릭이 통과하므로 마우스로 잡을 수 없습니다. 위치를 옮기거나 설정을 열려면 먼저 `Ctrl+Alt+O`로 일반 모드로 돌아오세요.

## ⚠️ 관리자 권한

많은 게임이 관리자 권한으로 실행됩니다. 이 경우 **타이머도 관리자 권한으로 실행해야** 게임이 포커스를 잡고 있을 때 키 입력을 감지할 수 있습니다. Windows가 권한이 낮은 프로그램의 입력 후킹을 차단하기 때문이며, 코드로 우회할 수 없는 OS 차원의 정책입니다.

게임 중 키가 감지되지 않으면 `JanusTimer.exe`를 우클릭 → **관리자 권한으로 실행**하세요. (배포된 exe가 `--uac-admin`으로 빌드된 경우 실행 시 자동으로 권한을 요청합니다.)

## 소스에서 실행

요구사항: Python 3.9+

```bash
pip install -r requirements.txt
python janus_timer.py
```

## 직접 빌드 (PyInstaller)

```bash
pip install pyinstaller
```

안 쓰는 거대 모듈을 제외한 빌드 명령(한 줄):

```bash
pyinstaller --onefile --windowed --uac-admin --name JanusTimer --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick3D --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.Qt3DCore --exclude-module PySide6.Qt3DRender --exclude-module PySide6.Qt3DExtras --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtUiTools --exclude-module PySide6.QtBluetooth --exclude-module PySide6.QtNfc --exclude-module PySide6.QtSensors --exclude-module PySide6.QtSerialPort --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtLocation --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtWebChannel --exclude-module PySide6.QtWebView janus_timer.py
```

결과물은 `dist/JanusTimer.exe`에 생성됩니다. `QtNetwork`는 알림음(QtMultimedia)이 내부적으로 참조할 수 있어 제외하지 않았습니다.

## 라이선스

[MIT](LICENSE)
