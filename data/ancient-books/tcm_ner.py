#!/usr/bin/env python3
"""
TCM NER Tool - 中医命名实体识别工具

功能:
  1. 训练CRF模型 (从BIO标注数据)
  2. 评估模型性能
  3. 对古籍做实体抽取
  4. 导出结构化结果

用法:
  python3 tcm-ner.py train                    # 训练模型
  python3 tcm-ner.py eval                     # 评估模型
  python3 tcm-ner.py predict 伤寒论.txt        # 抽取单本古籍
  python3 tcm-ner.py predict --all             # 批量抽取全部古籍
  python3 tcm-ner.py predict 伤寒论.txt --export result.json  # 导出JSON
"""

import os
import sys
import re
import json
import pickle
import time
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple

import numpy as np
import sklearn_crfsuite
from sklearn_crfsuite import metrics as crf_metrics

# ── 路径配置 ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # workspace 根目录
NER_DATA_DIR = BASE_DIR / "TCM-NER-Dataset"
BOOKS_DIR = BASE_DIR / "TCM-Ancient-Books"
MODEL_DIR = Path(__file__).parent / "tcm-ner-model"  # 模型跟脚本放一起
MODEL_PATH = MODEL_DIR / "crf_model.pkl"

# ── 数据加载 ──────────────────────────────────────────
# 标签中英文映射
TAG_MAP = {
    '书名': 'Book',
    '作者': 'Author',
    '中药': 'Herb',
    '方剂': 'Formula',
    '病名': 'Disease',
    '证候': 'Syndrome',
    '症候': 'Syndrome',
    '煎服法': 'Usage',
}

# 反向映射（用于显示）
TAG_MAP_REVERSE = {v: k for k, v in TAG_MAP.items()}

def convert_tag(tag: str) -> str:
    """将中文标签转为英文"""
    if tag == '0':
        return 'O'
    prefix = tag[0]  # B or I
    cn_type = tag[2:]
    en_type = TAG_MAP.get(cn_type, cn_type)
    return f'{prefix}-{en_type}'

def load_bio_file(filepath: Path) -> List[List[Tuple[str, str]]]:
    """加载BIO标注文件，返回句子列表（标签转为英文）"""
    sentences = []
    current = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                if current:
                    sentences.append(current)
                    current = []
                continue
            parts = line.split()
            if len(parts) == 2:
                char, tag = parts
                current.append((char, convert_tag(tag)))

    if current:
        sentences.append(current)

    return sentences

def load_all_training_data() -> List[List[Tuple[str, str]]]:
    """加载所有训练数据"""
    all_data = []
    for name in ['train5.txt', 'train伤寒论.txt', 'train温病.txt', 'train金贵要略.txt']:
        filepath = NER_DATA_DIR / name
        if filepath.exists():
            data = load_bio_file(filepath)
            all_data.extend(data)
            print(f"  {name}: {len(data)} 句")
    return all_data

# ── 特征提取 ──────────────────────────────────────────
# 中医常用字特征
TCM_RADICALS = set('艹木氵火土金石疒肉月目耳口鼻手足心辶宀')

def is_chinese(c: str) -> bool:
    return '\u4e00' <= c <= '\u9fff'

def is_punctuation(c: str) -> bool:
    return c in '，。、；：！？""''（）《》【】〈〉…—·～'

def is_number(c: str) -> bool:
    return c in '一二三四五六七八九十百千万两半' or c.isdigit()

def char_features(sentence: List[str], i: int) -> Dict:
    """提取单个字符的特征 - 所有值转为ASCII安全字符串"""
    char = sentence[i]
    o = lambda c: f'U{ord(c):04x}'  # Unicode编码

    features = {
        'char': o(char),
        'is_cn': int(is_chinese(char)),
        'is_punct': int(is_punctuation(char)),
        'is_num': int(is_number(char)),
        'is_rad': int(char in TCM_RADICALS),
        'pos': round(i / len(sentence), 2) if len(sentence) > 1 else 0,
        'bos': int(i == 0),
        'eos': int(i == len(sentence) - 1),
    }

    for offset in [-2, -1, 1, 2]:
        idx = i + offset
        if 0 <= idx < len(sentence):
            features[f'c{offset}'] = o(sentence[idx])
            features[f'cn{offset}'] = int(is_chinese(sentence[idx]))
        else:
            features[f'c{offset}'] = 'BND'

    if i >= 1:
        features['p2'] = f'{ord(sentence[i-1]):04x}_{ord(char):04x}'
    if i >= 2:
        features['p3'] = f'{ord(sentence[i-2]):04x}_{ord(sentence[i-1]):04x}_{ord(char):04x}'
    if i < len(sentence) - 1:
        features['s2'] = f'{ord(char):04x}_{ord(sentence[i+1]):04x}'
    if i < len(sentence) - 2:
        features['s3'] = f'{ord(char):04x}_{ord(sentence[i+1]):04x}_{ord(sentence[i+2]):04x}'

    # 强制所有值转str
    return {k: str(v) for k, v in features.items()}

