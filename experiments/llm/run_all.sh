#!/bin/zsh
# 받은 순서대로 후보를 Metal로 실행한다. 다운로드가 끝나고 sha256이 맞은 파일만 실행한다.
#   zsh experiments/llm/run_all.sh F C E A D
cd "$(dirname "$0")/../.."
export TMPDIR=$PWD/.cache-llm/tmp
for key in "$@"; do
  while true; do
    st=$(.venv-llm/bin/python -c "
import json,sys
try: d=json.load(open('results/exp_llm/downloads.json'))
except Exception: print('wait'); sys.exit()
r=d.get('$key')
print('wait' if r is None else ('ok' if r.get('match') else 'bad'))")
    [[ $st != wait ]] && break
    sleep 30
  done
  if [[ $st == ok ]]; then
    echo "=== $key 실행 $(date '+%H:%M:%S')"
    .venv-llm/bin/python experiments/llm/run_model.py --model $key --gpu -1 --tag metal > .cache-llm/run_$key.log 2>&1
    echo "=== $key 종료 코드 $? $(date '+%H:%M:%S')"
  else
    echo "=== $key 다운로드 실패 또는 sha256 불일치, 건너뜀"
  fi
done
