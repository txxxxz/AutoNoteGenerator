#!/usr/bin/env python3
"""测试 embedding 模型配置是否正常工作"""

import os
import sys
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.modules.note.llm_client import get_embedding_model
from app.utils.logger import logger

def test_embedding():
    """测试 embedding 模型"""
    print("=" * 70)
    print("🧪 测试 Embedding 模型配置")
    print("=" * 70)
    
    try:
        # 初始化模型
        print("\n📦 初始化 Embedding 模型...")
        embedding_model = get_embedding_model()
        print(f"✅ 模型类型: {type(embedding_model).__name__}")
        
        # 检查配置
        if hasattr(embedding_model, 'model'):
            print(f"✅ 模型名称: {embedding_model.model}")
        if hasattr(embedding_model, 'client') and hasattr(embedding_model.client, 'timeout'):
            print(f"✅ 超时设置: {embedding_model.client.timeout}秒")
        
        # 测试单个文本 embedding
        print("\n📝 测试单个文本 embedding...")
        test_text = "机器学习是人工智能的一个重要分支，通过算法让计算机从数据中学习规律。"
        print(f"   文本: {test_text[:50]}...")
        
        start_time = time.time()
        result = embedding_model.embed_query(test_text)
        elapsed = time.time() - start_time
        
        print(f"✅ Embedding 成功!")
        print(f"   向量维度: {len(result)}")
        print(f"   耗时: {elapsed:.2f}秒")
        print(f"   前5个值: {[round(x, 4) for x in result[:5]]}")
        
        # 测试批量文本 embedding
        print("\n📚 测试批量文档 embedding...")
        test_docs = [
            "监督学习需要标注数据，包括分类和回归任务。",
            "深度学习使用多层神经网络进行特征提取。",
            "自然语言处理让计算机理解和生成人类语言。",
            "强化学习通过奖励机制训练智能体做出决策。",
            "计算机视觉技术让机器能够理解图像和视频内容。"
        ]
        print(f"   文档数量: {len(test_docs)}")
        
        start_time = time.time()
        results = embedding_model.embed_documents(test_docs)
        elapsed = time.time() - start_time
        
        print(f"✅ 批量 Embedding 成功!")
        print(f"   返回向量数: {len(results)}")
        print(f"   每个向量维度: {len(results[0])}")
        print(f"   总耗时: {elapsed:.2f}秒")
        print(f"   平均每个: {elapsed/len(test_docs):.2f}秒")
        
        # 性能评估
        print("\n📊 性能评估:")
        if elapsed < 5:
            print("   ⚡ 速度: 非常快")
        elif elapsed < 10:
            print("   ✅ 速度: 正常")
        else:
            print("   ⚠️  速度: 较慢（可能是网络问题）")
        
        if len(results[0]) == 1536:
            print("   📏 维度: 1536 (text-embedding-3-small 或 ada-002)")
        elif len(results[0]) == 3072:
            print("   📏 维度: 3072 (text-embedding-3-large)")
        else:
            print(f"   📏 维度: {len(results[0])} (未知模型)")
        
        print("\n" + "=" * 70)
        print("✅ 所有测试通过！Embedding 模型配置正确，可以正常使用。")
        print("=" * 70)
        print("\n💡 下一步:")
        print("   1. 重启后端服务: uvicorn main:app --reload --port 8000")
        print("   2. 尝试生成笔记")
        print("   3. 如果还有问题，尝试使用 text-embedding-3-large\n")
        
        return True
        
    except ValueError as exc:
        print("\n" + "=" * 70)
        print("❌ Embedding API 返回空数据")
        print("=" * 70)
        print(f"\n错误详情: {exc}\n")
        print("可能原因:")
        print("  1. ❌ 代理服务器不支持当前 embedding 模型")
        print("  2. ❌ API Key 无效或额度不足")
        print("  3. ❌ 网络连接问题")
        print("\n💡 解决建议:")
        print("  1. 检查 .env.txt 中的 OPENAI_EMBEDDING_MODEL 设置")
        print("  2. 尝试其他模型:")
        print("     - text-embedding-ada-002 (最稳定)")
        print("     - text-embedding-3-small (推荐)")
        print("     - text-embedding-3-large (如果代理支持)")
        print("  3. 验证 API Key 是否有效")
        print("  4. 测试网络连接: curl https://api.zhizengzeng.com/v1/models\n")
        return False
        
    except TimeoutError as exc:
        print("\n" + "=" * 70)
        print("❌ Embedding API 请求超时")
        print("=" * 70)
        print(f"\n错误详情: {exc}\n")
        print("可能原因:")
        print("  1. ⏱️  网络延迟过高")
        print("  2. 🔌 代理服务器响应慢")
        print("  3. 📦 请求数据过大")
        print("\n💡 解决建议:")
        print("  1. 已设置 180秒超时，如果还是超时说明网络有问题")
        print("  2. 检查代理服务器状态")
        print("  3. 尝试使用更小的 embedding 模型\n")
        return False
        
    except Exception as exc:
        print("\n" + "=" * 70)
        print(f"❌ 发生未知错误: {type(exc).__name__}")
        print("=" * 70)
        print(f"\n错误详情: {exc}\n")
        import traceback
        traceback.print_exc()
        print("\n💡 建议:")
        print("  1. 检查错误日志中的详细信息")
        print("  2. 确认所有依赖包已正确安装")
        print("  3. 联系技术支持或查看文档\n")
        return False

if __name__ == "__main__":
    success = test_embedding()
    sys.exit(0 if success else 1)
