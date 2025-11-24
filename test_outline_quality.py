#!/usr/bin/env python3
"""
测试 outline 生成质量的脚本
"""
import os
import sys
import sqlite3
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def analyze_outline_quality():
    """分析数据库中outline的质量"""
    db_path = "db/lectureslides.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("📊 Analyzing Outline Quality")
    print("=" * 80)
    
    # 查询所有outline
    cursor.execute("""
        SELECT 
            cs.id,
            cs.title,
            cs.created_at,
            json_extract(a.payload_json, '$.root.children') as children
        FROM course_session cs
        JOIN artifact a ON cs.id = a.course_session_id
        WHERE a.kind = 'outline'
        ORDER BY cs.created_at DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    if not results:
        print("\n❌ No outlines found in database")
        conn.close()
        return
    
    print(f"\n✅ Found {len(results)} outlines\n")
    
    for idx, (session_id, title, created_at, children_json) in enumerate(results, 1):
        print(f"\n{'─' * 80}")
        print(f"#{idx} Session: {session_id[-12:]}")
        print(f"   Title: {title}")
        print(f"   Created: {created_at}")
        
        if not children_json or children_json == "null":
            print("   ❌ Status: No children (empty outline)")
            continue
        
        # 解析children数量
        import json
        try:
            children = json.loads(children_json)
            if not children:
                print("   ❌ Status: Empty children array")
                continue
            
            chapter_count = len(children)
            
            # 分析层级结构
            total_nodes = chapter_count
            max_depth = 2  # Level 2 is first level
            
            def analyze_depth(nodes, current_level):
                nonlocal total_nodes, max_depth
                for node in nodes:
                    if node.get('children'):
                        child_nodes = node['children']
                        total_nodes += len(child_nodes)
                        max_depth = max(max_depth, current_level + 1)
                        analyze_depth(child_nodes, current_level + 1)
            
            analyze_depth(children, 2)
            
            # 质量评估
            quality = "🟢 Good" if chapter_count >= 3 else "🟡 Fair" if chapter_count >= 2 else "🔴 Poor"
            
            print(f"   ✅ Status: {quality}")
            print(f"   📋 Top-level chapters: {chapter_count}")
            print(f"   🌲 Total nodes: {total_nodes}")
            print(f"   📏 Max depth: {max_depth}")
            
            # 显示前几个章节标题
            print(f"   📖 Chapters:")
            for i, child in enumerate(children[:5], 1):
                chapter_title = child.get('title', 'Untitled')
                page_start = child.get('page_start', '?')
                page_end = child.get('page_end', '?')
                print(f"      {i}. {chapter_title} (p.{page_start}–{page_end})")
            
            if len(children) > 5:
                print(f"      ... and {len(children) - 5} more")
        
        except json.JSONDecodeError as e:
            print(f"   ❌ Status: Invalid JSON - {e}")
        except Exception as e:
            print(f"   ❌ Status: Error analyzing - {e}")
    
    print("\n" + "=" * 80)
    
    # 统计总体质量
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN json_array_length(json_extract(a.payload_json, '$.root.children')) >= 3 THEN 1 ELSE 0 END) as good,
            SUM(CASE WHEN json_array_length(json_extract(a.payload_json, '$.root.children')) = 2 THEN 1 ELSE 0 END) as fair,
            SUM(CASE WHEN json_array_length(json_extract(a.payload_json, '$.root.children')) < 2 THEN 1 ELSE 0 END) as poor
        FROM course_session cs
        JOIN artifact a ON cs.id = a.course_session_id
        WHERE a.kind = 'outline'
    """)
    
    stats = cursor.fetchone()
    if stats:
        total, good, fair, poor = stats
        print(f"\n📈 Overall Statistics:")
        print(f"   Total outlines: {total}")
        print(f"   🟢 Good (≥3 chapters): {good} ({good/total*100:.1f}%)")
        print(f"   🟡 Fair (2 chapters): {fair} ({fair/total*100:.1f}%)")
        print(f"   🔴 Poor (<2 chapters): {poor} ({poor/total*100:.1f}%)")
    
    print("\n" + "=" * 80)
    
    conn.close()

if __name__ == "__main__":
    analyze_outline_quality()
