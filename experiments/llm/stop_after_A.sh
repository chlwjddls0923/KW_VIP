#!/bin/zsh
# 3단계 변경(사용자 지시 2026-11-24): D(9B)는 제외한다.
# run_all.sh(F C E A D)가 A 실행을 마친 뒤 D 파일을 기다리는 반복(30초 sleep)에 들어가면 그 프로세스를 끝낸다.
#   zsh experiments/llm/stop_after_A.sh <run_all.sh PID>
cd "$(dirname "$0")/../.."
P=$1
LOG=.cache-llm/stop_after_A.log
echo "시작 $(date '+%F %T') run_all PID=$P" >> $LOG
until grep -q '^=== A 종료' .cache-llm/run_all.log; do sleep 10; done
echo "A 종료 확인 $(date '+%T'): $(grep '^=== A 종료' .cache-llm/run_all.log)" >> $LOG
sleep 2
ps -o pid,command -p $P >> $LOG 2>&1
pkill -TERM -P $P sleep 2>/dev/null     # D 대기 중인 sleep
kill -TERM $P 2>/dev/null && echo "run_all.sh(PID $P)에 SIGTERM 보냄 $(date '+%T')" >> $LOG
sleep 2
if ps -p $P >/dev/null; then echo "아직 살아 있음" >> $LOG; else echo "run_all.sh 종료 확인" >> $LOG; fi
