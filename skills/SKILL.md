# 🐜 Pheromone Skill

## 触发条件

- **开始执行任务前**：先查询信息素，看看类似任务以前用什么方案成功率最高
- **任务完成后**：不管成功失败，都要沉积信息素，把经验记录下来
- **不确定用什么方案时**：让蚁群算法帮你选最优解
- **想了解某个 Agent 的能力画像时**：查询 Agent 的历史统计

## 核心工作流（MANDATORY）

### 执行前（必做）

```bash
# 查同类任务的历史最优方案
python pheromone_cli.py query "任务类型"
```

如果完全不确定用什么方案，用蚁群算法选择：
```bash
python pheromone_cli.py select "任务类型"
```

### 执行后（必做）

```bash
# 成功
python pheromone_cli.py deposit "任务类型" "方案名" --success --description "关键经验描述" --agent "你的Agent名"

# 失败（同样重要！让其他Agent避开坑）
python pheromone_cli.py deposit "任务类型" "方案名" --fail --description "失败原因" --agent "你的Agent名"
```

### 任务类型命名规范

- 使用简洁描述，「领域 + 动作」格式
- 示例：`批量图片压缩`、`网页数据采集`、`CDP生图`、`微信爬虫运维`
- 方案名要有区分度，体现具体方法：`Pillow垫图+凡道API` vs `requests直连API`

## CLI 命令速查

```bash
python pheromone_cli.py query "<任务类型>" [--top-k 5]   # 查方案
python pheromone_cli.py select "<任务类型>"               # 蚁群选方案
python pheromone_cli.py deposit "<任务类型>" "<方案名>" --success --description "内容" --agent "Agent名"
python pheromone_cli.py deposit "<任务类型>" "<方案名>" --fail --description "原因" --agent "Agent名"
python pheromone_cli.py status                            # 系统状态
python pheromone_cli.py list-tasks                        # 任务类型列表
python pheromone_cli.py agent-stats "<Agent名>"           # Agent能力画像
python pheromone_cli.py evaporate                         # 手动全量挥发
```

## 混合挥发模型 v2 说明

信息素浓度受四重机制调控：

1. **时间基线衰减 (0.5%/天)**：经验随时间自然淡化，防止过时知识误导
2. **活动竞争衰减 (3%/次)**：同类新方案成功后，竞争方案小幅削弱，防止强者锁死
3. **失败加速惩罚 (+10%)**：失败方案额外自挥发，坏路径快速退场
4. **置信度免疫 (时间衰减减半)**：成功≥5次且成功率≥90%的"铁律"方案更持久

🏆 标记 = 高置信度方案（成功率≥90%且样本≥5）
