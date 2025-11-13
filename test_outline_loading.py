"""
测试脚本：验证 outline 加载逻辑
"""
import sqlite3
import json

def test_outline_loading():
    # 连接数据库
    conn = sqlite3.connect('db/lectureslides.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取最新的 session
    cursor.execute('SELECT id, title, status FROM course_session ORDER BY created_at DESC LIMIT 1')
    session = cursor.fetchone()
    
    if not session:
        print("❌ 没有找到任何 session")
        return
    
    session_id = session['id']
    print(f"✅ 找到最新 session:")
    print(f"   ID: {session_id}")
    print(f"   标题: {session['title']}")
    print(f"   状态: {session['status']}")
    print()
    
    # 检查对应的 outline artifact
    outline_id = f"outline_{session_id}"
    cursor.execute('SELECT id, payload_json FROM artifact WHERE id = ?', (outline_id,))
    artifact = cursor.fetchone()
    
    if not artifact:
        print(f"❌ 没有找到 outline artifact: {outline_id}")
        print("   这会导致生成笔记时重新生成大纲！")
        
        # 检查是否有其他 outline
        cursor.execute('SELECT id FROM artifact WHERE course_session_id = ? AND kind = "outline"', (session_id,))
        other_outlines = cursor.fetchall()
        if other_outlines:
            print(f"\n   但找到了 {len(other_outlines)} 个相关 outline:")
            for row in other_outlines:
                print(f"     - {row['id']}")
    else:
        print(f"✅ 找到 outline artifact: {outline_id}")
        payload = json.loads(artifact['payload_json'])
        root = payload.get('root', {})
        children = root.get('children', [])
        print(f"   根节点标题: {root.get('title', 'N/A')}")
        print(f"   顶层章节数: {len(children)}")
        
        if children:
            print(f"\n   前 3 个章节:")
            for i, child in enumerate(children[:3], 1):
                print(f"     {i}. {child.get('title', 'N/A')}")
                print(f"        level={child.get('level', '?')}, section_id={child.get('section_id', 'N/A')[:20]}...")
                if child.get('children'):
                    print(f"        包含 {len(child['children'])} 个子章节")
    
    conn.close()
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)

if __name__ == '__main__':
    test_outline_loading()
