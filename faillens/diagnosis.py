from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Diagnosis, TestResult


@dataclass(frozen=True, slots=True)
class Rule:
    category: str
    label: str
    summary: str
    patterns: tuple[tuple[str, float], ...]
    suggestions: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        "locator_failure",
        "元素定位失败",
        "页面元素未找到、不可见或定位器已失效。",
        (
            (r"timeout.*(?:locator|element|selector)", 0.52),
            (r"(?:locator|element|selector).*(?:not found|not visible|detached)", 0.58),
            (r"waiting for (?:locator|selector)", 0.55),
            (r"strict mode violation", 0.65),
            (r"no such element", 0.65),
        ),
        (
            "检查页面结构和定位器是否在本次版本中发生变化。",
            "优先使用 data-testid 等稳定属性，避免依赖动态 class 或绝对 XPath。",
            "查看失败截图、DOM 和浏览器控制台日志，确认是否存在遮挡或异步加载。",
        ),
    ),
    Rule(
        "network_timeout",
        "网络或超时",
        "请求超时、连接被重置或目标服务不可达。",
        (
            (r"(?:read|connect|connection)?\s*timeout", 0.52),
            (r"timed out", 0.52),
            (r"connection (?:refused|reset|aborted)", 0.62),
            (r"econn(?:refused|reset|aborted)", 0.67),
            (r"name or service not known|dns", 0.62),
        ),
        (
            "确认目标服务、域名解析和测试环境网络是否正常。",
            "结合接口耗时记录判断是合理超时、环境抖动还是性能退化。",
            "不要只增加等待时间；先确认请求是否真正发出以及服务端是否收到。",
        ),
    ),
    Rule(
        "test_data_issue",
        "测试数据异常",
        "测试数据缺失、重复或违反数据库约束。",
        (
            (r"duplicate (?:key|entry)", 0.67),
            (r"unique constraint|integrityerror", 0.62),
            (r"foreign key constraint", 0.65),
            (r"(?:record|user|order|product).*(?:not found|does not exist)", 0.48),
            (r"test data|fixture data", 0.42),
        ),
        (
            "确认前置数据是否创建成功，以及用例之间是否共享并修改了同一份数据。",
            "为并行执行的数据增加唯一后缀，并在用例结束后可靠清理。",
            "检查环境初始化脚本和数据库约束是否与当前版本一致。",
        ),
    ),
    Rule(
        "environment_issue",
        "测试环境异常",
        "运行节点、浏览器或依赖服务存在环境问题。",
        (
            (r"no space left on device|disk full", 0.75),
            (r"browser executable.*(?:not found|missing)", 0.72),
            (r"service unavailable|http\s*503", 0.56),
            (r"out of memory|oomkilled", 0.7),
            (r"permission denied", 0.48),
        ),
        (
            "检查测试节点磁盘、内存、权限以及浏览器依赖。",
            "核对依赖服务健康状态和本次流水线的环境变更。",
            "修复环境后重跑；若同一错误频繁出现，应增加运行前健康检查。",
        ),
    ),
    Rule(
        "application_error",
        "疑似应用错误",
        "被测服务返回服务端错误或出现未处理异常。",
        (
            (r"http(?: status)?\s*5\d\d", 0.58),
            (r"status(?:_code)?\s*[=:]\s*5\d\d", 0.58),
            (r"internal server error", 0.65),
            (r"nullpointerexception|segmentation fault", 0.62),
        ),
        (
            "使用请求 ID 或时间范围关联服务端日志，定位第一个业务异常。",
            "确认输入数据合法后，创建产品缺陷并附上请求、响应和服务端错误信息。",
            "检查失败是否只出现在特定版本、环境或数据组合中。",
        ),
    ),
    Rule(
        "assertion_failure",
        "断言失败",
        "实际结果与测试预期不一致。",
        (
            (r"assertionerror", 0.5),
            (r"assert .*==|expected.+(?:but|got|actual)", 0.45),
            (r"json.*(?:diff|mismatch)", 0.48),
        ),
        (
            "比较实际值、预期值和本次需求，确认是产品行为变化还是断言过期。",
            "检查动态字段、浮点误差、排序以及时区等常见误报来源。",
            "若属于产品缺陷，保留最小可复现输入和完整响应。",
        ),
    ),
)


UNKNOWN = Diagnosis(
    category="unknown",
    label="暂未识别",
    confidence=0.2,
    summary="现有日志未命中明确故障模式，需要人工查看完整堆栈。",
    evidence=[],
    suggestions=[
        "补充异常堆栈、标准输出、截图、DOM 或网络日志后重新分析。",
        "查找与最近代码、环境和测试数据变更之间的关联。",
    ],
)


def diagnose(result: TestResult) -> Diagnosis | None:
    if result.status not in {"failed", "error"}:
        return None
    text = result.diagnostic_text
    if not text:
        return UNKNOWN

    candidates: list[tuple[float, int, Rule, list[str]]] = []
    for index, rule in enumerate(RULES):
        score = 0.0
        evidence: list[str] = []
        for pattern, weight in rule.patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                score += weight
                excerpt = " ".join(match.group(0).split())[:180]
                if excerpt not in evidence:
                    evidence.append(excerpt)
        if score:
            confidence = min(0.97, 0.28 + score)
            candidates.append((confidence, -index, rule, evidence))

    if not candidates:
        return UNKNOWN
    confidence, _, rule, evidence = max(candidates, key=lambda item: (item[0], item[1]))
    return Diagnosis(
        category=rule.category,
        label=rule.label,
        confidence=round(confidence, 2),
        summary=rule.summary,
        evidence=evidence[:3],
        suggestions=list(rule.suggestions),
    )

