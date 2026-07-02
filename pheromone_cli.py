#!/usr/bin/env python3
"""
🐜 信息素系统 CLI - 蚁群经验路由系统
用法：
  python pheromone_cli.py query <task_type> [--top-k 5]
  python pheromone_cli.py select <task_type>
  python pheromone_cli.py deposit <task_type> <solution_name> --success/--fail [--duration 秒] [--description "描述"] [--agent "Agent名"]
  python pheromone_cli.py status
  python pheromone_cli.py list-tasks
  python pheromone_cli.py agent-stats <agent_name>
  python pheromone_cli.py evaporate
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pheromone_core import get_core


def cmd_query(args):
    core = get_core()
    results = core.query(args.task_type, top_k=args.top_k)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print(f"未找到任务类型「{args.task_type}」的相关方案")
            return

        print(f"📊 任务类型：{args.task_type}")
        print(f"共找到 {len(results)} 个方案（按信息素浓度排序）：")
        print("-" * 60)
        for i, s in enumerate(results, 1):
            total = s["success_count"] + s["fail_count"]
            if total == 0:
                status = "❓"
            elif s["success_count"] > s["fail_count"]:
                status = "✅"
            elif s["success_count"] < s["fail_count"]:
                status = "❌"
            else:
                status = "⚠️"
            badge = " 🏆" if s.get("confident") else ""
            print(f"{i}. {status} {s['solution']}{badge}")
            print(f"   信息素: {s['pheromone']} | 成功: {s['success_count']} | 失败: {s['fail_count']}")
            if s["avg_time_seconds"] > 0:
                print(f"   平均耗时: {s['avg_time_seconds']:.1f}秒")
            if s["description"]:
                desc = s["description"]
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                print(f"   描述: {desc}")
            print()


def cmd_select(args):
    core = get_core()
    solution = core.select_solution(args.task_type)

    if args.json:
        print(json.dumps(solution, ensure_ascii=False, indent=2))
    else:
        if solution is None:
            print(f"未找到任务类型「{args.task_type}」的相关方案")
            return

        print("🐜 蚁群算法推荐方案：")
        print("=" * 40)
        print(f"方案名: {solution['solution']}")
        print(f"信息素浓度: {solution['pheromone']}")
        total = solution['success_count'] + solution['fail_count']
        print(f"成功率: {solution['success_count']}/{total}")
        if solution.get("confident"):
            print("🏆 高置信度方案（成功率≥90%且样本≥5）")
        if solution["description"]:
            print(f"描述: {solution['description']}")


def cmd_deposit(args):
    core = get_core()
    core.deposit(
        task_type=args.task_type,
        solution_name=args.solution_name,
        success=args.success,
        duration_seconds=args.duration or 0,
        description=args.description or "",
        agent_name=args.agent or "unknown"
    )

    if args.json:
        print(json.dumps({"success": True, "message": "信息素已沉积"}, ensure_ascii=False))
    else:
        status = "✅ 成功" if args.success else "❌ 失败"
        print(f"{status} - 已为「{args.task_type}」的「{args.solution_name}」方案沉积信息素")


def cmd_status(args):
    core = get_core()
    st = core.get_status()

    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
    else:
        print("🐜 信息素系统状态 (混合挥发模型 v2)")
        print("=" * 50)
        print(f"任务类型数: {st['task_types_count']}")
        print(f"方案总数:   {st['solutions_count']}")
        print(f"注册Agent数: {st['agents_count']}")
        print(f"累计沉积:   {st['total_deposits']} (成功{st['total_success']}/失败{st['total_fail']})")
        print(f"🏆 高置信度方案: {st['confident_solutions']}")
        print(f"数据目录:   {st['data_dir']}")
        print("-" * 50)
        print(f"时间基线挥发: 每天 {st['evaporation_rate']*100:.1f}%")
        print(f"活动竞争挥发: 每次deposit同类竞争方案 {st['activity_evaporation_rate']*100:.0f}%")
        print(f"失败加速惩罚: 失败方案额外自挥发 {st['failure_extra_evaporation']*100:.0f}%")
        print(f"置信度免疫:   成功≥{st['confidence_threshold']}次且成功率≥{st['confidence_rate_threshold']*100:.0f}% → 时间挥发减半")
        print(f"探索概率:     {st['exploration_rate']*100:.0f}%")
        print(f"信息素下限:   {core.MIN_PHEROMONE}")


def cmd_list_tasks(args):
    core = get_core()
    tasks = core.list_task_types()

    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        print(f"共 {len(tasks)} 种任务类型：")
        for t in tasks:
            solutions = core.query(t, top_k=100)
            best = solutions[0] if solutions else None
            if best:
                total = best["success_count"] + best["fail_count"]
                badge = "🏆" if best.get("confident") else "  "
                print(f"  {badge} {t} ({len(solutions)}个方案, 最优: {best['solution']} p={best['pheromone']})")
            else:
                print(f"     {t}")


def cmd_agent_stats(args):
    core = get_core()
    stats = core.get_agent_stats(args.agent_name)

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        if stats is None:
            print(f"未找到 Agent「{args.agent_name}」的统计数据")
            return

        print(f"🤖 Agent: {args.agent_name}")
        print("=" * 40)
        print(f"总任务数: {stats['total_tasks']}")
        print(f"成功: {stats['success_count']} | 失败: {stats['fail_count']}")
        if stats['total_tasks'] > 0:
            rate = stats['success_count'] / stats['total_tasks'] * 100
            print(f"成功率: {rate:.1f}%")
        print(f"最后活跃: {stats['last_active']}")

        if stats.get('specialties'):
            print("\n📚 专长领域：")
            sorted_specs = sorted(
                stats['specialties'].items(),
                key=lambda x: x[1]['success'] - x[1]['fail'],
                reverse=True
            )
            for task_type, data in sorted_specs:
                total = data['success'] + data['fail']
                rate = data['success'] / total * 100 if total > 0 else 0
                icon = "🏆" if data['success'] >= 5 and rate >= 90 else ("✅" if data['success'] > data['fail'] else "⚠️")
                print(f"  {icon} {task_type}: {data['success']}/{total} ({rate:.0f}%)")


def cmd_evaporate(args):
    core = get_core()
    core.evaporate_all()
    if args.json:
        print(json.dumps({"success": True, "message": "全量挥发完成"}, ensure_ascii=False))
    else:
        print("🌬️ 全量时间挥发已完成")


def main():
    parser = argparse.ArgumentParser(description="🐜 信息素系统 - 蚁群经验路由引擎 v2")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    query_parser = subparsers.add_parser("query", help="查询某类任务的方案")
    query_parser.add_argument("task_type", help="任务类型")
    query_parser.add_argument("--top-k", type=int, default=5, help="返回前N个方案")
    query_parser.set_defaults(func=cmd_query)

    select_parser = subparsers.add_parser("select", help="用蚁群算法选择一个方案")
    select_parser.add_argument("task_type", help="任务类型")
    select_parser.set_defaults(func=cmd_select)

    deposit_parser = subparsers.add_parser("deposit", help="沉积信息素（任务完成后调用）")
    deposit_parser.add_argument("task_type", help="任务类型")
    deposit_parser.add_argument("solution_name", help="方案名称")
    deposit_group = deposit_parser.add_mutually_exclusive_group(required=True)
    deposit_group.add_argument("--success", action="store_true", help="任务成功")
    deposit_group.add_argument("--fail", action="store_true", help="任务失败")
    deposit_parser.add_argument("--duration", type=float, help="耗时（秒）")
    deposit_parser.add_argument("--description", help="方案描述")
    deposit_parser.add_argument("--agent", help="执行的Agent名称")
    deposit_parser.set_defaults(func=cmd_deposit)

    status_parser = subparsers.add_parser("status", help="查看系统状态")
    status_parser.set_defaults(func=cmd_status)

    list_parser = subparsers.add_parser("list-tasks", help="列出所有任务类型")
    list_parser.set_defaults(func=cmd_list_tasks)

    agent_parser = subparsers.add_parser("agent-stats", help="查看Agent统计")
    agent_parser.add_argument("agent_name", help="Agent名称")
    agent_parser.set_defaults(func=cmd_agent_stats)

    evap_parser = subparsers.add_parser("evaporate", help="手动触发全量时间挥发")
    evap_parser.set_defaults(func=cmd_evaporate)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
