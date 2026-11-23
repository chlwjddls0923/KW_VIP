#!/bin/zsh
# 3단계: CPU 재실행(n_gpu_layers=0) 2회와 비교. cpu_selection.json의 (모델, 변형)을 한 번에 하나씩 실행한다.
#   zsh experiments/llm/run_cpu.sh
cd "$(dirname "$0")/../.."
export TMPDIR=$PWD/.cache-llm/tmp
PY=.venv-llm/bin/python
LOG=.cache-llm/run_cpu.log
pairs=$($PY -c "
import json; d=json.load(open('results/exp_llm/cpu_selection.json'))
print(' '.join(f\"{c['model']}:{c['name']}:{c['variant']}\" for c in d['chosen']))")
for tag in cpu1 cpu2; do
  for p in ${=pairs}; do
    k=${p%%:*}; rest=${p#*:}; name=${rest%%:*}; v=${rest#*:}
    extra=(); [[ $k == C ]] && extra=(--template experiments/llm/templates/kanana_fixed.jinja)
    echo "=== $tag $k $v 실행 $(date '+%T')" >> $LOG
    $PY experiments/llm/run_model.py --model $k --gpu 0 --tag ${tag}_$v --variants $v $extra > .cache-llm/run_${k}_${tag}_$v.log 2>&1
    echo "=== $tag $k $v 종료 코드 $? $(date '+%T')" >> $LOG
    # run_model은 raw_{name}_{v}_{tag}.jsonl로 쓰므로 tag에 변형을 붙인 이름을 표준 이름으로 바꾼다
    mv results/exp_llm/raw_${name}_${v}_${tag}_$v.jsonl results/exp_llm/raw_${name}_${v}_${tag}.jsonl
  done
done
for p in ${=pairs}; do
  rest=${p#*:}; name=${rest%%:*}; v=${rest#*:}
  $PY experiments/llm/compare_runs.py $name $v metal cpu1 >> $LOG
  $PY experiments/llm/compare_runs.py $name $v cpu1 cpu2 >> $LOG
done
$PY experiments/llm/combine.py --tag cpu1 > .cache-llm/combine_cpu1.log 2>&1
echo "=== 끝 $(date '+%T')" >> $LOG
