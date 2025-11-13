#!/usr/bin/env python3
"""验证 PDF 解析 bug 修复"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.parser.slide_parser import SlideParser

def test_pdf_parsing():
    """测试 PDF 解析是否正常"""
    print("=" * 80)
    print("🧪 测试 PDF 解析功能")
    print("=" * 80)
    
    # 查找最近上传的 PDF
    uploads_dir = Path("uploads")
    pdf_files = list(uploads_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("\n❌ 没有找到 PDF 文件进行测试")
        print("   请先上传一个 PDF 文件")
        return False
    
    # 使用最新的 PDF
    test_file = sorted(pdf_files, key=lambda f: f.stat().st_mtime, reverse=True)[0]
    print(f"\n📄 测试文件: {test_file.name}")
    print(f"   大小: {test_file.stat().st_size / 1024:.2f} KB")
    
    try:
        parser = SlideParser()
        print(f"\n🔄 开始解析...")
        
        result = parser.parse(test_file, "pdf", "test_session")
        
        print(f"\n✅ 解析成功!")
        print(f"   文档标题: {result.doc_meta.get('title', 'N/A')}")
        print(f"   页数: {result.doc_meta.get('pages', 0)}")
        print(f"   Slides 数量: {len(result.slides)}")
        
        if result.slides:
            print(f"\n📋 前5页内容:")
            for i, slide in enumerate(result.slides[:5], 1):
                print(f"\n   Page {slide.page_no}:")
                print(f"      Blocks: {len(slide.blocks)}")
                if slide.blocks:
                    for block in slide.blocks[:3]:
                        text_preview = block.raw_text[:100] if block.raw_text else "(no text)"
                        print(f"         - {block.type}: {text_preview}")
            
            # 统计
            total_blocks = sum(len(slide.blocks) for slide in result.slides)
            text_blocks = sum(1 for slide in result.slides for block in slide.blocks if block.type == "text")
            image_blocks = sum(1 for slide in result.slides for block in slide.blocks if block.type == "image")
            
            print(f"\n📊 统计:")
            print(f"   总 Blocks: {total_blocks}")
            print(f"   文本 Blocks: {text_blocks}")
            print(f"   图片 Blocks: {image_blocks}")
            
            if len(result.slides) < result.doc_meta.get('pages', 0):
                print(f"\n⚠️  WARNING: 解析的页数 ({len(result.slides)}) 少于文档总页数 ({result.doc_meta.get('pages', 0)})")
                return False
            
            return True
        else:
            print(f"\n❌ 解析失败: slides 数组为空")
            return False
            
    except Exception as e:
        print(f"\n❌ 解析出错: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_parsing()
    print("\n" + "=" * 80)
    if success:
        print("✅ PDF 解析测试通过！Bug 已修复。")
        print("\n💡 下一步:")
        print("   1. 重启后端服务")
        print("   2. 重新上传 PDF 并生成 outline")
        print("   3. 验证 outline children 不再为 0\n")
    else:
        print("❌ PDF 解析测试失败，仍有问题需要解决\n")
    print("=" * 80)
    sys.exit(0 if success else 1)