def sent_to_features(sentence: List[str]) -> List[Dict]:
    """提取句子中每个字符的特征"""
    return [char_features(sentence, i) for i in range(len(sentence))]

def sent_to_labels(sentence: List[Tuple[str, str]]) -> List[str]:
    """提取句子中每个字符的标签"""
    return [tag for _, tag in sentence]

def sent_to_chars(sentence) -> List[str]:
    """提取句子中的字符"""
    if isinstance(sentence[0], tuple):
        return [char for char, _ in sentence]
    return list(sentence)

# ── 模型训练 ──────────────────────────────────────────
def train_model():
    """训练CRF模型"""
    print("📚 加载训练数据...")
    train_data = load_all_training_data()
    print(f"  总计: {len(train_data)} 句\n")

    dev_file = NER_DATA_DIR / "dev5.txt"
    test_file = NER_DATA_DIR / "test5.txt"
    dev_data = load_bio_file(dev_file) if dev_file.exists() else []
    test_data = load_bio_file(test_file) if test_file.exists() else []
    print(f"  验证集: {len(dev_data)} 句")
    print(f"  测试集: {len(test_data)} 句\n")

    # 提取特征
    print("🔧 提取特征...")
    t0 = time.time()
    X_train = [sent_to_features(sent_to_chars(s)) for s in train_data]
    y_train = [sent_to_labels(s) for s in train_data]
    X_dev = [sent_to_features(sent_to_chars(s)) for s in dev_data]
    y_dev = [sent_to_labels(s) for s in dev_data]
    X_test = [sent_to_features(sent_to_chars(s)) for s in test_data]
    y_test = [sent_to_labels(s) for s in test_data]
    print(f"  耗时: {time.time()-t0:.1f}s\n")

    # 训练
    print("🏋️ 训练CRF模型...")
    t0 = time.time()
    crf = sklearn_crfsuite.CRF(
        algorithm='lbfgs',
        c1=0.1,
        c2=0.1,
        max_iterations=100,
        all_possible_transitions=True,
    )
    crf.fit(X_train, y_train)
    train_time = time.time() - t0
    print(f"  训练完成: {train_time:.1f}s\n")

    # 保存模型
    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(crf, f)
    print(f"💾 模型已保存: {MODEL_PATH}\n")

    # 评估
    labels = sorted(set(tag for sent in train_data for _, tag in sent))
    labels = [l for l in labels if l != 'O']

    print("📊 评估结果:")
    for name, X, y in [('训练集', X_train, y_train), ('验证集', X_dev, y_dev), ('测试集', X_test, y_test)]:
        if not X:
            continue
        y_pred = crf.predict(X)
        print(f"\n--- {name} ---")
        try:
            report = crf_metrics.flat_classification_report(
                y, y_pred, labels=labels, digits=4
            )
            print(report)
        except Exception as e:
            print(f"  报告生成失败: {e}")
            # 简单统计
            from collections import Counter
            pred_counts = Counter()
            for sent in y_pred:
                pred_counts.update(sent)
            print(f"  预测分布: {dict(pred_counts)}")

    return crf

def load_model():
    """加载已训练的模型"""
    if not MODEL_PATH.exists():
        print("❌ 模型不存在，请先运行: python3 tcm-ner.py train")
        sys.exit(1)
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)

# ── 预测/抽取 ──────────────────────────────────────────
def detect_and_decode(raw: bytes) -> str:
    """检测编码并解码"""
    for enc in ['utf-8', 'gbk', 'gb18030', 'gb2312']:
        try:
            text = raw.decode(enc)
            if any('\u4e00' <= c <= '\u9fff' for c in text):
                return text
        except:
            continue
    return raw.decode('gbk', errors='replace')

