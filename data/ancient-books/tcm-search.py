#!/usr/bin/env python3
"""
TCM Ancient Books Search Tool v2
中医古籍全文搜索工具 - 增强版

特性:
  - SQLite 索引缓存（首遍建索引，后续秒搜）
  - 关键词 / 正则搜索
  - 多关键词组合 (AND / OR)
  - 按分类 / 朝代 / 书籍过滤
  - JSON / CSV 导出

用法:
  python3 tcm-search.py 桂枝汤                     # 关键词搜索
  python3 tcm-search.py "桂枝.*汤" --regex          # 正则搜索
  python3 tcm-search.py --and "桂枝,白芍,甘草"      # 多词AND（必须同时出现）
  python3 tcm-search.py --or "麻黄,桂枝,杏仁"       # 多词OR（任一出现）
  python3 tcm-search.py 气虚 --cat 本草             # 按分类搜
  python3 tcm-search.py --cat 伤寒 --list-books     # 列出某分类的书
  python3 tcm-search.py --reindex                   # 强制重建索引
  python3 tcm-search.py --stats                     # 统计信息
  python3 tcm-search.py --export results.json 桂枝  # 导出结果
"""

import os
import sys
import re
import sqlite3
import hashlib
import time
import argparse
import json
import csv
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

# ── 配置 ──────────────────────────────────────────────
BOOKS_DIR = Path(__file__).parent
DB_PATH = BOOKS_DIR / ".tcm-search-index.db"

# 分类关键词映射
CATEGORIES = {
    '本草': ['本草'],
    '伤寒': ['伤寒'],
    '金匮': ['金匮'],
    '温病': ['温病', '瘟疫'],
    '针灸': ['针灸', '灸法', '灸经'],
    '方书': ['方', '普济', '千金', '肘后', '和剂', '圣济'],
    '医案': ['医案', '医话', '类案'],
    '女科': ['女科', '妇科', '产', '胎'],
    '儿科': ['儿科', '幼科', '小儿', '婴童', '麻疹', '痘疹'],
    '外科': ['外科', '疡'],
    '眼科': ['眼科', '目', '银海'],
    '喉科': ['喉'],
    '脉学': ['脉'],
    '内经': ['内经', '素问', '灵枢', '太素'],
    '难经': ['难经'],
    '养生': ['养生', '导引', '修', '寿世'],
}

# ── 编码处理 ───────────────────────────────────────────
def detect_and_decode(raw: bytes) -> str:
    for enc in ['utf-8', 'gbk', 'gb18030', 'gb2312', 'big5']:
        try:
            text = raw.decode(enc)
            if any('\u4e00' <= c <= '\u9fff' for c in text):
                return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode('gbk', errors='replace')

