from __future__ import annotations

import argparse
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .analyzer import analyze
from .junit import load_results
from .report import write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faillens", description="自动化测试失败诊断与 flaky 分析")
    parser.add_argument("--version", action="version", version=f"FailLens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("analyze", help="分析 JUnit XML 并生成报告")
    cmd.add_argument("inputs", nargs="+", metavar="INPUT", help="JUnit XML 文件或包含 XML 的目录")
    cmd.add_argument("--output", "-o", required=True, help="报告输出目录")
    cmd.add_argument("--project", default="自动化测试诊断报告", help="报告中的项目名称")
    cmd.add_argument("--min-confidence", type=float, default=0.45, help="重点诊断最低置信度（0-1）")
    cmd.add_argument("--no-artifacts", action="store_true", help="不复制截图、DOM 和日志附件")
    serve = sub.add_parser("serve", help="在本地浏览器中预览已生成的报告")
    serve.add_argument("directory", nargs="?", default="output/faillens-report", help="报告目录")
    serve.add_argument("--host", default="127.0.0.1", help="监听地址，默认仅本机可访问")
    serve.add_argument("--port", type=int, default=8765, help="监听端口")
    serve.add_argument("--open", action="store_true", help="启动后打开默认浏览器")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        directory = Path(args.directory).resolve()
        if not (directory / "report.html").exists():
            print(f"启动失败：{directory} 中没有 report.html", file=sys.stderr)
            return 1
        if not 1 <= args.port <= 65535:
            print("启动失败：端口必须在 1 到 65535 之间", file=sys.stderr)
            return 2
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        try:
            server = ThreadingHTTPServer((args.host, args.port), handler)
        except OSError as exc:
            print(f"启动失败：{exc}", file=sys.stderr)
            return 1
        url = f"http://{args.host}:{args.port}/report.html"
        print(f"FailLens 报告已启动：{url}")
        print("按 Ctrl+C 停止服务")
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")
        finally:
            server.server_close()
        return 0
    if not 0 <= args.min_confidence <= 1:
        print("错误：--min-confidence 必须在 0 到 1 之间", file=sys.stderr)
        return 2
    try:
        results, runs = load_results(args.inputs)
        report = analyze(results, runs, args.inputs, args.project, args.min_confidence)
        html_path, json_path = write_reports(report, Path(args.output).resolve(), not args.no_artifacts)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"分析失败：{exc}", file=sys.stderr)
        return 1

    failures = sum(item.result.status in {"failed", "error"} for item in report.results)
    flaky = sum(item.is_flaky for item in report.histories)
    print(f"分析完成：{len(report.results)} 条执行记录，{failures} 条失败，{flaky} 个 flaky 用例")
    print(f"HTML：{html_path}")
    print(f"JSON：{json_path}")
    return 0