def extract_entities_from_text(text: str, crf, chunk_size: int = 200) -> List[Dict]:
    """从文本中抽取实体"""
    # 按段落分句
    paragraphs = re.split(r'\n\s*\n|\n', text)
    sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 按标点分句
        parts = re.split(r'([，。、；：！？])', para)
        current = ''
        for part in parts:
            current += part
            if part in '。！？；' and len(current) > 2:
                sentences.append(current)
                current = ''
        if current.strip():
            sentences.append(current)

    # 对每个句子做预测
    all_entities = []
    entity_id = 0

    for sent_text in sentences:
        chars = list(sent_text)
        if len(chars) < 2 or len(chars) > 500:
            continue

        features = sent_to_features(chars)
        try:
            pred_tags = crf.predict_single(features)
        except:
            continue

        # 从BIO标签中提取实体
        current_entity = None
        for j, (char, tag) in enumerate(zip(chars, pred_tags)):
            if tag.startswith('B-'):
                # 保存之前的实体
                if current_entity:
                    all_entities.append(current_entity)
                entity_type = tag[2:]
                current_entity = {
                    'id': entity_id,
                    'type': entity_type,
                    'text': char,
                    'start': j,
                    'sentence': sent_text,
                }
                entity_id += 1
            elif tag.startswith('I-') and current_entity:
                entity_type = tag[2:]
                if entity_type == current_entity['type']:
                    current_entity['text'] += char
                else:
                    all_entities.append(current_entity)
                    current_entity = None
            else:
                if current_entity:
                    all_entities.append(current_entity)
                    current_entity = None

        if current_entity:
            all_entities.append(current_entity)

    return all_entities

def predict_book(filepath: Path, crf) -> Dict:
    """对单本古籍做实体抽取"""
    raw = filepath.read_bytes()
    text = detect_and_decode(raw)

    # 提取书名
    book_name = filepath.stem
    m = re.search(r'书名[：:]\s*(.+)', text[:1000])
    if m:
        book_name = m.group(1).strip()

    entities = extract_entities_from_text(text, crf)

    # 统计
    type_counts = defaultdict(int)
    type_examples = defaultdict(set)
    for e in entities:
        type_counts[e['type']] += 1
        type_examples[e['type']].add(e['text'])

    return {
        'file': filepath.name,
        'book_name': book_name,
        'total_entities': len(entities),
        'type_counts': dict(type_counts),
        'unique_entities': {k: list(v)[:50] for k, v in type_examples.items()},
        'entities': entities,
    }

def predict_all(crf, max_books: int = None):
    """批量抽取所有古籍"""
    books = sorted(BOOKS_DIR.glob("*.txt"))
    if max_books:
        books = books[:max_books]

    print(f"🔍 实体抽取: {len(books)} 本书\n")

    all_results = []
    total_entities = 0
    total_time = 0

    for i, book in enumerate(books, 1):
        t0 = time.time()
        result = predict_book(book, crf)
        elapsed = time.time() - t0
        total_time += elapsed
        total_entities += result['total_entities']
        all_results.append(result)

        if i % 20 == 0 or result['total_entities'] > 100:
            print(f"  [{i}/{len(books)}] {book.stem}: "
                  f"{result['total_entities']} 实体, {elapsed:.1f}s")

    print(f"\n✅ 完成: {total_entities:,} 个实体, 耗时 {total_time:.1f}s")
    return all_results

def print_results(result: Dict):
    """打印单本书的抽取结果"""
    print(f"\n📖 {result['book_name']} ({result['file']})")
    print(f"   总计: {result['total_entities']} 个实体\n")

    for etype, count in sorted(result['type_counts'].items(), key=lambda x: -x[1]):
        examples = result['unique_entities'].get(etype, [])[:15]
        print(f"  {etype} ({count}): {', '.join(examples)}")

