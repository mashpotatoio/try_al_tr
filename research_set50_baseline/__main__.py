"""PowerShell entry point: python -X utf8 -B -m research_set50_baseline COMMAND."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from .data import PACKAGE, ROOT, config, new_experiment, native_days, read_history, validate, write_json
from .runner import run_daily, run_native, daily_schedule
from .evaluation import make_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["validate","smoke","run-native","run-daily","report","_worker"])
    parser.add_argument("--config")
    parser.add_argument("--experiment")
    parser.add_argument("--job")
    args=parser.parse_args()
    if args.command=="_worker":
        job=json.loads(Path(args.job).read_text())
        run_native(**job)
        return
    if args.command=="report":
        if not args.experiment:
            parser.error("--experiment is required")
        path=Path(args.experiment)
        if not path.is_dir():
            path=PACKAGE/"experiments"/args.experiment
        make_report(path)
        print(path/"reports")
        return
    c=config(args.config)
    experiment=new_experiment(args.command,c)
    print(f"EXPERIMENT {experiment}",flush=True)
    try:
        if args.command=="validate":
            print(validate(experiment),flush=True)
        elif args.command in ("smoke","run-native"):
            days=native_days(c)
            if args.command=="smoke":
                days=days[:2]
            schedule=[dict(period_id="native_"+str(len(days))+"sessions",role="smoke" if args.command=="smoke" else "native",days=days)]
            write_json(experiment/"schedule.json",schedule)
            (experiment/"runs").mkdir()
            for strategy in c["strategies"]:
                run_id=schedule[0]["period_id"]+"_"+strategy
                job=dict(strategy=strategy,c=c,days=days,path=str(experiment/"runs"/run_id),
                         period_id=schedule[0]["period_id"],role=schedule[0]["role"])
                jobpath=experiment/(strategy+"_job.json"); write_json(jobpath,job)
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=str(ROOT))
                with (experiment/(strategy+".log")).open("w",encoding="utf-8") as log:
                    subprocess.run([sys.executable,"-X","utf8","-B","-m","research_set50_baseline","_worker","--job",str(jobpath)],
                                   cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
                print("Completed",run_id,flush=True)
            make_report(experiment)
        else:
            loaded=read_history()
            schedule=daily_schedule(loaded[2],c)
            schedule.append(dict(period_id="daily_native_overlap",role="execution_comparison_dependent",days=native_days(c)))
            write_json(experiment/"schedule.json",schedule)
            for period in schedule:
                for strategy in c["strategies"]:
                    run_id=period["period_id"]+"_"+strategy
                    run_daily(strategy,c,period["days"],experiment/"runs"/run_id,period["period_id"],period["role"],loaded)
                print("Completed",period["period_id"],flush=True)
            make_report(experiment)
        write_json(experiment/"status.json",dict(status="complete",command=args.command))
    except Exception as exc:
        write_json(experiment/"status.json",dict(status="failed",error=str(exc)))
        (experiment/"failure.log").write_text(traceback.format_exc(),encoding="utf-8")
        raise
    print("COMPLETE",experiment.name,flush=True)


if __name__=="__main__":
    main()
