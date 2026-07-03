"""
信息素核心库 - 蚁群智能的核心引擎 (v2.1)
提供信息素的查询、沉积、挥发三大核心功能

混合挥发模型 V2.1:
  总挥发 = 时间基线衰减 + 活动竞争衰减(置信度感知) + 失败加速惩罚(符号感知) - 置信度免疫
  - 置信度免疫同时作用于时间衰减和活动竞争
  - 失败惩罚使用符号感知公式 P -= |P|*rate，负值正确加速崩塌
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import threading
import random

_lock = threading.Lock()


class PheromoneCore:
    """信息素核心类 - 混合挥发模型"""

    EVAPORATION_RATE = 0.005

    ACTIVITY_EVAPORATION_RATE = 0.03

    FAILURE_EXTRA_EVAPORATION = 0.10

    DEPOSIT_SUCCESS = 1.0
    DEPOSIT_FAILURE = -0.5

    EXPLORATION_RATE = 0.15

    MIN_PHEROMONE = -5.0

    CONFIDENCE_SUCCESS_THRESHOLD = 5
    CONFIDENCE_RATE_THRESHOLD = 0.9

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.tasks_file = self.data_dir / "tasks.json"
        self.agents_file = self.data_dir / "agents.json"

        self._init_data_files()

    def _init_data_files(self):
        if not self.tasks_file.exists():
            self._write_json_atomic(self.tasks_file, {})
        if not self.agents_file.exists():
            self._write_json_atomic(self.agents_file, {})

    @staticmethod
    def _read_json(filepath: Path) -> Dict:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    @staticmethod
    def _write_json_atomic(filepath: Path, data: Dict):
        tmp_path = filepath.with_suffix('.tmp')
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(filepath))
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _is_confident(self, success_count: int, fail_count: int) -> bool:
        total = success_count + fail_count
        if total < self.CONFIDENCE_SUCCESS_THRESHOLD:
            return False
        return success_count / total >= self.CONFIDENCE_RATE_THRESHOLD

    def _calculate_time_evaporation(self, pheromone_value: float, last_used: str,
                                     success_count: int = 0, fail_count: int = 0) -> float:
        if not last_used:
            return pheromone_value
        try:
            last_time = datetime.fromisoformat(last_used)
            days_passed = (datetime.now() - last_time).days
            if days_passed <= 0:
                return pheromone_value
            rate = self.EVAPORATION_RATE
            if self._is_confident(success_count, fail_count):
                rate = rate * 0.5
            return pheromone_value * ((1 - rate) ** days_passed)
        except (ValueError, TypeError):
            return pheromone_value

    def _normalize_task_type(self, task_type: str) -> str:
        return task_type.strip().lower()

    def _evaporate_solution_time(self, solution_data: Dict) -> float:
        current = solution_data.get("pheromone", 0)
        last_used = solution_data.get("last_used", "")
        sc = solution_data.get("success_count", 0)
        fc = solution_data.get("fail_count", 0)
        evaporated = self._calculate_time_evaporation(current, last_used, sc, fc)
        if evaporated < self.MIN_PHEROMONE:
            evaporated = self.MIN_PHEROMONE
        solution_data["pheromone"] = round(evaporated, 4)
        return evaporated

    def query(self, task_type: str, top_k: int = 5) -> List[Dict]:
        task_type = self._normalize_task_type(task_type)
        tasks_data = self._read_json(self.tasks_file)

        if task_type not in tasks_data:
            return []

        solutions = tasks_data[task_type]
        result = []

        for solution_name, solution_data in solutions.items():
            sc = solution_data.get("success_count", 0)
            fc = solution_data.get("fail_count", 0)
            current_pheromone = self._calculate_time_evaporation(
                solution_data.get("pheromone", 0),
                solution_data.get("last_used", ""),
                sc, fc
            )
            if current_pheromone < self.MIN_PHEROMONE:
                current_pheromone = self.MIN_PHEROMONE

            confident = self._is_confident(sc, fc)
            result.append({
                "solution": solution_name,
                "pheromone": round(current_pheromone, 2),
                "success_count": sc,
                "fail_count": fc,
                "avg_time_seconds": solution_data.get("avg_time", 0),
                "last_used": solution_data.get("last_used", ""),
                "description": solution_data.get("description", ""),
                "confident": confident
            })

        result.sort(key=lambda x: x["pheromone"], reverse=True)
        return result[:top_k]

    def select_solution(self, task_type: str) -> Optional[Dict]:
        solutions = self.query(task_type)
        if not solutions:
            return None

        if random.random() < self.EXPLORATION_RATE:
            return random.choice(solutions)

        positive = [s for s in solutions if s["pheromone"] > 0]
        if not positive:
            return solutions[0]

        total_pheromone = sum(s["pheromone"] for s in positive)
        if total_pheromone <= 0:
            return solutions[0]

        rand_val = random.random() * total_pheromone
        cumulative = 0
        for s in positive:
            cumulative += s["pheromone"]
            if rand_val <= cumulative:
                return s

        return positive[-1]

    def deposit(self, task_type: str, solution_name: str, success: bool,
                duration_seconds: float = 0, description: str = "",
                agent_name: str = "unknown"):
        with _lock:
            task_type = self._normalize_task_type(task_type)
            tasks_data = self._read_json(self.tasks_file)

            if task_type not in tasks_data:
                tasks_data[task_type] = {}

            if solution_name not in tasks_data[task_type]:
                tasks_data[task_type][solution_name] = {
                    "pheromone": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "avg_time": 0,
                    "avg_time_sum": 0,
                    "avg_time_count": 0,
                    "last_used": "",
                    "description": description,
                    "agents": []
                }

            for sname, sdata in tasks_data[task_type].items():
                self._evaporate_solution_time(sdata)

            solution = tasks_data[task_type][solution_name]

            deposit_value = self.DEPOSIT_SUCCESS if success else self.DEPOSIT_FAILURE
            solution["pheromone"] = solution.get("pheromone", 0) + deposit_value

            if not success:
                solution["pheromone"] = solution["pheromone"] - abs(solution["pheromone"]) * self.FAILURE_EXTRA_EVAPORATION

            for sname, sdata in tasks_data[task_type].items():
                if sname == solution_name:
                    continue
                if sdata.get("pheromone", 0) > 0:
                    competitor_sc = sdata.get("success_count", 0)
                    competitor_fc = sdata.get("fail_count", 0)
                    competitor_confident = self._is_confident(competitor_sc, competitor_fc)
                    act_rate = self.ACTIVITY_EVAPORATION_RATE * (0.5 if competitor_confident else 1.0)
                    sdata["pheromone"] = round(
                        sdata["pheromone"] * (1 - act_rate), 4
                    )
                    if sdata["pheromone"] < self.MIN_PHEROMONE:
                        sdata["pheromone"] = self.MIN_PHEROMONE

            if solution["pheromone"] < self.MIN_PHEROMONE:
                solution["pheromone"] = self.MIN_PHEROMONE

            if success:
                solution["success_count"] = solution.get("success_count", 0) + 1
            else:
                solution["fail_count"] = solution.get("fail_count", 0) + 1

            if duration_seconds > 0:
                old_sum = solution.get("avg_time_sum", 0)
                old_count = solution.get("avg_time_count", 0)
                new_sum = old_sum + duration_seconds
                new_count = old_count + 1
                solution["avg_time"] = round(new_sum / new_count, 2)
                solution["avg_time_sum"] = new_sum
                solution["avg_time_count"] = new_count

            solution["last_used"] = datetime.now().isoformat()

            if description and not solution.get("description"):
                solution["description"] = description

            agents = solution.get("agents", [])
            if agent_name not in agents:
                agents.append(agent_name)
            solution["agents"] = agents

            self._write_json_atomic(self.tasks_file, tasks_data)

            self._update_agent_stats(agent_name, task_type, success)

    def _update_agent_stats(self, agent_name: str, task_type: str, success: bool):
        agents_data = self._read_json(self.agents_file)

        if agent_name not in agents_data:
            agents_data[agent_name] = {
                "total_tasks": 0,
                "success_count": 0,
                "fail_count": 0,
                "specialties": {},
                "last_active": ""
            }

        agent = agents_data[agent_name]
        agent["total_tasks"] = agent.get("total_tasks", 0) + 1
        if success:
            agent["success_count"] = agent.get("success_count", 0) + 1
        else:
            agent["fail_count"] = agent.get("fail_count", 0) + 1

        specialties = agent.get("specialties", {})
        if task_type not in specialties:
            specialties[task_type] = {"success": 0, "fail": 0}
        if success:
            specialties[task_type]["success"] += 1
        else:
            specialties[task_type]["fail"] += 1
        agent["specialties"] = specialties

        agent["last_active"] = datetime.now().isoformat()

        self._write_json_atomic(self.agents_file, agents_data)

    def get_agent_stats(self, agent_name: str) -> Optional[Dict]:
        agents_data = self._read_json(self.agents_file)
        return agents_data.get(agent_name)

    def list_task_types(self) -> List[str]:
        tasks_data = self._read_json(self.tasks_file)
        return list(tasks_data.keys())

    def evaporate_all(self):
        with _lock:
            tasks_data = self._read_json(self.tasks_file)
            for task_type, solutions in tasks_data.items():
                for solution_name, solution_data in solutions.items():
                    self._evaporate_solution_time(solution_data)
            self._write_json_atomic(self.tasks_file, tasks_data)

    def get_status(self) -> Dict:
        tasks_data = self._read_json(self.tasks_file)
        agents_data = self._read_json(self.agents_file)

        total_solutions = sum(len(solutions) for solutions in tasks_data.values())

        total_success = 0
        total_fail = 0
        confident_solutions = 0
        for solutions in tasks_data.values():
            for sdata in solutions.values():
                sc = sdata.get("success_count", 0)
                fc = sdata.get("fail_count", 0)
                total_success += sc
                total_fail += fc
                if self._is_confident(sc, fc):
                    confident_solutions += 1

        return {
            "task_types_count": len(tasks_data),
            "solutions_count": total_solutions,
            "agents_count": len(agents_data),
            "data_dir": str(self.data_dir),
            "evaporation_rate": self.EVAPORATION_RATE,
            "activity_evaporation_rate": self.ACTIVITY_EVAPORATION_RATE,
            "failure_extra_evaporation": self.FAILURE_EXTRA_EVAPORATION,
            "exploration_rate": self.EXPLORATION_RATE,
            "confidence_threshold": self.CONFIDENCE_SUCCESS_THRESHOLD,
            "confidence_rate_threshold": self.CONFIDENCE_RATE_THRESHOLD,
            "total_deposits": total_success + total_fail,
            "total_success": total_success,
            "total_fail": total_fail,
            "confident_solutions": confident_solutions
        }


_default_core = None


def get_core(data_dir: Optional[str] = None) -> PheromoneCore:
    global _default_core
    if _default_core is None:
        _default_core = PheromoneCore(data_dir)
    return _default_core