# ── 导出 ──────────────────────────────────────────────
def export_results(results: List[Dict], output_path: str):
    """导出结果"""
    output = Path(output_path)

    if output.suffix == '.json':
        # 简化输出（不包含全部实体列表，太大）
        export_data = []
        for r in results:
            export_data.append({
                'file': r['file'],
                'book_name': r['book_name'],
                'total_entities': r['total_entities'],
                'type_counts': r['type_counts'],
                'unique_entities': {k: v[:100] for k, v in r['unique_entities'].items()},
            })
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    elif output.suffix == '.csv':
        import csv
        with open(output, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['书名', '文件', '实体类型', '实体文本', '上下文'])
            for r in results:
                for e in r.get('entities', [])[:500]:  # 限制每本书最多500个
                    context = e.get('sentence', '')[:100]
                    writer.writerow([r['book_name'], r['file'], e['type'], e['text'], context])

    else:  # txt
        with open(output, 'w', encoding='utf-8') as f:
            for r in results:
                f.write(f"=== {r['book_name']} ({r['file']}) ===\n")
                f.write(f"总计: {r['total_entities']} 实体\n")
                for etype, count in sorted(r['type_counts'].items(), key=lambda x: -x[1]):
                    examples = r['unique_entities'].get(etype, [])
                    f.write(f"  {etype} ({count}): {', '.join(examples[:50])}\n")
                f.write("\n")

    print(f"✅ 已导出: {output_path}")

# ── 主函数 ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='TCM NER Tool - 中医命名实体识别',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s train                             训练CRF模型
  %(prog)s eval                              评估模型
  %(prog)s predict 457-伤寒论.txt              抽取单本古籍
  %(prog)s predict --all                     批量抽取全部古籍
  %(prog)s predict --all --max 10            抽取前10本
  %(prog)s predict 457-伤寒论.txt --export r.json  导出JSON
  %(prog)s predict --all --export results/   批量导出到目录
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # train
    train_parser = subparsers.add_parser('train', help='训练CRF模型')

    # eval
    eval_parser = subparsers.add_parser('eval', help='评估模型')

    # predict
    pred_parser = subparsers.add_parser('predict', help='实体抽取')
    pred_parser.add_argument('file', nargs='?', help='古籍文件名')
    pred_parser.add_argument('--all', action='store_true', help='批量抽取全部古籍')
    pred_parser.add_argument('--max', type=int, help='最多处理多少本书')
    pred_parser.add_argument('--export', help='导出路径 (.json/.csv/.txt)')

    args = parser.parse_args()

    if args.command == 'train':
        train_model()

    elif args.command == 'eval':
        crf = load_model()
        test_data = load_bio_file(NER_DATA_DIR / "test5.txt")
        print(f"📊 测试集评估 ({len(test_data)} 句)")
        X_test = [sent_to_features(sent_to_chars(s)) for s in test_data]
        y_test = [sent_to_labels(s) for s in test_data]
        y_pred = crf.predict(X_test)
        labels = sorted(set(tag for sent in test_data for _, tag in sent))
        labels = [l for l in labels if l != 'O']
        try:
            report = crf_metrics.flat_classification_report(
                y_test, y_pred, labels=labels, digits=4
            )
            print(report)
        except Exception as e:
            print(f"报告生成失败: {e}")
            correct = sum(1 for t, p in zip([x for s in y_test for x in s], [x for s in y_pred for x in s]) if t == p)
            total = sum(len(s) for s in y_test)
            print(f"字符级准确率: {correct}/{total} = {correct/total*100:.2f}%")

    elif args.command == 'predict':
        crf = load_model()

        if args.all:
            results = predict_all(crf, args.max)
            if args.export:
                export_results(results, args.export)
            else:
                # 打印汇总
                print(f"\n{'书名':<30}{'中药':<8}{'方剂':<8}{'病名':<8}{'证候':<8}{'煎服法':<8}{'总计':<8}")
                print("-" * 78)
                for r in sorted(results, key=lambda x: -x['total_entities'])[:30]:
                    tc = r['type_counts']
                    print(f"{r['book_name'][:28]:<30}"
                          f"{tc.get('中药',0):<8}{tc.get('方剂',0):<8}"
                          f"{tc.get('病名',0):<8}{tc.get('证候',0):<8}"
                          f"{tc.get('煎服法',0):<8}{r['total_entities']:<8}")

        elif args.file:
            # 查找文件
            filepath = BOOKS_DIR / args.file
            if not filepath.exists():
                # 模糊匹配
                matches = list(BOOKS_DIR.glob(f"*{args.file}*"))
                if matches:
                    filepath = matches[0]
                else:
                    print(f"❌ 找不到文件: {args.file}")
                    sys.exit(1)

            result = predict_book(filepath, crf)
            if args.export:
                export_results([result], args.export)
            else:
                print_results(result)
        else:
            pred_parser.print_help()

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