def get_file_hash(filepath: Path) -> str:
    stat = filepath.stat()
    return hashlib.md5(f"{filepath}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()

# ── 索引数据库 ─────────────────────────────────────────
class SearchIndex:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # 注册 REGEXP 函数
        self.conn.create_function("REGEXP", 2, lambda pattern, text: 1 if re.search(pattern, text or '') else 0)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT,
                file_size INTEGER,
                book_name TEXT,
                author TEXT,
                dynasty TEXT,
                category TEXT,
                line_count INTEGER,
                indexed_at REAL
            );
            CREATE TABLE IF NOT EXISTS lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                line_num INTEGER,
                content TEXT,
                FOREIGN KEY (file_path) REFERENCES books(file_path)
            );
            CREATE INDEX IF NOT EXISTS idx_lines_file ON lines(file_path);
            CREATE INDEX IF NOT EXISTS idx_lines_content ON lines(content);
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str):
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
        self.conn.commit()

    def is_book_indexed(self, filepath: Path) -> bool:
        file_hash = get_file_hash(filepath)
        row = self.conn.execute(
            "SELECT file_hash FROM books WHERE file_path=?", (str(filepath),)
        ).fetchone()
        return row is not None and row[0] == file_hash

    def index_book(self, filepath: Path, force: bool = False, auto_commit: bool = True):
        if not force and self.is_book_indexed(filepath):
            return False

        try:
            raw = filepath.read_bytes()
            text = detect_and_decode(raw)
        except Exception as e:
            print(f"  ⚠️ 无法读取: {filepath.name} ({e})", file=sys.stderr)
            return False

        lines = text.split('\n')
        info = extract_book_info(text)

        # 删除旧索引
        self.conn.execute("DELETE FROM lines WHERE file_path=?", (str(filepath),))
        self.conn.execute("DELETE FROM books WHERE file_path=?", (str(filepath),))

        # 插入书籍信息
        self.conn.execute(
            "INSERT INTO books VALUES(?,?,?,?,?,?,?,?,?)",
            (str(filepath), get_file_hash(filepath), filepath.stat().st_size,
             info.get('书名', ''), info.get('作者', ''), info.get('朝代', ''),
             classify_book(filepath.name), len(lines), time.time())
        )

        # 批量插入行（每5000行提交一次）
        batch = [(str(filepath), i+1, line) for i, line in enumerate(lines) if line.strip()]
        for chunk_start in range(0, len(batch), 5000):
            chunk = batch[chunk_start:chunk_start+5000]
            self.conn.executemany("INSERT INTO lines(file_path,line_num,content) VALUES(?,?,?)", chunk)
        if auto_commit:
            self.conn.commit()
        del batch  # 释放内存
        del lines
        return True

    def search(self, query: str, regex: bool = False, file_filter: str = None,
               category: str = None, dynasty: str = None, context_lines: int = 2,
               max_results: int = 50) -> List[Dict]:
        """搜索索引"""
        conditions = []
        params = []

        if regex:
            conditions.append("l.content REGEXP ?")
            params.append(query)
        else:
            conditions.append("l.content LIKE ?")
            params.append(f"%{query}%")

        if file_filter:
            conditions.append("b.file_path LIKE ?")
            params.append(f"%{file_filter}%")

        if category:
            conditions.append("b.category = ?")
            params.append(category)

        if dynasty:
            conditions.append("b.dynasty LIKE ?")
            params.append(f"%{dynasty}%")

        where = " AND ".join(conditions)

        sql = f"""
            SELECT l.file_path, l.line_num, l.content, b.book_name, b.author, b.dynasty
            FROM lines l JOIN books b ON l.file_path = b.file_path
            WHERE {where}
            ORDER BY b.book_name, l.line_num
            LIMIT ?
        """
        params.append(max_results)

        rows = self.conn.execute(sql, params).fetchall()
        return [{
            'file_path': r[0],
            'line_num': r[1],
            'content': r[2],
            'book_name': r[3],
            'author': r[4],
            'dynasty': r[5],
        } for r in rows]

    def search_multi(self, keywords: List[str], mode: str = 'AND',
                     file_filter: str = None, category: str = None,
                     dynasty: str = None, max_results: int = 50) -> List[Dict]:
        """多关键词搜索"""
        # 构建子查询
        sub_conditions = []
        base_params = []

        if file_filter:
            sub_conditions.append("b.file_path LIKE ?")
            base_params.append(f"%{file_filter}%")
        if category:
            sub_conditions.append("b.category = ?")
            base_params.append(category)
        if dynasty:
            sub_conditions.append("b.dynasty LIKE ?")
            base_params.append(f"%{dynasty}%")

        base_where = " AND ".join(sub_conditions) if sub_conditions else "1=1"

        if mode == 'AND':
            # 每个关键词必须在同一个文件中出现
            exists_clauses = []
            for kw in keywords:
                exists_clauses.append(f"""
                    EXISTS (
                        SELECT 1 FROM lines l2
                        WHERE l2.file_path = b.file_path AND l2.content LIKE ?
                    )
                """)
                base_params.append(f"%{kw}%")

            sql = f"""
                SELECT DISTINCT b.file_path, b.book_name, b.author, b.dynasty
                FROM books b
                WHERE {base_where} AND {' AND '.join(exists_clauses)}
                LIMIT ?
            """
            base_params.append(max_results)

            rows = self.conn.execute(sql, base_params).fetchall()

            results = []
            for r in rows:
                file_path, book_name, author, dynasty_val = r
                # 找出每个关键词的匹配行
                matches = {}
                for kw in keywords:
                    kw_rows = self.conn.execute(
                        "SELECT line_num, content FROM lines WHERE file_path=? AND content LIKE ? ORDER BY line_num LIMIT 5",
                        (file_path, f"%{kw}%")
                    ).fetchall()
                    matches[kw] = [{'line_num': kr[0], 'content': kr[1]} for kr in kw_rows]

                results.append({
                    'file_path': file_path,
                    'book_name': book_name,
                    'author': author,
                    'dynasty': dynasty_val,
                    'keyword_matches': matches,
                })
            return results

        else:  # OR mode
            like_clauses = []
            for kw in keywords:
                like_clauses.append("l.content LIKE ?")
                base_params.append(f"%{kw}%")

            sql = f"""
                SELECT l.file_path, l.line_num, l.content, b.book_name, b.author, b.dynasty
                FROM lines l JOIN books b ON l.file_path = b.file_path
                WHERE {base_where} AND ({' OR '.join(like_clauses)})
                ORDER BY b.book_name, l.line_num
                LIMIT ?
            """
            base_params.append(max_results)

            rows = self.conn.execute(sql, base_params).fetchall()
            return [{
                'file_path': r[0],
                'line_num': r[1],
                'content': r[2],
                'book_name': r[3],
                'author': r[4],
                'dynasty': r[5],
            } for r in rows]

    def get_stats(self) -> Dict:
        total_books = self.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        total_lines = self.conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0]
        total_size = self.conn.execute("SELECT COALESCE(SUM(file_size),0) FROM books").fetchone()[0]

        by_category = dict(self.conn.execute(
            "SELECT category, COUNT(*) FROM books GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall())

        by_dynasty = dict(self.conn.execute(
            "SELECT dynasty, COUNT(*) FROM books WHERE dynasty != '' GROUP BY dynasty ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall())

        return {
            'total_books': total_books,
            'total_lines': total_lines,
            'total_size_mb': total_size / 1024 / 1024,
            'by_category': by_category,
            'by_dynasty': by_dynasty,
        }

    def list_books(self, category: str = None, dynasty: str = None) -> List[Dict]:
        conditions = []
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if dynasty:
            conditions.append("dynasty LIKE ?")
            params.append(f"%{dynasty}%")
        where = " AND ".join(conditions) if conditions else "1=1"

        rows = self.conn.execute(
            f"SELECT file_path, book_name, author, dynasty, category, file_size FROM books WHERE {where} ORDER BY book_name",
            params
        ).fetchall()

        return [{
            'file_path': r[0],
            'book_name': r[1],
            'author': r[2],
            'dynasty': r[3],
            'category': r[4],
            'size_kb': r[5] / 1024,
        } for r in rows]

    def close(self):
        self.conn.close()

# ── 辅助函数 ───────────────────────────────────────────
def classify_book(filename: str) -> str:
    """根据文件名分类"""
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in filename:
                return cat
    return '其他'

def extract_book_info(text: str) -> Dict:
    """从文本头部提取书籍信息"""
    head = text[:2000]
    info = {}
    for pattern, key in [
        (r'书名[：:]\s*(.+)', '书名'),
        (r'作者[：:]\s*(.+)', '作者'),
        (r'朝代[：:]\s*(.+)', '朝代'),
        (r'年份[：:]\s*(.+)', '年份'),
    ]:
        m = re.search(pattern, head)
        if m:
            info[key] = m.group(1).strip()
    return info

# ── 索引构建 ───────────────────────────────────────────
def build_index(index: SearchIndex, force: bool = False):
    """构建或更新索引"""
    books = sorted(BOOKS_DIR.glob("*.txt"))
    total = len(books)
    new_count = 0
    skip_count = 0

    print(f"📚 索引构建中... ({total} 本书)", flush=True)
    if force:
        print("   ⚡ 强制重建模式", flush=True)

    t0 = time.time()
    for i, book in enumerate(books, 1):
        # 每50本提交一次（auto_commit=False 时手动提交）
        auto_commit = (i % 50 == 0) or (i == total)
        indexed = index.index_book(book, force=force, auto_commit=auto_commit)
        if indexed:
            new_count += 1
            if new_count % 100 == 0:
                elapsed = time.time() - t0
                rate = new_count / elapsed
                remaining = (total - i) / rate if rate > 0 else 0
                print(f"   已处理 {i}/{total} (新增 {new_count}), 预计剩余 {remaining:.0f}s", flush=True)
        else:
            skip_count += 1

    # 最后提交
    index.conn.commit()
    elapsed = time.time() - t0
    print(f"✅ 索引完成: 新增 {new_count}, 跳过 {skip_count}, 耗时 {elapsed:.1f}s", flush=True)
    index.set_meta('last_build', str(time.time()))

# ── 搜索输出 ───────────────────────────────────────────
def highlight(text: str, keyword: str, regex: bool = False) -> str:
    """高亮关键词"""
    try:
        if regex:
            return re.sub(f'({keyword})', r'\033[1;33m\1\033[0m', text)
        else:
            return text.replace(keyword, f'\033[1;33m{keyword}\033[0m')
    except:
        return text

def print_single_results(results: List[Dict], keyword: str, regex: bool = False,
                          context: int = 0, show_score: bool = False):
    """打印单关键词搜索结果"""
    if not results:
        print("❌ 未找到匹配结果")
        return

    # 按书分组
    by_book = defaultdict(list)
    for r in results:
        by_book[r['book_name'] or Path(r['file_path']).stem].append(r)

    print(f"\n✅ 共 {len(results)} 处匹配，分布在 {len(by_book)} 本书中\n")

    count = 0
    for book_name, items in by_book.items():
        print(f"── {book_name} ({len(items)} 处) ──")
        for r in items:
            content = r['content']
            if len(content) > 120:
                content = content[:120] + "..."
            print(f"  L{r['line_num']:>5} │ {highlight(content, keyword, regex)}")
            count += 1
        print()

def print_and_results(results: List[Dict], keywords: List[str]):
    """打印AND搜索结果"""
    if not results:
        print("❌ 未找到同时包含所有关键词的结果")
        return

    print(f"\n✅ 共 {len(results)} 本书同时包含全部关键词: {', '.join(keywords)}\n")

    for r in results:
        print(f"── {r['book_name'] or Path(r['file_path']).stem} ({r['dynasty']}) ──")
        for kw, matches in r['keyword_matches'].items():
            for m in matches[:3]:
                content = m['content']
                if len(content) > 100:
                    content = content[:100] + "..."
                print(f"  [{kw}] L{m['line_num']:>5} │ {content}")
        print()

def export_json(results, output_path, keywords, mode='single'):
    """导出为JSON"""
    data = {
        'search': {'keywords': keywords, 'mode': mode},
        'result_count': len(results),
        'results': results
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已导出到 {output_path}")

def export_csv(results, output_path, mode='single'):
    """导出为CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if mode == 'and':
            writer.writerow(['书名', '朝代', '文件路径', '关键词匹配详情'])
            for r in results:
                details = '; '.join(
                    f"{kw}: " + ' | '.join(m['content'][:60] for m in matches[:3])
                    for kw, matches in r.get('keyword_matches', {}).items()
                )
                writer.writerow([r.get('book_name', ''), r.get('dynasty', ''), r['file_path'], details])
        else:
            writer.writerow(['书名', '行号', '内容', '朝代', '作者'])
            for r in results:
                writer.writerow([
                    r.get('book_name', ''), r['line_num'],
                    r['content'][:200], r.get('dynasty', ''), r.get('author', '')
                ])
    print(f"✅ 已导出到 {output_path}")

# ── 主函数 ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='中医古籍搜索工具 v2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 桂枝汤                        关键词搜索
  %(prog)s "桂枝.*汤" --regex             正则搜索
  %(prog)s --and "桂枝,白芍,甘草"         AND组合（方剂组成反查）
  %(prog)s --or "麻黄,桂枝,杏仁"          OR组合
  %(prog)s 气虚 --cat 本草                按分类搜
  %(prog)s 脾胃 --dynasty 明              按朝代搜
  %(prog)s --cat 伤寒 --list-books        列出伤寒类书籍
  %(prog)s --stats                        统计信息
  %(prog)s --reindex                      重建索引
  %(prog)s 桂枝 --export results.json     导出JSON
  %(prog)s 桂枝 --export results.csv      导出CSV
        """
    )

    # 搜索模式
    parser.add_argument('keyword', nargs='?', help='搜索关键词')
    parser.add_argument('--and', dest='and_kw', help='AND搜索（逗号分隔多个关键词）')
    parser.add_argument('--or', dest='or_kw', help='OR搜索（逗号分隔多个关键词）')
    parser.add_argument('--regex', action='store_true', help='使用正则表达式搜索')

    # 过滤
    parser.add_argument('-f', '--file', help='限定书籍文件名')
    parser.add_argument('--cat', help='按分类过滤', choices=list(CATEGORIES.keys()))
    parser.add_argument('--dynasty', help='按朝代过滤')

    # 输出
    parser.add_argument('-n', '--max', type=int, default=50, help='最大结果数')
    parser.add_argument('-c', '--context', type=int, default=0, help='上下文行数')
    parser.add_argument('--show-score', action='store_true', help='显示相关度分数')

    # 索引管理
    parser.add_argument('--reindex', action='store_true', help='强制重建索引')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--list-books', action='store_true', help='列出书籍')
    parser.add_argument('--list-cats', action='store_true', help='列出所有分类')

    # 导出
    parser.add_argument('--export', help='导出结果到文件 (.json 或 .csv)')

    args = parser.parse_args()

    # 初始化索引
    index = SearchIndex()

    # 检查是否需要建索引
    book_count = index.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    txt_count = len(list(BOOKS_DIR.glob("*.txt")))

    if args.reindex or book_count == 0:
        build_index(index, force=args.reindex)
    elif book_count < txt_count:
        print(f"📚 检测到 {txt_count - book_count} 本新书，正在更新索引...")
        build_index(index, force=False)

    # 命令处理
    if args.stats:
        stats = index.get_stats()
        print(f"\n📊 中医古籍统计")
        print(f"  总计: {stats['total_books']} 本书, {stats['total_lines']:,} 行, {stats['total_size_mb']:.1f} MB")
        print(f"\n按分类:")
        for cat, cnt in stats['by_category'].items():
            print(f"  {cat}: {cnt} 本")
        print(f"\n按朝代 (Top 20):")
        for d, cnt in stats['by_dynasty'].items():
            print(f"  {d}: {cnt} 本")

    elif args.list_cats:
        print("\n📂 书籍分类:")
        for cat, keywords in CATEGORIES.items():
            print(f"  {cat}: 匹配关键词 {keywords}")

    elif args.list_books:
        books = index.list_books(category=args.cat, dynasty=args.dynasty)
        print(f"\n📚 书籍列表 ({len(books)} 本)")
        if args.cat:
            print(f"   分类: {args.cat}")
        print(f"\n{'书名':<30}{'作者':<15}{'朝代':<15}{'分类':<8}{'大小':<10}")
        print("-" * 78)
        for b in books:
            name = b['book_name'][:28] if b['book_name'] else Path(b['file_path']).stem[:28]
            print(f"{name:<30}{(b['author'] or '')[:13]:<15}{(b['dynasty'] or '')[:13]:<15}{b['category']:<8}{b['size_kb']:.0f}KB")

    elif args.and_kw:
        keywords = [k.strip() for k in args.and_kw.split(',') if k.strip()]
        if len(keywords) < 2:
            print("❌ AND模式至少需要2个关键词")
            sys.exit(1)
        t0 = time.time()
        results = index.search_multi(keywords, mode='AND',
                                      file_filter=args.file, category=args.cat,
                                      dynasty=args.dynasty, max_results=args.max)
        elapsed = time.time() - t0
        print(f"⏱️ 搜索耗时: {elapsed:.3f}s")
        print_and_results(results, keywords)
        if args.export:
            export_json(results, args.export, keywords, mode='and')

    elif args.or_kw:
        keywords = [k.strip() for k in args.or_kw.split(',') if k.strip()]
        t0 = time.time()
        results = index.search_multi(keywords, mode='OR',
                                      file_filter=args.file, category=args.cat,
                                      dynasty=args.dynasty, max_results=args.max)
        elapsed = time.time() - t0
        print(f"⏱️ 搜索耗时: {elapsed:.3f}s")
        print_single_results(results, '|'.join(keywords), regex=False)
        if args.export:
            if args.export.endswith('.csv'):
                export_csv(results, args.export, mode='or')
            else:
                export_json(results, args.export, keywords, mode='or')

    elif args.keyword:
        print(f"\n🔍 搜索: \"{args.keyword}\"", end='')
        filters = []
        if args.file: filters.append(f"书籍={args.file}")
        if args.cat: filters.append(f"分类={args.cat}")
        if args.dynasty: filters.append(f"朝代={args.dynasty}")
        if args.regex: filters.append("正则=✓")
        if filters:
            print(f"  [{', '.join(filters)}]", end='')
        print()

        t0 = time.time()
        results = index.search(args.keyword, regex=args.regex,
                                file_filter=args.file, category=args.cat,
                                dynasty=args.dynasty, context_lines=args.context,
                                max_results=args.max)
        elapsed = time.time() - t0
        print(f"⏱️ 搜索耗时: {elapsed:.3f}s")
        print_single_results(results, args.keyword, args.regex, args.context)

        if args.export:
            if args.export.endswith('.csv'):
                export_csv(results, args.export)
            else:
                export_json(results, args.export, [args.keyword])

    else:
        parser.print_help()

    index.close()

if __name__ == '__main__':
    main()
