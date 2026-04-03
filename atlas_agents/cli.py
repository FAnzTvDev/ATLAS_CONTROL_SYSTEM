from __future__ import annotations
import argparse
from .ops_coordinator import ops_autopilot
from .cast_agent import cast_agent_run
from .cast_propagator import propagate_cast_to_shots
from .plan_fixer import plan_fixer_run
from .critic_gate import critic_gate_run
from .live_sync import recent_renders_scan, get_jobs, get_recent

def main():
    ap = argparse.ArgumentParser(prog="atlas_agents")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_auto = sub.add_parser("autopilot")
    p_auto.add_argument("--project", required=True)
    p_auto.add_argument("--mode", choices=["prep","canary","full"], default="prep")
    p_auto.add_argument("--overwrite-cast", action="store_true")

    p_cast = sub.add_parser("cast")
    p_cast.add_argument("--project", required=True)
    p_cast.add_argument("--overwrite", action="store_true")

    p_prop = sub.add_parser("propagate")
    p_prop.add_argument("--project", required=True)

    p_plan = sub.add_parser("planfix")
    p_plan.add_argument("--project", required=True)

    p_gate = sub.add_parser("critics")
    p_gate.add_argument("--project", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--project", required=True)

    p_jobs = sub.add_parser("jobs")
    p_jobs.add_argument("--project", required=True)

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--project", required=True)

    args = ap.parse_args()

    if args.cmd == "autopilot":
        print(ops_autopilot(args.project, mode=args.mode, overwrite_cast=args.overwrite_cast))
    elif args.cmd == "cast":
        print(cast_agent_run(args.project, overwrite=args.overwrite))
    elif args.cmd == "propagate":
        print(propagate_cast_to_shots(args.project))
    elif args.cmd == "planfix":
        print(plan_fixer_run(args.project))
    elif args.cmd == "critics":
        print(critic_gate_run(args.project))
    elif args.cmd == "scan":
        print(recent_renders_scan(args.project))
    elif args.cmd == "jobs":
        print(get_jobs(args.project))
    elif args.cmd == "recent":
        print(get_recent(args.project))

if __name__ == "__main__":
    main()
