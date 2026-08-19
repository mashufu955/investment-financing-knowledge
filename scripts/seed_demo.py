"""投融资知识库 —— 演示数据生成脚本（一键造数 + 可选向量索引重建）。

=====================================================================
目的
---------------------------------------------------------------------
为「本地测试」与「上传云服务器后再度测试」提供一套：
  * 全面   —— 覆盖 5 大技能场景（知识维护 / 组织权限 / AI 问答 / 数据看板 / 知识沉淀）
  * 真实   —— 内部自洽的投融资业务数据（轮次、金额、币种、估值、阶段、保密级别）
  * 可靠   —— 严格遵循当前库的编号规则与字段规范化（行业中文规范名 / 轮次英文枚举 / 阶段枚举）
  * 可幂等 —— 默认清空 12 张表后整体重建，可无限重复执行
  * 可移植 —— 复用 app 的配置与 ORM，本地（docker compose）与云端（同一镜像）命令完全一致

=====================================================================
运行方式（务必在 backend 容器内执行，才能读到 .env 的 mysql 主机名与已装依赖）
---------------------------------------------------------------------
# 1) 让镜像包含本脚本（推荐，持久）：在宿主机项目根执行
docker compose --env-file ../.env build backend
docker compose --env-file ../.env up -d backend

# 2) 不想重建镜像的快捷方式（临时，容器重建即丢失）：
docker cp scripts/seed_demo.py ifk-backend:/app/scripts/seed_demo.py

# 3) 进入容器执行（--yes 是危险操作确认开关，必须显式传入）
docker compose --env-file ../.env exec backend python scripts/seed_demo.py --yes
#   仅造数、不重建向量索引：  ... --yes --no-index
#   同时把源文档导出到 uploads/demo_sources 供「导入流程」测试： ... --yes --emit-docs
#   仅清空演示数据、不重建：  ... --yes --clear-only

说明：
  * 脚本会 TRUNCATE 全部 12 张业务表并整体重建，适合演示/测试，不适合生产数据。
  * 加 --clear-only 时只清空 12 张业务表，不生成任何演示数据。
  * 默认在造数完成后自动重建向量/ES 索引：通过后端 HTTP API（POST /api/knowledge/reindex）
    触发，由持有 Milvus Lite 文件锁的 backend 主进程完成写入（见 sync_indexes_via_api）。
    若后端 API 不可达，降级为本进程直写 ES 关键字索引，并提示向量索引需补齐。
  * 向量索引重建依赖 embedding 网关（EMBEDDING_API_KEY）。若未配置，单元会标记为
    index_status=failed（数据本身已入库、列表可见），配置密钥后可用 /api/knowledge/reindex 补齐。
  * 管理员账号 admin / admin123 由本脚本一并重建。
=====================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

# 将项目根（scripts/ 的上级目录）加入 sys.path，确保无论从哪个 cwd 执行都能 `import app`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.config import settings
from app.core.database import SessionLocal
from app.models.models import (
    Department,
    Faq,
    KnowledgeGap,
    KnowledgeUnit,
    QaAccessLog,
    QaMessage,
    QaSession,
    Role,
    RolePermission,
    UnitPermission,
    User,
    UserRole,
)
from app.services.knowledge_service import KnowledgeService

# admin123 的 bcrypt cost=12 哈希（与 database/init.sql 保持一致）
ADMIN_HASH = "$2b$12$yiWGaU2vMKh.xsxV7Hfq8.hMw7d.0y4OsPF81dPguQOkjZ7neVMSa"

UTCNOW = lambda: datetime.now(timezone.utc).replace(tzinfo=None)


# =====================================================================
# 1) 组织与权限基线
# =====================================================================
ROLES = [
    (1, "系统管理员", "admin", "维护用户、团队、角色与权限"),
    (2, "投资经理", "investment_manager", "维护所负责项目、标的与融资需求"),
    (3, "投资总监/合伙人", "investment_partner", "查看授权项目组合、投决材料与业务看板"),
    (4, "投委会成员", "ic_member", "查看进入投决流程的项目资料、尽调结论与风险意见"),
    (5, "风控", "risk_control", "查看尽调、合规材料，维护风险知识"),
    (6, "法务", "legal", "查看协议、合规材料"),
    (7, "财务", "finance", "查看财务材料"),
    (8, "运营/IR", "ir_operation", "维护融资需求、资金方信息、投后报告"),
]

# id, parent_id, name, dept_type, leader_id, sort_order
DEPARTMENTS = [
    (1, None, "投资部", "team", 4, 1),
    (2, 1, "一期基金", "fund", 2, 1),
    (3, 1, "二期基金", "fund", 3, 2),
    (4, 1, "三期基金", "fund", 13, 3),
    (5, None, "风控部", "team", 6, 4),
    (6, None, "法务部", "team", 7, 5),
    (7, None, "财务部", "team", 8, 6),
    (8, None, "运营/IR部", "team", 9, 7),
    (9, 1, "投后管理部", "team", 10, 8),
    (10, 4, "医疗健康组", "sub", 13, 1),
    (11, 4, "人工智能组", "sub", 2, 2),
    (12, 2, "硬科技组", "sub", 2, 3),
]

# id, username, display_name, department_id, status(1启用/0停用)
USERS = [
    (1, "admin", "系统管理员", 1, 1),
    (2, "zhangwei", "张伟", 2, 1),
    (3, "lina", "李娜", 3, 1),
    (4, "wangqiang", "王强", 1, 1),
    (5, "zhaomin", "赵敏", 1, 1),
    (6, "chenjie", "陈杰", 5, 1),
    (7, "liufang", "刘芳", 6, 1),
    (8, "sunli", "孙丽", 7, 1),
    (9, "zhoutao", "周涛", 8, 1),
    (10, "wuqian", "吴倩", 9, 1),
    (11, "linjie", "林杰", 2, 0),  # 场景：停用账号（status=0）
    (12, "sumin", "苏敏", 2, 1),   # 场景：多角色（投资经理 + 投委会）
    (13, "hanxue", "韩雪", 10, 1),
]

USER_ROLES = [
    (1, 1), (2, 2), (3, 2), (10, 2), (12, 2), (13, 2),
    (4, 3), (5, 4), (12, 4),
    (6, 5), (7, 6), (8, 7), (9, 8),
]

ROLE_PERMISSIONS = [
    # 系统管理员：admin 拥有所有菜单与按钮权限（前端侧边栏与按钮按 permissions 严格过滤，无 admin 通配逻辑）
    (1, "dashboard:view", "menu"),
    (1, "knowledge:view", "menu"), (1, "knowledge:manage", "button"), (1, "knowledge:import", "button"),
    (1, "qa:chat", "menu"),
    (1, "settlement:gap:view", "menu"), (1, "settlement:faq:review", "button"),
    (1, "org:dept:manage", "menu"), (1, "org:user:manage", "menu"), (1, "org:role:manage", "menu"),
    # 投资经理
    (2, "dashboard:view", "menu"), (2, "knowledge:view", "menu"), (2, "qa:chat", "menu"),
    (2, "settlement:gap:view", "menu"), (2, "knowledge:manage", "button"), (2, "knowledge:import", "button"),
    # 投资总监/合伙人
    (3, "dashboard:view", "menu"), (3, "knowledge:view", "menu"), (3, "qa:chat", "menu"),
    (3, "settlement:gap:view", "menu"), (3, "settlement:faq:review", "button"),
    # 投委会成员
    (4, "dashboard:view", "menu"), (4, "knowledge:view", "menu"), (4, "qa:chat", "menu"),
    (4, "settlement:gap:view", "menu"),
    # 风控
    (5, "dashboard:view", "menu"), (5, "knowledge:view", "menu"), (5, "qa:chat", "menu"),
    (5, "settlement:gap:view", "menu"), (5, "knowledge:manage", "button"),
    # 法务
    (6, "knowledge:view", "menu"), (6, "qa:chat", "menu"),
    # 财务
    (7, "knowledge:view", "menu"), (7, "qa:chat", "menu"),
    # 运营/IR
    (8, "dashboard:view", "menu"), (8, "knowledge:view", "menu"), (8, "qa:chat", "menu"),
    (8, "settlement:gap:view", "menu"), (8, "knowledge:manage", "button"), (8, "knowledge:import", "button"),
]


# =====================================================================
# 2) 投融资知识单元（核心演示数据）
#    字段说明：
#      industry  —— 写入「原始别名」，脚本统一规范化为中文规范名（演示规范化能力）
#      round     —— 写入「中文轮次」，脚本统一规范化为英文枚举
#      stage     —— 直接写英文阶段枚举
#      conf      —— 保密级别 1~5
#      status    —— active / draft / archived
# =====================================================================
# key, title, category, industry(原始), round(原始), amount, currency, valuation, region, stage, conf, status, creator_id
UNITS = [
    ("ai_dw_a", "某AI大模型公司A轮融资尽调报告", "due_diligence", "AI", "A轮",
     250000000.0, "CNY", 2500000000.0, "北京", "due_diligence", 3, "active", 2,
     "项目：企业级知识增强大模型\n行业：AI\n轮次：A轮\n金额：2.5亿元 人民币\n估值：投前20亿/投后25亿\n地区：北京\n阶段：尽调\n"
     "业务情况：客户集中于金融、政务与医疗，续费率超90%。\n风险点：算力成本随规模上升较快；核心算法人才存在被头部厂商挖角风险。\n相关方：某AI大模型公司、GPU供应商。"),

    ("biotech_cro_b", "生物医药CRO企业B轮投决材料", "investment_committee", "创新药", "B轮",
     120000000.0, "USD", 800000000.0, "上海", "investment_committee", 4, "active", 2,
     "项目：药物临床前与临床CRO一体化服务\n行业：创新药\n轮次：B轮\n金额：1.2亿美元\n估值：投后8亿美元\n地区：上海\n阶段：投决\n"
     "在手订单超12亿元；收入结构：临床前动物实验占55%，临床I-III期占45%；毛利率42%，较同行高5个百分点。"),

    ("semicond_c", "半导体刻蚀设备公司C轮协议要点", "agreement", "芯片", "C轮",
     300000000.0, "CNY", 6000000000.0, "无锡", "closing", 3, "active", 4,
     "项目：国产化刻蚀设备\n行业：芯片\n轮次：C轮\n金额：3亿元\n估值：投后60亿\n地区：无锡\n阶段：交割\n"
     "协议要点：优先清算权1.2倍、反稀释（加权平均）、创始人3年竞业限制、董事会5席中我方占1席。"),

    ("newenergy_storage_seed", "新能源储能项目种子轮融资需求", "general", "储能", "种子轮",
     80000000.0, "CNY", 500000000.0, "合肥", "sourcing", 2, "active", 3,
     "融资需求：股权融资\n目标行业：新能源储能\n期望轮次：种子轮\n金额区间：8000万元 人民币\n地区：合肥\n阶段：sourcing\n"
     "资金用途：中试线建设与首批客户验证；核心团队来自宁德时代与阳光电源，已签约装机容量120MWh。"),

    ("saas_a", "SaaS财税一体化公司A轮投决", "investment_committee", "企业服务", "A轮",
     60000000.0, "USD", 400000000.0, "杭州", "investment_committee", 2, "active", 3,
     "项目：面向中小企业的财税一体化SaaS\n行业：企业服务\n轮次：A轮\n金额：6000万美元\n估值：投后4亿美元\n地区：杭州\n阶段：投决\n"
     "ARR达2.8亿元，NPS 65，客户月流失率1.8%；资金用于低代码平台与AI财务助手研发。"),

    ("medical_robot_preA", "骨科手术机器人公司Pre-A投资条款清单", "agreement", "医疗", "Pre-A轮",
     150000000.0, "CNY", 900000000.0, "苏州", "investment_committee", 3, "active", 4,
     "项目：骨科手术机器人\n行业：医疗\n轮次：Pre-A轮\n金额：1.5亿元\n估值：投前9亿\n地区：苏州\n阶段：投决\n"
     "产品进入NMPA创新通道；TS关键条款：董事会5名董事中投资方委派1名，对赌约定三年内取得三类证。"),

    ("robot_b_post", "工业机器人公司B轮投后季度报告", "post_investment", "机器人", "B轮",
     50000000.0, "CNY", 4500000000.0, "深圳", "post_investment", 2, "active", 10,
     "项目：工业机器人\n行业：机器人\n轮次：B轮\n金额：5000万元\n估值：投后45亿\n地区：深圳\n阶段：投后\n"
     "Q3出货量860台，同比增长38%；海外收入占比提升至28%；新工厂10月投产，年产能将达5000台；上游伺服电机交付周期延长至16周。"),

    ("chip_a_risk", "芯片设计公司A轮尽调风险清单", "due_diligence", "半导体", "A轮",
     200000000.0, "CNY", 1800000000.0, "上海", "due_diligence", 4, "active", 6,
     "项目：先进制程芯片设计\n行业：半导体\n轮次：A轮\n金额：2亿元\n估值：投后18亿\n地区：上海\n阶段：尽调\n"
     "风险点：①流片失败风险，先进制程流片费用高企；②客户验证周期长；③核心架构师离职风险；④地缘政治导致EDA工具授权受限。"),

    ("synthetic_bio_b", "合成生物学公司B轮投决备忘录", "investment_committee", "合成生物", "B轮",
     200000000.0, "CNY", 1800000000.0, "武汉", "investment_committee", 3, "active", 2,
     "项目：合成生物学改造氨基酸菌株\n行业：合成生物\n轮次：B轮\n金额：2亿元\n估值：投后18亿\n地区：武汉\n阶段：投决\n"
     "成本较传统发酵低30%；第一款产品已获食品级认证，2025年放量。"),

    ("logistics_c", "物流科技公司C轮协议定稿", "agreement", "企业服务", "C轮",
     240000000.0, "USD", 1800000000.0, "广州", "closing", 2, "active", 9,
     "项目：仓储机器人+调度软件\n行业：企业服务\n轮次：C轮\n金额：2.4亿美元\n估值：投后18亿美元\n地区：广州\n阶段：交割\n"
     "协议定稿：反稀释加权平均，无回购权，管理层股权激励池10%。"),

    ("nev_parts_a_post", "新能源汽车零部件公司A轮投后月报", "post_investment", "新能源", "A轮",
     300000000.0, "CNY", 2500000000.0, "宁波", "post_investment", 2, "active", 10,
     "项目：电池热管理系统\n行业：新能源\n轮次：A轮\n金额：3亿元\n估值：投后25亿\n地区：宁波\n阶段：投后\n"
     "8月出货1.2万套，环比+15%；新定点项目2个（国内头部车企）；应收账款周转天数58天；关注铝价上涨对毛利影响。"),

    ("ai_dw_supp", "大模型应用层公司天使轮尽调补充材料", "due_diligence", "AI", "天使轮",
     50000000.0, "CNY", 300000000.0, "成都", "due_diligence", 1, "active", 2,
     "项目：大模型应用层\n行业：AI\n轮次：天使轮\n金额：5000万元\n估值：投后3亿\n地区：成都\n阶段：尽调\n"
     "补充材料：推理成本随模型蒸馏下降60%测算；标杆客户POC效果（客服助手接通率提升40%）；近期竞品融资对比表。"),

    ("ai_data_agreement", "AI公司尽调数据授权协议（草稿）", "agreement", "人工智能", "A轮",
     None, "CNY", None, "北京", "due_diligence", 4, "draft", 7,
     "项目：尽调数据授权\n行业：人工智能\n轮次：A轮\n地区：北京\n阶段：尽调\n状态：草稿\n"
     "约定尽调期间目标公司向投资方提供经营数据的范围、用途与保密义务；数据范围含销售明细、客户合同、财务三表。"),

    ("fund1_review", "一期基金2024年度投资复盘报告", "post_investment", "人工智能", None,
     None, "CNY", None, "全国", "post_investment", 1, "archived", 4,
     "项目：一期基金整体复盘\n行业：人工智能（综合）\n地区：全国\n阶段：投后\n状态：归档\n"
     "整体投资12个项目，已退出3个，账面回报倍数2.1x；行业集中度人工智能33%、半导体25%；芯片方向尽调深度不足导致一个项目计提减值。"),

    ("battery_seed", "新能源电池材料公司种子轮融资需求", "general", "新能源", "种子轮",
     50000000.0, "CNY", 300000000.0, "宁德", "sourcing", 2, "active", 3,
     "融资需求：股权融资\n目标行业：新能源电池材料\n期望轮次：种子轮\n金额区间：5000万元 人民币\n地区：宁德\n阶段：sourcing\n"
     "资金用途：中试线建设与首批客户验证；公司拟分拆负极材料业务独立融资。"),

    ("autodrive_angel", "智能驾驶公司天使轮尽调报告", "due_diligence", "机器人", "天使轮",
     20000000.0, "USD", 150000000.0, "苏州", "due_diligence", 3, "active", 2,
     "项目：L2+级智能驾驶域控制器\n行业：机器人\n轮次：天使轮\n金额：2000万美元\n估值：投前1.2亿/投后1.5亿美元\n地区：苏州\n阶段：尽调\n"
     "已定点3家主机厂；团队来自大厂智驾部门；风险点：前装量产验证周期长、数据合规要求高。"),

    ("gene_preipo", "基因治疗公司Pre-IPO投决材料", "investment_committee", "创新药", "Pre-IPO轮",
     500000000.0, "CNY", 4000000000.0, "北京", "investment_committee", 4, "active", 4,
     "项目：AAV基因疗法\n行业：创新药\n轮次：Pre-IPO轮\n金额：5亿元\n估值：投后40亿\n地区：北京\n阶段：投决\n"
     "核心管线临床II期数据读出；研发费用率55%，预计2026年申报上市；关注临床终点设计、医保谈判影响、产能爬坡。"),

    ("newconsumer_strategic", "新消费品牌公司战略融资协议", "agreement", "新消费", "战略融资",
     100000000.0, "USD", 800000000.0, "上海", "closing", 2, "active", 9,
     "项目：高端植物基饮料\n行业：新消费\n轮次：战略融资\n金额：1亿美元\n估值：投后8亿美元\n地区：上海\n阶段：交割\n"
     "战略方派驻1名董事，分销渠道排他条款（3年），业绩对赌以2025年营收15亿元为基数。"),

    ("semicond_mat_a", "半导体材料公司A轮尽调", "due_diligence", "半导体", "A轮",
     100000000.0, "CNY", 800000000.0, "合肥", "due_diligence", 3, "active", 6,
     "项目：光刻胶单体与配套试剂\n行业：半导体\n轮次：A轮\n金额：1亿元\n估值：投后8亿\n地区：合肥\n阶段：尽调\n"
     "客户已通过两家晶圆厂导入验证；风险点：原材料依赖进口、二期扩产资金缺口约3000万元。"),

    ("ai_security_c", "人工智能安防公司C轮投决", "investment_committee", "人工智能", "C轮",
     400000000.0, "CNY", 3500000000.0, "深圳", "investment_committee", 3, "active", 4,
     "项目：多模态视频分析安防\n行业：人工智能\n轮次：C轮\n金额：4亿元\n估值：投后35亿\n地区：深圳\n阶段：投决\n"
     "合同负债6亿元，复购率85%；关注ToG回款账期、海外拓展策略。"),

    ("innov_drug_d", "创新药公司Pre-IPO轮交割材料", "agreement", "创新药", "Pre-IPO轮",
     300000000.0, "USD", 2500000000.0, "上海", "closing", 4, "active", 4,
     "项目：已获批上市创新药\n行业：创新药\n轮次：Pre-IPO轮\n金额：3亿美元\n估值：投后25亿美元\n地区：上海\n阶段：交割\n"
     "交割前置条件：老股东优先购买权放弃函、境外架构重组完成；交割时间本月底。"),

    ("pv_storage_b_post", "光伏储能公司B轮投后月报", "post_investment", "新能源", "B轮",
     80000000.0, "EUR", 700000000.0, "慕尼黑", "post_investment", 2, "active", 10,
     "项目：光伏+户储\n行业：新能源\n轮次：B轮\n金额：8000万欧元\n估值：投后7亿欧元\n地区：慕尼黑\n阶段：投后\n"
     "欧洲订单Q4环比增长40%，户储出货2.1万台；关注欧盟碳关税影响、汇率波动对冲；库存周转天数降至35天。"),

    ("ai_b_draft", "某AI公司B轮尽调（草稿·最高保密）", "due_diligence", "人工智能", "B轮",
     None, "CNY", None, "北京", "due_diligence", 5, "draft", 2,
     "（草稿，未定稿）公司B轮拟融资4亿元，投后估值40亿；本章节仅列出尽调提纲：商业/财务/法律三项分包计划与时间表。\n"
     "保密级别：5（最高），仅授权创建者张伟可见，用于演示「无权限访问被拦截」。"),

    ("fund1_reserve", "一期基金拟投资储备清单（机密）", "general", "人工智能", None,
     None, "CNY", None, "全国", "sourcing", 5, "draft", 4,
     "本清单列示一期基金拟尽调与储备项目12个，含联系人、保密评级与预计投入时间。\n"
     "保密级别：5（最高），仅授权王强可见，用于演示「无权限访问被拦截」。"),

    ("logistics_robot_a_post", "物流机器人公司A轮投后年报", "post_investment", "机器人", "A轮",
     150000000.0, "CNY", 1200000000.0, "东莞", "post_investment", 2, "archived", 10,
     "项目：物流机器人\n行业：机器人\n轮次：A轮\n金额：1.5亿元\n估值：投后12亿\n地区：东莞\n阶段：投后\n状态：归档\n"
     "2024全年出货4200台，收入6.8亿元，同比+45%；新签客户覆盖5家头部电商仓；2025计划海外占比提升至30%。"),

    ("crossborder_b", "跨境支付公司B轮投决", "investment_committee", "企业服务", "B轮",
     150000000.0, "USD", 1200000000.0, "香港", "investment_committee", 3, "active", 3,
     "项目：跨境收单与资金管理\n行业：企业服务\n轮次：B轮\n金额：1.5亿美元\n估值：投后12亿美元\n地区：香港\n阶段：投决\n"
     "合规牌照覆盖8个地区；毛利率38%，年交易流水400亿元。"),

    ("cell_therapy_preA", "细胞治疗公司Pre-A轮尽调", "due_diligence", "医疗", "Pre-A轮",
     200000000.0, "HKD", 1500000000.0, "广州", "due_diligence", 3, "active", 6,
     "项目：CAR-T实体瘤\n行业：医疗\n轮次：Pre-A轮\n金额：2亿港币\n估值：投后15亿港币\n地区：广州\n阶段：尽调\n"
     "临床前数据优于竞品，IND申报在即；风险点：临床入组与生产放行标准。"),

    ("smart_cockpit_c", "智能座舱公司C轮交割", "agreement", "机器人", "C轮",
     120000000.0, "EUR", 1000000000.0, "斯图加特", "closing", 2, "active", 4,
     "项目：智能座舱域控\n行业：机器人\n轮次：C轮\n金额：1.2亿欧元\n估值：投后10亿欧元\n地区：斯图加特\n阶段：交割\n"
     "交割完成：工商变更、代持还原、对赌补充协议签署。"),

    ("comm_astro_a", "商业航天公司A轮尽调简报", "due_diligence", "商业航天", "A轮",
     180000000.0, "CNY", 1500000000.0, "北京", "due_diligence", 3, "active", 2,
     "项目：商业运载火箭\n行业：商业航天\n轮次：A轮\n金额：1.8亿元\n估值：投后15亿\n地区：北京\n阶段：尽调\n"
     "中大型运力火箭完成方案论证，核心团队来自体制内院所；风险点：发射验证节奏、供应链自主可控。"),

    ("lowaltitude_seed", "低空经济eVTOL种子轮融资需求", "general", "低空经济", "种子轮",
     60000000.0, "CNY", 400000000.0, "深圳", "sourcing", 2, "active", 13,
     "融资需求：股权融资\n目标行业：低空经济eVTOL\n期望轮次：种子轮\n金额区间：6000万元 人民币\n地区：深圳\n阶段：sourcing\n"
     "资金用途：原型机研发与适航取证路径规划；团队来自头部无人机企业。"),
]


# =====================================================================
# 3) 知识单元数据权限（四维：global / department / role / user）
#    含「全四维组合」演示单元（autodrive_angel）与「最高保密·仅单人可见」单元（ai_b_draft / fund1_reserve）
# =====================================================================
# (unit_key, target_type, target_id)  target_id: global=0
UNIT_PERMISSIONS = [
    ("ai_dw_a", "department", 2), ("ai_dw_a", "role", 2),
    ("biotech_cro_b", "global", 0),
    ("semicond_c", "department", 3), ("semicond_c", "user", 4),
    ("newenergy_storage_seed", "role", 4),
    ("saas_a", "user", 2), ("saas_a", "user", 3),
    ("medical_robot_preA", "department", 1),
    ("robot_b_post", "global", 0),
    ("chip_a_risk", "department", 5),
    ("synthetic_bio_b", "role", 4), ("synthetic_bio_b", "department", 1),
    ("logistics_c", "user", 9),
    ("nev_parts_a_post", "department", 9),
    ("ai_dw_supp", "global", 0),
    ("ai_data_agreement", "department", 6),
    ("fund1_review", "department", 1),
    ("battery_seed", "role", 3),
    # 全四维组合演示：全局 + 部门 + 角色 + 个人
    ("autodrive_angel", "global", 0), ("autodrive_angel", "department", 1),
    ("autodrive_angel", "role", 2), ("autodrive_angel", "user", 4),
    ("gene_preipo", "role", 4), ("gene_preipo", "department", 1),
    ("newconsumer_strategic", "user", 9), ("newconsumer_strategic", "department", 8),
    ("semicond_mat_a", "department", 5),
    ("ai_security_c", "department", 1), ("ai_security_c", "role", 3),
    ("innov_drug_d", "role", 4),
    ("pv_storage_b_post", "department", 9),
    ("ai_b_draft", "user", 2),     # 最高保密：仅张伟
    ("fund1_reserve", "user", 4),  # 最高保密：仅王强
    ("logistics_robot_a_post", "department", 9),
    ("crossborder_b", "department", 3), ("crossborder_b", "role", 2),
    ("cell_therapy_preA", "department", 6), ("cell_therapy_preA", "user", 6),
    ("smart_cockpit_c", "department", 3),
    ("comm_astro_a", "global", 0),
    ("lowaltitude_seed", "role", 2), ("lowaltitude_seed", "department", 4),
]


# =====================================================================
# 4) 问答会话（含多轮对话）
# =====================================================================
# (user_id, title, [(role, content, days_ago)])
SESSIONS = [
    (2, "某AI公司A轮估值如何", [
        ("user", "某AI大模型公司A轮融资的投前估值和融资金额分别是多少？", 350),
        ("assistant", "本轮拟融资2.5亿元人民币，投前估值20亿元，投后25亿元；资金用于训练算力与商业化团队扩张。", 350),
        ("user", "那这家公司的主要客户集中在哪些行业？", 350),
        ("assistant", "客户集中于金融、政务与医疗三大行业，续费率超过90%。", 350),
    ]),
    (3, "生物医药CRO市场规模", [
        ("user", "生物医药CRO企业的在手订单和收入结构？", 347),
        ("assistant", "在手订单超12亿元，临床前动物实验占55%，临床I-III期占45%，毛利率42%。", 347),
    ]),
    (4, "一期基金投后项目进展", [
        ("user", "工业机器人公司Q3出货量和海外收入占比是多少？", 343),
        ("assistant", "Q3出货860台，同比增长38%，海外收入占比28%。", 343),
    ]),
    (1, "知识库数据权限如何配置", [
        ("user", "知识单元的数据权限有哪几个维度？", 338),
        ("assistant", "四个维度：全局公开(global)、团队/基金/项目范围(department)、角色(role)、人员(user)。", 338),
    ]),
    (12, "基因治疗Pre-IPO关注要点", [
        ("user", "基因治疗Pre-IPO投决关注要点？", 9),
        ("assistant", "临床终点设计、医保谈判影响、产能爬坡安排。", 9),
    ]),
    (6, "芯片流片风险", [
        ("user", "芯片流片失败的风险有多大，如何缓解？", 7),
        ("assistant", "流片失败是首要风险，先进制程费用高企；缓解含分阶段流片验证、多供应商备份与保险安排。", 7),
    ]),
]


# =====================================================================
# 5) 问答访问日志（看板趋势 + 权限缺失 + FAQ 自动挖掘触发）
#    created_at 用 UTC 计算，确保落在看板「近 7 天」窗口内。
#    recalled/authorized/unauthorized 用 unit_key 列表，脚本自动解析为整数 id。
# =====================================================================
# (user_id, question, answer, recalled_keys, authorized_keys, unauthorized_keys,
#  ptok, ctok, ttok, rt_ms, days_ago)
LOGS = [
    # —— 历史固定日期（不计入近7天趋势，但保留会话上下文） ——
    (2, "某AI大模型公司A轮融资的投前估值和融资金额？", "投前估值20亿元，拟融资2.5亿元，投后25亿元。",
     ["ai_dw_a"], ["ai_dw_a"], [], 1832, 512, 2344, 6842, 350),
    (2, "客户集中在哪些行业？", "金融、政务与医疗，续费率超90%。",
     ["ai_dw_a"], ["ai_dw_a"], [], 1205, 246, 1451, 5320, 350),
    (3, "生物医药CRO在手订单与收入结构？", "在手订单超12亿元，动物实验占55%，毛利率42%。",
     ["biotech_cro_b"], ["biotech_cro_b"], [], 1988, 421, 2409, 7831, 347),
    (4, "工业机器人公司Q3出货量？", "出货860台，同比增长38%，海外占比28%。",
     ["robot_b_post"], ["robot_b_post"], [], 1450, 302, 1752, 6210, 343),
    (1, "数据权限有几个维度？", "global/department/role/user 四维。",
     ["ai_dw_a", "semicond_c"], ["ai_dw_a", "semicond_c"], [], 980, 178, 1158, 3480, 338),
    (6, "芯片设计公司流片风险有哪些？", "流片失败、验证周期长、架构师离职、EDA授权受限。",
     ["chip_a_risk"], ["chip_a_risk"], [], 2100, 460, 2560, 8500, 7),

    # —— 近 7 天趋势（days_ago 0~6） ——
    (2, "AI大模型公司毛利率是多少？", "未检索到明确毛利率数据。",
     ["ai_dw_a"], ["ai_dw_a"], [], 1502, 220, 1722, 6110, 6),
    (3, "新能源储能项目的盈利模式？", "EPC一次性收入+峰谷价差分成。",
     ["newenergy_storage_seed"], ["newenergy_storage_seed"], [], 1680, 290, 1970, 7035, 6),
    (3, "合成生物学平台成本优势多大？", "较传统发酵成本低30%。",
     ["synthetic_bio_b"], ["synthetic_bio_b"], [], 1300, 210, 1510, 5400, 5),
    (5, "医疗器械Pre-A轮对赌条款？", "三年内取得三类证。",
     ["medical_robot_preA"], ["medical_robot_preA"], [], 1140, 180, 1320, 4520, 3),
    (2, "大模型应用公司推理成本下降依据？", "模型蒸馏使推理成本下降60%。",
     ["ai_dw_supp"], ["ai_dw_supp"], [], 1240, 205, 1445, 5100, 3),
    (8, "一期基金账面回报倍数？", "整体2.1倍，已退出3个项目。",
     ["fund1_review"], ["fund1_review"], [], 1100, 160, 1260, 4300, 2),
    (3, "SaaS公司ARR和客户流失率？", "ARR 2.8亿元，月流失率1.8%，NPS 65。",
     ["saas_a"], ["saas_a"], [], 1420, 240, 1660, 5880, 2),

    # 场景A：重复问题×3 → 触发 FAQ 自动挖掘（与已发布 FAQ 一致，演示命中/挖掘）
    (2, "某AI大模型公司的投前估值是多少", "投前估值20亿元，本轮拟融资2.5亿元，投后25亿元。",
     ["ai_dw_a"], ["ai_dw_a"], [], 1010, 150, 1160, 1900, 4),
    (3, "某AI大模型公司的投前估值是多少", "投前估值20亿元，本轮拟融资2.5亿元，投后25亿元。",
     ["ai_dw_a"], ["ai_dw_a"], [], 990, 145, 1135, 2100, 2),
    (4, "某AI大模型公司的投前估值是多少", "投前估值20亿元，本轮拟融资2.5亿元，投后25亿元。",
     ["ai_dw_a"], ["ai_dw_a"], [], 1020, 155, 1175, 2050, 0),

    # 场景B：重复问题×3 → 自动挖掘生成 pending FAQ（新问题上）
    (3, "新能源电池材料公司融资需求是什么", "股权融资，金额区间5000万元，期望种子轮。",
     ["battery_seed"], ["battery_seed"], [], 1180, 185, 1365, 4800, 6),
    (3, "新能源电池材料公司融资需求是什么", "股权融资5000万元，用于中试线建设与首批客户验证。",
     ["battery_seed"], ["battery_seed"], [], 1210, 195, 1405, 5050, 3),
    (13, "新能源电池材料公司融资需求是什么", "股权融资，金额区间5000万元，期望轮次种子轮。",
     ["battery_seed"], ["battery_seed"], [], 1150, 175, 1325, 4650, 1),

    # 场景C：重复问题×3（智能驾驶天使轮）
    (2, "智能驾驶公司天使轮投前估值", "投前估值1.2亿美元，投后1.5亿美元，融资2000万美元。",
     ["autodrive_angel"], ["autodrive_angel"], [], 1420, 230, 1650, 6100, 5),
    (2, "智能驾驶公司天使轮投前估值", "投前1.2亿美元，投后1.5亿美元。",
     ["autodrive_angel"], ["autodrive_angel"], [], 1350, 205, 1555, 5800, 3),
    (2, "智能驾驶公司天使轮投前估值", "投前估值1.2亿美元。",
     ["autodrive_angel"], ["autodrive_angel"], [], 1220, 185, 1405, 5200, 1),

    # 场景D：重复问题×3（基因治疗 Pre-IPO）
    (4, "基因治疗Pre-IPO投决关注要点", "临床终点设计、医保谈判影响、产能爬坡。",
     ["gene_preipo"], ["gene_preipo"], [], 1680, 320, 2000, 7800, 5),
    (5, "基因治疗Pre-IPO投决关注要点", "关注临床终点、医保谈判与产能爬坡。",
     ["gene_preipo"], ["gene_preipo"], [], 1550, 290, 1840, 7100, 3),
    (12, "基因治疗Pre-IPO投决关注要点", "临床终点设计、医保谈判影响、产能爬坡。",
     ["gene_preipo"], ["gene_preipo"], [], 1490, 280, 1770, 6900, 1),

    # 场景E：权限缺失（风控查最高机密储备清单 → 无权限）
    (6, "一期基金拟投资储备清单里有哪些项目", "该材料保密级别最高，未检索到授权内容。",
     ["fund1_reserve"], [], ["fund1_reserve"], 880, 120, 1000, 3800, 5),
    # 权限缺失（法务查最高保密 AI B轮草稿 → 无权限）
    (7, "某AI公司B轮尽调的重点风险有哪些", "草稿单元仅授权给张伟，当前无权限查看。",
     ["ai_b_draft"], [], ["ai_b_draft"], 880, 120, 1000, 3900, 3),

    # 其余日常访问（丰富当日趋势）
    (2, "光伏储能公司欧洲订单情况", "欧洲订单Q4环比增长40%，户储出货2.1万台。",
     ["pv_storage_b_post"], ["pv_storage_b_post"], [], 1380, 215, 1595, 5600, 0),
    (3, "跨境支付公司毛利率", "毛利率38%，年交易流水400亿元，合规牌照覆盖8个地区。",
     ["crossborder_b"], ["crossborder_b"], [], 1290, 200, 1490, 5400, 0),
    (5, "创新药Pre-IPO轮交割前置条件", "老股东优先购买权放弃函、境外架构重组完成。",
     ["innov_drug_d"], ["innov_drug_d"], [], 1410, 225, 1635, 5900, 0),
    (4, "智能座舱C轮交割是否完成", "交割完成：工商变更、代持还原、对赌补充协议签署。",
     ["smart_cockpit_c"], ["smart_cockpit_c"], [], 1050, 160, 1210, 780, 2),  # 极快
    (3, "半导体材料公司二期扩产资金缺口", "二期扩产资金缺口约3000万元。",
     ["semicond_mat_a"], ["semicond_mat_a"], [], 1340, 210, 1550, 28400, 1),  # 极慢
]


# =====================================================================
# 6) FAQ（覆盖 已发布/待审核/驳回 × 自动挖掘/人工）
# =====================================================================
# (id, question, answer, category, related_unit_key, source_type, status, hit_count,
#  reviewer_id, reviewed_at, created_at, updated_at)
FAQS = [
    (1, "某AI大模型公司的投前估值是多少？", "投前估值20亿元，本轮拟融资2.5亿元，投后25亿元。",
     "尽调", "ai_dw_a", "auto_mined", "published", 18, 4, "2024-09-10 09:00:00", "2024-09-01 09:30:00", "2024-09-10 09:00:00"),
    (2, "生物医药CRO企业的毛利率如何？", "整体毛利率42%，较同行高约5个百分点，在手订单超12亿元。",
     "行业", "biotech_cro_b", "auto_mined", "published", 12, 4, "2024-09-11 09:00:00", "2024-09-06 10:30:00", "2024-09-11 09:00:00"),
    (3, "半导体刻蚀设备C轮的反稀释条款是什么？", "采用加权平均反稀释，优先清算1.2倍，创始人3年竞业限制。",
     "条款", "semicond_c", "manual", "published", 9, 4, "2024-09-12 09:00:00", "2024-09-10 15:00:00", "2024-09-12 09:00:00"),
    (4, "新能源电池材料公司融资需求是什么？", "股权融资，金额区间5000万元，期望轮次种子轮，用于中试线建设。",
     "尽调", "battery_seed", "auto_mined", "published", 15, 4, "2024-09-14 09:00:00", "2024-09-08 17:00:00", "2024-09-14 09:00:00"),
    (5, "工业机器人公司Q3的海外收入占比？", "Q3海外收入占比28%，出货860台，同比增长38%。",
     "投后", "robot_b_post", "manual", "published", 7, 4, "2024-09-15 09:00:00", "2024-09-12 16:00:00", "2024-09-15 09:00:00"),
    (6, "基因治疗Pre-IPO投决关注要点是什么？", "临床终点设计、医保谈判影响、产能爬坡安排。",
     "投决", "gene_preipo", "auto_mined", "pending_review", 8, None, None, "2024-11-03 09:00:00", "2024-11-03 09:00:00"),
    (7, "智能驾驶公司天使轮投前估值是多少？", "投前估值1.2亿美元，拟融资2000万美元，投后1.5亿美元。",
     "尽调", "autodrive_angel", "auto_mined", "pending_review", 5, None, None, "2024-10-20 09:00:00", "2024-10-20 09:00:00"),
    (8, "跨境支付公司B轮合规要点有哪些？", "合规牌照覆盖8个地区，关注跨境收单与资金管理制度。",
     "合规", "crossborder_b", "auto_mined", "pending_review", 4, None, None, "2024-11-04 09:00:00", "2024-11-04 09:00:00"),
    (9, "数据授权协议的保密义务如何约定？", "数据范围含销售明细、客户合同、财务三表，禁止用于尽调以外用途。",
     "合规", "ai_data_agreement", "manual", "rejected", 0, 4, "2024-09-20 09:00:00", "2024-09-19 09:00:00", "2024-09-20 09:00:00"),
    (10, "一期基金拟投储备清单何时更新？", "拟投清单保密级别最高，仅限投资总监以上查阅，不做公开发布。",
     "投后", "fund1_reserve", "manual", "rejected", 0, 4, "2024-11-06 09:00:00", "2024-11-05 09:00:00", "2024-11-06 09:00:00"),
]


# =====================================================================
# 7) 知识缺口（覆盖 已解决/未解决/忽略）
# =====================================================================
# (id, pattern, samples, ask_count, last_asked, status, resolved_unit_key, created, updated)
GAPS = [
    (1, "{公司}最近一轮融资估值是多少", '["某AI公司最新估值","半导体设备公司投后估值变化"]',
     6, "2024-09-20 11:30:00", "resolved", "ai_dw_a", "2024-09-05 09:00:00", "2024-09-05 09:00:00"),
    (2, "{公司}的竞争格局如何", '["AI大模型赛道竞争格局","CRO行业竞争格局"]',
     8, "2024-09-21 15:20:00", "unresolved", None, "2024-09-06 09:00:00", "2024-09-06 09:00:00"),
    (3, "{项目}退出计划与预期回报", '["一期基金退出节奏","机器人项目退出预期"]',
     5, "2024-09-22 10:45:00", "unresolved", None, "2024-09-08 09:00:00", "2024-09-08 09:00:00"),
    (4, "{公司}创始人及核心团队背景", '["储能项目创始人履历","骨科机器人创始人背景"]',
     4, "2024-09-23 14:10:00", "unresolved", None, "2024-09-10 09:00:00", "2024-09-10 09:00:00"),
    (5, "{公司}对赌条款触发条件", '["医疗器械对赌条件","Pre-A对赌约定"]',
     3, "2024-09-18 09:40:00", "ignored", None, "2024-09-11 09:00:00", "2024-09-11 09:00:00"),
    (6, "一期基金已投项目的投后数据", '["一期基金投后项目进展","投后项目Q3数据"]',
     7, "2024-09-24 16:00:00", "resolved", "fund1_review", "2024-09-12 09:00:00", "2024-09-12 09:00:00"),
    (7, "某基金最近的投资动态", '["一期基金最近投了什么","基金最新投资动态"]',
     4, "2024-11-01 09:30:00", "unresolved", None, "2024-10-20 09:00:00", "2024-10-20 09:00:00"),
    (8, "投委会最近一次会议决议", '["投委会决议内容","最近投决会结果"]',
     5, "2024-11-03 11:00:00", "unresolved", None, "2024-10-22 09:00:00", "2024-10-22 09:00:00"),
    (9, "某公司Pre-IPO具体时间表", '["基因治疗公司上市时间表","Pre-IPO申报安排"]',
     3, "2024-11-08 15:00:00", "resolved", "gene_preipo", "2024-10-25 09:00:00", "2024-10-25 09:00:00"),
    (10, "某公司下季度融资计划", '["下季度融资安排","后续轮次计划"]',
     2, "2024-11-10 10:00:00", "ignored", None, "2024-10-28 09:00:00", "2024-10-28 09:00:00"),
]


# =====================================================================
# 执行逻辑
# =====================================================================
def reset_tables(db) -> None:
    """清空 12 张业务表（关闭外键约束后 TRUNCATE，重置自增 id）。"""
    db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    tables = [
        UnitPermission, QaMessage, QaAccessLog, KnowledgeGap, Faq,
        QaSession, UserRole, RolePermission, KnowledgeUnit, User, Department, Role,
    ]
    for t in tables:
        db.execute(text(f"TRUNCATE TABLE `{t.__tablename__}`"))
    db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db.commit()


def seed_base(db) -> None:
    for rid, name, code, desc in ROLES:
        db.add(Role(id=rid, role_name=name, role_code=code, description=desc))
    for did, pid, name, dtype, leader, sort in DEPARTMENTS:
        db.add(Department(id=did, parent_id=pid, name=name, dept_type=dtype,
                          leader_id=leader, sort_order=sort))
    for uid, uname, disp, dept, status in USERS:
        db.add(User(id=uid, username=uname, password_hash=ADMIN_HASH,
                    display_name=disp, department_id=dept, status=status))
    for uid, rid in USER_ROLES:
        db.add(UserRole(user_id=uid, role_id=rid))
    for rid, code, ptype in ROLE_PERMISSIONS:
        db.add(RolePermission(role_id=rid, permission_code=code, permission_type=ptype))
    db.commit()


def seed_units(db, ks) -> dict:
    """插入知识单元，返回 key -> id 映射。"""
    ids: dict = {}
    for (key, title, category, industry, rnd, amount, currency, valuation,
         region, stage, conf, status, creator, content) in UNITS:
        unit = KnowledgeUnit(
            unit_code=ks.generate_unit_code(db),
            title=title,
            content=content,
            summary=content[:120].replace("\n", " "),
            category=category,
            industry=ks.normalize_industry(industry) if industry else None,
            financing_round=ks.normalize_round(rnd) if rnd else None,
            amount=amount,
            currency=currency,
            valuation=valuation,
            region=region,
            deal_stage=stage,
            confidential_level=conf,
            status=status,
            version=1,
            creator_id=creator,
        )
        db.add(unit)
        db.flush()
        ids[key] = unit.id
    return ids


def seed_permissions(db, ids) -> None:
    for key, ttype, tid in UNIT_PERMISSIONS:
        db.add(UnitPermission(unit_id=ids[key], target_type=ttype, target_id=tid))


def seed_sessions(db) -> None:
    import uuid
    for user_id, title, messages in SESSIONS:
        sid = str(uuid.uuid4())
        base = UTCNOW() - timedelta(days=messages[0][2])
        db.add(QaSession(session_id=sid, user_id=user_id, title=title,
                         created_at=base, updated_at=base))
        for i, (role, content, days) in enumerate(messages):
            ts = base + timedelta(hours=i)
            db.add(QaMessage(session_id=sid, role=role, content=content, created_at=ts))


def seed_logs(db, ids) -> None:
    def resolve(keys):
        return [ids[k] for k in keys]
    for (user_id, question, answer, rec, auth, unauth,
         ptok, ctok, ttok, rt, days) in LOGS:
        created = UTCNOW() - timedelta(days=days, hours=8)
        db.add(QaAccessLog(
            session_id=None,
            user_id=user_id,
            question=question,
            answer=answer,
            recalled_unit_ids_json=resolve(rec),
            authorized_unit_ids_json=resolve(auth),
            unauthorized_unit_ids_json=resolve(unauth),
            prompt_tokens=ptok, completion_tokens=ctok, total_tokens=ttok,
            response_time_ms=rt, created_at=created,
        ))


def seed_faqs(db, ids) -> None:
    for (fid, q, a, cat, rel, stype, status, hit, reviewer, rev_at,
         created, updated) in FAQS:
        db.add(Faq(
            id=fid, question=q, answer=a, category=cat,
            related_unit_id=ids.get(rel), source_type=stype, status=status,
            hit_count=hit, reviewer_id=reviewer,
            reviewed_at=datetime.fromisoformat(rev_at.replace(" ", "T")) if rev_at else None,
            created_at=datetime.fromisoformat(created.replace(" ", "T")),
            updated_at=datetime.fromisoformat(updated.replace(" ", "T")),
        ))


def seed_gaps(db, ids) -> None:
    for (gid, pattern, samples, ask, last, status, rel, created, updated) in GAPS:
        db.add(KnowledgeGap(
            id=gid, question_pattern=pattern,
            sample_questions_json=samples,
            ask_count=ask, last_asked_at=datetime.fromisoformat(last.replace(" ", "T")),
            status=status, resolved_unit_id=ids.get(rel),
            created_at=datetime.fromisoformat(created.replace(" ", "T")),
            updated_at=datetime.fromisoformat(updated.replace(" ", "T")),
        ))


def emit_docs(ids) -> None:
    """把知识单元正文导出为 .md，便于在 UI 中测试「导入流程」。"""
    out = Path(settings.upload_dir) / "demo_sources"
    out.mkdir(parents=True, exist_ok=True)
    for (key, title, *_, content) in UNITS:
        safe = quote(title, safe="")[:40]
        (out / f"{ids[key]}_{safe}.md").write_text(content, encoding="utf-8")
    print(f"[seed_demo] 已导出 {len(UNITS)} 份源文档到 {out}")


def _api_call(method: str, path: str, token: str | None = None, payload: dict | None = None) -> dict:
    """调用后端 HTTP API（backend 容器内 localhost:8000，或 SEED_DEMO_API_BASE 覆盖）。"""
    base = os.environ.get("SEED_DEMO_API_BASE", "http://localhost:8000")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sync_indexes_via_api(db, ks, timeout: int = 900) -> dict:
    """通过后端 HTTP API 触发向量/ES 索引重建，并轮询到终态。

    为什么不能在本进程直调 rebuild_vector_index：
      本项目的向量存储是嵌入式 Milvus Lite（单文件 /app/data/milvus.db），
      文件锁被 backend 主进程持有；seed_demo 是独立进程，直连该文件会报
      「Open /app/data/milvus.db failed, the file has been opened by another program」，
      索引永远写不进去（表现为 index_status=pending、问答召回为空、误报"无授权片段"）。
      因此改为调用后端自己的 reindex API，由持有文件锁的 backend 进程完成
      Milvus + ES 写入，本脚本只负责触发与轮询。

    失败时降级：本进程直连 ES 写关键字索引（ES 无单文件锁），并返回标记提示
    向量索引需另行补齐（如 POST /api/knowledge/reindex）。
    """
    try:
        login = _api_call("POST", "/api/auth/login", payload={"username": "admin", "password": "admin123"})
        token = login.get("access_token")
        if not token:
            raise RuntimeError(f"admin 登录失败：{login}")
        started = _api_call("POST", "/api/knowledge/reindex?status=all&batch_size=16", token=token, payload={})
        task_id = started.get("task_id")
        if not task_id:
            raise RuntimeError(f"触发 reindex 失败：{started}")
        print(f"[seed_demo] 已通过后端 API 触发索引重建任务 {task_id}，轮询中...")
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            time.sleep(4)
            st = _api_call("GET", f"/api/knowledge/reindex/{task_id}", token=token)
            status = st.get("status")
            print(f"  - 进度: status={status} total={st.get('total')} indexed={st.get('indexed')} failed={st.get('failed')}")
            last = st
            if status in ("done", "error"):
                return st
        raise TimeoutError(f"reindex 任务 {task_id} 超过 {timeout}s 未完成（最后一次状态 {last}）")
    except Exception as exc:  # noqa: BLE001
        print(f"[seed_demo] ⚠️ HTTP 触发索引重建失败：{exc}")
        print("[seed_demo] 降级：本进程直连 ES 写入关键字索引（向量索引需另行补齐）...")
        try:
            from app.core.es import ensure_knowledge_index, index_keyword_unit

            from app.models.models import KnowledgeUnit
            from sqlalchemy import select

            ensure_knowledge_index()
            units = db.execute(select(KnowledgeUnit)).scalars().all()
            for u in units:
                index_keyword_unit(u.unit_code, ks._unit_metadata(u))
            db.commit()
            print(f"[seed_demo] ✅ 已直写 ES 关键字索引 {len(units)} 条（Milvus 向量索引未写入）。")
            print("[seed_demo] 提示：向量索引可用 POST /api/knowledge/reindex 补齐（需 backend 主进程执行）。")
            return {"status": "degraded", "indexed": len(units), "total": len(units), "failed": []}
        except Exception as exc2:  # noqa: BLE001
            print(f"[seed_demo] ❌ ES 降级写入也失败：{exc2}")
            return {"status": "error", "indexed": 0, "total": 0, "failed": []}


def print_coverage(db) -> None:
    from sqlalchemy import func, select
    print("\n========== 演示数据覆盖检查 ==========")
    for label, col in [
        ("项目阶段 deal_stage", KnowledgeUnit.deal_stage),
        ("融资轮次 financing_round", KnowledgeUnit.financing_round),
        ("币种 currency", KnowledgeUnit.currency),
        ("保密级别 confidential_level", KnowledgeUnit.confidential_level),
        ("状态 status", KnowledgeUnit.status),
        ("行业 industry", KnowledgeUnit.industry),
    ]:
        rows = db.execute(select(col, func.count(KnowledgeUnit.id)).group_by(col)).all()
        dist = ", ".join(f"{v or 'NULL'}={c}" for v, c in sorted(rows, key=lambda x: str(x[0])))
        print(f"  - {label}: {dist}")
    print("  - 权限四维: global / department / role / user 均已配置（含「全四维组合」与「最高保密仅单人可见」）")
    print("  - 账号场景: 普通/多角色(苏敏)/停用(林杰) 均已覆盖")
    print("  - 问答场景: 多轮对话 / 近7天趋势 / 权限缺失拦截 / FAQ自动挖掘(重复问题×3) 均已覆盖")
    print("=======================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="投融资知识库演示数据生成脚本")
    parser.add_argument("--yes", action="store_true",
                        help="确认执行（默认 TRUNCATE 12 张业务表后整体重建；仅清空需加 --clear-only）")
    parser.add_argument("--no-index", action="store_true",
                        help="跳过向量/ES 索引重建（仅造数）")
    parser.add_argument("--emit-docs", action="store_true",
                        help="额外把源文档导出到 uploads/demo_sources 供导入流程测试")
    parser.add_argument("--clear-only", action="store_true",
                        help="仅清空 12 张业务表，不生成演示数据（需与 --yes 搭配）")
    args = parser.parse_args()

    if not args.yes:
        print("⚠️  这是危险操作：脚本将清空演示数据（可再整体重建）。")
        print("     请确认后使用： python scripts/seed_demo.py --yes")
        print("     仅造数不建索引： python scripts/seed_demo.py --yes --no-index")
        print("     仅清空不重建：   python scripts/seed_demo.py --yes --clear-only")
        sys.exit(0)

    print(f"[seed_demo] MySQL -> {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

    db = SessionLocal()
    try:
        if args.clear_only:
            reset_tables(db)
            print("[seed_demo] ✅ 已清空 12 张业务表（--clear-only，未重建演示数据）")
            return
        reset_tables(db)
        print("[seed_demo] 已清空 12 张业务表")

        seed_base(db)
        ks = KnowledgeService()
        ids = seed_units(db, ks)
        seed_permissions(db, ids)
        seed_sessions(db)
        seed_logs(db, ids)
        seed_faqs(db, ids)
        seed_gaps(db, ids)
        db.commit()
        print(f"[seed_demo] 已写入：{len(UNITS)} 知识单元 / {len(UNIT_PERMISSIONS)} 权限规则 / "
              f"{len(SESSIONS)} 会话 / {len(LOGS)} 访问日志 / {len(FAQS)} FAQ / {len(GAPS)} 知识缺口")

        if args.emit_docs:
            emit_docs(ids)

        if args.no_index:
            print("[seed_demo] 已跳过向量索引重建（--no-index）")
        else:
            print("[seed_demo] 正在重建向量/ES 索引（依赖 embedding 网关，失败单元将标记 failed）...")
            try:
                result = sync_indexes_via_api(db, ks)
                if result.get("status") == "error":
                    print(f"[seed_demo] 索引重建未完成：{result}")
                else:
                    print(f"[seed_demo] 索引重建结果：总数={result.get('total')} "
                          f"成功={result.get('indexed')} 失败={len(result.get('failed') or [])} "
                          f"状态={result.get('status')}")
            except Exception as exc:  # noqa: BLE001
                print(f"[seed_demo] 索引重建异常（数据已入库）：{exc}")

        print_coverage(db)
        print("[seed_demo] ✅ 演示数据生成完成。管理员账号：admin / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
