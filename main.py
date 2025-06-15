# --- load environment variables from .env file before importing anything using them
import argparse
from dotenv import load_dotenv
from function import (fetch_from_table, export_to_local_document,
                      create_lark_app_table, recheck_invoices, sync_from_table,
                      sync_to_table, auto_sync, group_invoices)


def main():
    parser = argparse.ArgumentParser(description="发票处理脚本")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 子命令：fetch
    fetch_parser = subparsers.add_parser("fetch", help="从 收集表 提取表格信息并更新数据库")
    fetch_parser.add_argument("--url",
                              metavar="lark bitable url",
                              required=True,
                              help="(飞书)用于报销统计的多维表格数据表链接(需包含table参数)")
    fetch_parser.add_argument("--db",
                              default="invoices.db",
                              help="SQLite 数据库路径")
    fetch_parser.add_argument("--fallback",
                              default=False,
                              action="store_true",
                              help="启用备用解析服务（当主解析失败时）")

    # 子命令：sync
    sync_parser = subparsers.add_parser(
        "sync",
        help="同步 云文档 内发票状态",
        description="同步 云文档 内发票状态(默认根据修改时间判断同步方向)")
    sync_parser.add_argument("--url",
                             metavar="lark bitable url",
                             required=True,
                             help="(飞书)用于报销统计的多维表格数据表链接(需包含table参数)")

    sync_parser.add_argument(
        "--force",
        choices=["database", "table"],
        help="指定同步方向 [database: 将本地数据同步到云文档 | table: 将云文档数据同步到本地]")

    sync_parser.add_argument("--db",
                             default="invoices.db",
                             help="SQLite 数据库路径")

    # 子命令：create
    create_parser = subparsers.add_parser("create", help="创建 云文档 并上传数据库内的发票信息")
    create_parser.add_argument("--url",
                               metavar="lark bitable url",
                               required=True,
                               help="(飞书)用于报销统计的多维表格链接")
    create_parser.add_argument("--db",
                               default="invoices.db",
                               help="SQLite 数据库路径")

    # 子命令：export
    export_parser = subparsers.add_parser("export", help="从数据库导出电子文档")
    export_parser.add_argument("--db",
                               default="invoices.db",
                               help="SQLite 数据库路径")

    export_parser.add_argument("target", metavar="PATH", help="本地文件路径")

    # 子命令：recheck
    recheck_parser = subparsers.add_parser(
        "recheck", help="再次对所有解析后的发票(processed)进行自定义校验")
    recheck_parser.add_argument("--db",
                                default="invoices.db",
                                help="SQLite 数据库路径")

    # 子命令：group
    group_parser = subparsers.add_parser("group",
                                         help="解析给定的json文件,设置发票的status")
    group_parser.add_argument("target", help="必填参数：指定处理目标，例如 'group.json'")
    group_parser.add_argument("--db",
                              default="invoices.db",
                              help="SQLite 数据库路径")

    args = parser.parse_args()

    if args.command == "fetch":
        fetch_from_table(args.url, args.db, args.fallback)
    elif args.command == "export":
        export_to_local_document(args.db, args.target)
    elif args.command == "sync":
        if args.force == "database":
            sync_to_table(args.url, args.db)
        elif args.force == "table":
            sync_from_table(args.url, args.db)
        else:
            auto_sync(args.url, args.db)
    elif args.command == "create":
        create_lark_app_table(args.url, args.db)
    elif args.command == "recheck":
        recheck_invoices(args.db)
    elif args.command == "group":
        group_invoices(args.target, args.db)


if __name__ == "__main__":
    load_dotenv()
    main()
