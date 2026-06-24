# Orbit Wars

Kaggle 대회용 게임 AI 에이전트. PyTorch 기반 멀티플레이어 전략 봇.

## 에이전트

| 파일 | 설명 |
|---|---|
| `agent_2p.py` | 2인 플레이용 에이전트 |
| `agent_mp.py` | 멀티플레이어 에이전트 |
| `main.py` | 대회 제출 진입점 |

## 실행

```bash
pip install -r requirements.txt
python play.py
```

## 구조

```
orbit_lite/         # 게임 로직 라이브러리
notebooks/          # 분석 노트북
scratch/            # 실험 스크립트
```
